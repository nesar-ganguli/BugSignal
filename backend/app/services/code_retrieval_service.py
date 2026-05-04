from dataclasses import dataclass, field
import json
import math
import re

from sqlalchemy.orm import Session

from app.models import Cluster, CodeChunk, Ticket
from app.repositories.code_repository import (
    add_retrieved_evidence,
    clear_retrieved_evidence_for_cluster,
    get_code_chunks_by_ids,
    list_code_chunks,
)
from app.repositories.ticket_repository import list_tickets_for_cluster
from app.schemas.code_schema import CodeRetrievalResponse, CodeSnippetRead
from app.services.chroma_service import ChromaDependencyError, get_code_collection
from app.services.embedding_service import EmbeddingDependencyError, EmbeddingService


TOP_K_SEMANTIC = 24
TOP_K_KEYWORD = 24
TOP_K_FINAL = 8


class CodeRetrievalError(RuntimeError):
    pass


@dataclass
class RetrievalCandidate:
    code_chunk_id: int
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    exact_matches: list[str] = field(default_factory=list)
    keyword_matches: list[str] = field(default_factory=list)

    @property
    def final_score(self) -> float:
        exact_boost = min(len(self.exact_matches) * 0.08, 0.24)
        return round(min((self.semantic_score * 0.62) + (self.keyword_score * 0.38) + exact_boost, 1.0), 4)

    @property
    def evidence_type(self) -> str:
        if self.semantic_score and self.keyword_score:
            return "hybrid"
        if self.keyword_score:
            return "keyword"
        return "semantic"


def retrieve_code_for_cluster(db: Session, cluster: Cluster) -> CodeRetrievalResponse:
    tickets = list_tickets_for_cluster(db, cluster.id)
    query, terms, exact_terms = build_cluster_code_query(cluster, tickets)

    if not query.strip():
        raise CodeRetrievalError("Cluster does not have enough ticket context for code retrieval.")

    all_chunks = list_code_chunks(db)
    if not all_chunks:
        raise CodeRetrievalError("No indexed code chunks found. Index a codebase before retrieving code.")

    candidates: dict[int, RetrievalCandidate] = {}
    _merge_semantic_candidates(candidates, query, db)
    _merge_keyword_candidates(candidates, all_chunks, terms, exact_terms)

    if not candidates:
        clear_retrieved_evidence_for_cluster(db, cluster.id)
        db.commit()
        return CodeRetrievalResponse(
            cluster_id=cluster.id,
            query=query,
            snippets=[],
            message="No relevant code snippets found.",
        )

    top_candidates = sorted(candidates.values(), key=lambda candidate: candidate.final_score, reverse=True)[:TOP_K_FINAL]
    chunks_by_id = get_code_chunks_by_ids(db, [candidate.code_chunk_id for candidate in top_candidates])

    clear_retrieved_evidence_for_cluster(db, cluster.id)
    snippets: list[CodeSnippetRead] = []
    for candidate in top_candidates:
        chunk = chunks_by_id.get(candidate.code_chunk_id)
        if chunk is None:
            continue
        reason = _candidate_reason(candidate)
        evidence = add_retrieved_evidence(
            db,
            cluster_id=cluster.id,
            code_chunk_id=chunk.id,
            relevance_score=candidate.final_score,
            evidence_type=candidate.evidence_type,
            reason=reason,
        )
        snippets.append(_snippet_from_chunk(chunk, candidate.final_score, reason, evidence.id, candidate.evidence_type))

    db.commit()
    return CodeRetrievalResponse(
        cluster_id=cluster.id,
        query=query,
        snippets=snippets,
        message=f"Retrieved {len(snippets)} code snippets for cluster {cluster.id}.",
    )


def build_cluster_code_query(cluster: Cluster, tickets: list[Ticket]) -> tuple[str, list[str], list[str]]:
    parts = [
        cluster.title,
        cluster.summary,
        cluster.suspected_feature_area,
        cluster.priority_label,
    ]
    terms: list[str] = []
    exact_terms: list[str] = []

    for ticket in tickets:
        parts.extend(
            [
                ticket.title,
                ticket.body,
                ticket.extracted_intent,
                ticket.extracted_user_action,
                ticket.extracted_expected_behavior,
                ticket.extracted_actual_behavior,
                ticket.extracted_feature_area,
            ]
        )
        error_terms = _parse_error_terms(ticket.extracted_error_terms)
        parts.extend(error_terms)
        exact_terms.extend(error_terms)
        exact_terms.extend(_extract_exact_terms(ticket.title))
        exact_terms.extend(_extract_exact_terms(ticket.body))

    query = "\n".join(part for part in parts if part)
    terms = _dedupe_preserve_order(_tokenize(query))
    exact_terms = _dedupe_preserve_order(term for term in exact_terms if len(term) >= 4)
    return query, terms, exact_terms


def snippets_from_retrieved_rows(rows: list[tuple]) -> list[CodeSnippetRead]:
    snippets: list[CodeSnippetRead] = []
    for evidence, chunk in rows:
        snippets.append(
            _snippet_from_chunk(
                chunk,
                evidence.relevance_score,
                evidence.reason,
                evidence.id,
                evidence.evidence_type,
            )
        )
    return snippets


