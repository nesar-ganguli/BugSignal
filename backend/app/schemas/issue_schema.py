from pydantic import BaseModel


class IssueDraftRead(BaseModel):
    id: int
    cluster_id: int
    title: str
    body_markdown: str
    priority_label: str
    confidence_level: str
    status: str
    github_issue_url: str | None = None

    model_config = {"from_attributes": True}
