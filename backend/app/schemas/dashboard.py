from pydantic import BaseModel
class DashboardSummary(BaseModel):
    kpis: dict
    recent_projects: list[dict]
    active_jobs: list[dict]
