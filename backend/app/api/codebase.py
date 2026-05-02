from fastapi import APIRouter

router = APIRouter(prefix="/codebase", tags=["codebase"])


@router.get("/status")
async def codebase_status_placeholder() -> dict:
    return {
        "indexed_files": 0,
        "indexed_chunks": 0,
        "message": "Codebase indexing is implemented in Phase 6.",
    }
