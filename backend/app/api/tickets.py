from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.ticket_repository import (
    count_tickets,
    list_tickets,
    upsert_ticket,
)
from app.schemas.ticket_schema import (
    TicketListResponse,
    TicketProcessResponse,
    TicketRead,
    TicketUploadResponse,
)
from app.services.llm_client import LLMUnavailableError
from app.services.ticket_csv_service import parse_ticket_csv
from app.services.ticket_processing_service import process_ticket_batch
from app.services.tenant_service import TenantContext, require_editor_context, require_tenant_context
from app.config import get_settings
from app.services.rate_limit_service import enforce_expensive_rate_limit

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("/upload", response_model=TicketUploadResponse)
async def upload_tickets(file: UploadFile = File(...), db: Session = Depends(get_db), tenant: TenantContext = Depends(require_editor_context)) -> TicketUploadResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

    max_upload_bytes = get_settings().max_ticket_upload_size_bytes
    contents = await file.read(max_upload_bytes + 1)
    if len(contents) > max_upload_bytes:
        raise HTTPException(status_code=413, detail="Ticket CSV exceeds the configured upload limit.")
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty.")

    try:
        parse_result = parse_ticket_csv(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    inserted = 0
    updated = 0
    for ticket_data in parse_result.tickets:
        _, created = upsert_ticket(db, tenant.project_id, ticket_data)
        if created:
            inserted += 1
        else:
            updated += 1

    db.commit()
    total_tickets = count_tickets(db, tenant.project_id)

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
    tenant: TenantContext = Depends(require_tenant_context),
) -> TicketListResponse:
    tickets = list_tickets(db, tenant.project_id, limit=limit, offset=offset)
    return TicketListResponse(
        items=[TicketRead.model_validate(ticket) for ticket in tickets],
        total=count_tickets(db, tenant.project_id),
    )


@router.post("/process", response_model=TicketProcessResponse)
async def process_tickets(
    _: None = Depends(enforce_expensive_rate_limit),
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    force: bool = Query(default=False),
    tenant: TenantContext = Depends(require_editor_context),
) -> TicketProcessResponse:
    """Legacy synchronous endpoint. Prefer POST /workflows/ticket-processing."""
    try:
        return await process_ticket_batch(db, project_id=tenant.project_id, limit=limit, force=force)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
