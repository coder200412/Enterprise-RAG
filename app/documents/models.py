"""
SQLAlchemy models for document metadata.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database.session import Base


class Document(Base):
    """
    Stores metadata about uploaded documents.
    The actual content is chunked and stored in the vector store.
    clearance_level controls who can access this document's chunks.
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)  # "pdf", "xlsx"
    clearance_level = Column(Integer, nullable=False, default=1)
    department = Column(String(100), default="general")
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    chunk_count = Column(Integer, default=0)
    status = Column(String(20), default="processing")  # processing, ready, error
    error_message = Column(Text, default="")

    # Relationships
    uploader = relationship("User")

    def __repr__(self):
        return f"<Document(filename='{self.filename}', clearance={self.clearance_level}, status='{self.status}')>"
