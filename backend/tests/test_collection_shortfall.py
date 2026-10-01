from app.workers.tasks import _collection_shortfall_message


def test_no_shortfall_when_unique_saved_posts_fill_target():
    assert _collection_shortfall_message(100, 100, 100) is None


def test_shortfall_explains_provider_exhaustion_and_duplicates():
    message = _collection_shortfall_message(460, 303, 720)

    assert "460 of 720 requested" in message
    assert "303 unique posts were saved" in message
    assert "157 duplicate or previously saved" in message
    assert "exhausted matching results or stopped pagination" in message


def test_cursor_only_shortfall_explains_credit_safeguard():
    message = _collection_shortfall_message(
        19, 19, 100, "empty_page_with_continuation"
    )

    assert "next provider page contained no posts" in message
    assert "stopped to avoid additional credit usage" in message
