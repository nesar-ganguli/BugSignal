from sqlalchemy.orm import Session

from app.repositories.workflow_repository import (
    create_workflow_run,
    get_active_workflow_run,
    mark_workflow_dispatched,
    fail_workflow,
    requeue_workflow,
)


def queue_triage_workflow(db: Session, project_id: int, *, force: bool = False):
    from app.tasks.workflow_tasks import triage_pipeline_workflow

    workflow = get_active_workflow_run(db, project_id, "triage_pipeline")
    if workflow and workflow.status in {"queued", "running"}:
        return workflow
    if workflow and workflow.status == "waiting_for_codebase":
        requeue_workflow(db, workflow, "tickets_uploaded")
    else:
        workflow = create_workflow_run(
            db,
            project_id,
            "triage_pipeline",
            {"force": force},
        )
    try:
        task = triage_pipeline_workflow.delay(workflow.id)
    except Exception as exc:
        fail_workflow(db, workflow, f"Unable to dispatch triage pipeline: {exc}")
        raise
    mark_workflow_dispatched(db, workflow, task.id)
    db.refresh(workflow)
    return workflow


def resume_triage_after_codebase(db: Session, project_id: int):
    from app.tasks.workflow_tasks import triage_pipeline_workflow

    workflow = get_active_workflow_run(db, project_id, "triage_pipeline")
    if workflow is None or workflow.status != "waiting_for_codebase":
        return None
    requeue_workflow(db, workflow, "codebase_indexed")
    try:
        task = triage_pipeline_workflow.delay(workflow.id)
    except Exception as exc:
        fail_workflow(db, workflow, f"Unable to resume triage pipeline: {exc}")
        raise
    mark_workflow_dispatched(db, workflow, task.id)
    db.refresh(workflow)
    return workflow
