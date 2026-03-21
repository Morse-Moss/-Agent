from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...db import get_db
from ...schemas import (
    CreateProjectRequest,
    GenerateProjectRequest,
    GenerationResult,
    ProjectDetail,
    ProjectListItem,
    RegenerateVersionRequest,
    ReviewVersionRequest,
)
from ...services.generation import ProjectService
from ...services.image_pipeline import ImagePipeline
from ...services.model_gateway import ModelGateway
from ...services.storage import StorageService
from ...services.system_settings import SystemSettingsService
from ..dependencies import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


def get_project_service(db: Session) -> ProjectService:
    settings_service = SystemSettingsService(db)
    runtime_config = settings_service.build_gateway_runtime_config()
    storage = StorageService()
    gateway = ModelGateway(runtime_config=runtime_config)
    pipeline = ImagePipeline(storage, gateway=gateway)
    return ProjectService(db, gateway=gateway, image_pipeline=pipeline)


@router.get("", response_model=list[ProjectListItem])
def list_projects(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[ProjectListItem]:
    service = get_project_service(db)
    return service.list_projects(current_user, status=status)


@router.post("", response_model=ProjectDetail)
def create_project(
    payload: CreateProjectRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ProjectDetail:
    service = get_project_service(db)
    return service.create_project(payload.model_dump(), current_user)


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ProjectDetail:
    service = get_project_service(db)
    try:
        return service.get_project_detail(project_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> dict[str, bool]:
    service = get_project_service(db)
    try:
        service.delete_project(project_id, current_user)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{project_id}/generate", response_model=GenerationResult)
def generate_project(
    project_id: int,
    payload: GenerateProjectRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> GenerationResult:
    service = get_project_service(db)
    try:
        return service.generate(project_id=project_id, payload=payload.model_dump(), current_user=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/versions/{version_id}/regenerate", response_model=GenerationResult)
def regenerate_version(
    project_id: int,
    version_id: int,
    payload: RegenerateVersionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> GenerationResult:
    service = get_project_service(db)
    try:
        return service.regenerate(project_id=project_id, version_id=version_id, payload=payload.model_dump(), current_user=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/versions/{version_id}/review", response_model=ProjectDetail)
def review_version(
    project_id: int,
    version_id: int,
    payload: ReviewVersionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ProjectDetail:
    service = get_project_service(db)
    try:
        return service.review(
            project_id=project_id,
            version_id=version_id,
            action=payload.action,
            comment=payload.comment,
            current_user=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/versions/{version_id}/finalize", response_model=ProjectDetail)
def finalize_version(
    project_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ProjectDetail:
    service = get_project_service(db)
    try:
        return service.finalize(project_id=project_id, version_id=version_id, current_user=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/versions/{version_id}/derive", response_model=GenerationResult)
def derive_version(
    project_id: int,
    version_id: int,
    payload: RegenerateVersionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> GenerationResult:
    service = get_project_service(db)
    try:
        return service.derive(project_id=project_id, version_id=version_id, payload=payload.model_dump(), current_user=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
