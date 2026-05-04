from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TicketCreate(BaseModel):
    external_ticket_id: str
    title: str
    body: str
    created_at: datetime | None = None
    source: str | None = None
    customer_plan: str | None = None
    severity: str | None = None


class TicketRead(BaseModel):
    id: int
    external_ticket_id: str
    title: str
    body: str
    created_at: datetime | None = None
    source: str | None = None
    customer_plan: str | None = None
    severity: str | None = None
    extracted_intent: str | None = None
    extracted_user_action: str | None = None
    extracted_expected_behavior: str | None = None
    extracted_actual_behavior: str | None = None
    extracted_feature_area: str | None = None
    extracted_error_terms: str | None = None
    sentiment: str | None = None
    contains_payment_or_revenue_issue: bool = False
    contains_data_loss_issue: bool = False
    contains_auth_issue: bool = False
    contains_performance_issue: bool = False
    extraction_status: str = "pending"
    extracted_at: datetime | None = None
    extraction_error: str | None = None
    cluster_id: int | None = None

    model_config = {"from_attributes": True}


class TicketListResponse(BaseModel):
    items: list[TicketRead]
    total: int


class TicketUploadResponse(BaseModel):
    filename: str
    bytes_received: int
    inserted: int
    updated: int
    skipped: int
    total_tickets: int
    status: str
    message: str
    errors: list[str] = []


class TicketExtractionResult(BaseModel):
    intent: str | None = None
    user_action: str | None = None
    expected_behavior: str | None = None
    actual_behavior: str | None = None
    feature_area: str | None = None
    error_terms: list[str] = []
    sentiment: Literal["neutral", "frustrated", "angry", "urgent"] | None = None
    contains_payment_or_revenue_issue: bool = False
    contains_data_loss_issue: bool = False
    contains_auth_issue: bool = False
    contains_performance_issue: bool = False


class TicketProcessResponse(BaseModel):
    processed: int
    failed: int
    total_tickets: int
    clusters_created: int = 0
    clustered_tickets: int = 0
    outlier_tickets: int = 0
    message: str
    errors: list[str] = []
