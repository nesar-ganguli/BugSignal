from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import re

import numpy as np

from app.models import Ticket


class ClusteringDependencyError(RuntimeError):
    pass


MIN_CLUSTER_SIZE = 3
MIN_SAMPLES = 1
LOW_COHESION_SPLIT_THRESHOLD = 0.50
SUBCLUSTER_DISTANCE_THRESHOLD = 0.55
MIN_ACCEPTABLE_CLUSTER_COHESION = 0.35


@dataclass
class TicketClusterAssignment:
    label: int
    tickets: list[Ticket]
    cohesion_score: float
    title: str
    summary: str
    suspected_feature_area: str | None
    is_outlier_group: bool = False


@dataclass
class ClusteringResult:
    assignments: list[TicketClusterAssignment]
    clustered_tickets: int
    outlier_tickets: int


def cluster_tickets(tickets: list[Ticket], embeddings: np.ndarray) -> ClusteringResult:
    if not tickets:
        return ClusteringResult(assignments=[], clustered_tickets=0, outlier_tickets=0)

    if len(tickets) < 3:
        assignment = TicketClusterAssignment(
            label=-1,
            tickets=tickets,
            cohesion_score=_cohesion_score(embeddings),
            title="Needs manual triage",
            summary="Fewer than 3 tickets are available, so clustering is tentative.",
            suspected_feature_area=None,
            is_outlier_group=True,
        )
        return ClusteringResult(assignments=[assignment], clustered_tickets=0, outlier_tickets=len(tickets))

    try:
        import hdbscan
    except ImportError as exc:
        raise ClusteringDependencyError(
            "hdbscan is not installed. Install backend requirements before clustering."
        ) from exc

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=MIN_CLUSTER_SIZE,
        min_samples=MIN_SAMPLES,
        metric="euclidean",
        cluster_selection_method="eom",
    )
    labels = clusterer.fit_predict(embeddings)

    tickets_by_label: dict[int, list[tuple[int, Ticket]]] = defaultdict(list)
    for index, (label, ticket) in enumerate(zip(labels, tickets)):
        tickets_by_label[int(label)].append((index, ticket))

    assignments: list[TicketClusterAssignment] = []
    clustered_tickets = 0
    outlier_tickets = 0

    next_split_label = (max(tickets_by_label.keys()) + 1) if tickets_by_label else 0

    for label, indexed_tickets in sorted(tickets_by_label.items(), key=lambda item: item[0]):
        indices = [index for index, _ in indexed_tickets]
        group_tickets = [ticket for _, ticket in indexed_tickets]
        group_embeddings = embeddings[indices]
        is_outlier = label == -1

        split_assignments, next_split_label = _split_low_cohesion_group(
            label=label,
            tickets=group_tickets,
            embeddings=group_embeddings,
            is_outlier=is_outlier,
            next_label=next_split_label,
        )

        for assignment in split_assignments:
            if assignment.is_outlier_group:
                outlier_tickets += len(assignment.tickets)
            else:
                clustered_tickets += len(assignment.tickets)
            assignments.append(assignment)

    assignments = _merge_outlier_assignments(assignments)

    return ClusteringResult(
        assignments=assignments,
        clustered_tickets=clustered_tickets,
        outlier_tickets=outlier_tickets,
    )


def _split_low_cohesion_group(
    *,
    label: int,
    tickets: list[Ticket],
    embeddings: np.ndarray,
    is_outlier: bool,
    next_label: int,
) -> tuple[list[TicketClusterAssignment], int]:
    cohesion = _cohesion_score(embeddings)
    if is_outlier or len(tickets) < MIN_CLUSTER_SIZE * 2 or cohesion >= LOW_COHESION_SPLIT_THRESHOLD:
        return [_make_assignment(label, tickets, embeddings, is_outlier)], next_label

    try:
        from sklearn.cluster import AgglomerativeClustering
    except ImportError as exc:
        raise ClusteringDependencyError(
            "scikit-learn is not installed. Install backend requirements before clustering."
        ) from exc

    splitter = AgglomerativeClustering(
        n_clusters=None,
        metric="cosine",
        linkage="average",
        distance_threshold=SUBCLUSTER_DISTANCE_THRESHOLD,
    )
    split_labels = splitter.fit_predict(embeddings)
    indexed_by_split: dict[int, list[int]] = defaultdict(list)
    for index, split_label in enumerate(split_labels):
        indexed_by_split[int(split_label)].append(index)

    assignments: list[TicketClusterAssignment] = []
    manual_triage_indices: list[int] = []

    for split_label, indices in sorted(indexed_by_split.items(), key=lambda item: item[0]):
        split_tickets = [tickets[index] for index in indices]
        split_embeddings = embeddings[indices]
        split_cohesion = _cohesion_score(split_embeddings)
        if len(split_tickets) < MIN_CLUSTER_SIZE or split_cohesion < MIN_ACCEPTABLE_CLUSTER_COHESION:
            manual_triage_indices.extend(indices)
            continue

        assignments.append(
            _make_assignment(
                next_label,
                split_tickets,
                split_embeddings,
                is_outlier=False,
            )
        )
        next_label += 1

    if manual_triage_indices:
        manual_tickets = [tickets[index] for index in manual_triage_indices]
        manual_embeddings = embeddings[manual_triage_indices]
        assignments.append(_make_assignment(-1, manual_tickets, manual_embeddings, is_outlier=True))

    if not assignments:
        return [_make_assignment(-1, tickets, embeddings, is_outlier=True)], next_label

    return assignments, next_label


