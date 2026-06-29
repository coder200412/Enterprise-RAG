"""
Cross-Encoder re-ranking module to optimize document retrieval.
Uses the HuggingFace CrossEncoder model to re-evaluate similarity.
"""
from typing import Optional
from langchain_core.documents import Document as LCDocument

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None


class BGECrossEncoderReranker:
    """Enterprise-grade CrossEncoder Reranker using HuggingFace sentence-transformers."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.enabled = CrossEncoder is not None
        self.model_name = model_name
        self.model = None
        if self.enabled:
            print("[*] BGE CrossEncoder configured for lazy-loading.")
        else:
            print("[*] sentence-transformers not installed. Re-ranking is bypassed.")

    def load_model(self):
        """Perform lazy-loading of the model."""
        if self.enabled and self.model is None:
            try:
                print(f"[*] Loading CrossEncoder reranker model '{self.model_name}'...")
                self.model = CrossEncoder(self.model_name)
                print("[OK] CrossEncoder model ready!")
            except Exception as e:
                print(f"[!] Error loading CrossEncoder model: {e}")
                self.enabled = False

    def rerank(self, query: str, documents: list[LCDocument], top_k: int = 5) -> list[LCDocument]:
        """
        Re-evaluate the relevance of retrieved documents using a Cross-Encoder.
        
        Args:
            query: The search query
            documents: List of retrieved documents to re-rank
            top_k: Number of documents to return
        """
        if not documents:
            return []

        if not self.enabled:
            # Bypass and return top_k of the original documents directly
            return documents[:top_k]

        try:
            self.load_model()
            if self.model is None:
                return documents[:top_k]

            # Construct query-passage pairs
            pairs = [[query, doc.page_content] for doc in documents]
            
            # Predict similarity scores (higher is more relevant)
            scores = self.model.predict(pairs)
            
            # Pair documents with their calculated scores
            doc_scores = list(zip(documents, scores))
            
            # Sort documents descending by score
            doc_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Attach BGE score to metadata for transparency and display
            reranked_docs = []
            for doc, score in doc_scores[:top_k]:
                doc.metadata["rerank_score"] = float(score)
                reranked_docs.append(doc)

            return reranked_docs

        except Exception as e:
            print(f"[!] Re-ranking failed: {e}. Falling back to default order.")
            return documents[:top_k]
