"""
Pydantic schemas for document management.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DocumentUploadRequest(BaseModel):
    clearance_level: int = Field(default=1, ge=1, le=3)
    department: str = Field(default="general", max_length=100)


class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    clearance_level: int
    department: str
    uploaded_by: int
    uploaded_at: datetime
    chunk_count: int
    status: str
    error_message: str

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