def _make_assignment(
    label: int,
    tickets: list[Ticket],
    embeddings: np.ndarray,
    is_outlier: bool,
) -> TicketClusterAssignment:
    return TicketClusterAssignment(
        label=label,
        tickets=tickets,
        cohesion_score=_cohesion_score(embeddings),
        title=_cluster_title(tickets, is_outlier),
        summary=_cluster_summary(tickets, is_outlier),
        suspected_feature_area=_most_common_feature_area(tickets),
        is_outlier_group=is_outlier,
    )


def _merge_outlier_assignments(assignments: list[TicketClusterAssignment]) -> list[TicketClusterAssignment]:
    outlier_assignments = [assignment for assignment in assignments if assignment.is_outlier_group]
    regular_assignments = [assignment for assignment in assignments if not assignment.is_outlier_group]
    if len(outlier_assignments) <= 1:
        return assignments

    tickets: list[Ticket] = []
    for assignment in outlier_assignments:
        tickets.extend(assignment.tickets)

    merged = TicketClusterAssignment(
        label=-1,
        tickets=tickets,
        cohesion_score=0.0,
        title="Needs manual triage",
        summary="Tickets that were too isolated or too weakly related for a confident cluster.",
        suspected_feature_area=_most_common_feature_area(tickets),
        is_outlier_group=True,
    )
    return [merged] + regular_assignments


def build_ticket_embedding_text(ticket: Ticket) -> str:
    error_terms = _parse_error_terms(ticket.extracted_error_terms)
    parts = [
        ticket.title,
        ticket.body,
        ticket.extracted_intent,
        ticket.extracted_user_action,
        ticket.extracted_expected_behavior,
        ticket.extracted_actual_behavior,
        ticket.extracted_feature_area,
        " ".join(error_terms),
        ticket.sentiment,
        ticket.severity,
    ]
    return "\n".join(part for part in parts if part)


def confidence_from_cohesion(cohesion_score: float, ticket_count: int) -> float:
    count_bonus = min(ticket_count / 10, 1.0) * 0.2
    return round(min(max((cohesion_score * 0.8) + count_bonus, 0.0), 1.0), 3)


def _cohesion_score(embeddings: np.ndarray) -> float:
    if len(embeddings) < 2:
        return 0.0
    similarities = np.matmul(embeddings, embeddings.T)
    upper_triangle = similarities[np.triu_indices(len(embeddings), k=1)]
    if len(upper_triangle) == 0:
        return 0.0
    return round(float(np.mean(upper_triangle)), 3)


def _cluster_title(tickets: list[Ticket], is_outlier: bool) -> str:
    if is_outlier:
        return "Needs manual triage"

    feature_area = _most_common_feature_area(tickets)
    if feature_area:
        return feature_area

    words = Counter()
    for ticket in tickets:
        words.update(_keywords(ticket.title))
    common = [word for word, _ in words.most_common(5)]
    return " ".join(common).title() if common else "Related support complaints"


def _cluster_summary(tickets: list[Ticket], is_outlier: bool) -> str:
    if is_outlier:
        return "Tickets that HDBSCAN marked as noise or too isolated for a confident cluster."

    actual_behaviors = [ticket.extracted_actual_behavior for ticket in tickets if ticket.extracted_actual_behavior]
    if actual_behaviors:
        most_common_actual = Counter(actual_behaviors).most_common(1)[0][0]
        return f"Related tickets report: {most_common_actual}"

    titles = [ticket.title for ticket in tickets[:3]]
    return "Related tickets include: " + "; ".join(titles)


def _most_common_feature_area(tickets: list[Ticket]) -> str | None:
    feature_areas = [ticket.extracted_feature_area for ticket in tickets if ticket.extracted_feature_area]
    if not feature_areas:
        return None
    return Counter(feature_areas).most_common(1)[0][0]


def _parse_error_terms(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [value]
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return []


def _keywords(value: str) -> list[str]:
    stopwords = {
        "after",
        "with",
        "from",
        "that",
        "this",
        "page",
        "issue",
        "error",
        "never",
        "keeps",
        "when",
        "user",
        "users",
    }
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9]+", value.lower())
    return [word for word in words if len(word) > 3 and word not in stopwords]
