import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Organization, Project
from app.repositories.workflow_repository import (
    complete_workflow,
    create_workflow_run,
    get_active_workflow_run,
    get_workflow_run,
    mark_workflow_running,
    update_workflow_progress,
)
from app.services.workflow_service import workflow_to_read


class WorkflowRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)

    def create_project(self, db: Session, suffix: str = "one") -> Project:
        organization = Organization(external_id=f"org-{suffix}", name=f"Org {suffix}")
        db.add(organization)
        db.flush()
        project = Project(organization_id=organization.id, name="Project", slug="default")
        db.add(project)
        db.flush()
        return project

    def test_workflow_lifecycle_is_persisted(self) -> None:
        with Session(self.engine) as db:
            project = self.create_project(db)
            workflow = create_workflow_run(
                db, project.id, "ticket_processing", {"limit": 20, "force": False}
            )
            self.assertEqual(workflow.status, "queued")
            self.assertEqual(get_active_workflow_run(db, project.id, "ticket_processing").id, workflow.id)

            mark_workflow_running(db, workflow, "extracting_tickets")
            update_workflow_progress(db, workflow, "clustering_tickets", 82)
            complete_workflow(db, workflow, {"processed": 12, "failed": 0})

            response = workflow_to_read(workflow)
            self.assertEqual(response.status, "completed")
            self.assertEqual(response.progress_percent, 100)
            self.assertEqual(response.result["processed"], 12)
            self.assertIsNone(get_active_workflow_run(db, project.id, "ticket_processing"))

    def test_progress_is_bounded_before_completion(self) -> None:
        with Session(self.engine) as db:
            project = self.create_project(db)
            workflow = create_workflow_run(db, project.id, "ticket_processing", {})
            update_workflow_progress(db, workflow, "finalizing", 150)
            self.assertEqual(workflow.progress_percent, 99)

    def test_workflows_are_isolated_by_project(self) -> None:
        with Session(self.engine) as db:
            project_one = self.create_project(db, "one")
            project_two = self.create_project(db, "two")
            workflow = create_workflow_run(db, project_one.id, "ticket_processing", {})

            self.assertIsNotNone(get_workflow_run(db, project_one.id, workflow.id))
            self.assertIsNone(get_workflow_run(db, project_two.id, workflow.id))


if __name__ == "__main__":
    unittest.main()
