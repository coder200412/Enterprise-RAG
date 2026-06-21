"""
Tests for the RAG pipeline and chain assembly.
"""
from unittest.mock import MagicMock, patch
import pytest
from langchain_core.documents import Document as LCDocument

from app.rag.chain import format_docs, query_rag, _response_cache, _cache_key, _cache_put


def test_format_docs_empty():
    assert format_docs([]) == "No relevant documents found."
    assert format_docs(None) == "No relevant documents found."


def test_format_docs_with_metadata():
    docs = [
        LCDocument(
            page_content="Policy line 1.",
            metadata={"source": "benefits.pdf", "page": 2}
        ),
        LCDocument(
            page_content="Policy line 2.",
            metadata={"source": "rules.pdf"}
        )
    ]

    formatted = format_docs(docs)

    assert "[Document 1: benefits.pdf (Page 2)]" in formatted
    assert "Policy line 1." in formatted
    assert "[Document 2: rules.pdf]" in formatted
    assert "Policy line 2." in formatted


@patch("app.rag.chain.get_llm")
@patch("app.rag.chain.RBACRetriever")
def test_query_rag_execution(mock_retriever_cls, mock_get_llm):
    """Test the full query_rag pipeline with mocked retriever and LLM."""
    _response_cache.clear()

    # Setup mock retriever
    mock_retriever = MagicMock()
    mock_docs = [
        LCDocument(page_content="Content A", metadata={"source": "docA.pdf", "page": 1}),
        LCDocument(page_content="Content B", metadata={"source": "docB.pdf"}),
        # Duplicate source to test dedup
        LCDocument(page_content="Content A page 2", metadata={"source": "docA.pdf", "page": 1}),
    ]
    mock_retriever.invoke.return_value = mock_docs
    mock_retriever_cls.return_value = mock_retriever

    # Mock LLM — the chain is: prompt | llm | parser
    # prompt.__or__(llm) => temp;  temp.__or__(parser) => final_chain
    mock_llm = MagicMock()
    mock_get_llm.return_value = mock_llm

    with patch("app.rag.chain.ChatPromptTemplate") as mock_prompt_cls:
        # Make the pipe chain resolve to a mock with invoke
        mock_final_chain = MagicMock()
        mock_final_chain.invoke.return_value = "This is the generated answer."

        # prompt | llm  => intermediate
        mock_intermediate = MagicMock()
        mock_prompt_cls.from_messages.return_value.__or__ = MagicMock(return_value=mock_intermediate)
        # intermediate | StrOutputParser()  => final_chain
        mock_intermediate.__or__ = MagicMock(return_value=mock_final_chain)

        response = query_rag(
            question="What is the policy?",
            clearance_level=2,
            department="Finance"
        )

    # Verify response structure
    assert response["answer"] == "This is the generated answer."
    assert response["context_found"] is True

    # Check deduplicated sources list
    expected_sources = [
        {"document": "docA.pdf", "page": 1},
        {"document": "docB.pdf"}
    ]
    assert response["sources"] == expected_sources

    mock_retriever.invoke.assert_called_once_with("What is the policy?")
    _response_cache.clear()


@patch("app.rag.chain.get_llm")
@patch("app.rag.chain.RBACRetriever")
def test_query_rag_no_context(mock_retriever_cls, mock_get_llm):
    """When no documents are retrieved, context_found should be False."""
    _response_cache.clear()

    mock_retriever = MagicMock()
    mock_retriever.invoke.return_value = []
    mock_retriever_cls.return_value = mock_retriever

    mock_llm = MagicMock()
    mock_get_llm.return_value = mock_llm

    with patch("app.rag.chain.ChatPromptTemplate") as mock_prompt_cls:
        mock_final_chain = MagicMock()
        mock_final_chain.invoke.return_value = "I don't have sufficient authorized information."

        mock_intermediate = MagicMock()
        mock_prompt_cls.from_messages.return_value.__or__ = MagicMock(return_value=mock_intermediate)
        mock_intermediate.__or__ = MagicMock(return_value=mock_final_chain)

        response = query_rag(
            question="What is the confidential project name?",
            clearance_level=1
        )

    assert response["answer"] == "I don't have sufficient authorized information."
    assert response["context_found"] is False
    assert len(response["sources"]) == 0
    _response_cache.clear()


def test_response_caching():
    """Test that repeated identical queries hit the cache."""
    _response_cache.clear()

    fake_result = {
        "answer": "Cached answer",
        "sources": [{"document": "test.pdf"}],
        "context_found": True,
    }

    # Manually populate cache
    key = _cache_key("test question", 2, None)
    _cache_put(key, fake_result)

    # query_rag should return the cached result without calling retriever/LLM
    response = query_rag("test question", clearance_level=2)
    assert response["answer"] == "Cached answer"
    assert response["sources"] == [{"document": "test.pdf"}]

    _response_cache.clear()
