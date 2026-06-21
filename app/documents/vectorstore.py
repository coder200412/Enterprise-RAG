"""
ChromaDB vector store operations.
Handles embedding storage, retrieval, and RBAC-filtered similarity search.
Uses Ollama embeddings (nomic-embed-text) for local operation.

Performance optimizations:
- Query embedding cache (LRU) to avoid re-embedding repeated questions
- Batch embedding via Ollama's native /api/embed endpoint
- Singleton instances for embeddings and vectorstore
"""
from typing import Optional
import hashlib
import json
import urllib.request

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document as LCDocument

from app.config import settings

# Singleton embedding model and vector store
_embeddings = None
_vectorstore = None

# ── Query embedding cache ────────────────────────────────────
# Caches query_text -> embedding_vector to skip re-embedding
_embed_cache: dict[str, list[float]] = {}
_EMBED_CACHE_MAX = 256


class ConcurrentOllamaEmbeddings(OllamaEmbeddings):
    """OllamaEmbeddings subclass with batch embedding and query caching."""

    # Maximum texts per batch API call — keeps each HTTP request small enough
    # to complete well within timeout even on CPU-only Ollama.
    _BATCH_SIZE = 10
    _BATCH_TIMEOUT = 120  # seconds per sub-batch

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        url = f"{self.base_url.rstrip('/')}/api/embed"
        headers = {"Content-Type": "application/json"}
        all_embeddings: list[list[float]] = []

        # Process in small sub-batches to avoid timeout on large document sets
        for i in range(0, len(texts), self._BATCH_SIZE):
            batch = texts[i : i + self._BATCH_SIZE]
            payload = {"model": self.model, "input": batch}

            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self._BATCH_TIMEOUT) as response:
                    response_data = json.loads(response.read().decode("utf-8"))
                    batch_embeddings = response_data.get("embeddings", [])
                    all_embeddings.extend(batch_embeddings)
            except Exception as e:
                # Fallback to sequential embedding for this sub-batch only
                print(f"[!] Batch {i // self._BATCH_SIZE + 1} embedding failed: {e}. Falling back to sequential.")
                for text in batch:
                    all_embeddings.append(self.embed_query(text))

        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query with caching."""
        cache_key = hashlib.md5(text.strip().lower().encode()).hexdigest()

        if cache_key in _embed_cache:
            return _embed_cache[cache_key]

        result = super().embed_query(text)

        # Store in cache, evict oldest if full
        if len(_embed_cache) >= _EMBED_CACHE_MAX:
            oldest = next(iter(_embed_cache))
            del _embed_cache[oldest]
        _embed_cache[cache_key] = result

        return result


def get_embeddings() -> ConcurrentOllamaEmbeddings:
    """Get or create the Ollama embedding model instance."""
    global _embeddings
    if _embeddings is None:
        _embeddings = ConcurrentOllamaEmbeddings(
            model=settings.ollama_embed_model,
            base_url=settings.ollama_base_url,
        )
    return _embeddings


def get_vectorstore() -> Chroma:
    """Get or create the ChromaDB vector store instance."""
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = Chroma(
            collection_name="enterprise_docs",
            embedding_function=get_embeddings(),
            persist_directory=settings.chroma_persist_dir,
        )
    return _vectorstore


def add_documents(chunks: list[LCDocument]) -> int:
    """
    Embed and store document chunks in ChromaDB.
    Returns the number of chunks added.
    """
    if not chunks:
        return 0

    vs = get_vectorstore()
    vs.add_documents(chunks)
    return len(chunks)


def delete_document_chunks(doc_id: int) -> None:
    """
    Remove all chunks belonging to a specific document from the vector store.
    """
    vs = get_vectorstore()

    # Get all chunk IDs for this document
    results = vs.get(where={"doc_id": doc_id})
    if results and results["ids"]:
        vs.delete(ids=results["ids"])


import math
import re

class SimpleBM25:
    """A pure Python BM25 implementation to avoid external dependencies."""
    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.avg_doc_len = sum(len(doc) for doc in corpus) / max(self.corpus_size, 1)
        self.doc_lens = [len(doc) for doc in corpus]
        self.doc_freqs = {}
        self.idf = {}

        # Calculate doc frequencies
        for doc in corpus:
            seen = set(doc)
            for word in seen:
                self.doc_freqs[word] = self.doc_freqs.get(word, 0) + 1

        # Calculate IDF
        for word, freq in self.doc_freqs.items():
            self.idf[word] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)

    def get_scores(self, query: list[str], corpus: list[list[str]]) -> list[float]:
        scores = []
        for i, doc in enumerate(corpus):
            score = 0.0
            doc_len = self.doc_lens[i]
            word_counts = {}
            for word in doc:
                word_counts[word] = word_counts.get(word, 0) + 1

            for word in query:
                if word not in self.idf:
                    continue
                tf = word_counts.get(word, 0)
                denom = tf + self.k1 * (1.0 - self.b + self.b * doc_len / max(self.avg_doc_len, 1.0))
                score += self.idf[word] * tf * (self.k1 + 1.0) / denom
            scores.append(score)
        return scores


def tokenize(text: str) -> list[str]:
    """Tokenize helper to split text into lowercase words."""
    return re.findall(r"\b\w+\b", text.lower())


def similarity_search(
    query: str,
    clearance_level: int,
    k: Optional[int] = None,
    department: Optional[str] = None,
) -> list[LCDocument]:
    """
    Perform RBAC-filtered similarity search (Hybrid: Dense Vector + Sparse BM25).
    Only returns chunks that the user's clearance level can access, merged with RRF.

    Args:
        query: The search query text
        clearance_level: User's clearance level (1-3)
        k: Number of results to return
        department: Optional department filter

    Returns:
        List of matching documents the user is authorized to see
    """
    vs = get_vectorstore()
    top_k = k or settings.retrieval_top_k

    # Build the ChromaDB filter
    # Only return chunks where clearance_level <= user's clearance
    where_filter = {
        "clearance_level": {"$lte": clearance_level}
    }

    # Add optional department filter
    if department:
        where_filter = {
            "$and": [
                {"clearance_level": {"$lte": clearance_level}},
                {"department": department},
            ]
        }

    # ── 1. Dense (Vector) Search ──────────────────────────────
    dense_docs = []
    try:
        results_with_scores = vs.similarity_search_with_relevance_scores(
            query=query,
            k=top_k * 2,  # Fetch slightly more for ranking fusion
            filter=where_filter,
        )
        threshold = settings.retrieval_score_threshold
        dense_docs = [doc for doc, score in results_with_scores if score >= threshold]
    except Exception as e:
        print(f"[!] Vector similarity search failed: {e}")
        dense_docs = []

    # ── 2. Sparse (BM25) Search ───────────────────────────────
    sparse_docs = []
    try:
        all_chunks = vs.get(where=where_filter)
        if all_chunks and all_chunks["documents"]:
            docs_list = []
            for text, meta in zip(all_chunks["documents"], all_chunks["metadatas"]):
                docs_list.append(LCDocument(page_content=text, metadata=meta))

            tokenized_corpus = [tokenize(doc.page_content) for doc in docs_list]
            tokenized_query = tokenize(query)

            bm25 = SimpleBM25(tokenized_corpus)
            scores = bm25.get_scores(tokenized_query, tokenized_corpus)

            scored_docs = list(zip(docs_list, scores))
            # Keep only items with matching terms (score > 0)
            scored_docs = [sd for sd in scored_docs if sd[1] > 0.0]
            scored_docs.sort(key=lambda x: x[1], reverse=True)

            sparse_docs = [doc for doc, score in scored_docs[:top_k * 2]]
    except Exception as e:
        print(f"[!] BM25 sparse search failed: {e}")
        sparse_docs = []

    # ── 3. Reciprocal Rank Fusion (RRF) ───────────────────────
    if not dense_docs and not sparse_docs:
        return []

    def unpack_parents(docs: list[LCDocument]) -> list[LCDocument]:
        unpacked = []
        for doc in docs:
            d = LCDocument(page_content=doc.page_content, metadata=doc.metadata.copy())
            if "parent_content" in d.metadata:
                d.metadata["child_content"] = d.page_content
                d.page_content = d.metadata["parent_content"]
            unpacked.append(d)
        return unpacked

    if not sparse_docs:
        return unpack_parents(dense_docs[:top_k])
    elif not dense_docs:
        return unpack_parents(sparse_docs[:top_k])

    rrf_scores = {}
    doc_map = {}

    def doc_key(doc):
        return f"{doc.page_content}|{json.dumps(doc.metadata, sort_keys=True)}"

    for rank, doc in enumerate(dense_docs, 1):
        key = doc_key(doc)
        doc_map[key] = doc
        rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (60.0 + rank))

    for rank, doc in enumerate(sparse_docs, 1):
        key = doc_key(doc)
        doc_map[key] = doc
        rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (60.0 + rank))

    # Sort by RRF score descending
    sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)
    merged_docs = [doc_map[key] for key in sorted_keys[:top_k]]
    return unpack_parents(merged_docs)


def get_collection_stats() -> dict:
    """Get statistics about the vector store collection."""
    vs = get_vectorstore()
    try:
        collection = vs._collection
        return {
            "total_chunks": collection.count(),
            "name": collection.name,
        }
    except Exception:
        return {"total_chunks": 0, "name": "enterprise_docs"}
