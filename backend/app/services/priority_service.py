from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models import Ticket


@dataclass
class PriorityResult:
    score: float
    label: str
    breakdown: list[dict[str, int | str]]


def score_cluster_priority(tickets: list[Ticket]) -> PriorityResult:
    score = 0
    breakdown: list[dict[str, int | str]] = []

    if any(_has_data_loss_signal(ticket) for ticket in tickets):
        score += 30
        breakdown.append({"label": "Data loss signal", "points": 30})

    if any(ticket.contains_payment_or_revenue_issue for ticket in tickets):
        score += 25
        breakdown.append({"label": "Payment or revenue issue", "points": 25})

    if any(ticket.contains_auth_issue for ticket in tickets):
        score += 20
        breakdown.append({"label": "Auth or account access issue", "points": 20})

    if any(ticket.contains_performance_issue for ticket in tickets):
        score += 10
        breakdown.append({"label": "Performance issue", "points": 10})

    ticket_count = len(tickets)
    if ticket_count > 20:
        score += 20
        breakdown.append({"label": "More than 20 related tickets", "points": 20})
    elif 5 <= ticket_count <= 20:
        score += 10
        breakdown.append({"label": "5 to 20 related tickets", "points": 10})

    if any((ticket.sentiment or "").lower() in {"angry", "urgent"} for ticket in tickets):
        score += 10
        breakdown.append({"label": "Angry or urgent sentiment", "points": 10})

    if _has_high_velocity(tickets):
        score += 15
        breakdown.append({"label": "High ticket velocity", "points": 15})

    severity_points = _customer_severity_points(tickets)
    if severity_points:
        score += severity_points
        breakdown.append({"label": "Customer-provided severity", "points": severity_points})

    score = min(score, 100)
    return PriorityResult(
        score=float(score),
        label=_priority_label(score),
        breakdown=breakdown,
    )


def _priority_label(score: int) -> str:
    if score >= 75:
        return "P0 Critical"
    if score >= 50:
        return "P1 High"
    if score >= 25:
        return "P2 Medium"
    return "P3 Low"


def _customer_severity_points(tickets: list[Ticket]) -> int:
    severity_values = {(ticket.severity or "").lower() for ticket in tickets}
    if "critical" in severity_values:
        return 20
    if "high" in severity_values:
        return 10
    if "medium" in severity_values:
        return 5
    return 0


def _has_data_loss_signal(ticket: Ticket) -> bool:
    text = _ticket_text(ticket)
    if "data loss" in text:
        return True

    loss_terms = [
        "disappear",
        "disappeared",
        "vanish",
        "vanished",
        "lost",
        "not saved",
        "not persist",
        "does not persist",
        "missing after refresh",
    ]
    artifact_terms = [
        "file",
        "upload",
        "uploaded",
        "document",
        "attachment",
        "csv",
        "spreadsheet",
        "record",
        "workspace",
        "project",
    ]
    return any(term in text for term in loss_terms) and any(term in text for term in artifact_terms)


def _ticket_text(ticket: Ticket) -> str:
    return " ".join(
        value
        for value in [
            ticket.title,
            ticket.body,
            ticket.extracted_intent,
            ticket.extracted_user_action,
            ticket.extracted_expected_behavior,
            ticket.extracted_actual_behavior,
            ticket.extracted_feature_area,
            ticket.extracted_error_terms,
        ]
        if value
    ).lower()


def _has_high_velocity(tickets: list[Ticket]) -> bool:
    timestamps = sorted(ticket.created_at for ticket in tickets if ticket.created_at)
    if len(timestamps) < 5:
        return False

    window = timedelta(hours=24)
    for index, start_time in enumerate(timestamps):
        if not isinstance(start_time, datetime):
            continue
        count = sum(1 for timestamp in timestamps[index:] if timestamp - start_time <= window)
        if count >= 5:
            return True
    return False
