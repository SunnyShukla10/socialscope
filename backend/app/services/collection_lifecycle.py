from datetime import datetime
from typing import Optional


JOB_STATUSES = {
    "pending",
    "queued",
    "running",
    "cancelling",
    "completed",
    "completed_with_errors",
    "cancelled",
    "failed",
}

TERMINAL_JOB_STATUSES = {
    "completed",
    "completed_with_errors",
    "cancelled",
    "failed",
}

PLATFORM_STATUSES = {
    "pending",
    "running",
    "completed",
    "failed",
    "cancel_requested",
    "cancelled",
}

TERMINAL_PLATFORM_STATUSES = {
    "completed",
    "failed",
    "cancelled",
}


def can_transition_job_status(current_status: str, next_status: str) -> bool:
    """Keep terminal or cancelling jobs from being restarted by task redelivery."""
    if current_status not in JOB_STATUSES or next_status not in JOB_STATUSES:
        return False
    if current_status == next_status:
        return True
    if current_status == "cancelling":
        return next_status == "cancelled"
    return current_status not in TERMINAL_JOB_STATUSES


def request_platform_cancellation(
    platforms: list[str],
    current_states: dict,
) -> tuple[dict, list[str], list[str]]:
    """
    Return copied platform state with unfinished platforms marked cancel_requested.

    Existing completed/failed/cancelled states and post counts are preserved. The
    input mapping is never mutated so concurrent readers do not share writable
    state.
    """
    states = {
        key: dict(value)
        for key, value in (current_states or {}).items()
    }
    completed_platforms: list[str] = []
    cancelling_platforms: list[str] = []

    for configured_platform in platforms:
        platform = configured_platform.lower()
        state_key = next(
            (
                key
                for key in states
                if str(key).lower() == platform
            ),
            platform,
        )
        state = dict(states.get(state_key) or platform_state("pending"))
        platform_status = state.get("status", "pending")

        if platform_status == "completed":
            completed_platforms.append(platform)
        elif platform_status in {"pending", "running", "cancel_requested"}:
            state["status"] = "cancel_requested"
            states[state_key] = state
            cancelling_platforms.append(platform)

    return states, completed_platforms, cancelling_platforms


def finalize_platform_cancellation(
    platforms: list[str],
    current_states: dict,
    *,
    cancelled_at: datetime,
) -> dict:
    """Mark every unfinished platform cancelled without changing saved counts."""
    states = {
        key: dict(value)
        for key, value in (current_states or {}).items()
    }
    for configured_platform in platforms:
        platform = configured_platform.lower()
        state_key = next(
            (key for key in states if str(key).lower() == platform),
            platform,
        )
        state = dict(states.get(state_key) or platform_state("pending"))
        if state.get("status") in {"pending", "running", "cancel_requested"}:
            state["status"] = "cancelled"
            state["completed_at"] = cancelled_at.isoformat()
            state["last_progress_at"] = cancelled_at.isoformat()
            state["error"] = "Cancelled by user"
            states[state_key] = state
    return states


def platform_state(
    status: str,
    *,
    posts_collected: int = 0,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
    last_progress_at: Optional[datetime] = None,
    error: Optional[str] = None,
    provider_stop_reason: Optional[str] = None,
    provider_stop_details: Optional[dict] = None,
) -> dict:
    if status not in PLATFORM_STATUSES:
        raise ValueError(f"Unsupported platform collection status: {status}")
    return {
        "status": status,
        "posts_collected": posts_collected,
        "started_at": started_at.isoformat() if started_at else None,
        "completed_at": completed_at.isoformat() if completed_at else None,
        "last_progress_at": last_progress_at.isoformat() if last_progress_at else None,
        "error": error,
        "provider_stop_reason": provider_stop_reason,
        "provider_stop_details": provider_stop_details,
    }
