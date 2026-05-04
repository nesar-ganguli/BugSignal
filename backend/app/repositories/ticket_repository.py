import json
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Ticket
from app.schemas.ticket_schema import TicketCreate, TicketExtractionResult


def count_tickets(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Ticket)) or 0


def list_tickets(db: Session, limit: int = 100, offset: int = 0) -> list[Ticket]:
    statement = (
        select(Ticket)
        .order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement).all())


def list_clusterable_tickets(db: Session) -> list[Ticket]:
    statement = (
        select(Ticket)
        .where(Ticket.extraction_status == "completed")
        .order_by(Ticket.id.asc())
    )
    return list(db.scalars(statement).all())


def list_tickets_for_cluster(db: Session, cluster_id: int) -> list[Ticket]:
    statement = (
        select(Ticket)
        .where(Ticket.cluster_id == cluster_id)
        .order_by(Ticket.created_at.desc(), Ticket.id.desc())
    )
    return list(db.scalars(statement).all())


def list_tickets_for_extraction(db: Session, limit: int = 50, force: bool = False) -> list[Ticket]:
    statement = select(Ticket).order_by(Ticket.created_at.desc(), Ticket.id.desc()).limit(limit)
    if not force:
        statement = statement.where(Ticket.extraction_status != "completed")
    return list(db.scalars(statement).all())


def get_ticket_by_external_id(db: Session, external_ticket_id: str) -> Ticket | None:
    return db.scalar(select(Ticket).where(Ticket.external_ticket_id == external_ticket_id))


def upsert_ticket(db: Session, ticket_data: TicketCreate) -> tuple[Ticket, bool]:
    ticket = get_ticket_by_external_id(db, ticket_data.external_ticket_id)
    created = ticket is None

    if ticket is None:
        ticket = Ticket(
            external_ticket_id=ticket_data.external_ticket_id,
            title=ticket_data.title,
            body=ticket_data.body,
        )
        db.add(ticket)
    elif _ticket_input_changed(ticket, ticket_data):
        reset_ticket_extraction(ticket, status="stale")

    ticket.title = ticket_data.title
    ticket.body = ticket_data.body
    ticket.created_at = ticket_data.created_at
    ticket.source = ticket_data.source
    ticket.customer_plan = ticket_data.customer_plan
    ticket.severity = ticket_data.severity

    return ticket, created


def apply_ticket_extraction(ticket: Ticket, extraction: TicketExtractionResult) -> None:
    ticket.extracted_intent = extraction.intent
    ticket.extracted_user_action = extraction.user_action
    ticket.extracted_expected_behavior = extraction.expected_behavior
    ticket.extracted_actual_behavior = extraction.actual_behavior
    ticket.extracted_feature_area = extraction.feature_area
    ticket.extracted_error_terms = json.dumps(extraction.error_terms)
    ticket.sentiment = extraction.sentiment
    ticket.contains_payment_or_revenue_issue = extraction.contains_payment_or_revenue_issue
    ticket.contains_data_loss_issue = extraction.contains_data_loss_issue
    ticket.contains_auth_issue = extraction.contains_auth_issue
    ticket.contains_performance_issue = extraction.contains_performance_issue
    ticket.extraction_status = "completed"
    ticket.extracted_at = datetime.utcnow()
    ticket.extraction_error = None


def mark_ticket_extraction_failed(ticket: Ticket, error: str) -> None:
    ticket.extraction_status = "failed"
    ticket.extraction_error = error[:1000]


def reset_ticket_extraction(ticket: Ticket, status: str = "pending") -> None:
    ticket.extracted_intent = None
    ticket.extracted_user_action = None
    ticket.extracted_expected_behavior = None
    ticket.extracted_actual_behavior = None
    ticket.extracted_feature_area = None
    ticket.extracted_error_terms = None
    ticket.sentiment = None
    ticket.contains_payment_or_revenue_issue = False
    ticket.contains_data_loss_issue = False
    ticket.contains_auth_issue = False
    ticket.contains_performance_issue = False
    ticket.extraction_status = status
    ticket.extracted_at = None
    ticket.extraction_error = None
    ticket.embedding_id = None
    ticket.cluster_id = None


def set_ticket_cluster(ticket: Ticket, cluster_id: int | None, embedding_id: str | None = None) -> None:
    ticket.cluster_id = cluster_id
    if embedding_id is not None:
        ticket.embedding_id = embedding_id


def _ticket_input_changed(ticket: Ticket, ticket_data: TicketCreate) -> bool:
    return any(
        [
            ticket.title != ticket_data.title,
            ticket.body != ticket_data.body,
            ticket.created_at != ticket_data.created_at,
            ticket.source != ticket_data.source,
            ticket.customer_plan != ticket_data.customer_plan,
            ticket.severity != ticket_data.severity,
        ]
    )
