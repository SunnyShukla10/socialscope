import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.search_job import SearchJob
from app.schemas.search_job import SearchJobOut
from app.services.collection_lifecycle import (
    JOB_STATUSES,
    PLATFORM_STATUSES,
    can_transition_job_status,
    platform_state,
    request_platform_cancellation,
)


def _job_payload(**overrides):
    now = datetime.now(timezone.utc)
    payload = {
        "id": uuid.uuid4(),
        "project_id": uuid.uuid4(),
        "name": "Collection",
        "status": "running",
        "platforms": ["twitter"],
        "date_from": None,
        "date_to": None,
        "max_results_per_platform": 100,
        "requested_post_count": 100,
        "platform_allocations": {"twitter": 100},
        "platform_states": {"twitter": {"status": "running"}},
        "total_posts_collected": 0,
        "error_message": None,
        "celery_task_id": None,
        "started_at": now,
        "completed_at": None,
        "cancel_requested_at": None,
        "cancelled_at": None,
        "cancel_requested_by": None,
        "last_progress_at": now,
        "created_at": now,
        "updated_at": now,
        "query_versions": [],
    }
    payload.update(overrides)
    return payload


def test_supported_collection_states_are_explicit():
    assert {"cancelling", "cancelled"} <= JOB_STATUSES
    assert {"cancel_requested", "cancelled"} <= PLATFORM_STATUSES


def test_historical_minimal_platform_state_remains_compatible():
    job = SearchJobOut.model_validate(_job_payload())

    state = job.platform_states["twitter"]
    assert state.status == "running"
    assert state.posts_collected == 0
    assert state.started_at is None
    assert state.error is None


def test_rich_platform_state_and_cancellation_metadata_serialize():
    now = datetime.now(timezone.utc)
    requested_by = uuid.uuid4()
    job = SearchJobOut.model_validate(
        _job_payload(
            status="cancelled",
            platform_states={
                "twitter": platform_state(
                    "cancelled",
                    posts_collected=42,
                    started_at=now,
                    completed_at=now,
                    last_progress_at=now,
                    error="Cancelled by user",
                )
            },
            cancel_requested_at=now,
            cancelled_at=now,
            cancel_requested_by=requested_by,
        )
    )

    serialized = job.model_dump(mode="json")
    assert serialized["status"] == "cancelled"
    assert serialized["cancel_requested_by"] == str(requested_by)
    assert serialized["platform_states"]["twitter"]["posts_collected"] == 42
    assert serialized["platform_states"]["twitter"]["completed_at"] is not None


def test_unknown_job_and_platform_states_are_rejected():
    with pytest.raises(ValidationError):
        SearchJobOut.model_validate(_job_payload(status="unknown"))
    with pytest.raises(ValidationError):
        SearchJobOut.model_validate(
            _job_payload(platform_states={"twitter": {"status": "unknown"}})
        )


@pytest.mark.parametrize(
    "terminal_status",
    ["completed", "completed_with_errors", "cancelled", "failed"],
)
def test_terminal_job_cannot_transition_back_to_running(terminal_status):
    assert can_transition_job_status(terminal_status, "running") is False
    assert can_transition_job_status(terminal_status, terminal_status) is True


def test_cancelling_job_cannot_transition_back_to_running():
    assert can_transition_job_status("cancelling", "running") is False
    assert can_transition_job_status("cancelling", "failed") is False
    assert can_transition_job_status("cancelling", "cancelled") is True


def test_request_platform_cancellation_preserves_finished_results():
    current_states = {
        "twitter": platform_state("running", posts_collected=0),
        "tiktok": platform_state("completed", posts_collected=42),
        "reddit": platform_state("failed", posts_collected=0, error="Unavailable"),
    }

    states, completed, cancelling = request_platform_cancellation(
        ["twitter", "tiktok", "reddit", "youtube"],
        current_states,
    )

    assert states["twitter"]["status"] == "cancel_requested"
    assert states["youtube"]["status"] == "cancel_requested"
    assert states["tiktok"]["status"] == "completed"
    assert states["tiktok"]["posts_collected"] == 42
    assert states["reddit"]["status"] == "failed"
    assert completed == ["tiktok"]
    assert cancelling == ["twitter", "youtube"]
    assert current_states["twitter"]["status"] == "running"
    assert "youtube" not in current_states


def test_search_job_model_has_cancellation_and_progress_columns():
    columns = SearchJob.__table__.columns

    assert "cancel_requested_at" in columns
    assert "cancelled_at" in columns
    assert "cancel_requested_by" in columns
    assert "last_progress_at" in columns