def _merge_semantic_candidates(candidates: dict[int, RetrievalCandidate], query: str, db: Session) -> None:
    collection = get_code_collection()
    query_embedding = EmbeddingService().embed_texts([query])[0].tolist()
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=TOP_K_SEMANTIC,
        include=["distances", "metadatas"],
    )

    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    for metadata, distance in zip(metadatas, distances):
        if not metadata:
            continue
        code_chunk_id = int(metadata.get("code_chunk_id"))
        candidate = candidates.setdefault(code_chunk_id, RetrievalCandidate(code_chunk_id=code_chunk_id))
        candidate.semantic_score = max(candidate.semantic_score, _distance_to_score(float(distance)))


def _merge_keyword_candidates(
    candidates: dict[int, RetrievalCandidate],
    chunks: list[CodeChunk],
    terms: list[str],
    exact_terms: list[str],
) -> None:
    scored_chunks: list[tuple[float, CodeChunk, list[str], list[str]]] = []
    searchable_terms = [term for term in terms if len(term) >= 3][:80]
    searchable_exact_terms = exact_terms[:40]

    for chunk in chunks:
        haystack = _chunk_search_text(chunk)
        keyword_matches = [term for term in searchable_terms if term in haystack]
        exact_matches = [term for term in searchable_exact_terms if term.lower() in haystack]
        if not keyword_matches and not exact_matches:
            continue

        keyword_score = _keyword_score(keyword_matches, exact_matches, chunk)
        scored_chunks.append((keyword_score, chunk, keyword_matches[:8], exact_matches[:6]))

    for keyword_score, chunk, keyword_matches, exact_matches in sorted(scored_chunks, key=lambda item: item[0], reverse=True)[:TOP_K_KEYWORD]:
        candidate = candidates.setdefault(chunk.id, RetrievalCandidate(code_chunk_id=chunk.id))
        candidate.keyword_score = max(candidate.keyword_score, keyword_score)
        candidate.keyword_matches = _dedupe_preserve_order([*candidate.keyword_matches, *keyword_matches])[:8]
        candidate.exact_matches = _dedupe_preserve_order([*candidate.exact_matches, *exact_matches])[:6]


def _distance_to_score(distance: float) -> float:
    if math.isnan(distance):
        return 0.0
    return round(1 / (1 + max(distance, 0.0)), 4)


def _keyword_score(keyword_matches: list[str], exact_matches: list[str], chunk: CodeChunk) -> float:
    score = min(len(keyword_matches) / 18, 0.55) + min(len(exact_matches) / 8, 0.35)
    path_text = f"{chunk.file_path} {chunk.function_or_class_name or ''}".lower()
    path_hits = sum(1 for term in keyword_matches if term in path_text)
    score += min(path_hits * 0.04, 0.1)
    return round(min(score, 1.0), 4)


def _candidate_reason(candidate: RetrievalCandidate) -> str:
    reasons: list[str] = []
    if candidate.semantic_score:
        reasons.append(f"Semantic score {candidate.semantic_score:.2f}")
    if candidate.exact_matches:
        reasons.append("Exact matches: " + ", ".join(candidate.exact_matches[:6]))
    if candidate.keyword_matches:
        reasons.append("Keyword matches: " + ", ".join(candidate.keyword_matches[:8]))
    return "; ".join(reasons) if reasons else "Retrieved by hybrid search."


def _snippet_from_chunk(
    chunk: CodeChunk,
    relevance_score: float,
    reason: str,
    evidence_id: int | None,
    evidence_type: str | None,
) -> CodeSnippetRead:
    return CodeSnippetRead(
        evidence_id=evidence_id,
        code_chunk_id=chunk.id,
        file_path=chunk.file_path,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        snippet=chunk.chunk_text,
        relevance_score=round(relevance_score, 4),
        evidence_type=evidence_type,
        reason=reason,
    )


def _chunk_search_text(chunk: CodeChunk) -> str:
    return " ".join(
        [
            chunk.file_path,
            chunk.language,
            chunk.function_or_class_name or "",
            chunk.chunk_text,
        ]
    ).lower()


def _tokenize(value: str) -> list[str]:
    stopwords = {
        "and",
        "after",
        "asking",
        "before",
        "between",
        "but",
        "can",
        "cannot",
        "could",
        "does",
        "doesn",
        "don",
        "during",
        "each",
        "for",
        "with",
        "without",
        "from",
        "has",
        "have",
        "into",
        "just",
        "later",
        "needs",
        "not",
        "old",
        "our",
        "out",
        "over",
        "should",
        "than",
        "that",
        "the",
        "this",
        "there",
        "their",
        "through",
        "when",
        "where",
        "while",
        "will",
        "would",
        "ticket",
        "tickets",
        "issue",
        "expected",
        "actual",
        "behavior",
        "customer",
        "cluster",
        "related",
        "report",
        "reports",
    }
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_\-/]{2,}", value.lower())
    return [word for word in words if len(word) >= 4 and word not in stopwords]


def _parse_error_terms(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [value]
    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item).strip()]
    return []


def _extract_exact_terms(value: str) -> list[str]:
    quoted = re.findall(r"['\"]([^'\"]{4,120})['\"]", value)
    routes = re.findall(r"/[a-zA-Z0-9_/\-{}:?.=]+", value)
    camel_or_snake = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*(?:Error|Exception|Controller|Service|Repository|Route|Handler|Client|API)\b", value)
    return [*quoted, *routes, *camel_or_snake]


def _dedupe_preserve_order(values) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = str(value).strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped
