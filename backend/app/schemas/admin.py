from pydantic import BaseModel

from app.schemas.activity import ActivityEventOut


class ApiKeyStatus(BaseModel):
    key: str
    label: str
    status: str
    masked_value: str | None = None


class AdminOverview(BaseModel):
    api_keys: list[ApiKeyStatus]
    audit_log: list[ActivityEventOut]
