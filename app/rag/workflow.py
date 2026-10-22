"""LangGraph orchestration for direct and document-grounded questions."""
import re
from typing import Any, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.guardrails.topic_guard import CORPORATE_KEYWORDS
from app.rag.chain import get_llm, query_rag

INSUFFICIENT_CONTEXT_ANSWER = (
    "I don't have sufficient authorized information to answer this from the available documents."
)


class QueryState(TypedDict, total=False):
    question: str
    clearance_level: int
    department: str | None
    history: list[dict[str, str]] | None
    route: Literal["direct", "rag"]
    answer: str
    sources: list[dict[str, Any]]
    context_found: bool
    guardrail_flags: list[str]


_DIRECT_QUERY_PATTERNS = (
    r"^(hi|hello|hey|good morning|good afternoon|good evening)[!.\s]*$",
    r"^(thanks|thank you|thx)[!.\s]*$",
    r"^(who are you|what can you do|how are you)[?!.\s]*$",
)


def classify_query(question: str) -> Literal["direct", "rag"]:
    """Route conversational/general questions directly and company queries to RAG."""
    normalized = re.sub(r"\s+", " ", question.strip().lower())
    if any(re.fullmatch(pattern, normalized) for pattern in _DIRECT_QUERY_PATTERNS):
        return "direct"
    if any(keyword in normalized for keyword in CORPORATE_KEYWORDS):
        return "rag"
    return "direct"


def _route_node(state: QueryState) -> dict[str, Any]:
    return {"route": classify_query(state["question"])}


def _direct_response_node(state: QueryState) -> dict[str, Any]:
    response = get_llm().invoke([
        SystemMessage(content=(
            "You are a concise enterprise document assistant. Answer greetings and general "
            "assistant-capability questions naturally. Do not claim that a response is based "
            "on company documents unless document retrieval was used."
        )),
        HumanMessage(content=state["question"]),
    ])
    answer = response.content if hasattr(response, "content") else str(response)
    return {
        "answer": str(answer).strip(),
        "sources": [],
        "context_found": False,
        "guardrail_flags": [],
    }


def _rag_search_node(state: QueryState) -> dict[str, Any]:
    result = query_rag(
        question=state["question"],
        clearance_level=state["clearance_level"],
        department=state.get("department"),
        history=state.get("history"),
    )
    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "context_found": bool(result.get("context_found")),
        "guardrail_flags": result.get("guardrail_flags", []),
    }


def _validate_node(state: QueryState) -> dict[str, Any]:
    if state.get("route") == "rag" and not state.get("context_found", False):
        flags = list(state.get("guardrail_flags", []))
        if "Insufficient retrieved context" not in flags:
            flags.append("Insufficient retrieved context")
        return {
            "answer": INSUFFICIENT_CONTEXT_ANSWER,
            "sources": [],
            "guardrail_flags": flags,
        }
    return {}


def _select_route(state: QueryState) -> Literal["direct_response", "rag_search"]:
    return "direct_response" if state["route"] == "direct" else "rag_search"


def build_query_graph():
    """Build the query StateGraph with shared state and conditional routing."""
    graph = StateGraph(QueryState)
    graph.add_node("router", _route_node)
    graph.add_node("direct_response", _direct_response_node)
    graph.add_node("rag_search", _rag_search_node)
    graph.add_node("validation", _validate_node)
    graph.set_entry_point("router")
    graph.add_conditional_edges(
        "router",
        _select_route,
        {"direct_response": "direct_response", "rag_search": "rag_search"},
    )
    graph.add_edge("direct_response", "validation")
    graph.add_edge("rag_search", "validation")
    graph.add_edge("validation", END)
    return graph.compile()


query_graph = build_query_graph()


def run_query(
    question: str,
    clearance_level: int,
    department: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Run a query through the router and return the API-compatible result."""
    state = query_graph.invoke({
        "question": question,
        "clearance_level": clearance_level,
        "department": department,
        "history": history,
    })
    return {
        "answer": state["answer"],
        "sources": state.get("sources", []),
        "context_found": state.get("context_found", False),
        "guardrail_flags": state.get("guardrail_flags", []),
    }
