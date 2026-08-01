from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.config import get_settings
from app.database import get_db
from app.models import Cluster
from app.repositories.issue_repository import (
    get_issue_draft,
    list_issue_drafts,
    update_issue_approval,
)
from app.schemas.issue_schema import IssueApprovalResponse, IssueDraftRead
from app.services.github_service import GitHubIssueCreationError, GitHubService
from app.services.tenant_service import TenantContext, require_editor_context, require_tenant_context

router = APIRouter(prefix="/issues", tags=["issues"])


@router.get("", response_model=list[IssueDraftRead])
async def get_issue_drafts(db: Session = Depends(get_db), tenant: TenantContext = Depends(require_tenant_context)) -> list[IssueDraftRead]:
    return [IssueDraftRead.model_validate(issue) for issue in list_issue_drafts(db, tenant.project_id)]


@router.post("/{issue_id}/approve", response_model=IssueApprovalResponse)
async def approve_issue(issue_id: int, db: Session = Depends(get_db), tenant: TenantContext = Depends(require_editor_context)) -> IssueApprovalResponse:
    issue = get_issue_draft(db, tenant.project_id, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue draft not found.")
    if issue.status == "issue_created":
        return IssueApprovalResponse(
            issue=IssueDraftRead.model_validate(issue),
            github_issue_created=True,
            message="Issue was already created on GitHub.",
        )

    github_service = GitHubService(get_settings())
    try:
        result = await github_service.create_issue(issue)
    except GitHubIssueCreationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if result.created:
        update_issue_approval(issue, status="issue_created", github_issue_url=result.url)
        cluster = db.scalar(select(Cluster).where(Cluster.project_id == tenant.project_id, Cluster.id == issue.cluster_id))
        if cluster:
            cluster.status = "issue_created"
    else:
        update_issue_approval(issue, status="approved")

    db.commit()
    db.refresh(issue)
    return IssueApprovalResponse(
        issue=IssueDraftRead.model_validate(issue),
        github_issue_created=result.created,
        message=result.message,
    )
