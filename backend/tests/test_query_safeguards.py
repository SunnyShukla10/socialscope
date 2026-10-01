import uuid

import pytest

from app.schemas.search_job import SearchJobCreate
from app.services.query_validation import (
    QueryValidationError,
    query_limits_payload,
    validate_query,
)
from app.services.search_service import SearchService


def test_query_within_limit_is_valid():
    validate_query(
        "migraine AND treatment",
        ["twitter"],
        provider_limits={"xpoz": 30, "socialvault": 30},
    )


def test_query_exactly_at_limit_is_valid():
    validate_query(
        "x" * 200,
        ["twitter"],
        provider_limits={"xpoz": 200, "socialvault": 200},
    )


def test_query_over_limit_has_structured_platform_provider_error():
    with pytest.raises(QueryValidationError) as caught:
        validate_query(
            "x" * 201,
            ["twitter"],
            provider_limits={"xpoz": 200, "socialvault": 200},
        )

    assert caught.value.issue.to_dict() == {
        "code": "QUERY_TOO_LONG",
        "platform": "twitter",
        "provider": "socialvault",
        "actual_length": 201,
        "maximum_length": 200,
        "message": (
            "Twitter / X via SociaVault is configured for queries up to 200 characters; "
            "this query has 201. Shorten the query without changing its intended meaning."
        ),
    }


def test_most_restrictive_selected_platform_is_reported():
    with pytest.raises(QueryValidationError) as caught:
        validate_query(
            "x" * 151,
            ["reddit", "instagram"],
            provider_limits={"xpoz": 150, "socialvault": 180},
        )

    assert caught.value.issue.platform == "instagram"
    assert caught.value.issue.provider == "xpoz"
    assert caught.value.issue.maximum_length == 150


@pytest.mark.parametrize(
    ("query", "code"),
    [
        ("migraine AND (treatment OR care", "UNBALANCED_PARENTHESES"),
        ('migraine AND "treatment experience', "UNBALANCED_QUOTES"),
        ("migraine AND OR treatment", "MALFORMED_BOOLEAN_QUERY"),
        ("migraine && treatment", "UNSUPPORTED_BOOLEAN_OPERATOR"),
    ],
)
def test_invalid_boolean_query_is_rejected(query, code):
    with pytest.raises(QueryValidationError) as caught:
        validate_query(query, ["reddit"])

    assert caught.value.issue.code == code
    assert caught.value.issue.platform == "reddit"
    assert caught.value.issue.provider == "socialvault"


@pytest.mark.asyncio
async def test_backend_service_rejects_bypass_before_database_access():
    class DatabaseMustNotBeUsed:
        async def execute(self, *_args, **_kwargs):
            raise AssertionError("database should not be touched for an invalid query")

    service = SearchService(DatabaseMustNotBeUsed())
    body = SearchJobCreate(
        name="Bypassed frontend",
        platforms=["twitter"],
        query="x" * 201,
        requested_post_count=100,
    )

    with pytest.raises(QueryValidationError) as caught:
        await service.create_job(uuid.uuid4(), body, uuid.uuid4())

    assert caught.value.issue.code == "QUERY_TOO_LONG"


def test_limit_payload_identifies_defaults_as_non_official():
    payload = query_limits_payload()

    assert payload["limits_are_official_provider_guarantees"] is False
    assert payload["platforms"]["twitter"]["provider"] == "socialvault"
    assert payload["platforms"]["reddit"]["provider"] == "socialvault"
