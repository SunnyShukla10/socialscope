from app.services.analytics_service import AnalyticsService


def test_hashtag_normalization_collates_case_and_plural():
    service = AnalyticsService(db=None)

    tags = service.extract_hashtags(
        "Trying #Psoriasis, #psoriasis! and #treatments. Ignore #",
        ["#Treatment"],
    )

    counts = {}
    for normalized, _display in tags:
        counts[normalized] = counts.get(normalized, 0) + 1

    assert "psoriasis" in counts
    assert "treatment" in counts
    assert "" not in counts


def test_wordmap_tokenization_removes_stopwords_mentions_urls_and_lemmatizes():
    service = AnalyticsService(db=None)

    tokens = service.tokenize_for_wordmap(
        "RT The patients are just really sharing treatments with @clinic at https://example.com treatments! amp like got"
    )

    assert "the" not in tokens
    assert "clinic" not in tokens
    assert "http" not in tokens
    assert "amp" not in tokens
    assert "like" not in tokens
    assert "just" not in tokens
    assert tokens.count("treatment") == 2


def test_wordmap_top_quarter_threshold_uses_ceil_and_minimum_one():
    service = AnalyticsService(db=None)

    assert service._top_cooccurrence_pair_count(0) == 0
    assert service._top_cooccurrence_pair_count(1) == 1
    assert service._top_cooccurrence_pair_count(4) == 1
    assert service._top_cooccurrence_pair_count(5) == 2
