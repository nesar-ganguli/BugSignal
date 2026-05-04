from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models import Cluster, CodeChunk, RetrievedEvidence, Ticket
from app.repositories.code_repository import list_retrieved_evidence_for_cluster
from app.repositories.issue_repository import create_issue_draft
from app.repositories.ticket_repository import list_tickets_for_cluster
from app.schemas.issue_schema import IssueDraftLLMResult, IssueDraftResponse, IssueDraftRead
from app.services.evidence_guard_service import validate_issue_draft_evidence
from app.services.llm_client import LLMClient, LLMResponseError


class IssueDraftingError(RuntimeError):
    pass


async def draft_issue_for_cluster(db: Session, cluster: Cluster, llm_client: LLMClient) -> IssueDraftResponse:
    tickets = list_tickets_for_cluster(db, cluster.id)
    retrieved_rows = list_retrieved_evidence_for_cluster(db, cluster.id)
    if not retrieved_rows:
        raise IssueDraftingError("Retrieve code evidence for this cluster before drafting an issue.")

    prompt_rows = retrieved_rows[:5]
    prompt = _build_issue_prompt(cluster, tickets, prompt_rows)
    raw = await llm_client.generate_json(prompt)
    structured = _parse_llm_result(raw)
    warnings = validate_issue_draft_evidence(structured, tickets, prompt_rows)
    body_markdown = _render_issue_markdown(structured, tickets, warnings)

    issue = create_issue_draft(
        db,
        cluster_id=cluster.id,
        title=structured.title,
        body_markdown=body_markdown,
        priority_label=structured.priority_label,
        confidence_level=structured.confidence,
        warnings=warnings,
        status="draft",
    )
    cluster.status = "ready_for_issue"
    db.commit()
    db.refresh(issue)

    return IssueDraftResponse(
        draft=IssueDraftRead.model_validate(issue),
        structured=structured,
        message=_draft_message(warnings),
    )


def _build_issue_prompt(
    cluster: Cluster,
    tickets: list[Ticket],
    retrieved_rows: list[tuple[RetrievedEvidence, CodeChunk]],
) -> str:
    ticket_payload = [_ticket_payload(ticket) for ticket in tickets[:8]]
    code_payload = [_code_payload(evidence, chunk) for evidence, chunk in retrieved_rows[:5]]

    return f"""
You are BugSignal AI, an engineering triage assistant. Draft a GitHub issue using only the provided support tickets and retrieved code evidence.

Non-negotiable rules:
- Do not claim a definite root cause.
- Always use the phrase "suspected root cause".
- If the retrieved code does not support a suspected root cause, set suspected_root_cause to "Insufficient evidence to identify a suspected root cause."
- Every evidence item must cite an existing ticket source_id or code source_id from the provided payload.
- For ticket evidence, source_type must be "ticket" and source_id must be the exact external_ticket_id.
- For code evidence, source_type must be "code" and source_id must be the exact retrieved evidence id as a string.
- relevant_files may only include file_path values from the retrieved code evidence.
- Do not invent stack traces, file names, functions, endpoints, platforms, versions, or logs.
- Needs engineer verification is always Yes.
- Return only valid JSON.

Required JSON shape:
{{
  "title": "...",
  "summary": "...",
  "user_impact": "...",
  "steps_to_reproduce": ["..."],
  "expected_behavior": "...",
  "actual_behavior": "...",
  "suspected_root_cause": "...",
  "evidence": [
    {{
      "claim": "...",
      "source_type": "ticket",
      "source_id": "BUG-001"
    }},
    {{
      "claim": "...",
      "source_type": "code",
      "source_id": "12"
    }}
  ],
  "relevant_files": ["..."],
  "confidence": "Low",
  "open_questions": ["..."],
  "priority_label": "{cluster.priority_label}"
}}

Cluster:
{json.dumps(_cluster_payload(cluster), indent=2)}

Tickets:
{json.dumps(ticket_payload, indent=2)}

Retrieved code evidence:
{json.dumps(code_payload, indent=2)}
""".strip()


