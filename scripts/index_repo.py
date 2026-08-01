from pathlib import Path
import os
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"

os.chdir(BACKEND_DIR)
sys.path.append(str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.services.code_indexing_service import index_codebase  # noqa: E402
from app.models import Project  # noqa: E402
from sqlalchemy import select  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/index_repo.py /path/to/repo")

    with SessionLocal() as db:
        project = db.scalar(select(Project).order_by(Project.id.asc()).limit(1))
        if project is None:
            raise SystemExit("No project exists. Run `alembic upgrade head` first.")
        result = index_codebase(db, project.id, sys.argv[1])

    print(
        f"{result.message} Skipped {result.skipped_files} files. "
        f"Repo: {result.repo_path}"
    )
    if result.errors:
        print("Indexing warnings:")
        for error in result.errors:
            print(f"- {error}")


if __name__ == "__main__":
    main()
