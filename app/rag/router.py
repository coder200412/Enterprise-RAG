"""
Chat/Query API routes.
Handles RAG queries with guardrail integration and audit logging.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.auth.dependencies import get_current_user, require_admin
from app.auth.models import User, AuditLog
from app.rag.chain import query_rag
from app.guardrails.input_filter import check_input
from app.guardrails.output_filter import filter_output
from app.guardrails.topic_guard import check_topic
from app.config import settings

router = APIRouter(prefix="/chat", tags=["Chat"])


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    department: str | None = Field(default=None)
    session_id: int | None = Field(default=None)


class QueryResponse(BaseModel):
    answer: str
    sources: list[dict]
    guardrail_flags: list[str]
    context_found: bool
    session_id: int | None = None


class ChatSessionCreate(BaseModel):
    title: str | None = Field(default="New Chat")


@router.post("/sessions")
async def create_session(
    request: ChatSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.auth.models import ChatSession
    session = ChatSession(user_id=current_user.id, title=request.title or "New Chat")
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"session_id": session.id, "title": session.title, "created_at": session.created_at.isoformat()}


@router.get("/sessions")
async def get_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.auth.models import ChatSession
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )
    return [{"session_id": s.id, "title": s.title, "created_at": s.created_at.isoformat()} for s in sessions]


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.auth.models import ChatSession
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()
    return {"status": "success"}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.auth.models import ChatSession
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    sorted_msgs = sorted(session.messages, key=lambda m: m.id)
    return [
        {
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
        }
        for msg in sorted_msgs
    ]


@router.post("/query", response_model=QueryResponse)
async def chat_query(
    request: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a question to the RAG pipeline.
    Applies input guardrails, RBAC-filtered retrieval, and output filtering.
    """
    import time
    start_time = time.time()
    guardrail_flags = []

    # ── Step 1: Input Guardrails ──────────────────────────────
    input_result = check_input(request.question)
    if input_result.blocked:
        # Log the blocked attempt
        latency_ms = int((time.time() - start_time) * 1000)
        _log_audit(db, current_user.id, request.question, "[BLOCKED]", "", input_result.reason, latency_ms)
        return QueryResponse(
            answer=f"⚠️ Query blocked: {input_result.reason}",
            sources=[],
            guardrail_flags=[input_result.reason],
            context_found=False,
            session_id=request.session_id,
        )

    if input_result.warnings:
        guardrail_flags.extend(input_result.warnings)

    # ── Step 2: Topic Guard ───────────────────────────────────
    if settings.enable_topic_guard:
        topic_result = check_topic(request.question)
        if topic_result.blocked:
            latency_ms = int((time.time() - start_time) * 1000)
            _log_audit(db, current_user.id, request.question, "[OFF-TOPIC]", "", topic_result.reason, latency_ms)
            return QueryResponse(
                answer=f"⚠️ {topic_result.reason}",
                sources=[],
                guardrail_flags=[topic_result.reason],
                context_found=False,
                session_id=request.session_id,
            )

    # ── Step 2.5: LLM Guardrail (LlamaGuard) ──────────────────
    if settings.enable_llamaguard:
        from app.guardrails.llamaguard import check_llamaguard
        llamaguard_blocked, llamaguard_reason = check_llamaguard(request.question)
        if llamaguard_blocked:
            latency_ms = int((time.time() - start_time) * 1000)
            _log_audit(db, current_user.id, request.question, "[BLOCKED - LLAMAGUARD]", "", llamaguard_reason, latency_ms)
            return QueryResponse(
                answer=f"⚠️ Query blocked: {llamaguard_reason}",
                sources=[],
                guardrail_flags=[llamaguard_reason],
                context_found=False,
                session_id=request.session_id,
            )

    # ── Fetch History if session_id passed ────────────────────
    history = None
    chat_session = None
    if request.session_id:
        from app.auth.models import ChatSession
        chat_session = (
            db.query(ChatSession)
            .filter(ChatSession.id == request.session_id, ChatSession.user_id == current_user.id)
            .first()
        )
        if chat_session:
            sorted_msgs = sorted(chat_session.messages, key=lambda m: m.id)
            history = [{"role": m.role, "content": m.content} for m in sorted_msgs]

    # ── Step 3: RAG Query with RBAC ───────────────────────────
    try:
        result = query_rag(
            question=request.question,
            clearance_level=current_user.role.clearance_level,
            department=request.department,
            history=history,
        )
    except Exception as e:
        error_msg = str(e)
        error_msg_lower = error_msg.lower()
        crash_keywords = [
            "cuda",
            "llama-server",
            "0xc0000409",
            "shared object",
            "overrun",
            "buffer",
            "stack"
        ]
        if any(term in error_msg_lower for term in crash_keywords):
            friendly_detail = (
                "Ollama/llama-server failed to initialize or crashed (likely a CUDA/GPU driver issue or buffer overrun).\n"
                "We have configured the application to automatically restart Ollama in CPU-only mode to prevent this.\n\n"
                "If you are still seeing this error, please try the following manual steps:\n"
                "1. Fully quit Ollama (right-click the Ollama icon in your Windows system tray and select 'Quit').\n"
                "2. Open a Command Prompt or PowerShell and set the CPU-only environment variables:\n"
                "   [System.Environment]::SetEnvironmentVariable('CUDA_VISIBLE_DEVICES', '-1', 'User')\n"
                "   [System.Environment]::SetEnvironmentVariable('OLLAMA_LLM_LIBRARY', 'cpu', 'User')\n"
                "3. Restart the application using: python scripts/run_all.py"
            )
            raise HTTPException(
                status_code=500,
                detail=f"{friendly_detail}\n\n[Original Error: {error_msg}]",
            )
        raise HTTPException(
            status_code=500,
            detail=f"RAG pipeline error: {error_msg}",
        )

    # ── Step 4: Output Guardrails ─────────────────────────────
    answer = result["answer"]
    if "guardrail_flags" in result:
        guardrail_flags.extend(result["guardrail_flags"])

    if settings.enable_pii_filter:
        output_result = filter_output(answer)
        answer = output_result.filtered_text
        if output_result.flags:
            guardrail_flags.extend(output_result.flags)

    # ── Save messages & update session title if applicable ────
    if chat_session:
        from app.auth.models import ChatMessage
        db.add(ChatMessage(session_id=chat_session.id, role="user", content=request.question))
        db.add(ChatMessage(session_id=chat_session.id, role="assistant", content=answer))
        
        # If title is default, set to first question excerpt
        if chat_session.title == "New Chat":
            excerpt = request.question.strip()
            if len(excerpt) > 40:
                excerpt = excerpt[:37] + "..."
            chat_session.title = excerpt
        
        db.commit()

    # ── Step 5: Audit Log ─────────────────────────────────────
    latency_ms = int((time.time() - start_time) * 1000)
    _log_audit(
        db,
        current_user.id,
        request.question,
        answer[:500],
        json.dumps(result["sources"]),
        json.dumps(guardrail_flags),
        latency_ms,
    )

    return QueryResponse(
        answer=answer,
        sources=result["sources"],
        guardrail_flags=guardrail_flags,
        context_found=result["context_found"],
        session_id=request.session_id,
    )


@router.get("/history")
async def get_chat_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current user's query history.
    """
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == current_user.id)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": log.id,
            "query": log.query,
            "response_summary": log.response_summary,
            "timestamp": log.timestamp.isoformat(),
            "guardrail_flags": log.guardrail_flags,
            "latency_ms": log.latency_ms,
        }
        for log in logs
    ]


@router.get("/admin/audit-logs")
async def get_admin_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Get system-wide audit logs for security monitoring.
    Only accessible by administrators.
    """
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": log.id,
            "username": log.user.username if log.user else "Unknown",
            "query": log.query,
            "response_summary": log.response_summary,
            "timestamp": log.timestamp.isoformat(),
            "guardrail_flags": log.guardrail_flags,
            "latency_ms": log.latency_ms,
        }
        for log in logs
    ]


def _log_audit(
    db: Session,
    user_id: int,
    query: str,
    response_summary: str,
    sources: str,
    flags: str,
    latency_ms: int = 0,
):
    """Write an audit log entry."""
    log = AuditLog(
        user_id=user_id,
        query=query,
        response_summary=response_summary,
        sources_accessed=sources,
        guardrail_flags=flags,
        latency_ms=latency_ms,
    )
    db.add(log)
    db.commit()
