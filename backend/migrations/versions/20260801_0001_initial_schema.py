"""Create the initial BugSignal schema.

Revision ID: 20260801_0001
Revises:
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa


revision = "20260801_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clusters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("ticket_count", sa.Integer(), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("priority_label", sa.String(80), nullable=False),
        sa.Column("priority_breakdown", sa.Text()),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("cohesion_score", sa.Float(), nullable=False),
        sa.Column("llm_coherence_label", sa.String(120)),
        sa.Column("suspected_feature_area", sa.String(200)),
        sa.Column("status", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_clusters_id", "clusters", ["id"])

    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_ticket_id", sa.String(120), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("source", sa.String(120)),
        sa.Column("customer_plan", sa.String(120)),
        sa.Column("severity", sa.String(80)),
        sa.Column("extracted_intent", sa.Text()),
        sa.Column("extracted_user_action", sa.Text()),
        sa.Column("extracted_expected_behavior", sa.Text()),
        sa.Column("extracted_actual_behavior", sa.Text()),
        sa.Column("extracted_feature_area", sa.String(200)),
        sa.Column("extracted_error_terms", sa.Text()),
        sa.Column("sentiment", sa.String(80)),
        sa.Column("contains_payment_or_revenue_issue", sa.Boolean(), nullable=False),
        sa.Column("contains_data_loss_issue", sa.Boolean(), nullable=False),
        sa.Column("contains_auth_issue", sa.Boolean(), nullable=False),
        sa.Column("contains_performance_issue", sa.Boolean(), nullable=False),
        sa.Column("extraction_status", sa.String(40), nullable=False),
        sa.Column("extracted_at", sa.DateTime()),
        sa.Column("extraction_error", sa.Text()),
        sa.Column("embedding_id", sa.String(200)),
        sa.Column("cluster_id", sa.Integer(), sa.ForeignKey("clusters.id")),
    )
    op.create_index("ix_tickets_id", "tickets", ["id"])
    op.create_index("ix_tickets_external_ticket_id", "tickets", ["external_ticket_id"], unique=True)

    op.create_table(
        "code_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repo_path", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("language", sa.String(80), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("contextualized_text", sa.Text()),
        sa.Column("function_or_class_name", sa.String(300)),
        sa.Column("chunk_type", sa.String(80), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("embedding_id", sa.String(200)),
        sa.Column("indexed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_code_chunks_id", "code_chunks", ["id"])

    op.create_table(
        "retrieved_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cluster_id", sa.Integer(), sa.ForeignKey("clusters.id"), nullable=False),
        sa.Column("code_chunk_id", sa.Integer(), sa.ForeignKey("code_chunks.id"), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("evidence_type", sa.String(120), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
    )
    op.create_index("ix_retrieved_evidence_cluster_id", "retrieved_evidence", ["cluster_id"])
    op.create_index("ix_retrieved_evidence_code_chunk_id", "retrieved_evidence", ["code_chunk_id"])
    op.create_index("ix_retrieved_evidence_id", "retrieved_evidence", ["id"])

    op.create_table(
        "issue_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cluster_id", sa.Integer(), sa.ForeignKey("clusters.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("priority_label", sa.String(80), nullable=False),
        sa.Column("confidence_level", sa.String(80), nullable=False),
        sa.Column("status", sa.String(80), nullable=False),
        sa.Column("warnings", sa.Text()),
        sa.Column("github_issue_url", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_issue_drafts_cluster_id", "issue_drafts", ["cluster_id"])
    op.create_index("ix_issue_drafts_id", "issue_drafts", ["id"])

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_type", sa.String(120), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("current_step", sa.String(120), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("input_json", sa.Text()),
        sa.Column("result_json", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("queue_task_id", sa.String(255)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_workflow_runs_workflow_type", "workflow_runs", ["workflow_type"])
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])
    op.create_index("ix_workflow_runs_queue_task_id", "workflow_runs", ["queue_task_id"])

    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            """
            CREATE VIRTUAL TABLE code_chunks_fts USING fts5(
                code_chunk_id UNINDEXED,
                repo_path UNINDEXED,
                file_path,
                symbol_name,
                contextualized_text,
                tokenize = 'unicode61'
            )
            """
        )
    elif op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE INDEX ix_code_chunks_full_text
            ON code_chunks USING gin (
                to_tsvector(
                    'simple',
                    coalesce(file_path, '') || ' ' ||
                    coalesce(function_or_class_name, '') || ' ' ||
                    coalesce(contextualized_text, chunk_text)
                )
            )
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute("DROP TABLE IF EXISTS code_chunks_fts")
    elif op.get_bind().dialect.name == "postgresql":
        op.drop_index("ix_code_chunks_full_text", table_name="code_chunks")

    op.drop_table("workflow_runs")
    op.drop_table("issue_drafts")
    op.drop_table("retrieved_evidence")
    op.drop_table("tickets")
    op.drop_table("code_chunks")
    op.drop_table("clusters")
