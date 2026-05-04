from sqlalchemy.orm import Session
import json

from app.repositories.cluster_repository import clear_clusters, create_cluster
from app.repositories.ticket_repository import list_clusterable_tickets, set_ticket_cluster
from app.schemas.cluster_schema import ClusterRunResponse
from app.services.clustering_service import cluster_tickets, confidence_from_cohesion, build_ticket_embedding_text
from app.services.embedding_service import EmbeddingService
from app.services.priority_service import score_cluster_priority


def rebuild_ticket_clusters(db: Session) -> ClusterRunResponse:
    tickets = list_clusterable_tickets(db)
    if not tickets:
        clear_clusters(db)
        db.commit()
        return ClusterRunResponse(
            clusters_created=0,
            clustered_tickets=0,
            outlier_tickets=0,
            message="No extracted tickets are available for clustering.",
        )

    texts = [build_ticket_embedding_text(ticket) for ticket in tickets]
    embedding_service = EmbeddingService()
    embeddings = embedding_service.embed_texts(texts)
    clustering_result = cluster_tickets(tickets, embeddings)

    clear_clusters(db)
    clusters_created = 0

    for assignment in clustering_result.assignments:
        ticket_count = len(assignment.tickets)
        confidence_score = confidence_from_cohesion(assignment.cohesion_score, ticket_count)
        priority_result = score_cluster_priority(assignment.tickets)
        cluster = create_cluster(
            db,
            title=assignment.title,
            summary=assignment.summary,
            ticket_count=ticket_count,
            cohesion_score=assignment.cohesion_score,
            confidence_score=confidence_score,
            priority_score=priority_result.score,
            priority_label=priority_result.label,
            priority_breakdown=json.dumps(priority_result.breakdown),
            suspected_feature_area=assignment.suspected_feature_area,
            status="needs_review",
        )
        clusters_created += 1

        for ticket in assignment.tickets:
            set_ticket_cluster(ticket, cluster.id, embedding_id=f"ticket-{ticket.id}-all-MiniLM-L6-v2")

    db.commit()

    return ClusterRunResponse(
        clusters_created=clusters_created,
        clustered_tickets=clustering_result.clustered_tickets,
        outlier_tickets=clustering_result.outlier_tickets,
        message=(
            f"Created {clusters_created} cluster groups with "
            f"{clustering_result.clustered_tickets} clustered tickets and "
            f"{clustering_result.outlier_tickets} manual-triage tickets."
        ),
    )
