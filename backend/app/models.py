from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    contains_payment_or_revenue_issue: Mapped[bool] = mapped_column(Boolean, default=False)
    contains_data_loss_issue: Mapped[bool] = mapped_column(Boolean, default=False)
    contains_auth_issue: Mapped[bool] = mapped_column(Boolean, default=False)
    contains_performance_issue: Mapped[bool] = mapped_column(Boolean, default=False)
    extraction_status: Mapped[str] = mapped_column(String(40), default="pending")
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    priority_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    contextualized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    function_or_class_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    chunk_type: Mapped[str] = mapped_column(String(80), default="code")
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    embedding_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_issue_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_type: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    current_step: Mapped[str] = mapped_column(String(120), default="queued")
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    input_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    queue_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("issuer", "subject", name="uq_users_issuer_subject"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    issuer: Mapped[str] = mapped_column(String(500))
    subject: Mapped[str] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_membership"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(80), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
