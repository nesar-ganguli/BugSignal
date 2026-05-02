from fastapi import APIRouter

router = APIRouter(prefix="/issues", tags=["issues"])


@router.get("")
async def issues_placeholder() -> dict:
    return {
        "items": [],
        "message": "Issue drafting and approval are implemented in Phases 8-10.",
    }
