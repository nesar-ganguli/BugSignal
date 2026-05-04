from datetime import datetime

from sqlalchemy import delete, distinct, func, select
from sqlalchemy.orm import Session

from app.models import CodeChunk, RetrievedEvidence


def clear_code_chunks_for_repo(db: Session, repo_path: str) -> None:
    db.execute(delete(CodeChunk).where(CodeChunk.repo_path == repo_path))
    db.flush()


def add_code_chunk(
    db: Session,
    *,
    repo_path: str,
    file_path: str,
    language: str,
    chunk_text: str,
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
        function_or_class_name=function_or_class_name,
        chunk_type=chunk_type,
        start_line=start_line,
        end_line=end_line,
        embedding_id=embedding_id,
        indexed_at=datetime.utcnow(),
    )
    db.add(chunk)
    return chunk


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
