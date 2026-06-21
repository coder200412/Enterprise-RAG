"""
Unit tests for the corporate RAG core feature enhancements:
- Hybrid Search (BM25 + Dense RRF)
- Chat Session & Message storage
- Async Ingestion task
"""
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document as LCDocument

from app.documents.vectorstore import SimpleBM25, tokenize, similarity_search
from app.documents.router import ingest_document_task
from app.auth.models import ChatSession, ChatMessage


def test_bm25_tokenization():
    text = "The quick brown fox, jumps over the lazy dog!"
    tokens = tokenize(text)
    assert tokens == ["the", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog"]


def test_simple_bm25_scoring():
    corpus = [
        ["hr", "holiday", "policy", "employee"],
        ["manager", "expense", "approval", "finance"],
        ["confidential", "project", "mercury", "blueprint"]
    ]
    bm25 = SimpleBM25(corpus)
    
    # Check idf calculated
    assert "hr" in bm25.idf
    assert "finance" in bm25.idf
    
    # Query matching first doc
    scores1 = bm25.get_scores(["holiday"], corpus)
    assert scores1[0] > 0.0
    assert scores1[1] == 0.0
    assert scores1[2] == 0.0
    
    # Query matching second doc
    scores2 = bm25.get_scores(["expense", "approval"], corpus)
    assert scores2[1] > 0.0
    assert scores2[0] == 0.0


@patch("app.documents.vectorstore.get_vectorstore")
def test_hybrid_search_rrf_merging(mock_get_vs):
    """Test that dense and sparse results are merged correctly using RRF."""
    mock_vs = MagicMock()
    mock_get_vs.return_value = mock_vs

    # 1. Setup mock dense results
    doc_dense = LCDocument(page_content="Holiday allowance is 25 days.", metadata={"doc_id": 1, "clearance_level": 1})
    mock_vs.similarity_search_with_relevance_scores.return_value = [
        (doc_dense, 0.8)
    ]

    # 2. Setup mock all chunks (for sparse BM25 index)
    mock_vs.get.return_value = {
        "documents": [
            "Holiday allowance is 25 days.",
            "Managers expense limit is $5000."
        ],
        "metadatas": [
            {"doc_id": 1, "clearance_level": 1},
            {"doc_id": 2, "clearance_level": 2}
        ]
    }

    # Execute search
    results = similarity_search("holiday allowance", clearance_level=2)
    
    # Should contain the holiday allowance document first due to top ranking in both dense and sparse
    assert len(results) > 0
    assert "Holiday allowance" in results[0].page_content


@patch("app.documents.router.SessionLocal")
@patch("app.documents.router.process_file")
@patch("app.documents.router.add_documents")
def test_ingest_document_task_success(mock_add_docs, mock_proc_file, mock_session_local):
    """Verify that ingest_document_task updates status to ready."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    
    mock_doc = MagicMock()
    mock_doc.id = 123
    mock_doc.status = "processing"
    
    # mock query filter
    mock_db.query.return_value.filter.return_value.first.return_value = mock_doc
    
    # mock parsing and chunk addition
    mock_proc_file.return_value = [LCDocument(page_content="chunk")]
    mock_add_docs.return_value = 1
    
    ingest_document_task(123, "test.pdf", 1, "general")
    
    assert mock_doc.status == "ready"
    assert mock_doc.chunk_count == 1
    mock_db.commit.assert_called()


@patch("app.documents.router.SessionLocal")
@patch("app.documents.router.process_file")
def test_ingest_document_task_error(mock_proc_file, mock_session_local):
    """Verify that ingest_document_task sets status to error on failure."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    
    mock_doc = MagicMock()
    mock_doc.id = 123
    mock_doc.status = "processing"
    
    mock_db.query.return_value.filter.return_value.first.return_value = mock_doc
    
    # Raise error
    mock_proc_file.side_effect = Exception("Parsing error")
    
    ingest_document_task(123, "test.pdf", 1, "general")
    
    assert mock_doc.status == "error"
    assert "Parsing error" in mock_doc.error_message
    mock_db.commit.assert_called()
