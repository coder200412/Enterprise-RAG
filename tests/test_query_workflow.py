"""Tests for LangGraph query routing and evidence validation."""
from unittest.mock import MagicMock, patch

from app.rag.workflow import INSUFFICIENT_CONTEXT_ANSWER, classify_query, run_query


def test_greetings_and_assistant_faqs_route_directly():
    assert classify_query("Hello!") == "direct"
    assert classify_query("what can you do?") == "direct"
    assert classify_query("Thanks") == "direct"


def test_general_knowledge_questions_route_directly():
    assert classify_query("What is photosynthesis?") == "direct"


def test_document_questions_route_to_rag():
    assert classify_query("What is the annual leave policy?") == "rag"


@patch("app.rag.workflow.query_rag")
def test_rag_route_passes_authorization_and_query_context(mock_query_rag):
    mock_query_rag.return_value = {
        "answer": "The policy grants 20 days.",
        "sources": [{"document": "leave-policy.pdf", "page": 2}],
        "context_found": True,
        "guardrail_flags": [],
    }

    result = run_query(
        "What is the annual leave policy?",
        clearance_level=2,
        department="People",
        history=[{"role": "user", "content": "I am an employee."}],
    )

    mock_query_rag.assert_called_once_with(
        question="What is the annual leave policy?",
        clearance_level=2,
        department="People",
        history=[{"role": "user", "content": "I am an employee."}],
    )
    assert result["answer"] == "The policy grants 20 days."
    assert result["sources"] == [{"document": "leave-policy.pdf", "page": 2}]
    assert result["context_found"] is True


@patch("app.rag.workflow.query_rag")
def test_missing_context_returns_fixed_fallback_and_no_sources(mock_query_rag):
    mock_query_rag.return_value = {
        "answer": "Unsupported generated claim.",
        "sources": [],
        "context_found": False,
        "guardrail_flags": [],
    }

    result = run_query("What is the secret project name?", clearance_level=1)

    assert result["answer"] == INSUFFICIENT_CONTEXT_ANSWER
    assert result["sources"] == []
    assert result["context_found"] is False
    assert "Insufficient retrieved context" in result["guardrail_flags"]


@patch("app.rag.workflow.query_rag")
@patch("app.rag.workflow.get_llm")
def test_direct_route_skips_retrieval(mock_get_llm, mock_query_rag):
    mock_get_llm.return_value.invoke.return_value = MagicMock(content="Hello! How can I help?")

    result = run_query("Hello", clearance_level=1)

    mock_query_rag.assert_not_called()
    assert result["answer"] == "Hello! How can I help?"
    assert result["sources"] == []
