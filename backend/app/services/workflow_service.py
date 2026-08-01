import json
from typing import Any

from app.models import WorkflowRun
from app.schemas.workflow_schema import WorkflowRunRead


def workflow_to_read(workflow: WorkflowRun) -> WorkflowRunRead:
    return WorkflowRunRead(
        id=workflow.id,
        workflow_type=workflow.workflow_type,
        status=workflow.status,
        current_step=workflow.current_step,
        progress_percent=workflow.progress_percent,
        input=_parse_json_object(workflow.input_json),
        result=_parse_json_object(workflow.result_json),
        error_message=workflow.error_message,
        attempt_count=workflow.attempt_count,
        queue_task_id=workflow.queue_task_id,
        created_at=workflow.created_at,
        started_at=workflow.started_at,
        completed_at=workflow.completed_at,
        updated_at=workflow.updated_at,
    )


def _parse_json_object(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
