import csv
from datetime import datetime, timezone
from io import StringIO

from app.schemas.ticket_schema import TicketCreate


REQUIRED_COLUMNS = {"ticket_id", "title", "body", "created_at"}
OPTIONAL_COLUMNS = {"customer_plan", "severity", "source"}


class TicketCSVParseResult:
    def __init__(self, tickets: list[TicketCreate], errors: list[str], skipped: int) -> None:
        self.tickets = tickets
        self.errors = errors
        self.skipped = skipped


def parse_ticket_csv(contents: bytes) -> TicketCSVParseResult:
    text = _decode_csv(contents)
    reader = csv.DictReader(StringIO(text))

    if not reader.fieldnames:
        raise ValueError("CSV must include a header row.")

    normalized_columns = {column.strip() for column in reader.fieldnames if column}
    missing_columns = sorted(REQUIRED_COLUMNS - normalized_columns)
    if missing_columns:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing_columns)}.")

    tickets: list[TicketCreate] = []
    errors: list[str] = []
    skipped = 0

    for row_number, row in enumerate(reader, start=2):
        normalized_row = {
            (key.strip() if key else ""): (value.strip() if isinstance(value, str) else value)
            for key, value in row.items()
        }

        try:
            ticket = _parse_ticket_row(normalized_row)
        except ValueError as exc:
            skipped += 1
            errors.append(f"Row {row_number}: {exc}")
            continue

        tickets.append(ticket)

    return TicketCSVParseResult(tickets=tickets, errors=errors, skipped=skipped)


def _decode_csv(contents: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return contents.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("CSV must be UTF-8 encoded.")


def _parse_ticket_row(row: dict[str, str | None]) -> TicketCreate:
    external_ticket_id = _required_value(row, "ticket_id")
    title = _required_value(row, "title")
    body = _required_value(row, "body")

    return TicketCreate(
        external_ticket_id=external_ticket_id,
        title=title,
        body=body,
        created_at=_parse_datetime(row.get("created_at")),
        customer_plan=_optional_value(row, "customer_plan"),
        severity=_optional_value(row, "severity"),
        source=_optional_value(row, "source"),
    )


def _required_value(row: dict[str, str | None], column: str) -> str:
    value = row.get(column)
    if not value:
        raise ValueError(f"{column} is required.")
    return value


def _optional_value(row: dict[str, str | None], column: str) -> str | None:
    value = row.get(column)
    return value or None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"created_at must be an ISO 8601 datetime, got {value}.") from exc

    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)
