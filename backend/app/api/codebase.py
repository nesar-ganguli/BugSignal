from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.repositories.code_repository import codebase_status
from app.schemas.code_schema import (
    CodebaseIndexRequest,
    CodebaseIndexResponse,
    CodebaseStatusResponse,
    GitHubCodebaseIndexRequest,
)
from app.services.chroma_service import ChromaDependencyError
from app.services.code_indexing_service import index_codebase
from app.services.embedding_service import EmbeddingDependencyError
from app.services.github_repo_service import GitHubRepoImportError, clone_github_repo

router = APIRouter(prefix="/codebase", tags=["codebase"])


@router.post("/index", response_model=CodebaseIndexResponse)
async def index_local_codebase(
    request: CodebaseIndexRequest,
    db: Session = Depends(get_db),
) -> CodebaseIndexResponse:
    try:
        return index_codebase(db, request.local_repo_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ChromaDependencyError, EmbeddingDependencyError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/github/index", response_model=CodebaseIndexResponse)
async def index_github_codebase(
    request: GitHubCodebaseIndexRequest,
    db: Session = Depends(get_db),
) -> CodebaseIndexResponse:
    try:
        repo_path = clone_github_repo(request.github_url, get_settings())
        response = index_codebase(db, str(repo_path))
    except GitHubRepoImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ChromaDependencyError, EmbeddingDependencyError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    response.source_url = request.github_url
    response.message = f"Cloned and indexed GitHub repo. {response.message}"
    return response


@router.get("/status", response_model=CodebaseStatusResponse)
async def get_codebase_status(db: Session = Depends(get_db)) -> CodebaseStatusResponse:
    indexed_files, indexed_chunks, last_indexed_at = codebase_status(db)
    return CodebaseStatusResponse(
        indexed_files=indexed_files,
        indexed_chunks=indexed_chunks,
        last_indexed_at=last_indexed_at.isoformat() if last_indexed_at else None,
    )
