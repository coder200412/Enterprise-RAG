"""
SQLAlchemy models for users and roles (RBAC).
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database.session import Base


class Role(Base):
    """
    Represents an access role with a clearance level.
    Higher clearance_level = more access to documents.
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    clearance_level = Column(Integer, nullable=False)  # 1=employee, 2=manager, 3=admin
    description = Column(Text, default="")

    # Relationships
    users = relationship("User", back_populates="role")

    def __repr__(self):
        return f"<Role(name='{self.name}', clearance={self.clearance_level})>"


class User(Base):
    """
    Represents a system user with authentication credentials and role assignment.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    lockout_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    role = relationship("Role", back_populates="users")

    def __repr__(self):
        return f"<User(username='{self.username}', role='{self.role.name if self.role else 'N/A'}')>"


class AuditLog(Base):
    """
    Tracks all queries made by users for security auditing.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    query = Column(Text, nullable=False)
    response_summary = Column(Text, default="")
    sources_accessed = Column(Text, default="")  # JSON string of source doc names
    guardrail_flags = Column(Text, default="")  # JSON string of triggered flags
    latency_ms = Column(Integer, default=0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User")


class ChatSession(Base):
    """
    Represents a chat conversation session between a user and the assistant.
    """
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), default="New Chat")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """
    Represents an individual message in a chat session.
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    session = relationship("ChatSession", back_populates="messages")


class RevokedToken(Base):
    """
    Stores revoked JWT access tokens (e.g. from user logouts) to prevent reuse.
    """
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(500), unique=True, nullable=False, index=True)
    revoked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

