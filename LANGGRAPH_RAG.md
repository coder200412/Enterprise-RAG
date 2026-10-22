# LangGraph Query Workflow

The `/chat/query` endpoint now runs through a LangGraph `StateGraph` while keeping
the existing FastAPI endpoint, guardrails, RBAC, hybrid retriever, vector store,
and response format intact.

## Architecture

The graph carries the question, clearance level, department, history, route,
answer, sources, and evidence status in shared state. Its router sends greetings
and general assistant questions to a direct-response node, and company/document
questions to the existing `query_rag` pipeline. Both paths pass through a
validation node. If document retrieval finds no context, the graph replaces the
generated answer with a fixed insufficient-evidence response and clears sources.

The API's existing input, topic, and LlamaGuard checks still run before graph
execution, and output filtering, session persistence, and audit logging remain
in place afterward.

## Installation

Install the project's dependencies in the active virtual environment:

```bash
pip install -r requirements.txt
```

## Run

Start the FastAPI application using the existing project command:

```bash
uvicorn app.main:app --reload
```

The workflow is invoked through the existing authenticated `POST /chat/query`
endpoint; no second server or separate vector store is introduced.

## Tests

Run the workflow tests:

```bash
pytest -q tests/test_query_workflow.py
```

Run the workflow tests together with the existing RAG tests:

```bash
pytest -q tests/test_query_workflow.py tests/test_rag.py
```
