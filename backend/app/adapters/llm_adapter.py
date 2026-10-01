import logging
import json
from typing import List
from app.config import settings

logger = logging.getLogger(__name__)


def _extract_keywords(text: str) -> List[str]:
    """Extract meaningful keywords from a research question."""
    stop_words = {
        "what", "how", "why", "when", "where", "who", "is", "are", "do", "does",
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "about", "people", "think", "feel", "say",
        "regarding", "related", "users", "consumers", "social", "media",
    }
    words = text.lower().replace("?", "").replace(",", "").replace(".", "").split()
    return [w for w in words if w not in stop_words and len(w) > 3]


def _build_simple_natural_query(keywords: List[str]) -> str:
    """Build a plain, high-recall query without boolean operators or acronyms."""
    non_acronyms = [
        keyword
        for keyword in keywords
        if len(keyword) > 3
    ]
    if len(non_acronyms) >= 2:
        return f"{non_acronyms[0]} {non_acronyms[1]}"
    if non_acronyms:
        return non_acronyms[0]
    return "topic discussion"


def _build_mock_candidates(research_question: str, domain: str) -> List[dict]:
    keywords = _extract_keywords(research_question)
    if not keywords:
        keywords = ["topic", "discussion", "experience", "review"]

    primary = keywords[0] if keywords else "topic"
    secondary = keywords[1] if len(keywords) > 1 else "experience"
    tertiary = keywords[2] if len(keywords) > 2 else "review"

    context_terms = {
        "health": ["treatment", "symptom"],
        "consumer": ["review", "experience"],
        "general": ["opinion", "experience"],
    }.get(domain, ["opinion", "experience"])
    natural_query = _build_simple_natural_query(keywords)
    moderate_boolean = f'("{primary}" OR "{secondary}") AND ("{tertiary}" OR "{context_terms[0]}")'
    complex_boolean = (
        f'("{primary}" OR "{secondary}") '
        f'AND ("{tertiary}" OR "{context_terms[0]}") '
        f'AND ("{context_terms[1]}" OR "discussion")'
    )

    candidates = [
        {
            "label": "Natural Language Query",
            "query_type": "natural_language",
            "boolean_query": natural_query,
            "description": "Plain search phrase for the broadest initial pull.",
            "or_groups": [[natural_query]],
        },
        {
            "label": "Moderate Boolean Query",
            "query_type": "boolean",
            "boolean_query": moderate_boolean,
            "description": "Adds one context group for a little more precision.",
            "or_groups": [[primary, secondary], [tertiary, context_terms[0]]],
        },
        {
            "label": "Complex Boolean Query",
            "query_type": "boolean",
            "boolean_query": complex_boolean,
            "description": "Adds multiple concept groups for a more targeted pull.",
            "or_groups": [[primary, secondary], [tertiary, context_terms[0]], [context_terms[1], "discussion"]],
        },
    ]
    return candidates


class MockLLMAdapter:
    """Deterministic mock LLM that generates boolean query suggestions."""

    async def generate_boolean_queries(self, research_question: str, domain: str) -> List[dict]:
        return _build_mock_candidates(research_question, domain)

class RealLLMAdapter:
    """OpenAI-backed LLM adapter."""

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY

    async def generate_boolean_queries(self, research_question: str, domain: str) -> List[dict]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        import httpx

        prompt = f"""You are a social media research expert. Generate exactly 3 social listening query candidates.

Research question: {research_question}
Domain: {domain}

Return ONLY valid JSON with this shape:
{{
  "candidates": [
    {{
      "label": "Simple Natural Language",
      "query_type": "natural_language",
      "boolean_query": "plain search phrase or sentence",
      "description": "string explaining the query strategy",
      "or_groups": [["term 1", "term 2"]]
    }}
  ]
}}

Candidate requirements:
1. The first candidate MUST be labeled "Natural Language Query", query_type "natural_language", and be one short plain search phrase. Do not use AND, OR, NOT, parentheses, abbreviations, or acronyms in this first query.
2. The second candidate MUST be labeled "Moderate Boolean Query", query_type "boolean", and use 2 grouped concepts joined with AND. Each group should contain 2-3 synonyms joined with OR. Keep it readable and avoid NOT clauses.
3. The third candidate MUST be labeled "Complex Boolean Query", query_type "boolean", and use 3-4 grouped concepts joined with AND. Each group should contain 2-4 synonyms joined with OR. It may include one carefully chosen NOT clause only if it clearly removes irrelevant results, but do not use advanced platform-specific syntax.

Generate exactly 3 candidates. Do not include markdown or any text outside the JSON object."""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 1500,
                        "response_format": {"type": "json_object"},
                    },
                    timeout=30.0,
                )
                response.raise_for_status()

            payload = response.json()
            content = payload["choices"][0]["message"].get("content") or ""
            if not content.strip():
                raise ValueError("OpenAI returned empty message content")

            parsed = json.loads(content)
            candidates = parsed.get("candidates")
            if not isinstance(candidates, list):
                raise ValueError("OpenAI JSON response missing candidates list")

            valid_candidates = []
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                if not all(
                    key in candidate
                    for key in ("label", "boolean_query", "description", "or_groups")
                ):
                    continue
                candidate.setdefault("query_type", "boolean")
                valid_candidates.append(candidate)

            if not valid_candidates:
                raise ValueError("OpenAI response did not contain valid candidates")

            logger.info("OpenAI generated query candidates: count=%s", len(valid_candidates))
            return valid_candidates[:3]
        except Exception as exc:
            logger.warning(
                "OpenAI query generation failed: error=%s",
                type(exc).__name__,
            )
            raise

def get_llm_adapter():
    return RealLLMAdapter() if settings.OPENAI_API_KEY else MockLLMAdapter()
