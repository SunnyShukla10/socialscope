"""Tests for LLM query generation — pure unit tests, no DB needed."""
import pytest
from app.adapters.llm_adapter import MockLLMAdapter, _extract_keywords


@pytest.mark.asyncio
async def test_mock_llm_adapter_health_domain():
    adapter = MockLLMAdapter()
    results = await adapter.generate_boolean_queries(
        "How do patients discuss Ubrelvy for migraine treatment?",
        "health",
    )
    assert len(results) == 3
    assert [r["label"] for r in results] == [
        "Natural Language Query",
        "Moderate Boolean Query",
        "Complex Boolean Query",
    ]
    assert results[0]["query_type"] == "natural_language"
    assert "AND" not in results[0]["boolean_query"]
    assert "OR" not in results[0]["boolean_query"]
    assert results[1]["query_type"] == "boolean"
    assert results[1]["boolean_query"].count(" AND ") == 1
    assert results[2]["query_type"] == "boolean"
    assert results[2]["boolean_query"].count(" AND ") >= 2
    for r in results:
        assert "boolean_query" in r
        assert "query_type" in r
        assert "description" in r
        assert "or_groups" in r
        assert len(r["boolean_query"]) > 10


@pytest.mark.asyncio
async def test_mock_llm_adapter_consumer_domain():
    adapter = MockLLMAdapter()
    results = await adapter.generate_boolean_queries(
        "What are EV owners saying about charging station reliability?",
        "consumer",
    )
    assert len(results) == 3
    for r in results:
        assert "boolean_query" in r
        assert "query_type" in r
        assert "or_groups" in r
        assert isinstance(r["or_groups"], list)


@pytest.mark.asyncio
async def test_mock_llm_adapter_general_domain():
    adapter = MockLLMAdapter()
    results = await adapter.generate_boolean_queries(
        "What do people think about remote work policies?",
        "general",
    )
    assert len(results) == 3


@pytest.mark.asyncio
async def test_mock_llm_adapter_empty_keywords():
    adapter = MockLLMAdapter()
    results = await adapter.generate_boolean_queries("what is the?", "general")
    assert len(results) == 3
    # Should still produce valid queries with fallback keywords
    for r in results:
        assert len(r["boolean_query"]) > 5


def test_extract_keywords_basic():
    keywords = _extract_keywords("How do patients discuss Ozempic side effects?")
    assert "ozempic" in keywords
    assert "effects" in keywords
    # Stop words excluded
    assert "how" not in keywords
    assert "the" not in keywords


def test_extract_keywords_empty():
    keywords = _extract_keywords("what is the?")
    assert keywords == []


def test_extract_keywords_preserves_meaningful_words():
    keywords = _extract_keywords(
        "migraine treatment effectiveness comparison Ubrelvy Nurtec"
    )
    assert "migraine" in keywords
    assert "treatment" in keywords
    assert "ubrelvy" in keywords
    assert "nurtec" in keywords
