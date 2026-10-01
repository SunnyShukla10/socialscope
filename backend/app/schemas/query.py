from pydantic import BaseModel
from typing import List, Literal, Optional


class QueryGenerateRequest(BaseModel):
    research_question: str
    domain: str = "general"  # health | consumer | general


class QueryCandidate(BaseModel):
    label: str
    boolean_query: str
    query_type: Literal["natural_language", "boolean"] = "boolean"
    description: str
    or_groups: List[List[str]]


class QueryGenerateResponse(BaseModel):
    candidates: List[QueryCandidate]
    research_question: str
    domain: str
