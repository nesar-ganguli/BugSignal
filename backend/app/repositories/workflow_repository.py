import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import WorkflowRun


def create_workflow_run(
    db: Session, project_id: int, workflow_type: str, workflow_input: dict[str, Any]
) -> WorkflowRun:
    workflow = WorkflowRun(
        id=str(uuid4()),
        project_id=project_id,
        workflow_type=workflow_type,
        status="queued",
        current_step="queued",
        progress_percent=0,
        input_json=json.dumps(workflow_input),
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return workflow


def get_workflow_run(db: Session, project_id: int, workflow_id: str) -> WorkflowRun | None:
    return db.scalar(select(WorkflowRun).where(WorkflowRun.project_id == project_id, WorkflowRun.id == workflow_id))


def get_workflow_run_by_id(db: Session, workflow_id: str) -> WorkflowRun | None:
    """Internal worker lookup; external callers must use the project-scoped lookup."""
    return db.get(WorkflowRun, workflow_id)


def list_workflow_runs(db: Session, project_id: int, limit: int = 20) -> list[WorkflowRun]:
    statement = select(WorkflowRun).where(WorkflowRun.project_id == project_id).order_by(WorkflowRun.created_at.desc()).limit(limit)
    return list(db.scalars(statement).all())


def count_workflow_runs(db: Session, project_id: int) -> int:
    return db.scalar(select(func.count()).select_from(WorkflowRun).where(WorkflowRun.project_id == project_id)) or 0


def get_active_workflow_run(db: Session, project_id: int, workflow_type: str) -> WorkflowRun | None:
    statement = (
        select(WorkflowRun)
        .where(
            WorkflowRun.workflow_type == workflow_type,
            WorkflowRun.project_id == project_id,
            WorkflowRun.status.in_(["queued", "running"]),
        )
        .order_by(WorkflowRun.created_at.desc())
        .limit(1)
    )
    return db.scalar(statement)


def mark_workflow_dispatched(db: Session, workflow: WorkflowRun, task_id: str) -> None:
    workflow.queue_task_id = task_id
    workflow.updated_at = datetime.utcnow()
    db.commit()


def mark_workflow_running(db: Session, workflow: WorkflowRun, step: str) -> None:
    workflow.status = "running"
    workflow.current_step = step
    workflow.progress_percent = max(workflow.progress_percent, 1)
    workflow.attempt_count += 1
    workflow.started_at = workflow.started_at or datetime.utcnow()
    workflow.error_message = None
    workflow.updated_at = datetime.utcnow()
    db.commit()


def update_workflow_progress(
    db: Session, workflow: WorkflowRun, step: str, progress_percent: int
) -> None:
    workflow.current_step = step
    workflow.progress_percent = min(max(progress_percent, 0), 99)
    workflow.updated_at = datetime.utcnow()
    db.commit()


def complete_workflow(db: Session, workflow: WorkflowRun, result: dict[str, Any]) -> None:
    now = datetime.utcnow()
    workflow.status = "completed"
    workflow.current_step = "completed"
    workflow.progress_percent = 100
    workflow.result_json = json.dumps(result)
    workflow.error_message = None
    workflow.completed_at = now
    workflow.updated_at = now
    db.commit()


def fail_workflow(db: Session, workflow: WorkflowRun, error_message: str) -> None:
    now = datetime.utcnow()
    workflow.status = "failed"
    workflow.current_step = "failed"
    workflow.error_message = error_message[:4000]
    workflow.completed_at = now
    workflow.updated_at = now
    db.commit()


def mark_workflow_retrying(db: Session, workflow: WorkflowRun, error_message: str) -> None:
    workflow.status = "queued"
    workflow.current_step = "retrying"
    workflow.error_message = error_message[:4000]
    workflow.updated_at = datetime.utcnow()
    db.commit()


def cancel_workflow(db: Session, workflow: WorkflowRun) -> None:
    now = datetime.utcnow()
    workflow.status = "cancelled"
    workflow.current_step = "cancelled"
    workflow.completed_at = now
    workflow.updated_at = now
    db.commit()
