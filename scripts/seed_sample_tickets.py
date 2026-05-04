from pathlib import Path
import os
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
SAMPLE_CSV_PATH = BACKEND_DIR / "app" / "data" / "sample_tickets.csv"

os.chdir(BACKEND_DIR)
sys.path.append(str(BACKEND_DIR))

from app.database import Base, SessionLocal, engine, run_sqlite_migrations  # noqa: E402
from app.repositories.ticket_repository import count_tickets, upsert_ticket  # noqa: E402
from app.services.ticket_csv_service import parse_ticket_csv  # noqa: E402


def main() -> None:
    Base.metadata.create_all(bind=engine)
    run_sqlite_migrations()
    parse_result = parse_ticket_csv(SAMPLE_CSV_PATH.read_bytes())

    inserted = 0
    updated = 0
    with SessionLocal() as db:
        for ticket_data in parse_result.tickets:
            _, created = upsert_ticket(db, ticket_data)
            if created:
                inserted += 1
            else:
                updated += 1
        db.commit()
        total = count_tickets(db)

    print(
        f"Seeded {inserted} new tickets, updated {updated}, skipped {parse_result.skipped}. "
        f"Total tickets: {total}."
    )
    if parse_result.errors:
        print("Skipped rows:")
        for error in parse_result.errors:
            print(f"- {error}")


if __name__ == "__main__":
    main()
