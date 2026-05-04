from __future__ import annotations

import re
from typing import Iterable

from app.models import CodeChunk, RetrievedEvidence, Ticket
from app.schemas.issue_schema import IssueDraftLLMResult


FILE_PATH_PATTERN = re.compile(
    r"(?<![\w/.-])[\w./-]+\.(?:py|ts|tsx|js|jsx|java|go|sql|ya?ml|json)(?![\w/.-])"
)
VERSION_PATTERN = re.compile(r"\b(?:v|version\s*)?\d+\.\d+(?:\.\d+)?\b", re.IGNORECASE)
QUOTED_TERM_PATTERN = re.compile(r"`([^`]{3,120})`|\"([^\"]{3,120})\"|'([^']{3,120})'")

PLATFORM_TERMS = {
    "android",
    "chrome",
    "desktop",
    "edge",
    "firefox",
    "ios",
    "iphone",
    "linux",
    "macos",
    "mobile",
    "safari",
    "tablet",
    "windows",
}

ERROR_LIKE_TERMS = {
    "error",
    "exception",
    "failed",
    "failure",
    "stack",
    "trace",
    "timeout",
    "unauthorized",
    "forbidden",
}


def validate_issue_draft_evidence(
    result: IssueDraftLLMResult,
    tickets: list[Ticket],
    retrieved_rows: list[tuple[RetrievedEvidence, CodeChunk]],
) -> list[str]:
    warnings: list[str] = []
    allowed_ticket_ids = {ticket.external_ticket_id for ticket in tickets}
    allowed_code_ids = {str(evidence.id) for evidence, _ in retrieved_rows}
    allowed_files = {chunk.file_path for _, chunk in retrieved_rows}
    ticket_and_code_corpus = _build_corpus(tickets, retrieved_rows)
    draft_text = _draft_text(result)

    warnings.extend(_citation_warnings(result, allowed_ticket_ids, allowed_code_ids))
    warnings.extend(_file_warnings(result, draft_text, allowed_files))
    warnings.extend(_unsupported_platform_warnings(draft_text, ticket_and_code_corpus))
    warnings.extend(_unsupported_version_warnings(draft_text, ticket_and_code_corpus))
    warnings.extend(_unsupported_error_or_technical_term_warnings(draft_text, ticket_and_code_corpus))
    warnings.extend(_root_cause_language_warnings(result))

    return _dedupe(warnings)


def _citation_warnings(
    result: IssueDraftLLMResult,
    allowed_ticket_ids: set[str],
    allowed_code_ids: set[str],
) -> list[str]:
    warnings: list[str] = []
    if not result.evidence:
        warnings.append("The draft has no evidence citations.")
        return warnings

    for item in result.evidence:
        if item.source_type == "ticket" and item.source_id not in allowed_ticket_ids:
            warnings.append(f"Evidence cites unknown ticket source_id `{item.source_id}`.")
        if item.source_type == "code" and item.source_id not in allowed_code_ids:
            warnings.append(f"Evidence cites unknown code evidence source_id `{item.source_id}`.")
    return warnings


def _file_warnings(result: IssueDraftLLMResult, draft_text: str, allowed_files: set[str]) -> list[str]:
    warnings: list[str] = []
    for file_path in result.relevant_files:
        if file_path not in allowed_files:
            warnings.append(f"Relevant file `{file_path}` was not part of the retrieved code evidence.")

    mentioned_paths = set(FILE_PATH_PATTERN.findall(draft_text))
    for file_path in mentioned_paths:
        if file_path not in allowed_files:
            warnings.append(f"Draft mentions file `{file_path}` that was not retrieved as evidence.")
    return warnings


def _unsupported_platform_warnings(draft_text: str, corpus: str) -> list[str]:
    warnings: list[str] = []
    draft_lower = draft_text.lower()
    for platform in sorted(PLATFORM_TERMS):
        if _contains_word(draft_lower, platform) and not _contains_word(corpus, platform):
            warnings.append(f"Draft mentions platform `{platform}` but that platform was not found in tickets or snippets.")
    return warnings


