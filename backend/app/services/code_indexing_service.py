from dataclasses import dataclass
from pathlib import Path
import hashlib
import os
import re

from sqlalchemy.orm import Session

from app.repositories.code_repository import add_code_chunk, clear_code_chunks_for_repo
from app.schemas.code_schema import CodebaseIndexResponse
from app.services.chroma_service import ChromaDependencyError, get_code_collection
from app.services.embedding_service import EmbeddingDependencyError, EmbeddingService


MAX_FILE_BYTES = 300_000
MAX_CHUNK_LINES = 160

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".vite",
    ".venv",
    "venv",
    "env",
    "target",
    "coverage",
    "chroma_data",
}

IGNORED_FILE_NAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pipfile.lock",
    "cargo.lock",
    "go.sum",
}

LANGUAGE_BY_SUFFIX = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".go": "Go",
    ".sql": "SQL",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
}

BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".mp4",
    ".mov",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".pyc",
    ".so",
    ".dylib",
}


@dataclass
class CodeChunkCandidate:
    file_path: str
    language: str
    chunk_text: str
    function_or_class_name: str | None
    chunk_type: str
    start_line: int
    end_line: int
    embedding_id: str


def index_codebase(db: Session, local_repo_path: str) -> CodebaseIndexResponse:
    repo_root = Path(local_repo_path).expanduser().resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise ValueError("local_repo_path must point to an existing directory.")

    candidates, skipped_files, errors = _scan_repo(repo_root)
    repo_path = str(repo_root)

    collection = get_code_collection()
    _delete_chroma_repo(collection, repo_path)
    clear_code_chunks_for_repo(db, repo_path)

    if not candidates:
        db.commit()
        return CodebaseIndexResponse(
            repo_path=repo_path,
            indexed_files=0,
            indexed_chunks=0,
            skipped_files=skipped_files,
            message="No supported code files were found.",
            errors=errors,
        )

    embeddings = EmbeddingService().embed_texts([candidate.chunk_text for candidate in candidates])

    db_chunks = []
    for candidate in candidates:
        db_chunks.append(
            add_code_chunk(
                db,
                repo_path=repo_path,
                file_path=candidate.file_path,
                language=candidate.language,
                chunk_text=candidate.chunk_text,
                function_or_class_name=candidate.function_or_class_name,
                chunk_type=candidate.chunk_type,
                start_line=candidate.start_line,
                end_line=candidate.end_line,
                embedding_id=candidate.embedding_id,
            )
        )
    db.flush()

    collection.add(
        ids=[candidate.embedding_id for candidate in candidates],
        documents=[candidate.chunk_text for candidate in candidates],
        embeddings=embeddings.tolist(),
        metadatas=[
            {
                "code_chunk_id": db_chunk.id,
                "repo_path": repo_path,
                "file_path": candidate.file_path,
                "language": candidate.language,
                "function_or_class_name": candidate.function_or_class_name or "",
                "chunk_type": candidate.chunk_type,
                "start_line": candidate.start_line,
                "end_line": candidate.end_line,
            }
            for candidate, db_chunk in zip(candidates, db_chunks)
        ],
    )
    db.commit()

    indexed_files = len({candidate.file_path for candidate in candidates})
    return CodebaseIndexResponse(
        repo_path=repo_path,
        indexed_files=indexed_files,
        indexed_chunks=len(candidates),
        skipped_files=skipped_files,
        message=f"Indexed {indexed_files} files into {len(candidates)} code chunks.",
        errors=errors,
    )


def _scan_repo(repo_root: Path) -> tuple[list[CodeChunkCandidate], int, list[str]]:
    candidates: list[CodeChunkCandidate] = []
    skipped_files = 0
    errors: list[str] = []

    for root, dir_names, file_names in os.walk(repo_root):
        dir_names[:] = [dir_name for dir_name in dir_names if dir_name not in IGNORED_DIRS]

        for file_name in file_names:
            path = Path(root, file_name)
            if _should_ignore_file(path, repo_root):
                skipped_files += 1
                continue

            language = LANGUAGE_BY_SUFFIX.get(path.suffix.lower())
            if not language:
                skipped_files += 1
                continue

            try:
                contents = _read_text_file(path)
            except ValueError as exc:
                skipped_files += 1
                errors.append(f"{path.relative_to(repo_root)}: {exc}")
                continue

            relative_path = str(path.relative_to(repo_root))
            candidates.extend(_chunk_file(relative_path, language, contents))

    return candidates, skipped_files, errors[:20]


