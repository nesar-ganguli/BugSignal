import asyncio
import json
import logging

from celery import Task

from app.celery_app import celery_app
from app.database import SessionLocal
from app.repositories.workflow_repository import (
    complete_workflow,
    fail_workflow,
    get_workflow_run_by_id,
    mark_workflow_retrying,
    mark_workflow_running,
    pause_workflow_for_codebase,
    update_workflow_progress,
)
from app.repositories.cluster_repository import list_clusters
from app.repositories.code_repository import codebase_status
from app.repositories.issue_repository import get_latest_issue_draft_for_cluster
from app.config import get_settings
from app.services.code_retrieval_service import retrieve_code_for_cluster
from app.services.issue_drafting_service import draft_issue_for_cluster
from app.services.llm_client import LLMClient
from app.services.cluster_workflow_service import rebuild_ticket_clusters
from app.repositories.ticket_repository import count_tickets, reset_project_extractions
from app.services.ticket_processing_service import extract_pending_ticket_batch, process_ticket_batch


logger = logging.getLogger("bugsignal.workflow")


class WorkflowCancelled(RuntimeError):
    pass


@celery_app.task(bind=True, max_retries=2, name="bugsignal.triage_pipeline")
def triage_pipeline_workflow(self: Task, workflow_id: str) -> dict:
    logger.info("Triage pipeline received", extra={"workflow_id": workflow_id})
    with SessionLocal() as db:
        workflow = get_workflow_run_by_id(db, workflow_id)
        if workflow is None:
            return {"workflow_id": workflow_id, "status": "missing"}
        if workflow.status == "completed":
            return {"workflow_id": workflow_id, "status": "completed"}

        resume_after_codebase = workflow.current_step == "codebase_indexed"
        workflow_input = json.loads(workflow.input_json or "{}")
        mark_workflow_running(db, workflow, "resuming_after_codebase" if resume_after_codebase else "extracting_tickets")

        try:
            result = asyncio.run(
                _run_triage_pipeline(
                    db,
                    workflow,
                    resume_after_codebase=resume_after_codebase,
                    force=bool(workflow_input.get("force", False)) and self.request.retries == 0,
                )
            )
        except WorkflowCancelled:
            return {"workflow_id": workflow_id, "status": "cancelled"}
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            logger.exception("Triage pipeline failed", extra={"workflow_id": workflow_id})
            db.rollback()
            workflow = get_workflow_run_by_id(db, workflow_id)
            if workflow is None:
                raise
            if self.request.retries < self.max_retries:
                mark_workflow_retrying(db, workflow, message)
                raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))
            fail_workflow(db, workflow, message)
            raise

        if result["status"] == "waiting_for_codebase":
            pause_workflow_for_codebase(db, workflow, result)
            return {"workflow_id": workflow_id, **result}
        complete_workflow(db, workflow, result)
        logger.info("Triage pipeline completed", extra={"workflow_id": workflow_id})
        return {"workflow_id": workflow_id, "status": "completed", "result": result}