def _unsupported_version_warnings(draft_text: str, corpus: str) -> list[str]:
    warnings: list[str] = []
    for version in sorted(set(VERSION_PATTERN.findall(draft_text))):
        if version.lower() not in corpus:
            warnings.append(f"Draft mentions version `{version}` but that version was not found in tickets or snippets.")
    return warnings


def _unsupported_error_or_technical_term_warnings(draft_text: str, corpus: str) -> list[str]:
    warnings: list[str] = []
    for term in _quoted_terms(draft_text):
        normalized = term.lower().strip()
        if not _looks_like_technical_claim(normalized):
            continue
        if normalized not in corpus:
            warnings.append(f"Draft mentions technical detail `{term}` that was not found in tickets or snippets.")
    return warnings


def _root_cause_language_warnings(result: IssueDraftLLMResult) -> list[str]:
    warnings: list[str] = []
    root_cause = result.suspected_root_cause.strip()
    root_cause_lower = root_cause.lower()
    insufficient = root_cause_lower.startswith("insufficient evidence")
    code_citations = [item for item in result.evidence if item.source_type == "code"]

    if not insufficient and "suspected" not in root_cause_lower:
        warnings.append("Suspected root cause text does not use explicitly tentative language.")
    if not insufficient and not result.evidence:
        warnings.append("Suspected root cause is present without any cited evidence.")
    if not insufficient and not code_citations:
        warnings.append("Suspected root cause has no code evidence citation.")
    if result.confidence == "High" and root_cause_lower.startswith("insufficient evidence"):
        warnings.append("Draft marks confidence High while also saying evidence is insufficient.")
    return warnings


def _build_corpus(
    tickets: list[Ticket],
    retrieved_rows: list[tuple[RetrievedEvidence, CodeChunk]],
) -> str:
    values: list[str] = []
    for ticket in tickets:
        values.extend(
            _compact_values(
                [
                    ticket.external_ticket_id,
                    ticket.title,
                    ticket.body,
                    ticket.severity,
                    ticket.customer_plan,
                    ticket.extracted_intent,
                    ticket.extracted_user_action,
                    ticket.extracted_expected_behavior,
                    ticket.extracted_actual_behavior,
                    ticket.extracted_feature_area,
                    ticket.extracted_error_terms,
                    ticket.sentiment,
                ]
            )
        )
    for evidence, chunk in retrieved_rows:
        values.extend(
            _compact_values(
                [
                    str(evidence.id),
                    evidence.reason,
                    chunk.file_path,
                    chunk.language,
                    chunk.function_or_class_name,
                    chunk.chunk_text,
                ]
            )
        )
    return "\n".join(values).lower()


def _draft_text(result: IssueDraftLLMResult) -> str:
    evidence_text = "\n".join(f"{item.claim} {item.source_type}:{item.source_id}" for item in result.evidence)
    return "\n".join(
        _compact_values(
            [
                result.title,
                result.summary,
                result.user_impact,
                "\n".join(result.steps_to_reproduce),
                result.expected_behavior,
                result.actual_behavior,
                result.suspected_root_cause,
                evidence_text,
                "\n".join(result.relevant_files),
                "\n".join(result.open_questions),
                result.priority_label,
            ]
        )
    )


def _compact_values(values: Iterable[str | None]) -> list[str]:
    return [value for value in values if value]


def _quoted_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for match in QUOTED_TERM_PATTERN.findall(text):
        term = next((value for value in match if value), "")
        if term:
            terms.add(term.strip())
    return terms


def _looks_like_technical_claim(value: str) -> bool:
    if FILE_PATH_PATTERN.search(value) or VERSION_PATTERN.search(value):
        return True
    if any(term in value for term in ERROR_LIKE_TERMS):
        return True
    if "/" in value or "." in value or "::" in value:
        return True
    if re.search(r"\w+\(\)", value):
        return True
    return False


def _contains_word(text: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def _dedupe(warnings: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for warning in warnings:
        if warning in seen:
            continue
        deduped.append(warning)
        seen.add(warning)
    return deduped
