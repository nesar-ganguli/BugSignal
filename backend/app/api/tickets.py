from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("/upload")
async def upload_tickets_preview(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty.")

    return {
        "filename": file.filename,
        "bytes_received": len(contents),
        "status": "accepted",
        "message": "CSV accepted. Ticket parsing and persistence are implemented in Phase 2.",
    }


@router.get("")
async def list_tickets_placeholder() -> dict:
    return {
        "items": [],
        "message": "Ticket listing is implemented in Phase 2.",
    }
