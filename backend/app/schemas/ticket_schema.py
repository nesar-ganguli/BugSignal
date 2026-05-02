from datetime import datetime

from pydantic import BaseModel


class TicketRead(BaseModel):
    id: int
    external_ticket_id: str
    title: str
    body: str
    created_at: datetime | None = None
    source: str | None = None
    customer_plan: str | None = None
    severity: str | None = None
    cluster_id: int | None = None

    model_config = {"from_attributes": True}
