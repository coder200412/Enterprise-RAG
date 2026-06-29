"""
FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database.session import init_db
from app.database.seed import seed_initial_data
from app.auth.router import router as auth_router
from app.documents.router import router as documents_router
from app.rag.router import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    print("[*] Initializing database...")
    init_db()
    print("[*] Seeding initial data...")
    seed_initial_data()
    print("[*] Seeding default documents...")
    from app.database.seed import seed_documents
    seed_documents()
    print("[OK] Enterprise RAG API ready!")
    yield
    # Shutdown
    print("[*] Shutting down...")


app = FastAPI(
    title="Enterprise RAG API",
    description="Corporate Document Assistant with RBAC & Guardrails",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(chat_router)


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    from app.documents.vectorstore import get_collection_stats
    stats = get_collection_stats()
    return {
        "status": "healthy",
        "service": "Enterprise RAG API",
        "vector_store": stats,
    }
