import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.repositories.workflow_repository import (
    complete_workflow,
    create_workflow_run,
    get_active_workflow_run,
    mark_workflow_running,
    update_workflow_progress,
)
from app.services.workflow_service import workflow_to_read


class WorkflowRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)

    def test_workflow_lifecycle_is_persisted(self) -> None:
        with Session(self.engine) as db:
            workflow = create_workflow_run(
                db, "ticket_processing", {"limit": 20, "force": False}
            )
            self.assertEqual(workflow.status, "queued")
            self.assertEqual(get_active_workflow_run(db, "ticket_processing").id, workflow.id)

            mark_workflow_running(db, workflow, "extracting_tickets")
            update_workflow_progress(db, workflow, "clustering_tickets", 82)
            complete_workflow(db, workflow, {"processed": 12, "failed": 0})

            response = workflow_to_read(workflow)
            self.assertEqual(response.status, "completed")
            self.assertEqual(response.progress_percent, 100)
            self.assertEqual(response.result["processed"], 12)
            self.assertIsNone(get_active_workflow_run(db, "ticket_processing"))

    def test_progress_is_bounded_before_completion(self) -> None:
        with Session(self.engine) as db:
            workflow = create_workflow_run(db, "ticket_processing", {})
            update_workflow_progress(db, workflow, "finalizing", 150)
            self.assertEqual(workflow.progress_percent, 99)


if __name__ == "__main__":
    unittest.main()
