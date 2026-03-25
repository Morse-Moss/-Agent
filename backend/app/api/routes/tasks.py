"""Task API routes — create, query, advance, select candidates.

P0 fixes: 409 for conflicts, expected_step CAS, step-restricted select-candidate.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...api.dependencies import get_current_user
from ...db import get_db
from ...models import User
from ...schemas import (
    AdvanceTaskRequest,
    CandidateRead,
    CreateTaskRequest,
    SelectCandidateRequest,
    TaskRead,
)
from ...services.task_orchestrator import TaskOrchestrator

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskRead)
def create_task(
    body: CreateTaskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskRead:
    orch = TaskOrchestrator(db)
    try:
        task = orch.create_task(
            entry_type=body.entry_type,
            config=body.task_config_json,
            product_category_id=body.product_category_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(task)
    return TaskRead.model_validate(task)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskRead:
    orch = TaskOrchestrator(db)
    task = orch.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskRead.model_validate(task)


@router.post("/{task_id}/advance", response_model=TaskRead)
def advance_task(
    task_id: int,
    body: AdvanceTaskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskRead:
    orch = TaskOrchestrator(db)
    task = orch.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    ok, reason = orch.advance(
        task,
        target_step=body.target_step,
        expected_step=body.expected_step,
    )
    if not ok:
        # Distinguish conflict (409) from precondition failure (400)
        status_code = 409 if "Conflict" in reason or "Illegal transition" in reason else 400
        raise HTTPException(status_code=status_code, detail=reason)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(task)
    return TaskRead.model_validate(task)


@router.post("/{task_id}/select-candidate", response_model=TaskRead)
def select_candidate(
    task_id: int,
    body: SelectCandidateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskRead:
    orch = TaskOrchestrator(db)
    task = orch.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    ok, reason = orch.select_candidate(task, body.candidate_id)
    if not ok:
        status_code = 409 if "Cannot select candidate at step" in reason else 400
        raise HTTPException(status_code=status_code, detail=reason)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(task)
    return TaskRead.model_validate(task)


@router.get("/{task_id}/candidates", response_model=list[CandidateRead])
def list_candidates(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CandidateRead]:
    orch = TaskOrchestrator(db)
    task = orch.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return [CandidateRead.model_validate(c) for c in task.candidates]


# ---------------------------------------------------------------------------
# v0.5: Video generation, copy generation, detail modules
# ---------------------------------------------------------------------------

@router.post("/{task_id}/generate-video")
async def generate_video(
    task_id: int,
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    from ...core.config import settings as app_settings
    from ...services.video_gateway import VideoGateway

    orch = TaskOrchestrator(db)
    task = orch.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    gateway = VideoGateway(
        provider=app_settings.video_provider,
        api_url=app_settings.video_api_url,
        api_key=app_settings.video_api_key,
        model=app_settings.video_model,
    )

    result = await gateway.generate_video(
        prompt=body.get("prompt", ""),
        image_url=body.get("image_url"),
        duration_seconds=body.get("duration_seconds", 5),
        orientation=body.get("orientation", "landscape"),
        resolution=body.get("resolution", "1080p"),
    )
    return result


@router.post("/{task_id}/generate-copy")
def generate_copy(
    task_id: int,
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    from ...services.model_gateway import ModelGateway
    from ...services.system_settings import SystemSettingsService

    orch = TaskOrchestrator(db)
    task = orch.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    svc = SystemSettingsService(db)
    runtime_config = svc.build_gateway_runtime_config()
    gateway = ModelGateway(runtime_config)

    copies = gateway.generate_multi_platform_copy(
        product_name=body.get("product_name", ""),
        scene_description=body.get("scene_description", ""),
        selling_points=body.get("selling_points"),
        platforms=body.get("platforms"),
    )
    return {"copies": copies}
