"""Scope BugSignal data to organization projects.

Revision ID: 20260801_0003
Revises: 20260801_0002
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa


revision = "20260801_0003"
down_revision = "20260801_0002"
branch_labels = None
depends_on = None


SCOPED_TABLES = (
    "tickets",
    "clusters",
    "code_chunks",
    "retrieved_evidence",
    "issue_drafts",
    "workflow_runs",
)


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "slug", name="uq_projects_org_slug"),
    )
    op.create_index("ix_projects_id", "projects", ["id"])
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO organizations (external_id, name, created_at) "
            "SELECT 'local-development', 'Local Development', CURRENT_TIMESTAMP "
            "WHERE NOT EXISTS (SELECT 1 FROM organizations WHERE external_id='local-development')"
        )
    )
    organization_id = connection.scalar(
        sa.text("SELECT id FROM organizations WHERE external_id='local-development'")
    )
    connection.execute(
        sa.text(
            "INSERT INTO projects (organization_id, name, slug, created_at) "
            "VALUES (:organization_id, 'Default Project', 'default', CURRENT_TIMESTAMP)"
        ),
        {"organization_id": organization_id},
    )
    project_id = connection.scalar(
        sa.text(
            "SELECT id FROM projects WHERE organization_id=:organization_id AND slug='default'"
        ),
        {"organization_id": organization_id},
    )

    for table_name in SCOPED_TABLES:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        connection.execute(
            sa.text(f"UPDATE {table_name} SET project_id=:project_id"),
            {"project_id": project_id},
        )
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column("project_id", nullable=False)
            batch_op.create_foreign_key(
                f"fk_{table_name}_project_id_projects", "projects", ["project_id"], ["id"]
            )
            batch_op.create_index(f"ix_{table_name}_project_id", ["project_id"])

    op.drop_index("ix_tickets_external_ticket_id", table_name="tickets")
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.create_index("ix_tickets_external_ticket_id", ["external_ticket_id"])
        batch_op.create_unique_constraint(
            "uq_tickets_project_external_id", ["project_id", "external_ticket_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_constraint("uq_tickets_project_external_id", type_="unique")
        batch_op.drop_index("ix_tickets_external_ticket_id")
        batch_op.create_index("ix_tickets_external_ticket_id", ["external_ticket_id"], unique=True)

    for table_name in reversed(SCOPED_TABLES):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_index(f"ix_{table_name}_project_id")
            batch_op.drop_constraint(f"fk_{table_name}_project_id_projects", type_="foreignkey")
            batch_op.drop_column("project_id")
    op.drop_table("projects")
