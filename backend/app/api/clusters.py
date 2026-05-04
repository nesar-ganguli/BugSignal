import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.repositories.cluster_repository import count_clusters, get_cluster, list_clusters
from app.repositories.code_repository import list_retrieved_evidence_for_cluster
from app.repositories.issue_repository import get_latest_issue_draft_for_cluster
from app.repositories.ticket_repository import list_tickets_for_cluster
from app.schemas.cluster_schema import (
    ClusterDetailResponse,
    ClusterListResponse,
    ClusterRead,
    ClusterRunResponse,
    PriorityBreakdownItem,
)
from app.schemas.code_schema import CodeRetrievalResponse
from app.schemas.issue_schema import IssueDraftRead, IssueDraftResponse
from app.schemas.ticket_schema import TicketRead
from app.services.chroma_service import ChromaDependencyError
from app.services.cluster_workflow_service import rebuild_ticket_clusters
from app.services.clustering_service import ClusteringDependencyError
from app.services.code_retrieval_service import (
    CodeRetrievalError,
    retrieve_code_for_cluster,
    snippets_from_retrieved_rows,
)
from app.services.embedding_service import EmbeddingDependencyError
from app.services.issue_drafting_service import IssueDraftingError, draft_issue_for_cluster
from app.services.llm_client import LLMClient, LLMResponseError, LLMUnavailableError

router = APIRouter(prefix="/clusters", tags=["clusters"])


@router.get("", response_model=ClusterListResponse)
async def get_clusters(db: Session = Depends(get_db)) -> ClusterListResponse:
    clusters = list_clusters(db)
    return ClusterListResponse(
        items=[ClusterRead.model_validate(cluster) for cluster in clusters],
        total=count_clusters(db),
    )


@router.post("/rebuild", response_model=ClusterRunResponse)
async def rebuild_clusters(db: Session = Depends(get_db)) -> ClusterRunResponse:
    try:
        return rebuild_ticket_clusters(db)
    except (EmbeddingDependencyError, ClusteringDependencyError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{cluster_id}/retrieve-code", response_model=CodeRetrievalResponse)
async def retrieve_cluster_code(cluster_id: int, db: Session = Depends(get_db)) -> CodeRetrievalResponse:
    cluster = get_cluster(db, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Cluster not found.")

    try:
        return retrieve_code_for_cluster(db, cluster)
    except CodeRetrievalError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ChromaDependencyError, EmbeddingDependencyError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{cluster_id}/draft-issue", response_model=IssueDraftResponse)
async def draft_cluster_issue(cluster_id: int, db: Session = Depends(get_db)) -> IssueDraftResponse:
    cluster = get_cluster(db, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Cluster not found.")

    settings = get_settings()
    llm_client = LLMClient(settings.ollama_base_url, settings.ollama_model, timeout_seconds=180.0)
    try:
        return await draft_issue_for_cluster(db, cluster, llm_client)
    except IssueDraftingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{cluster_id}", response_model=ClusterDetailResponse)
async def get_cluster_detail(cluster_id: int, db: Session = Depends(get_db)) -> ClusterDetailResponse:
    cluster = get_cluster(db, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Cluster not found.")

    tickets = list_tickets_for_cluster(db, cluster_id)
    retrieved_rows = list_retrieved_evidence_for_cluster(db, cluster_id)
    issue_draft = get_latest_issue_draft_for_cluster(db, cluster_id)
    return ClusterDetailResponse(
        cluster=ClusterRead.model_validate(cluster),
        tickets=[TicketRead.model_validate(ticket) for ticket in tickets],
        priority_breakdown=_parse_priority_breakdown(cluster.priority_breakdown),
        retrieved_code_snippets=snippets_from_retrieved_rows(retrieved_rows),
        issue_draft=IssueDraftRead.model_validate(issue_draft) if issue_draft else None,
    )


def _parse_priority_breakdown(value: str | None) -> list[PriorityBreakdownItem]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    items: list[PriorityBreakdownItem] = []
    for item in parsed:
        if isinstance(item, dict):
            items.append(PriorityBreakdownItem.model_validate(item))
    return items
