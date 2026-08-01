import unittest

from app.models import Ticket
from app.services.ticket_extraction_service import (
    _apply_deterministic_flags,
    _normalize_extraction_payload,
)
from app.schemas.ticket_schema import TicketExtractionResult


class TicketExtractionNormalizationTests(unittest.TestCase):
    def test_small_model_enum_echo_and_placeholder_terms_are_normalized(self) -> None:
        ticket = Ticket(
            external_ticket_id="TCK-1",
            title="Checkout hangs",
            body="Checkout keeps failing after the session expires.",
        )
        payload = _normalize_extraction_payload(
            ticket,
            {
                "intent": "complete checkout",
                "error_terms": ["...", " session timeout "],
                "sentiment": "neutral | frustrated | angry | urgent",
                "contains_payment_or_revenue_issue": False,
            },
        )
        extraction = TicketExtractionResult.model_validate(payload)
        extraction = _apply_deterministic_flags(ticket, extraction)

        self.assertEqual(extraction.sentiment, "frustrated")
        self.assertEqual(extraction.error_terms, ["session timeout"])
        self.assertTrue(extraction.contains_payment_or_revenue_issue)
        self.assertTrue(extraction.contains_performance_issue)

    def test_unsupported_model_boolean_does_not_create_priority_signal(self) -> None:
        ticket = Ticket(
            external_ticket_id="TCK-2",
            title="Button color is wrong",
            body="The button should be blue.",
        )
        extraction = TicketExtractionResult(contains_payment_or_revenue_issue=True)

        extraction = _apply_deterministic_flags(ticket, extraction)

        self.assertFalse(extraction.contains_payment_or_revenue_issue)


if __name__ == "__main__":
    unittest.main()
