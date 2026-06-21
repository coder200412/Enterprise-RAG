"""
Unit tests for the advanced features suite:
- Semantic Splitting & Chunking
- Parent-Child Retrieval Mapping
- Self-RAG Hallucination Checks
- DLP Output Redactions (DB connections, codenames, local IPs)
"""
from unittest.mock import MagicMock, patch
import pytest
from langchain_core.documents import Document as LCDocument

from app.documents.ingestion import semantic_split, chunk_documents
from app.documents.vectorstore import similarity_search
from app.rag.chain import query_rag
from app.guardrails.output_filter import filter_output


def test_semantic_split():
    text = (
        "# General Policy\n"
        "This is paragraph one of the general policy.\n"
        "It contains some general guidelines.\n\n"
        "## Section 1: Expenses\n"
        "This is paragraph two detailing travel expenses.\n"
        "All receipts must be submitted within 30 days."
    )
    
    # Using small size to force split at semantic boundaries
    chunks = semantic_split(text, chunk_size=100, chunk_overlap=10)
    assert len(chunks) >= 2
    assert "General Policy" in chunks[0]
    assert "Expenses" in chunks[1]


def test_parent_child_chunking():
    doc = LCDocument(
        page_content=(
            "This is a paragraph representing parent block number one. "
            "It is long enough to be split. Let's make sure it contains "
            "sufficient keywords to verify retrieval alignment.\n\n"
            "This is parent block number two. It represents a different policy. "
            "For example, remote work requirements and clearance rules."
        ),
        metadata={"source": "test_policy.pdf", "page": 1}
    )

    # Split: parent_size=1500, child_size=250.
    # The parent texts will be separated on \n\n.
    child_docs = chunk_documents([doc], chunk_size=1500)
    
    assert len(child_docs) > 0
    # Every child must have parent_content in metadata
    for child in child_docs:
        assert "parent_content" in child.metadata
        assert "test_policy.pdf" in child.metadata["source"]
        assert child.metadata["page"] == 1
        assert len(child.page_content) <= 250
        # The parent content must contain the child text
        assert child.page_content in child.metadata["parent_content"]


@patch("app.documents.vectorstore.get_vectorstore")
def test_parent_child_retrieval_unpacking(mock_get_vs):
    """Test that similarity_search replaces child text with parent_content."""
    mock_vs = MagicMock()
    mock_get_vs.return_value = mock_vs

    # Mock ChromaDB returning a child chunk with parent_content in metadata
    child_doc = LCDocument(
        page_content="child text",
        metadata={
            "doc_id": 1,
            "clearance_level": 1,
            "parent_content": "This is the full parent block content."
        }
    )
    mock_vs.similarity_search_with_relevance_scores.return_value = [
        (child_doc, 0.9)
    ]

    # Run search
    results = similarity_search("query text", clearance_level=1)
    
    assert len(results) == 1
    # Check that page_content is swapped with the parent_content
    assert results[0].page_content == "This is the full parent block content."
    assert results[0].metadata["child_content"] == "child text"


@patch("app.rag.chain.get_llm")
@patch("app.rag.chain.RBACRetriever")
def test_self_rag_hallucination_check(mock_retriever_cls, mock_get_llm):
    """Verify that hallucination triggers Potential Hallucination Detected flag."""
    # Setup mock retriever
    mock_retriever = MagicMock()
    mock_retriever.invoke.return_value = [
        LCDocument(page_content="Employees are allowed 20 vacation days per year.", metadata={"source": "hr.pdf"})
    ]
    mock_retriever_cls.return_value = mock_retriever

    # Mock ChatOllama responses:
    # 1. rewrite prompt (optional / skipped if no history)
    # 2. HyDE prompt (returns a hypothetical passage)
    # 3. main RAG generation chain (returns answer)
    # 4. self-rag hallucination check (returns NO)
    mock_llm = MagicMock()
    mock_get_llm.return_value = mock_llm

    # Patch the LangChain chain invoke for HyDE, RAG, and Self-RAG
    with patch("app.rag.chain.ChatPromptTemplate") as mock_prompt_cls:
        # We need three separate chains for:
        # - hyde_chain
        # - rag_chain
        # - check_chain
        mock_final_chain = MagicMock()
        
        # side_effect returns:
        # First call (HyDE): "Hypothetical passage text."
        # Second call (RAG): "Employees get 50 vacation days per year."
        # Third call (Self-RAG check): "NO"
        mock_final_chain.invoke.side_effect = [
            "Hypothetical passage text.",
            "Employees get 50 vacation days per year.",
            "NO"
        ]

        mock_intermediate = MagicMock()
        mock_prompt_cls.from_messages.return_value.__or__ = MagicMock(return_value=mock_intermediate)
        mock_intermediate.__or__ = MagicMock(return_value=mock_final_chain)

        # Execute query
        from app.rag.chain import _response_cache
        _response_cache.clear()
        
        response = query_rag(
            question="How many vacation days?",
            clearance_level=1
        )

        assert response["answer"] == "Employees get 50 vacation days per year."
        # Hallucination check failed, flag should be set
        assert "Potential Hallucination Detected" in response["guardrail_flags"]


def test_dlp_output_filtering():
    # 1. DB connection string redaction
    res1 = filter_output("The database string is postgresql://postgres:my-secret-pass123@192.168.1.50:5432/production_db")
    assert "[DB CONNECTION REDACTED]" in res1.filtered_text
    assert "my-secret-pass123" not in res1.filtered_text
    assert any("connection string" in f.lower() for f in res1.flags)

    # 2. Project Codenames redaction
    res2 = filter_output("Please proceed with Project Mercury and Project Falcon deployment.")
    assert "[CODENAME REDACTED]" in res2.filtered_text
    assert "Project Mercury" not in res2.filtered_text
    assert "Project Falcon" not in res2.filtered_text
    assert any("codename" in f.lower() for f in res2.flags)

    # 3. Local server IP redaction
    res3 = filter_output("Connect directly to the server at 192.168.1.10 or 10.0.0.5 for setups.")
    assert "[LOCAL IP REDACTED]" in res3.filtered_text
    assert "192.168.1.10" not in res3.filtered_text
    assert "10.0.0.5" not in res3.filtered_text
    assert any("local server ip" in f.lower() for f in res3.flags)
