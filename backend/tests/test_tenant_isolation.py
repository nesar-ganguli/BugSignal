import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Organization, Project, Ticket
from app.repositories.ticket_repository import count_tickets, list_tickets
from app.services.tenant_service import TenantContext, require_editor_context


class TenantIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)

    def test_ticket_queries_never_cross_project_boundary(self) -> None:
        with Session(self.engine) as db:
            organization = Organization(external_id="org", name="Org")
            db.add(organization)
            db.flush()
            first = Project(organization_id=organization.id, name="First", slug="first")
            second = Project(organization_id=organization.id, name="Second", slug="second")
            db.add_all([first, second])
            db.flush()
            db.add_all(
                [
                    Ticket(project_id=first.id, external_ticket_id="SAME", title="First", body="A"),
                    Ticket(project_id=second.id, external_ticket_id="SAME", title="Second", body="B"),
                ]
            )
            db.commit()

            self.assertEqual(count_tickets(db, first.id), 1)
            self.assertEqual(list_tickets(db, first.id)[0].title, "First")
            self.assertEqual(list_tickets(db, second.id)[0].title, "Second")

    def test_viewer_cannot_mutate_project(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            require_editor_context(TenantContext(1, 1, 1, "viewer"))
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
