import asyncio
import json

from celery import Task

from app.celery_app import celery_app
from app.database import SessionLocal
from app.repositories.workflow_repository import (
    complete_workflow,
    fail_workflow,
    get_workflow_run,
    mark_workflow_retrying,
    mark_workflow_running,
    update_workflow_progress,
)
from app.services.ticket_processing_service import process_ticket_batch


class WorkflowCancelled(RuntimeError):
    pass


@celery_app.task(bind=True, max_retries=2, name="bugsignal.process_tickets")
def process_tickets_workflow(self: Task, workflow_id: str) -> dict:
    with SessionLocal() as db:
        workflow = get_workflow_run(db, workflow_id)
        if workflow is None:
            return {"workflow_id": workflow_id, "status": "missing"}
        if workflow.status == "completed":
            return {"workflow_id": workflow_id, "status": "completed"}

        mark_workflow_running(db, workflow, "starting")
        workflow_input = json.loads(workflow.input_json or "{}")

        def report(step: str, percent: int) -> None:
            db.refresh(workflow)
            if workflow.status == "cancelled":
                raise WorkflowCancelled("Workflow was cancelled.")
            update_workflow_progress(db, workflow, step, percent)

        try:
            result = asyncio.run(
                process_ticket_batch(
                    db,
                    limit=int(workflow_input.get("limit", 20)),
                    # A retry resumes pending/failed tickets instead of repeating completed work.
                    force=bool(workflow_input.get("force", False)) and self.request.retries == 0,
                    progress=report,
                )
            )
        except WorkflowCancelled:
            return {"workflow_id": workflow_id, "status": "cancelled"}
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            if self.request.retries < self.max_retries:
                mark_workflow_retrying(db, workflow, message)
                raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))
            fail_workflow(db, workflow, message)
            raise

        db.refresh(workflow)
        if workflow.status == "cancelled":
            return {"workflow_id": workflow_id, "status": "cancelled"}
        result_payload = result.model_dump(mode="json")
        complete_workflow(db, workflow, result_payload)
        return {"workflow_id": workflow_id, "status": "completed", "result": result_payload}
