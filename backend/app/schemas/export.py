from typing import Literal
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime


class ExportRequest(BaseModel):
    scope: Literal["included", "excluded", "all"] = "included"
    format: str = "csv"
    platform: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = None


class ExportJobOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    format: str
    filters: dict
    file_path: Optional[str]
    file_size_bytes: Optional[int]
    row_count: Optional[int]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    download_url: Optional[str] = None

    model_config = {"from_attributes": True}
