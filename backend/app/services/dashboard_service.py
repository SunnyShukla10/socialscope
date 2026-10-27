from sqlalchemy import select, func
from app.models.project import Project
from app.models.normalized_post import NormalizedPost
from app.models.search_job import SearchJob
from app.services.project_service import ProjectService
from app.services.activity_service import ActivityService
from app.services.project_access import visible_projects

class DashboardService:
    def __init__(self, db): self.db = db
    async def get_summary(self, organization_id, user):
        projects = await ProjectService(self.db).list_projects(organization_id, user=user)
        jobs = (await self.db.execute(select(SearchJob).join(Project).where(
            visible_projects(organization_id, user),
            SearchJob.status.in_(["pending","queued","running","cancelling"])))).scalars().all()
        return {"kpis": {"total_projects": len(projects), "total_posts": sum(p["post_count"] for p in projects), "active_jobs":len(jobs)},
            "recent_projects": projects[:6], "active_jobs": [{"id":j.id,"project_id":j.project_id,
            "status":j.status,"platforms":j.platforms,"total_posts_collected":j.total_posts_collected} for j in jobs]}
