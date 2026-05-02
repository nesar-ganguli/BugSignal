from pydantic import BaseModel


class ClusterRead(BaseModel):
    id: int
    title: str
    ticket_count: int
    priority_score: float
    priority_label: str
    confidence_score: float
    suspected_feature_area: str | None = None
    status: str

    model_config = {"from_attributes": True}
