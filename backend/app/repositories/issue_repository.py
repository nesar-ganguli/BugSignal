import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import IssueDraft


def create_issue_draft(
    db: Session,
    *,
    cluster_id: int,
    title: str,
    body_markdown: str,
    priority_label: str,
    confidence_level: str,
    warnings: list[str] | None = None,
    status: str = "draft",
) -> IssueDraft:
    issue = IssueDraft(
        cluster_id=cluster_id,
        title=title,
        body_markdown=body_markdown,
        priority_label=priority_label,
        confidence_level=confidence_level,
        warnings=json.dumps(warnings or []),
        status=status,
    )
    db.add(issue)
    db.flush()
    return issue


def get_issue_draft(db: Session, issue_id: int) -> IssueDraft | None:
    return db.get(IssueDraft, issue_id)


def update_issue_approval(
    issue: IssueDraft,
    *,
    status: str,
    github_issue_url: str | None = None,
) -> None:
    issue.status = status
    if github_issue_url:
        issue.github_issue_url = github_issue_url


def get_latest_issue_draft_for_cluster(db: Session, cluster_id: int) -> IssueDraft | None:
    statement = (
        select(IssueDraft)
        .where(IssueDraft.cluster_id == cluster_id)
        .order_by(IssueDraft.created_at.desc(), IssueDraft.id.desc())
        .limit(1)
    )
    return db.scalar(statement)


def list_issue_drafts(db: Session) -> list[IssueDraft]:
    statement = select(IssueDraft).order_by(IssueDraft.created_at.desc(), IssueDraft.id.desc())
    return list(db.scalars(statement).all())
