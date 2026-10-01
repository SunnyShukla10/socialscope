import logging
from typing import List
from app.adapters.llm_adapter import get_llm_adapter
from app.schemas.query import QueryCandidate

logger = logging.getLogger(__name__)


class QueryService:
    def __init__(self):
        self.llm = get_llm_adapter()

    async def generate_queries(
        self, research_question: str, domain: str
    ) -> List[QueryCandidate]:
        logger.info(
            "Generating query candidates: adapter=%s domain=%s question_length=%s",
            self.llm.__class__.__name__,
            domain,
            len(research_question),
        )
        raw = await self.llm.generate_boolean_queries(research_question, domain)
        candidates = []
        for item in raw:
            query_type = item.get("query_type", "boolean")
            if query_type not in {"natural_language", "boolean"}:
                query_type = "boolean"
            candidates.append(
                QueryCandidate(
                    label=item["label"],
                    boolean_query=item["boolean_query"],
                    query_type=query_type,
                    description=item["description"],
                    or_groups=item["or_groups"],
                )
            )
        logger.info("Generated query candidates: count=%s", len(candidates))
        return candidates
