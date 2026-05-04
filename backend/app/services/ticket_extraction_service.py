from pydantic import ValidationError

from app.models import Ticket
from app.schemas.ticket_schema import TicketExtractionResult
from app.services.llm_client import LLMClient, LLMResponseError


class TicketExtractionError(RuntimeError):
    pass


async def extract_ticket_fields(ticket: Ticket, llm_client: LLMClient) -> TicketExtractionResult:
    prompt = _build_ticket_extraction_prompt(ticket)
    payload = await llm_client.generate_json(prompt)

    try:
        extraction = TicketExtractionResult.model_validate(payload)
    except ValidationError as exc:
        raise TicketExtractionError(
            f"Ticket {ticket.external_ticket_id}: LLM returned JSON with invalid fields."
        ) from exc
    except LLMResponseError:
        raise

    return _apply_deterministic_flags(ticket, extraction)


def _build_ticket_extraction_prompt(ticket: Ticket) -> str:
    return f"""
You extract structured facts from support tickets for an engineering triage system.

Return only valid JSON with exactly this shape:
{{
  "intent": "...",
  "user_action": "...",
  "expected_behavior": "...",
  "actual_behavior": "...",
  "feature_area": "...",
  "error_terms": ["..."],
  "sentiment": "neutral | frustrated | angry | urgent",
  "contains_payment_or_revenue_issue": true,
  "contains_data_loss_issue": false,
  "contains_auth_issue": false,
  "contains_performance_issue": false
}}

Rules:
- Use null for unknown string fields.
- Use an empty list for unknown error_terms.
- Do not guess details not present in the ticket.
- Do not invent stack traces, product versions, platforms, endpoints, file names, or exact errors.
- Treat duplicate charges, failed billing, invoices, checkout payment failures, and revenue-impacting checkout issues as payment or revenue issues.
- Treat missing uploads, vanished files, missing saved documents, and lost records as data loss issues.
- Treat login, session expiry, authentication, authorization, password reset, and account access issues as auth issues.
- Treat slow, timeout, hanging, and long-loading behavior as performance issues.

Ticket ID: {ticket.external_ticket_id}
Title: {ticket.title}
Body: {ticket.body}
Customer plan: {ticket.customer_plan or "unknown"}
Severity: {ticket.severity or "unknown"}
Source: {ticket.source or "unknown"}
""".strip()


def _apply_deterministic_flags(ticket: Ticket, extraction: TicketExtractionResult) -> TicketExtractionResult:
    text = " ".join(
        value
        for value in [
            ticket.title,
            ticket.body,
            ticket.severity or "",
            extraction.intent or "",
            extraction.user_action or "",
            extraction.actual_behavior or "",
            extraction.feature_area or "",
        ]
        if value
    ).lower()

    payment_terms = [
        "payment",
        "checkout",
        "charge",
        "charged",
        "billing",
        "invoice",
        "card",
        "pay button",
        "duplicate charge",
        "revenue",
    ]
    data_loss_terms = [
        "data loss",
        "disappear",
        "disappeared",
        "vanish",
        "vanished",
        "lost",
        "not saved",
        "not persist",
    ]
    auth_terms = [
        "auth",
        "login",
        "log in",
        "session",
        "password reset",
        "reset link",
        "account access",
        "sign in",
    ]
    performance_terms = [
        "slow",
        "timeout",
        "timing out",
        "hang",
        "hanging",
        "stuck",
        "spinning",
        "loads forever",
        "loading forever",
    ]

    extraction.contains_payment_or_revenue_issue = (
        extraction.contains_payment_or_revenue_issue or _contains_any(text, payment_terms)
    )
    extraction.contains_data_loss_issue = extraction.contains_data_loss_issue or _contains_any(
        text, data_loss_terms
    )
    extraction.contains_auth_issue = extraction.contains_auth_issue or _contains_any(text, auth_terms)
    extraction.contains_performance_issue = (
        extraction.contains_performance_issue or _contains_any(text, performance_terms)
    )
    return extraction


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)
