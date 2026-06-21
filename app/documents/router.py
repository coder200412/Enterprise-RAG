"""
Document management API routes.
Handles file upload, listing, and deletion with RBAC enforcement.
"""
import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import get_db, SessionLocal
from app.auth.dependencies import get_current_user, require_admin, require_manager
from app.auth.models import User
from app.documents.models import Document
from app.documents.schemas import DocumentResponse, DocumentListResponse
from app.documents.ingestion import process_file
from app.documents.vectorstore import add_documents, delete_document_chunks

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls"}


def ingest_document_task(
    doc_id: int,
    file_path: str,
    clearance_level: int,
    department: str,
):
    """Background worker for document ingestion to prevent API timeouts."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return

        chunks = process_file(
            file_path=file_path,
            doc_id=doc.id,
            clearance_level=clearance_level,
            department=department,
        )
        chunk_count = add_documents(chunks)

        doc.chunk_count = chunk_count
        doc.status = "ready"
        db.commit()

    except Exception as e:
        db.rollback()
        # Fetch fresh record within this session
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = "error"
            doc.error_message = str(e)
            db.commit()
    finally:
        db.close()


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    clearance_level: int = Form(default=1, ge=1, le=3),
    department: str = Form(default="general"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    """
    Upload and ingest a document (PDF or Excel) asynchronously.
    Requires manager or higher access.
    Returns status 'processing' immediately while the worker runs.
    """
    # Validate file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}",
        )

    # Save uploaded file to disk
    file_path = os.path.join(settings.upload_dir, file.filename)
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}",
        )

    # Create document metadata record
    doc = Document(
        filename=file.filename,
        file_type=ext.lstrip("."),
        clearance_level=clearance_level,
        department=department,
        uploaded_by=current_user.id,
        status="processing",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Start background ingestion
    background_tasks.add_task(
        ingest_document_task,
        doc_id=doc.id,
        file_path=file_path,
        clearance_level=clearance_level,
        department=department,
    )

    return DocumentResponse.model_validate(doc)


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all documents the current user is authorized to see.
    Filters by the user's clearance level.
    """
    docs = (
        db.query(Document)
        .filter(Document.clearance_level <= current_user.role.clearance_level)
        .order_by(Document.uploaded_at.desc())
        .all()
    )

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in docs],
        total=len(docs),
    )


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific document's metadata.
    Only returns if user has sufficient clearance.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.clearance_level > current_user.role.clearance_level:
        raise HTTPException(status_code=403, detail="Insufficient clearance")

    return DocumentResponse.model_validate(doc)


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Delete a document and its vector chunks. Requires admin access.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove vector chunks
    try:
        delete_document_chunks(doc_id)
    except Exception:
        pass  # Continue even if vector deletion fails

    # Remove file from disk
    file_path = os.path.join(settings.upload_dir, doc.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    # Remove database record
    db.delete(doc)
    db.commit()

    return {"message": f"Document '{doc.filename}' deleted successfully"}
