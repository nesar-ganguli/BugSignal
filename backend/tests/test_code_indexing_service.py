import unittest

from app.services.code_indexing_service import (
    CHUNK_OVERLAP_LINES,
    MAX_CHUNK_LINES,
    _chunk_file,
    _symbol_boundaries,
)


class CodeIndexingServiceTests(unittest.TestCase):
    def test_typescript_boundaries_ignore_local_const_variables(self) -> None:
        lines = """
import { searchPatients } from "./api";

const API_PATH = "/patients";

export const PatientSearch = () => {
  const response = searchPatients();
  const result = response.items;
  return result;
};

export async function loadPatient(id: string) {
  const token = localStorage.getItem("token");
  return fetch(`${API_PATH}/${id}`, { headers: { Authorization: token } });
}
""".strip().splitlines()

        boundaries = _symbol_boundaries("TypeScript", lines)

        self.assertEqual(
            [symbol_name for _, symbol_name in boundaries],
            ["PatientSearch", "loadPatient"],
        )

    def test_contextualized_chunk_contains_file_and_symbol_context(self) -> None:
        contents = """
import { searchPatients } from "./api";

export const PatientSearch = () => {
  return searchPatients();
};
""".strip()

        chunks = _chunk_file(
            "frontend/components/patient-search.tsx",
            "TypeScript",
            contents,
        )
        symbol_chunk = next(
            chunk for chunk in chunks if chunk.function_or_class_name == "PatientSearch"
        )

        self.assertIn(
            "File: frontend/components/patient-search.tsx",
            symbol_chunk.contextualized_text,
        )
        self.assertIn(
            "Module: frontend.components.patient-search",
            symbol_chunk.contextualized_text,
        )
        self.assertIn("Enclosing symbol: PatientSearch", symbol_chunk.contextualized_text)
        self.assertIn(
            'Imports: import { searchPatients } from "./api";',
            symbol_chunk.contextualized_text,
        )
        self.assertIn("Original code:", symbol_chunk.contextualized_text)
        self.assertEqual(
            symbol_chunk.chunk_text,
            'export const PatientSearch = () => {\n  return searchPatients();\n};',
        )

    def test_oversized_chunks_use_line_overlap(self) -> None:
        contents = "\n".join(f"line_{index} = {index}" for index in range(1, 151))

        chunks = _chunk_file("backend/generated.py", "Python", contents)

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].end_line, MAX_CHUNK_LINES)
        self.assertEqual(
            chunks[1].start_line,
            MAX_CHUNK_LINES - CHUNK_OVERLAP_LINES + 1,
        )
        self.assertEqual(chunks[1].end_line, 150)


if __name__ == "__main__":
    unittest.main()
