"""
LangChain RAG chain assembly.
Builds a per-request chain with RBAC-filtered retrieval.

Performance optimizations:
- Single retrieval pass (no double-invocation)
- In-memory LRU cache for repeated queries
- Constrained LLM output length for faster CPU inference
"""
import hashlib
from functools import lru_cache

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from app.config import settings
from app.rag.retriever import RBACRetriever
from app.rag.prompts import SYSTEM_PROMPT, USER_PROMPT

# ── Singleton LLM instance (reused across requests) ─────────
_llm_instance = None


def get_llm() -> ChatOllama:
    """Get or create a singleton Ollama LLM instance with optimized settings."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatOllama(
            model=settings.ollama_llm_model,
            base_url=settings.ollama_base_url,
            temperature=0.1,       # Low temperature for factual responses
            num_ctx=2048,          # Smaller context window = faster processing
            num_predict=512,       # Cap output length to prevent runaway generation
        )
    return _llm_instance


# ── Response cache ───────────────────────────────────────────
# Caches (question, clearance, department) -> full response dict
# Evicts LRU after 128 entries to bound memory usage
_response_cache: dict[str, dict] = {}
_CACHE_MAX = 128


def _cache_key(question: str, clearance_level: int, department: str | None) -> str:
    """Create a deterministic cache key from query parameters."""
    raw = f"{question.strip().lower()}|{clearance_level}|{department or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_get(key: str) -> dict | None:
    return _response_cache.get(key)


def _cache_put(key: str, value: dict) -> None:
    if len(_response_cache) >= _CACHE_MAX:
        # Evict the oldest entry (first inserted)
        oldest = next(iter(_response_cache))
        del _response_cache[oldest]
    _response_cache[key] = value


def format_docs(docs) -> str:
    """Format retrieved documents into a single context string."""
    if not docs:
        return "No relevant documents found."

    formatted = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "Unknown")
        page = doc.metadata.get("page", "")
        page_info = f" (Page {page})" if page else ""
        formatted.append(f"[Document {i}: {source}{page_info}]\n{doc.page_content}")

    return "\n\n---\n\n".join(formatted)


def query_rag(question: str, clearance_level: int, department: str | None = None, history: list[dict] = None) -> dict:
    """
    Execute a RAG query with RBAC filtering and multi-turn history rewriting.

    Performance: retrieves documents ONCE and passes them directly to the
    LLM prompt instead of running the retriever a second time through the
    LangChain chain.  Also caches full responses for repeated questions.

    Returns:
        Dict with 'answer', 'sources', and 'context_found' keys
    """
    # ── Check cache first ─────────────────────────────────────
    if history:
        history_hash = hashlib.md5(str(history).encode()).hexdigest()
        key = _cache_key(question + "|" + history_hash, clearance_level, department)
    else:
        key = _cache_key(question, clearance_level, department)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    # ── Step 0: Condense Question with History ────────────────
    standalone_question = question
    if history:
        # Build a concise history string
        formatted_history = []
        for msg in history[-5:]:  # Last 5 messages are sufficient
            role = "User" if msg.get("role") == "user" else "Assistant"
            formatted_history.append(f"{role}: {msg.get('content')}")
        chat_history_str = "\n".join(formatted_history)

        condense_prompt = ChatPromptTemplate.from_messages([
            ("system", "You rewrite follow-up questions to be standalone search queries."),
            ("human", (
                "Given the following conversation history and a follow-up question, "
                "rephrase the follow-up question to be a standalone question.\n"
                "Respond ONLY with the standalone question. Do not include any explanation or extra text.\n\n"
                "Chat History:\n{chat_history}\n"
                "Follow-up Question: {question}\n"
                "Standalone Question:"
            ))
        ])

        llm = get_llm()
        rewrite_chain = condense_prompt | llm | StrOutputParser()
        try:
            condensed = rewrite_chain.invoke({
                "chat_history": chat_history_str,
                "question": question,
            })
            if condensed and condensed.strip():
                # Avoid rewriting if LLM gives a meta-response or copies rules
                cleaned = condensed.strip()
                if not cleaned.startswith("User:") and not cleaned.startswith("Assistant:"):
                    standalone_question = cleaned
                    print(f"[*] Rewrote query '{question}' -> '{standalone_question}'")
        except Exception as e:
            print(f"[!] Query rewrite failed: {e}. Using original question.")

    # ── HyDE Generation ───────────────────────────────────────
    hyde_query = standalone_question
    if settings.enable_hyde:
        try:
            hyde_prompt = ChatPromptTemplate.from_messages([
                ("system", "You write a hypothetical passage answering the question to help with document search. Write a brief response based on what the document might say. Respond ONLY with the hypothetical passage. Keep it short."),
                ("human", "Question: {question}\nHypothetical Passage:")
            ])
            llm = get_llm()
            hyde_chain = hyde_prompt | llm | StrOutputParser()
            hypothetical_passage = hyde_chain.invoke({"question": standalone_question})
            if hypothetical_passage and hypothetical_passage.strip():
                hyde_query = hypothetical_passage.strip()
                print(f"[*] HyDE generated: '{hyde_query[:100]}...'")
        except Exception as e:
            print(f"[!] HyDE generation failed: {e}. Using standalone question.")

    # ── Step 1: Retrieve once using HyDE query ────────────────
    retriever = RBACRetriever(
        clearance_level=clearance_level,
        department=department,
    )
    retrieved_docs = retriever.invoke(hyde_query)

    # ── Step 2: Format context ────────────────────────────────
    context_str = format_docs(retrieved_docs)

    # ── Step 3: Build prompt and invoke LLM ───────────────────
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ])

    llm = get_llm()
    chain = prompt | llm | StrOutputParser()

    answer = chain.invoke({
        "context": context_str,
        "question": standalone_question,
    })

    # ── Step 3.5: Self-RAG Hallucination Check ────────────────
    guardrail_flags = []
    if settings.enable_self_rag:
        try:
            check_prompt = ChatPromptTemplate.from_messages([
                ("system", "You verify if an answer is fully supported by the provided context. Reply with YES or NO only. Do not explain."),
                ("human", "Context:\n{context}\n\nAnswer to verify:\n{answer}\n\nIs the answer supported by context? YES/NO:")
            ])
            check_chain = check_prompt | llm | StrOutputParser()
            check_result = check_chain.invoke({
                "context": context_str,
                "answer": answer
            })
            if "NO" in check_result.upper():
                guardrail_flags.append("Potential Hallucination Detected")
                print(f"[!] Hallucination check failed. Result: {check_result}")
        except Exception as e:
            print(f"[!] Hallucination check failed: {e}")

    # ── Step 4: Extract sources ───────────────────────────────
    sources = []
    seen = set()
    for doc in retrieved_docs:
        source = doc.metadata.get("source", "Unknown")
        page = doc.metadata.get("page", "")
        doc_key = f"{source}:{page}"
        if doc_key not in seen:
            seen.add(doc_key)
            source_info = {"document": source}
            if page:
                source_info["page"] = page
            sources.append(source_info)

    result = {
        "answer": answer,
        "sources": sources,
        "context_found": len(retrieved_docs) > 0,
        "guardrail_flags": guardrail_flags,
    }

    # ── Cache the result ──────────────────────────────────────
    _cache_put(key, result)

    return result
