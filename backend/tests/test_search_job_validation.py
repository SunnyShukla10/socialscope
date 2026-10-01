import pytest
from pydantic import ValidationError

from app.schemas.project import ProjectLaunchCreate
from app.schemas.search_job import MAX_RESULTS_PER_PLATFORM, MIN_REQUESTED_POST_COUNT, SearchJobCreate
from app.services.search_service import allocate_post_counts


def test_search_job_accepts_configured_limit():
    job = SearchJobCreate(
        name="Collection",
        platforms=["twitter"],
        query="migraine",
        max_results_per_platform=MAX_RESULTS_PER_PLATFORM,
    )

    assert job.max_results_per_platform == MAX_RESULTS_PER_PLATFORM


@pytest.mark.parametrize("limit", [MIN_REQUESTED_POST_COUNT - 1, MAX_RESULTS_PER_PLATFORM + 1])
def test_search_job_rejects_limits_outside_slider_range(limit):
    with pytest.raises(ValidationError):
        SearchJobCreate(
            name="Collection",
            platforms=["twitter"],
            query="migraine",
            requested_post_count=limit,
        )


def test_platform_allocation_weights_and_preserves_total():
    allocations = allocate_post_counts(["twitter", "reddit", "instagram"], 1000)

    assert sum(allocations.values()) == 1000
    assert allocations["twitter"] < allocations["instagram"]
    assert allocations["reddit"] < allocations["instagram"]


def test_platform_allocation_gives_facebook_smaller_share():
    allocations = allocate_post_counts(["twitter", "reddit", "tiktok", "facebook"], 1000)

    assert sum(allocations.values()) == 1000
    assert allocations["twitter"] < allocations["facebook"]
    assert allocations["reddit"] < allocations["facebook"]
    assert allocations["tiktok"] > allocations["facebook"]


def test_platform_allocation_tiktok_gets_more_than_instagram():
    allocations = allocate_post_counts(["tiktok", "instagram", "facebook"], 1000)

    assert sum(allocations.values()) == 1000
    assert allocations["tiktok"] > allocations["instagram"]
    assert allocations["tiktok"] > allocations["facebook"]


def test_platform_allocation_facebook_only_preserves_total():
    allocations = allocate_post_counts(["facebook"], 1000)

    assert allocations == {"facebook": 1000}


def test_platform_allocation_deduplicates_platforms():
    allocations = allocate_post_counts(["twitter", "twitter", "instagram"], 301)

    assert sum(allocations.values()) == 301
    assert set(allocations) == {"twitter", "instagram"}


def test_project_launch_payload_includes_initial_job():
    payload = ProjectLaunchCreate(
        name="Collection Project",
        description="Launch project and collect posts",
        domain="general",
        research_question="What are people saying?",
        boolean_query="people AND saying",
        platforms=["twitter", "reddit"],
        initial_job=SearchJobCreate(
            name="Initial collection",
            platforms=["twitter", "reddit"],
            query="people AND saying",
            requested_post_count=300,
        ),
    )

    assert payload.name == "Collection Project"
    assert payload.initial_job.query == "people AND saying"
    assert payload.initial_job.requested_post_count == 300