def _cluster_payload(cluster: Cluster) -> dict[str, Any]:
    return {
        "cluster_id": cluster.id,
        "title": cluster.title,
        "summary": cluster.summary,
        "ticket_count": cluster.ticket_count,
        "priority_score": cluster.priority_score,
        "priority_label": cluster.priority_label,
        "confidence_score": cluster.confidence_score,
        "cohesion_score": cluster.cohesion_score,
        "suspected_feature_area": cluster.suspected_feature_area,
    }


def _ticket_payload(ticket: Ticket) -> dict[str, Any]:
    return {
        "source_id": ticket.external_ticket_id,
        "title": ticket.title,
        "body": _truncate(ticket.body, 500),
        "severity": ticket.severity,
        "customer_plan": ticket.customer_plan,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "intent": ticket.extracted_intent,
        "user_action": ticket.extracted_user_action,
        "expected_behavior": ticket.extracted_expected_behavior,
        "actual_behavior": ticket.extracted_actual_behavior,
        "feature_area": ticket.extracted_feature_area,
        "error_terms": _safe_json_list(ticket.extracted_error_terms),
        "sentiment": ticket.sentiment,
    }


def _code_payload(evidence: RetrievedEvidence, chunk: CodeChunk) -> dict[str, Any]:
    return {
        "source_id": str(evidence.id),
        "code_chunk_id": chunk.id,
        "file_path": chunk.file_path,
        "language": chunk.language,
        "function_or_class_name": chunk.function_or_class_name,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "reason": evidence.reason,
        "relevance_score": round(evidence.relevance_score, 4),
        "snippet": _truncate(chunk.chunk_text, 850),
    }


def _parse_llm_result(raw: dict[str, Any]) -> IssueDraftLLMResult:
    try:
        return IssueDraftLLMResult.model_validate(raw)
    except ValidationError as exc:
        raise LLMResponseError(f"Ollama issue draft JSON did not match the required schema: {exc}") from exc


def _render_issue_markdown(result: IssueDraftLLMResult, tickets: list[Ticket], warnings: list[str]) -> str:
    affected_ticket_ids = ", ".join(ticket.external_ticket_id for ticket in tickets)
    steps = "\n".join(f"{index}. {step}" for index, step in enumerate(result.steps_to_reproduce, start=1))
    evidence_lines = "\n".join(
        f"- {item.claim} [{item.source_type}:{item.source_id}]" for item in result.evidence
    )
    files = "\n".join(f"- `{file_path}`" for file_path in result.relevant_files)
    questions = "\n".join(f"- {question}" for question in result.open_questions)
    warning_lines = "\n".join(f"- {warning}" for warning in warnings)

    return f"""## Summary
{result.summary}

## User impact
{result.user_impact}

## Affected tickets
{affected_ticket_ids or "None provided"}

## Steps to reproduce
{steps or "Insufficient ticket detail to provide reliable reproduction steps."}

## Expected behavior
{result.expected_behavior}

## Actual behavior
{result.actual_behavior}

## Suspected root cause
{result.suspected_root_cause}

## Evidence
{evidence_lines or "No evidence claims were provided by the model."}

## Evidence guard warnings
{warning_lines or "No evidence guard warnings."}

## Relevant files
{files or "No retrieved files were strong enough to cite."}

## Confidence level
{result.confidence}

## Open questions for engineer
{questions or "- Verify whether the retrieved files are the correct implementation path for this ticket cluster."}

## Priority
{result.priority_label}

## Needs engineer verification
Yes
"""


def _draft_message(warnings: list[str]) -> str:
    if warnings:
        return (
            f"Issue draft created with {len(warnings)} evidence guard warning"
            f"{'' if len(warnings) == 1 else 's'}. Human approval is still required."
        )
    return "Issue draft created from retrieved code evidence. Human approval is still required."


def _safe_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if item is not None]


def _truncate(value: str | None, max_chars: int) -> str | None:
    if value is None or len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."
