"""
RBAC-filtered retriever for LangChain.
Wraps ChromaDB similarity search with clearance-level filtering.
"""
from typing import Any

from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document as LCDocument
from pydantic import Field

from app.documents.vectorstore import similarity_search


class RBACRetriever(BaseRetriever):
    """
    Custom LangChain retriever that enforces Role-Based Access Control.

    When querying, it only returns document chunks that the requesting
    user's clearance level is authorized to access.

    Example:
        - Employee (clearance=1) → only sees clearance=1 docs
        - Manager (clearance=2) → sees clearance 1 and 2 docs
        - Admin (clearance=3) → sees all docs
    """

    clearance_level: int = Field(default=1, description="User's clearance level")
    department: str | None = Field(default=None, description="Optional department filter")
    top_k: int | None = Field(default=None, description="Number of results")

    def _get_relevant_documents(self, query: str, **kwargs: Any) -> list[LCDocument]:
        """
        Retrieve documents filtered by the user's clearance level.
        This is where RBAC enforcement happens at the retrieval layer.
        """
        results = similarity_search(
            query=query,
            clearance_level=self.clearance_level,
            k=self.top_k,
            department=self.department,
        )
        return results
