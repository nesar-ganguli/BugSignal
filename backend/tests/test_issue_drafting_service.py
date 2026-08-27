import unittest

from app.models import Cluster
from app.services.issue_drafting_service import _parse_llm_result
from app.services.llm_client import LLMResponseError


def valid_draft_payload() -> dict:
    return {
        "title": "Checkout cannot complete",
        "summary": "Several customers report checkout failures.",
        "user_impact": "Customers cannot place orders.",
        "steps_to_reproduce": ["Attempt checkout."],
        "expected_behavior": "The order completes.",
        "actual_behavior": "Checkout remains loading.",
        "suspected_root_cause": "Insufficient evidence to identify a suspected root cause.",
        "evidence": [],
        "relevant_files": [],
        "open_questions": ["Which service logs contain the failure?"],
    }


class IssueDraftingNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cluster = Cluster(priority_label="P1 High")

    def test_missing_small_model_tail_fields_use_safe_deterministic_values(self) -> None:
        result = _parse_llm_result(valid_draft_payload(), self.cluster)

        self.assertEqual(result.confidence, "Low")
        self.assertEqual(result.priority_label, "P1 High")

    def test_model_cannot_override_scored_cluster_priority(self) -> None:
        payload = valid_draft_payload()
        payload.update({"confidence": "Medium", "priority_label": "P3 Low"})

        result = _parse_llm_result(payload, self.cluster)

        self.assertEqual(result.confidence, "Medium")
        self.assertEqual(result.priority_label, "P1 High")

    def test_other_required_content_remains_required(self) -> None:
        payload = valid_draft_payload()
        del payload["summary"]

        with self.assertRaises(LLMResponseError):
            _parse_llm_result(payload, self.cluster)


if __name__ == "__main__":
    unittest.main()
