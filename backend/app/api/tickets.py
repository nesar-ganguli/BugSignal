from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.repositories.ticket_repository import (
    apply_ticket_extraction,
    count_tickets,
    list_tickets,
    list_tickets_for_extraction,
    mark_ticket_extraction_failed,
    upsert_ticket,
)
from app.schemas.ticket_schema import (
    TicketListResponse,
    TicketProcessResponse,
    TicketRead,
    TicketUploadResponse,
)
from app.services.llm_client import LLMClient, LLMResponseError, LLMUnavailableError
from app.services.ticket_csv_service import parse_ticket_csv
from app.services.ticket_extraction_service import TicketExtractionError, extract_ticket_fields
from app.services.cluster_workflow_service import rebuild_ticket_clusters
from app.services.clustering_service import ClusteringDependencyError
from app.services.embedding_service import EmbeddingDependencyError

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("/upload", response_model=TicketUploadResponse)
async def upload_tickets(file: UploadFile = File(...), db: Session = Depends(get_db)) -> TicketUploadResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty.")

    try:
        parse_result = parse_ticket_csv(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    inserted = 0
    updated = 0
    for ticket_data in parse_result.tickets:
        _, created = upsert_ticket(db, ticket_data)
        if created:
            inserted += 1
        else:
            updated += 1

    db.commit()
    total_tickets = count_tickets(db)

    return TicketUploadResponse(
        filename=file.filename,
        bytes_received=len(contents),
        inserted=inserted,
        updated=updated,
        skipped=parse_result.skipped,
        total_tickets=total_tickets,
        status="accepted",
        message=f"Imported {inserted} new tickets and updated {updated} existing tickets.",
        errors=parse_result.errors,
    )


@router.get("", response_model=TicketListResponse)
async def get_tickets(
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> TicketListResponse:
    tickets = list_tickets(db, limit=limit, offset=offset)
    return TicketListResponse(
        items=[TicketRead.model_validate(ticket) for ticket in tickets],
        total=count_tickets(db),
    )


@router.post("/process", response_model=TicketProcessResponse)
async def process_tickets(
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    force: bool = Query(default=False),
) -> TicketProcessResponse:
    settings = get_settings()
    llm_client = LLMClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout_seconds=90,
    )

    tickets = list_tickets_for_extraction(db, limit=limit, force=force)
    processed = 0
    errors: list[str] = []

    for ticket in tickets:
        try:
            extraction = await extract_ticket_fields(ticket, llm_client)
        except LLMUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except (LLMResponseError, TicketExtractionError) as exc:
            error_message = str(exc)
            mark_ticket_extraction_failed(ticket, error_message)
            errors.append(error_message)
            continue

        apply_ticket_extraction(ticket, extraction)
        processed += 1

    db.commit()

    remaining_message = "Extraction complete for this batch."
    if not tickets:
        remaining_message = "No tickets need extraction."

    clusters_created = 0
    clustered_tickets = 0
    outlier_tickets = 0
    if processed or not tickets:
        try:
            cluster_result = rebuild_ticket_clusters(db)
        except (EmbeddingDependencyError, ClusteringDependencyError) as exc:
            errors.append(str(exc))
        else:
            clusters_created = cluster_result.clusters_created
            clustered_tickets = cluster_result.clustered_tickets
            outlier_tickets = cluster_result.outlier_tickets
            remaining_message = f"{remaining_message} {cluster_result.message}"

    return TicketProcessResponse(
        processed=processed,
        failed=len(errors),
        total_tickets=count_tickets(db),
        clusters_created=clusters_created,
        clustered_tickets=clustered_tickets,
        outlier_tickets=outlier_tickets,
        message=remaining_message,
        errors=errors,
    )
