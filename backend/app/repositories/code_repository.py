from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, distinct, func, select, text
from sqlalchemy.orm import Session

from app.models import CodeChunk, RetrievedEvidence


@dataclass(frozen=True)
class BM25SearchResult:
    code_chunk_id: int
    rank: int
    score: float


def ensure_code_search_index(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS code_chunks_fts USING fts5(
                code_chunk_id UNINDEXED,
                repo_path UNINDEXED,
                file_path,
                symbol_name,
                contextualized_text,
                tokenize = 'unicode61'
            )
            """
        )
    )


def clear_code_chunks_for_repo(db: Session, repo_path: str) -> None:
    ensure_code_search_index(db)
    db.execute(
        text("DELETE FROM code_chunks_fts WHERE repo_path = :repo_path"),
        {"repo_path": repo_path},
    )
    chunk_ids = select(CodeChunk.id).where(CodeChunk.repo_path == repo_path)
    db.execute(delete(RetrievedEvidence).where(RetrievedEvidence.code_chunk_id.in_(chunk_ids)))
    db.execute(delete(CodeChunk).where(CodeChunk.repo_path == repo_path))
    db.flush()


def add_code_chunk(
    db: Session,
    *,
    repo_path: str,
    file_path: str,
    language: str,
    chunk_text: str,
    contextualized_text: str,
    function_or_class_name: str | None,
    chunk_type: str,
    start_line: int,
    end_line: int,
    embedding_id: str,
) -> CodeChunk:
    chunk = CodeChunk(
        repo_path=repo_path,
        file_path=file_path,
        language=language,
        chunk_text=chunk_text,
        contextualized_text=contextualized_text,
        function_or_class_name=function_or_class_name,
        chunk_type=chunk_type,
        start_line=start_line,
        end_line=end_line,
        embedding_id=embedding_id,
        indexed_at=datetime.utcnow(),
    )
    db.add(chunk)
    return chunk


def replace_code_search_index(
    db: Session,
    repo_path: str,
    chunks: list[CodeChunk],
) -> None:
    ensure_code_search_index(db)
    db.execute(
        text("DELETE FROM code_chunks_fts WHERE repo_path = :repo_path"),
        {"repo_path": repo_path},
    )
    if not chunks:
        return

    db.execute(
        text(
            """
            INSERT INTO code_chunks_fts (
                code_chunk_id,
                repo_path,
                file_path,
                symbol_name,
                contextualized_text
            )
            VALUES (
                :code_chunk_id,
                :repo_path,
                :file_path,
                :symbol_name,
                :contextualized_text
            )
            """
        ),
        [
            {
                "code_chunk_id": chunk.id,
                "repo_path": repo_path,
                "file_path": chunk.file_path,
                "symbol_name": chunk.function_or_class_name or "",
                "contextualized_text": chunk.contextualized_text or chunk.chunk_text,
            }
            for chunk in chunks
        ],
    )


def search_code_chunks_bm25(
    db: Session,
    query: str,
    limit: int,
) -> list[BM25SearchResult]:
    if not query.strip() or limit <= 0:
        return []

    ensure_code_search_index(db)
    rows = db.execute(
        text(
            """
            SELECT
                CAST(code_chunk_id AS INTEGER) AS code_chunk_id,
                bm25(code_chunks_fts, 0.0, 0.0, 3.0, 4.0, 1.0) AS bm25_score
            FROM code_chunks_fts
            WHERE code_chunks_fts MATCH :query
            ORDER BY bm25_score ASC
            LIMIT :limit
            """
        ),
        {"query": query, "limit": limit},
    ).all()

    return [
        BM25SearchResult(
            code_chunk_id=int(row.code_chunk_id),
            rank=index,
            score=round(float(row.bm25_score), 4),
        )
        for index, row in enumerate(rows, start=1)
    ]


def codebase_status(db: Session) -> tuple[int, int, datetime | None]:
    indexed_files = db.scalar(select(func.count(distinct(CodeChunk.file_path)))) or 0
    indexed_chunks = db.scalar(select(func.count()).select_from(CodeChunk)) or 0
    last_indexed_at = db.scalar(select(func.max(CodeChunk.indexed_at)))
    return indexed_files, indexed_chunks, last_indexed_at


def list_code_chunks(db: Session) -> list[CodeChunk]:
    return list(db.scalars(select(CodeChunk).order_by(CodeChunk.file_path.asc(), CodeChunk.start_line.asc())).all())


def get_code_chunks_by_ids(db: Session, code_chunk_ids: list[int]) -> dict[int, CodeChunk]:
    if not code_chunk_ids:
        return {}
    chunks = db.scalars(select(CodeChunk).where(CodeChunk.id.in_(code_chunk_ids))).all()
    return {chunk.id: chunk for chunk in chunks}


def clear_retrieved_evidence_for_cluster(db: Session, cluster_id: int) -> None:
    db.execute(delete(RetrievedEvidence).where(RetrievedEvidence.cluster_id == cluster_id))
    db.flush()


def add_retrieved_evidence(
    db: Session,
    *,
    cluster_id: int,
    code_chunk_id: int,
    relevance_score: float,
    evidence_type: str,
    reason: str,
) -> RetrievedEvidence:
    evidence = RetrievedEvidence(
        cluster_id=cluster_id,
        code_chunk_id=code_chunk_id,
        relevance_score=relevance_score,
        evidence_type=evidence_type,
        reason=reason,
    )
    db.add(evidence)
    db.flush()
    return evidence


def list_retrieved_evidence_for_cluster(db: Session, cluster_id: int) -> list[tuple[RetrievedEvidence, CodeChunk]]:
    statement = (
        select(RetrievedEvidence, CodeChunk)
        .join(CodeChunk, CodeChunk.id == RetrievedEvidence.code_chunk_id)
        .where(RetrievedEvidence.cluster_id == cluster_id)
        .order_by(RetrievedEvidence.relevance_score.desc(), RetrievedEvidence.id.asc())
    )
    return list(db.execute(statement).all())
