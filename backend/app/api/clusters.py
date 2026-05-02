from fastapi import APIRouter

router = APIRouter(prefix="/clusters", tags=["clusters"])


@router.get("")
async def list_clusters_placeholder() -> dict:
    return {
        "items": [],
        "message": "Cluster listing is implemented in Phase 5.",
    }
