import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Organization, Project
from app.repositories.workflow_repository import create_workflow_run
from app.tasks.workflow_tasks import _run_triage_pipeline


class TriagePipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_pipeline_processes_batches_then_waits_for_codebase(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        with Session(engine) as db:
            organization = Organization(external_id="triage-org", name="Triage Org")
            db.add(organization)
            db.flush()
            project = Project(organization_id=organization.id, name="Triage", slug="triage")
            db.add(project)
            db.flush()
            workflow = create_workflow_run(db, project.id, "triage_pipeline", {})

            extraction = AsyncMock(side_effect=[(2, 2, 0, []), (0, 0, 0, [])])
            cluster_result = SimpleNamespace(
                clusters_created=1,
                clustered_tickets=2,
                outlier_tickets=0,
            )
            with (
                patch("app.tasks.workflow_tasks.extract_pending_ticket_batch", extraction),
                patch("app.tasks.workflow_tasks.count_tickets", return_value=2),
                patch("app.tasks.workflow_tasks.rebuild_ticket_clusters", return_value=cluster_result),
                patch("app.tasks.workflow_tasks.codebase_status", return_value=(0, 0, None)),
            ):
                result = await _run_triage_pipeline(
                    db,
                    workflow,
                    resume_after_codebase=False,
                    force=False,
                )

            self.assertEqual(result["status"], "waiting_for_codebase")
            self.assertEqual(result["extraction"]["processed"], 2)
            self.assertEqual(result["clusters_created"], 1)
            self.assertIn("Add a repository", result["message"])


if __name__ == "__main__":
    unittest.main()
