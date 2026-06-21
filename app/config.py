"""
Application configuration loaded from environment variables.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # Ollama (Local LLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "phi3:mini"
    ollama_embed_model: str = "nomic-embed-text"

    # Security
    jwt_secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # Database (PostgreSQL)
    database_url: str = "postgresql://postgres:1234@localhost:5432/enterprise_rag"

    # Storage
    chroma_persist_dir: str = str(BASE_DIR / "data" / "chroma_db")
    upload_dir: str = str(BASE_DIR / "data" / "uploads")

    # RAG Settings
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_top_k: int = 5
    retrieval_score_threshold: float = 0.25

    # Guardrails
    max_query_length: int = 2000
    enable_topic_guard: bool = True
    enable_pii_filter: bool = True
    enable_llamaguard: bool = False

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Check and secure the JWT secret key
import secrets
if settings.jwt_secret_key == "change-this-in-production":
    if os.getenv("ENV") == "production" or os.getenv("PRODUCTION") == "true":
        raise ValueError("CRITICAL SECURITY ERROR: You must configure a secure JWT_SECRET_KEY in production environment!")
    else:
        # Dev fallback: Auto-generate a secure random 256-bit key
        settings.jwt_secret_key = secrets.token_hex(32)
        print("[WARNING] Using default JWT secret. Auto-generated a secure temporary key for this session.")

# Ensure data directories exist
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.chroma_persist_dir, exist_ok=True)
