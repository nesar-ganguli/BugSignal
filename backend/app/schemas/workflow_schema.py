from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


WorkflowStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class TicketProcessingWorkflowRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    force: bool = False


class WorkflowRunRead(BaseModel):
    id: str
    workflow_type: str
    status: WorkflowStatus
    current_step: str
    progress_percent: int
    input: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error_message: str | None = None
    attempt_count: int
    queue_task_id: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime


class WorkflowRunListResponse(BaseModel):
    items: list[WorkflowRunRead]
    total: int
