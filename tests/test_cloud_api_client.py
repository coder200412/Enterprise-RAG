import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import config
from app.documents import vectorstore
from app.rag import chain
from streamlit_app.utils.api_client import HttpAPIClient


def test_http_client_sends_bearer_token_and_returns_json():
    client = HttpAPIClient.__new__(HttpAPIClient)
    client.base_url = "https://api.example.test"
    client.token = "test-token"
    response = Mock(ok=True)
    response.json.return_value = {"status": "healthy"}

    with patch("streamlit_app.utils.api_client.requests.request", return_value=response) as request:
        result = client.health_check()

    assert result == {"status": "healthy"}
    request.assert_called_once_with(
        "GET",
        "https://api.example.test/health",
        headers={"Authorization": "Bearer test-token"},
        timeout=60,
    )


def test_http_client_routes_chat_to_real_api():
    client = HttpAPIClient.__new__(HttpAPIClient)
    client.base_url = "http://api:8000"
    client.token = None
    response = Mock(ok=True)
    response.json.return_value = {"answer": "grounded", "sources": []}

    with patch("streamlit_app.utils.api_client.requests.request", return_value=response) as request:
        result = client.query("What is our policy?", department="HR", session_id=4)

    assert result["answer"] == "grounded"
    request.assert_called_once_with(
        "POST",
        "http://api:8000/chat/query",
        headers={},
        timeout=60,
        json={"question": "What is our policy?", "department": "HR", "session_id": 4},
    )


def test_oci_chat_provider_uses_instance_principal_without_key_file(monkeypatch):
    monkeypatch.setattr(config.settings, "llm_provider", "oci")
    monkeypatch.setattr(config.settings, "oci_compartment_id", "ocid1.compartment.test")
    monkeypatch.setattr(config.settings, "oci_auth_type", "INSTANCE_PRINCIPAL")
    monkeypatch.setattr(chain, "_llm_instance", None)
    fake_oci = SimpleNamespace(ChatOCIGenAI=lambda **kwargs: kwargs)
    monkeypatch.setitem(sys.modules, "langchain_oci", fake_oci)

    model = chain.get_llm()

    assert model["model_id"] == config.settings.oci_chat_model
    assert model["auth_type"] == "INSTANCE_PRINCIPAL"
    assert "auth_profile" not in model
    assert "auth_file_location" not in model


def test_oci_embedding_provider_uses_the_shared_model_configuration(monkeypatch):
    monkeypatch.setattr(config.settings, "embedding_provider", "oci")
    monkeypatch.setattr(config.settings, "oci_compartment_id", "ocid1.compartment.test")
    monkeypatch.setattr(config.settings, "oci_auth_type", "INSTANCE_PRINCIPAL")
    monkeypatch.setattr(vectorstore, "_embeddings", None)
    fake_oci = SimpleNamespace(OCIGenAIEmbeddings=lambda **kwargs: kwargs)
    monkeypatch.setitem(sys.modules, "langchain_oci", fake_oci)

    embeddings = vectorstore.get_embeddings()

    assert embeddings["model_id"] == config.settings.oci_embedding_model
    assert embeddings["auth_type"] == "INSTANCE_PRINCIPAL"