async def _run_triage_pipeline(db, workflow, *, resume_after_codebase: bool, force: bool) -> dict:
    settings = get_settings()
    project_id = workflow.project_id
    extraction = {"processed": 0, "failed": 0, "errors": []}

    if not resume_after_codebase:
        if force:
            reset_project_extractions(db, project_id)
        total = count_tickets(db, project_id)
        while True:
            db.refresh(workflow)
            if workflow.status == "cancelled":
                raise WorkflowCancelled()
            attempted, processed, failed, errors = await extract_pending_ticket_batch(
                db, project_id=project_id, limit=settings.triage_batch_size
            )
            extraction["processed"] += processed
            extraction["failed"] += failed
            extraction["errors"].extend(errors)
            if attempted == 0:
                break
            progress = 5 + round(((extraction["processed"] + extraction["failed"]) / max(total, 1)) * 35)
            update_workflow_progress(db, workflow, "extracting_tickets", min(progress, 40))

        update_workflow_progress(db, workflow, "clustering_tickets", 45)
        cluster_result = rebuild_ticket_clusters(db, project_id)
        stage_result = {
            "total_tickets": total,
            "extraction": extraction,
            "clusters_created": cluster_result.clusters_created,
            "clustered_tickets": cluster_result.clustered_tickets,
            "outlier_tickets": cluster_result.outlier_tickets,
        }
        indexed_files, indexed_chunks, _ = codebase_status(db, project_id)
        if indexed_chunks == 0:
            return {
                "status": "waiting_for_codebase",
                **stage_result,
                "message": "Ticket processing is complete. Add a repository to continue code retrieval and issue drafting.",
            }
    else:
        stage_result = json.loads(workflow.result_json or "{}")
        indexed_files, indexed_chunks, _ = codebase_status(db, project_id)
        if indexed_chunks == 0:
            return {**stage_result, "status": "waiting_for_codebase"}

    update_workflow_progress(db, workflow, "retrieving_code", 60)
    clusters = list_clusters(db, project_id)
    eligible = [
        cluster for cluster in clusters
        if cluster.title != "Needs manual triage" and cluster.cohesion_score >= settings.triage_min_cluster_cohesion
    ]
    cluster_results = []
    llm_client = LLMClient(settings.ollama_base_url, settings.ollama_model, timeout_seconds=180)
    for index, cluster in enumerate(eligible, start=1):
        item = {"cluster_id": cluster.id, "title": cluster.title}
        try:
            retrieval = retrieve_code_for_cluster(db, project_id, cluster)
            item["evidence_count"] = len(retrieval.snippets)
            existing = get_latest_issue_draft_for_cluster(db, project_id, cluster.id)
            if existing:
                item.update({"status": "draft_exists", "issue_id": existing.id})
            elif retrieval.snippets:
                draft = await draft_issue_for_cluster(db, project_id, cluster, llm_client)
                item.update({"status": "drafted", "issue_id": draft.draft.id})
            else:
                item["status"] = "no_evidence"
        except Exception as exc:
            db.rollback()
            item.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:1000]})
        cluster_results.append(item)
        update_workflow_progress(db, workflow, "drafting_issues", 60 + round((index / max(len(eligible), 1)) * 35))

    return {
        **stage_result,
        "status": "completed",
        "indexed_files": indexed_files,
        "indexed_chunks": indexed_chunks,
        "eligible_clusters": len(eligible),
        "cluster_results": cluster_results,
        "drafted_issues": sum(item["status"] == "drafted" for item in cluster_results),
        "failed_clusters": sum(item["status"] == "failed" for item in cluster_results),
        "message": "Automated triage completed. Review and approve the generated issue drafts.",
    }


@celery_app.task(bind=True, max_retries=2, name="bugsignal.process_tickets")
def process_tickets_workflow(self: Task, workflow_id: str) -> dict:
    logger.info("Workflow task received", extra={"workflow_id": workflow_id})
    with SessionLocal() as db:
        workflow = get_workflow_run_by_id(db, workflow_id)
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
                    project_id=workflow.project_id,
                    limit=int(workflow_input.get("limit", 20)),
                    # A retry resumes pending/failed tickets instead of repeating completed work.
                    force=bool(workflow_input.get("force", False)) and self.request.retries == 0,
                    progress=report,
                )
            )
        except WorkflowCancelled:
            logger.info("Workflow cancelled", extra={"workflow_id": workflow_id})
            return {"workflow_id": workflow_id, "status": "cancelled"}
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            logger.exception("Workflow execution failed", extra={"workflow_id": workflow_id})
            # A flush/commit error leaves the session unusable until it is rolled
            # back. Reload the workflow after rollback before persisting retry or
            # terminal failure state.
            db.rollback()
            workflow = get_workflow_run_by_id(db, workflow_id)
            if workflow is None:
                raise
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
        logger.info("Workflow completed", extra={"workflow_id": workflow_id})
        return {"workflow_id": workflow_id, "status": "completed", "result": result_payload}
