from pydantic import BaseModel

from app.schemas.code_schema import CodeSnippetRead
from app.schemas.issue_schema import IssueDraftRead
from app.schemas.ticket_schema import TicketRead


class PriorityBreakdownItem(BaseModel):
    label: str
    points: int


class ClusterRead(BaseModel):
    id: int
    title: str
    summary: str | None = None
    ticket_count: int
    priority_score: float
    priority_label: str
    priority_breakdown: str | None = None
    confidence_score: float
    cohesion_score: float
    llm_coherence_label: str | None = None
    suspected_feature_area: str | None = None
    status: str

    model_config = {"from_attributes": True}


class ClusterListResponse(BaseModel):
    items: list[ClusterRead]
    total: int


class ClusterRunResponse(BaseModel):
    clusters_created: int
    clustered_tickets: int
    outlier_tickets: int
    message: str


class ClusterDetailResponse(BaseModel):
    cluster: ClusterRead
    tickets: list[TicketRead]
    priority_breakdown: list[PriorityBreakdownItem]
    retrieved_code_snippets: list[CodeSnippetRead] = []
    issue_draft: IssueDraftRead | None = None
