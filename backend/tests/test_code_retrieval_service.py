import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import CodeChunk
from app.repositories.code_repository import (
    replace_code_search_index,
    search_code_chunks_bm25,
)
from app.services.code_retrieval_service import (
    RetrievalCandidate,
    _build_bm25_query,
)


class CodeRetrievalServiceTests(unittest.TestCase):
    def test_bm25_search_prefers_matching_contextual_code(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)

        with Session(engine) as db:
            patient_search = CodeChunk(
                repo_path="/tmp/repo",
                file_path="backend/routes/patients.py",
                language="Python",
                chunk_text="def search_patients(name):\n    return fhir_client.search(name)",
                contextualized_text=(
                    "File: backend/routes/patients.py\n"
                    "Enclosing symbol: search_patients\n"
                    "Handles FHIR patient search and empty search results."
                ),
                function_or_class_name="search_patients",
                chunk_type="symbol",
                start_line=10,
                end_line=12,
                embedding_id="patient-search",
            )
            payment = CodeChunk(
                repo_path="/tmp/repo",
                file_path="backend/routes/payments.py",
                language="Python",
                chunk_text="def retry_payment():\n    return gateway.retry()",
                contextualized_text=(
                    "File: backend/routes/payments.py\n"
                    "Enclosing symbol: retry_payment\n"
                    "Retries failed checkout payments."
                ),
                function_or_class_name="retry_payment",
                chunk_type="symbol",
                start_line=20,
                end_line=22,
                embedding_id="retry-payment",
            )
            db.add_all([patient_search, payment])
            db.flush()
            replace_code_search_index(db, "/tmp/repo", [patient_search, payment])

            results = search_code_chunks_bm25(
                db,
                _build_bm25_query(["patient", "search"], ["FHIR patient search"]),
                limit=5,
            )

            self.assertTrue(results)
            self.assertEqual(results[0].code_chunk_id, patient_search.id)
            self.assertEqual(results[0].rank, 1)

    def test_rank_fusion_rewards_candidates_found_by_both_retrievers(self) -> None:
        hybrid = RetrievalCandidate(
            code_chunk_id=1,
            semantic_rank=2,
            bm25_rank=3,
        )
        semantic_only = RetrievalCandidate(
            code_chunk_id=2,
            semantic_rank=1,
        )

        self.assertGreater(hybrid.final_score, semantic_only.final_score)
        self.assertEqual(hybrid.evidence_type, "hybrid")
        self.assertEqual(semantic_only.evidence_type, "semantic")

    def test_exact_identifiers_add_a_bounded_boost(self) -> None:
        baseline = RetrievalCandidate(
            code_chunk_id=1,
            semantic_rank=5,
            bm25_rank=5,
        )
        exact = RetrievalCandidate(
            code_chunk_id=2,
            semantic_rank=5,
            bm25_rank=5,
            exact_matches=["/patients/search", "FHIRClient", "PatientNotFoundError"],
        )

        self.assertGreater(exact.final_score, baseline.final_score)
        self.assertLessEqual(exact.final_score, 1.0)


if __name__ == "__main__":
    unittest.main()
