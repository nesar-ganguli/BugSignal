from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Cluster, Ticket


def count_clusters(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Cluster)) or 0


def list_clusters(db: Session) -> list[Cluster]:
    statement = select(Cluster).order_by(Cluster.priority_score.desc(), Cluster.ticket_count.desc(), Cluster.id.asc())
    return list(db.scalars(statement).all())


def get_cluster(db: Session, cluster_id: int) -> Cluster | None:
    return db.get(Cluster, cluster_id)


def clear_clusters(db: Session) -> None:
    db.query(Ticket).update({Ticket.cluster_id: None})
    db.execute(delete(Cluster))
    db.flush()


def create_cluster(
    db: Session,
    *,
    title: str,
    summary: str,
    ticket_count: int,
    cohesion_score: float,
    confidence_score: float,
    priority_score: float,
    priority_label: str,
    priority_breakdown: str,
    suspected_feature_area: str | None,
    status: str = "needs_review",
) -> Cluster:
    cluster = Cluster(
        title=title,
        summary=summary,
        ticket_count=ticket_count,
        priority_score=priority_score,
        priority_label=priority_label,
        priority_breakdown=priority_breakdown,
        cohesion_score=cohesion_score,
        confidence_score=confidence_score,
        llm_coherence_label="pending",
        suspected_feature_area=suspected_feature_area,
        status=status,
    )
    db.add(cluster)
    db.flush()
    return cluster
