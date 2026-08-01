from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.workflow_repository import (
    count_workflow_runs,
    cancel_workflow,
    create_workflow_run,
    get_active_workflow_run,
    get_workflow_run,
    list_workflow_runs,
    mark_workflow_dispatched,
)
from app.schemas.workflow_schema import (
    TicketProcessingWorkflowRequest,
    WorkflowRunListResponse,
    WorkflowRunRead,
)
from app.services.workflow_service import workflow_to_read
from app.tasks.workflow_tasks import process_tickets_workflow


router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post(
    "/ticket-processing",
    response_model=WorkflowRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_ticket_processing_workflow(
    request: TicketProcessingWorkflowRequest,
    db: Session = Depends(get_db),
) -> WorkflowRunRead:
    active_workflow = get_active_workflow_run(db, "ticket_processing")
    if active_workflow is not None:
        return workflow_to_read(active_workflow)

    workflow = create_workflow_run(db, "ticket_processing", request.model_dump())
    try:
        task = process_tickets_workflow.delay(workflow.id)
    except Exception as exc:
        from app.repositories.workflow_repository import fail_workflow

        fail_workflow(db, workflow, f"Unable to dispatch workflow: {exc}")
        raise HTTPException(status_code=503, detail="Workflow queue is unavailable.") from exc
    mark_workflow_dispatched(db, workflow, task.id)
    db.refresh(workflow)
    return workflow_to_read(workflow)


@router.get("", response_model=WorkflowRunListResponse)
async def get_workflows(
    limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)
) -> WorkflowRunListResponse:
    return WorkflowRunListResponse(
        items=[workflow_to_read(item) for item in list_workflow_runs(db, limit)],
        total=count_workflow_runs(db),
    )


@router.get("/{workflow_id}", response_model=WorkflowRunRead)
async def get_workflow(workflow_id: str, db: Session = Depends(get_db)) -> WorkflowRunRead:
    workflow = get_workflow_run(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return workflow_to_read(workflow)


@router.post("/{workflow_id}/cancel", response_model=WorkflowRunRead)
async def cancel_running_workflow(
    workflow_id: str, db: Session = Depends(get_db)
) -> WorkflowRunRead:
    workflow = get_workflow_run(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    if workflow.status in {"completed", "failed", "cancelled"}:
        return workflow_to_read(workflow)
    if workflow.queue_task_id:
        process_tickets_workflow.AsyncResult(workflow.queue_task_id).revoke(terminate=False)
    cancel_workflow(db, workflow)
    db.refresh(workflow)
    return workflow_to_read(workflow)