def _should_ignore_file(path: Path, repo_root: Path) -> bool:
    relative_parts = path.relative_to(repo_root).parts
    if any(part in IGNORED_DIRS for part in relative_parts[:-1]):
        return True
    if path.name.lower() in IGNORED_FILE_NAMES:
        return True
    if "lock" in path.name.lower() and path.suffix.lower() in {".json", ".yaml", ".yml"}:
        return True
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return True
    except OSError:
        return True
    return False


def _read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    if b"\x00" in raw[:2048]:
        raise ValueError("binary file skipped")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("not UTF-8 text") from exc


def _chunk_file(relative_path: str, language: str, contents: str) -> list[CodeChunkCandidate]:
    lines = contents.splitlines()
    if not lines:
        return []

    boundaries = _symbol_boundaries(language, lines)
    if not boundaries:
        return _fixed_line_chunks(relative_path, language, lines, None, "file")

    chunks: list[CodeChunkCandidate] = []
    for index, (start_line, symbol_name) in enumerate(boundaries):
        end_line = boundaries[index + 1][0] - 1 if index + 1 < len(boundaries) else len(lines)
        symbol_lines = lines[start_line - 1:end_line]
        chunks.extend(
            _fixed_line_chunks(
                relative_path,
                language,
                symbol_lines,
                symbol_name,
                "symbol",
                line_offset=start_line - 1,
            )
        )

    first_boundary = boundaries[0][0]
    if first_boundary > 1:
        chunks = _fixed_line_chunks(relative_path, language, lines[: first_boundary - 1], None, "file") + chunks

    return chunks


def _fixed_line_chunks(
    relative_path: str,
    language: str,
    lines: list[str],
    symbol_name: str | None,
    chunk_type: str,
    line_offset: int = 0,
) -> list[CodeChunkCandidate]:
    chunks: list[CodeChunkCandidate] = []
    for start in range(0, len(lines), MAX_CHUNK_LINES):
        end = min(start + MAX_CHUNK_LINES, len(lines))
        chunk_lines = lines[start:end]
        chunk_text = "\n".join(chunk_lines).strip()
        if not chunk_text:
            continue
        start_line = line_offset + start + 1
        end_line = line_offset + end
        chunks.append(
            CodeChunkCandidate(
                file_path=relative_path,
                language=language,
                chunk_text=chunk_text,
                function_or_class_name=symbol_name,
                chunk_type=chunk_type,
                start_line=start_line,
                end_line=end_line,
                embedding_id=_embedding_id(relative_path, start_line, end_line, chunk_text),
            )
        )
    return chunks


def _symbol_boundaries(language: str, lines: list[str]) -> list[tuple[int, str]]:
    patterns = {
        "Python": re.compile(r"^\s*(?:async\s+def|def|class)\s+([A-Za-z_][A-Za-z0-9_]*)"),
        "TypeScript": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][A-Za-z0-9_$]*)|^\s*(?:export\s+)?const\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*="),
        "JavaScript": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][A-Za-z0-9_$]*)|^\s*(?:export\s+)?const\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*="),
        "Java": re.compile(r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:class|interface|enum|[A-Za-z0-9_<>\[\]]+\s+)\s*([A-Za-z_][A-Za-z0-9_]*)\s*[({]"),
        "Go": re.compile(r"^\s*(?:func)\s+(?:\([^)]+\)\s*)?([A-Za-z_][A-Za-z0-9_]*)"),
        "SQL": re.compile(r"^\s*(?:CREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|PROCEDURE|VIEW|TABLE))\s+([A-Za-z0-9_\.]+)", re.IGNORECASE),
    }
    pattern = patterns.get(language)
    if pattern is None:
        return []

    boundaries: list[tuple[int, str]] = []
    for line_number, line in enumerate(lines, start=1):
        match = pattern.search(line)
        if match:
            symbol_name = next((group for group in match.groups() if group), None)
            if symbol_name:
                boundaries.append((line_number, symbol_name))
    return boundaries


def _embedding_id(relative_path: str, start_line: int, end_line: int, chunk_text: str) -> str:
    digest = hashlib.sha1(f"{relative_path}:{start_line}:{end_line}:{chunk_text}".encode("utf-8")).hexdigest()
    return f"code-{digest}"


def _delete_chroma_repo(collection, repo_path: str) -> None:
    try:
        collection.delete(where={"repo_path": repo_path})
    except Exception:
        # Chroma raises for some empty-collection delete paths; indexing should still proceed.
        return
