from app.services.collection_status import collection_terminal_status


def test_collection_status_failed_when_all_platforms_error_without_posts():
    assert collection_terminal_status(0, ["twitter: 502 Bad Gateway"]) == "failed"


def test_collection_status_completed_with_errors_when_some_posts_collected():
    assert collection_terminal_status(12, ["twitter: 502 Bad Gateway"]) == "completed_with_errors"


def test_collection_status_completed_without_errors():
    assert collection_terminal_status(0, []) == "completed"


def test_collection_status_partial_success_can_have_zero_posts():
    assert (
        collection_terminal_status(
            0,
            ["twitter: provider error"],
            successful_platforms=1,
        )
        == "completed_with_errors"
    )
