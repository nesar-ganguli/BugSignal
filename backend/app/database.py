from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_sqlite_migrations() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    ticket_columns = {
        "contains_payment_or_revenue_issue": "BOOLEAN DEFAULT 0 NOT NULL",
        "contains_data_loss_issue": "BOOLEAN DEFAULT 0 NOT NULL",
        "contains_auth_issue": "BOOLEAN DEFAULT 0 NOT NULL",
        "contains_performance_issue": "BOOLEAN DEFAULT 0 NOT NULL",
        "extraction_status": "VARCHAR(40) DEFAULT 'pending' NOT NULL",
        "extracted_at": "DATETIME",
        "extraction_error": "TEXT",
    }

    cluster_columns = {
        "priority_breakdown": "TEXT",
    }
    code_chunk_columns = {
        "chunk_type": "VARCHAR(80) DEFAULT 'code' NOT NULL",
        "indexed_at": "DATETIME",
    }
    issue_draft_columns = {
        "warnings": "TEXT",
    }

    with engine.begin() as connection:
        existing_ticket_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(tickets)")).fetchall()
        }
        for column_name, column_definition in ticket_columns.items():
            if column_name not in existing_ticket_columns:
                connection.execute(
                    text(f"ALTER TABLE tickets ADD COLUMN {column_name} {column_definition}")
                )
        connection.execute(
            text(
                """
                UPDATE tickets
                SET extraction_status = 'completed'
                WHERE extraction_status = 'pending'
                  AND (
                    extracted_intent IS NOT NULL
                    OR extracted_user_action IS NOT NULL
                    OR extracted_expected_behavior IS NOT NULL
                    OR extracted_actual_behavior IS NOT NULL
                    OR extracted_feature_area IS NOT NULL
                    OR extracted_error_terms IS NOT NULL
                    OR sentiment IS NOT NULL
                  )
                """
            )
        )

        existing_cluster_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(clusters)")).fetchall()
        }
        for column_name, column_definition in cluster_columns.items():
            if column_name not in existing_cluster_columns:
                connection.execute(
                    text(f"ALTER TABLE clusters ADD COLUMN {column_name} {column_definition}")
                )

        existing_code_chunk_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(code_chunks)")).fetchall()
        }
        for column_name, column_definition in code_chunk_columns.items():
            if column_name not in existing_code_chunk_columns:
                connection.execute(
                    text(f"ALTER TABLE code_chunks ADD COLUMN {column_name} {column_definition}")
                )

        existing_issue_draft_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(issue_drafts)")).fetchall()
        }
        for column_name, column_definition in issue_draft_columns.items():
            if column_name not in existing_issue_draft_columns:
                connection.execute(
                    text(f"ALTER TABLE issue_drafts ADD COLUMN {column_name} {column_definition}")
                )
