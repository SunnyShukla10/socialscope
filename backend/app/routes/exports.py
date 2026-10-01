from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging
import uuid
import os
from app.database import get_db
from app.schemas.export import ExportRequest, ExportJobOut
from app.services.export_service import ExportService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/projects/{project_id}/exports", tags=["exports"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ExportJobOut, status_code=201)
async def create_export(
    project_id: uuid.UUID,
    body: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    logger.info(
        "Create export request: project_id=%s user_id=%s format=%s platform=%s",
        project_id,
        getattr(current_user, "id", None),
        body.format,
        body.platform,
    )
    service = ExportService(db)
    try:
        export_job = await service.create_export(
            project_id=project_id,
            organization_id=current_user.organization_id,
            request=body,
            actor=current_user,
        )
    except Exception:
        logger.exception(
            "Create export failed: project_id=%s user_id=%s",
            project_id,
            getattr(current_user, "id", None),
        )
        raise
    logger.info(
        "Create export succeeded: project_id=%s export_id=%s status=%s rows=%s",
        project_id,
        export_job.id,
        export_job.status,
        export_job.row_count,
    )
    return export_job


@router.get("", response_model=List[ExportJobOut])
async def list_exports(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    logger.info(
        "List exports request: project_id=%s user_id=%s",
        project_id,
        getattr(current_user, "id", None),
    )
    service = ExportService(db)
    try:
        exports = await service.list_exports(project_id, current_user.organization_id)
    except Exception:
        logger.exception(
            "List exports failed: project_id=%s user_id=%s",
            project_id,
            getattr(current_user, "id", None),
        )
        raise
    logger.info("List exports succeeded: project_id=%s count=%s", project_id, len(exports))
    return exports


@router.get("/{export_id}/download")
async def download_export(
    project_id: uuid.UUID,
    export_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(AuthService.get_current_user),
):
    logger.info(
        "Download export request: project_id=%s export_id=%s user_id=%s",
        project_id,
        export_id,
        getattr(current_user, "id", None),
    )
    from app.services.project_service import ProjectService
    if not await ProjectService(db).get_project(project_id, current_user.organization_id):
        raise HTTPException(404, "Project not found")
    service = ExportService(db)
    export_job = await service.get_export(export_id, project_id)
    if not export_job:
        logger.warning("Download export not found: project_id=%s export_id=%s", project_id, export_id)
        raise HTTPException(status_code=404, detail="Export not found")
    if export_job.status != "completed":
        logger.warning(
            "Download export not ready: project_id=%s export_id=%s status=%s",
            project_id,
            export_id,
            export_job.status,
        )
        raise HTTPException(status_code=400, detail="Export is not ready yet")
    if not export_job.file_path or not os.path.exists(export_job.file_path):
        logger.warning(
            "Download export file missing: project_id=%s export_id=%s file_path=%s",
            project_id,
            export_id,
            export_job.file_path,
        )
        raise HTTPException(status_code=404, detail="Export file not found")
    logger.info(
        "Download export succeeded: project_id=%s export_id=%s",
        project_id,
        export_id,
    )
    return FileResponse(
        path=export_job.file_path,
        media_type="text/csv",
        filename=f"export_{export_id}.csv",
    )
