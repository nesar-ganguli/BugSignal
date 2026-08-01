from collections.abc import Callable

from sqlalchemy.orm import Session

from app.config import get_settings
from app.repositories.ticket_repository import (
    apply_ticket_extraction,
    count_tickets,
    list_tickets_for_extraction,
    mark_ticket_extraction_failed,
)
from app.schemas.ticket_schema import TicketProcessResponse
from app.services.cluster_workflow_service import rebuild_ticket_clusters
from app.services.clustering_service import ClusteringDependencyError
from app.services.embedding_service import EmbeddingDependencyError
from app.services.llm_client import LLMClient, LLMResponseError, LLMUnavailableError
from app.services.ticket_extraction_service import TicketExtractionError, extract_ticket_fields


ProgressCallback = Callable[[str, int], None]


async def process_ticket_batch(
    db: Session,
    *,
    limit: int,
    force: bool,
    progress: ProgressCallback | None = None,
) -> TicketProcessResponse:
    settings = get_settings()
    llm_client = LLMClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout_seconds=90,
    )
    tickets = list_tickets_for_extraction(db, limit=limit, force=force)
    processed = 0
    errors: list[str] = []

    _report(progress, "extracting_tickets", 5)
    for index, ticket in enumerate(tickets, start=1):
        try:
            extraction = await extract_ticket_fields(ticket, llm_client)
        except LLMUnavailableError:
            raise
        except (LLMResponseError, TicketExtractionError) as exc:
            error_message = str(exc)
            mark_ticket_extraction_failed(ticket, error_message)
            errors.append(error_message)
        else:
            apply_ticket_extraction(ticket, extraction)
            processed += 1

        db.commit()
        extraction_progress = 5 + round((index / max(len(tickets), 1)) * 70)
        _report(progress, "extracting_tickets", extraction_progress)

    message = "Extraction complete for this batch." if tickets else "No tickets need extraction."
    clusters_created = 0
    clustered_tickets = 0
    outlier_tickets = 0
    # Clustering operates on every completed ticket, not only tickets completed in this
    # batch. This is important when a retry batch contains only persistent failures.
    _report(progress, "clustering_tickets", 82)
    try:
        cluster_result = rebuild_ticket_clusters(db)
    except (EmbeddingDependencyError, ClusteringDependencyError) as exc:
        errors.append(str(exc))
    else:
        clusters_created = cluster_result.clusters_created
        clustered_tickets = cluster_result.clustered_tickets
        outlier_tickets = cluster_result.outlier_tickets
        message = f"{message} {cluster_result.message}"

    _report(progress, "finalizing", 95)
    return TicketProcessResponse(
        processed=processed,
        failed=len(errors),
        total_tickets=count_tickets(db),
        clusters_created=clusters_created,
        clustered_tickets=clustered_tickets,
        outlier_tickets=outlier_tickets,
        message=message,
        errors=errors,
    )


def _report(progress: ProgressCallback | None, step: str, percent: int) -> None:
    if progress:
        progress(step, percent)
