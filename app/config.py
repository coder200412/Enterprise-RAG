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

    # Cloud model providers remain opt-in so local development keeps using Ollama.
    llm_provider: str = "ollama"
    embedding_provider: str = "ollama"
    oci_region: str = "us-chicago-1"
    oci_service_endpoint: str | None = None
    oci_compartment_id: str | None = None
    oci_auth_type: str = "API_KEY"
    oci_auth_profile: str = "DEFAULT"
    oci_auth_file_location: str | None = None
    oci_chat_model: str = "meta.llama-3.3-70b-instruct"
    oci_embedding_model: str = "cohere.embed-english-v3.0"
    cors_allowed_origins: str = "http://localhost:8501"

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

    # Advanced Suite Switches
    enable_hyde: bool = True
    enable_self_rag: bool = True
    enable_auto_tagging: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Require real secrets in production and generate only a development-only fallback.
import secrets
is_production = os.getenv("ENV", "").lower() == "production" or os.getenv("PRODUCTION", "").lower() == "true"
placeholder_secrets = {
    "change-this-in-production",
    "change-this-to-a-random-secret-key-in-production",
}
if is_production and (
    settings.jwt_secret_key in placeholder_secrets or len(settings.jwt_secret_key) < 32
):
    raise ValueError("CRITICAL SECURITY ERROR: Set JWT_SECRET_KEY to a unique random value of at least 32 characters.")
if is_production and any(
    marker in settings.database_url.upper()
    for marker in ("POSTGRES:1234@", "YOUR_PASSWORD", "REPLACE_WITH")
):
    raise ValueError("CRITICAL SECURITY ERROR: Set DATABASE_URL to the production database credentials.")
if not is_production and settings.jwt_secret_key in placeholder_secrets:
    settings.jwt_secret_key = secrets.token_hex(32)
    print("[WARNING] Using a temporary development JWT secret for this session.")

# Ensure data directories exist
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.chroma_persist_dir, exist_ok=True)
