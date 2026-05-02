from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_ticket_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_plan: Mapped[str | None] = mapped_column(String(120), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(80), nullable=True)

    extracted_intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_user_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_expected_behavior: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_actual_behavior: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_feature_area: Mapped[str | None] = mapped_column(String(200), nullable=True)
    extracted_error_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(80), nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cluster_id: Mapped[int | None] = mapped_column(ForeignKey("clusters.id"), nullable=True)

    cluster: Mapped["Cluster | None"] = relationship(back_populates="tickets")


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_count: Mapped[int] = mapped_column(Integer, default=0)
    priority_score: Mapped[float] = mapped_column(Float, default=0)
    priority_label: Mapped[str] = mapped_column(String(80), default="P3 Low")
    confidence_score: Mapped[float] = mapped_column(Float, default=0)
    cohesion_score: Mapped[float] = mapped_column(Float, default=0)
    llm_coherence_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    suspected_feature_area: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(80), default="needs_review")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tickets: Mapped[list[Ticket]] = relationship(back_populates="cluster")


class CodeChunk(Base):
    __tablename__ = "code_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    repo_path: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(80))
    chunk_text: Mapped[str] = mapped_column(Text)
    function_or_class_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    embedding_id: Mapped[str | None] = mapped_column(String(200), nullable=True)


class RetrievedEvidence(Base):
    __tablename__ = "retrieved_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"), index=True)
    code_chunk_id: Mapped[int] = mapped_column(ForeignKey("code_chunks.id"), index=True)
    relevance_score: Mapped[float] = mapped_column(Float)
    evidence_type: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text)


class IssueDraft(Base):
    __tablename__ = "issue_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    body_markdown: Mapped[str] = mapped_column(Text)
    priority_label: Mapped[str] = mapped_column(String(80))
    confidence_level: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(80), default="draft")
    github_issue_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
