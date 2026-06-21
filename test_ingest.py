"""Re-test ingestion after the batch-size fix."""
import time

# Clear any previous test chunks from the vector store
print("[0] Cleaning up previous test data...")
from app.documents.vectorstore import get_vectorstore
vs = get_vectorstore()
try:
    results = vs.get(where={"doc_id": 999})
    if results and results["ids"]:
        vs.delete(ids=results["ids"])
        print(f"    -> Deleted {len(results['ids'])} old test chunks")
except Exception:
    pass

# Force re-create singleton to pick up code changes
import app.documents.vectorstore as vs_mod
vs_mod._embeddings = None
vs_mod._vectorstore = None

print("[1] Processing file...")
t0 = time.time()
from app.documents.ingestion import process_file
chunks = process_file("iso27001.pdf", 999, 1, "general")
t1 = time.time()
print(f"    -> {len(chunks)} chunks in {t1 - t0:.1f}s")

print("[2] Adding to vector store (with sub-batch fix)...")
from app.documents.vectorstore import add_documents
count = add_documents(chunks)
t2 = time.time()
print(f"    -> {count} chunks added in {t2 - t1:.1f}s")

print(f"\n[TOTAL] {t2 - t0:.1f}s")
print(f"[SPEEDUP] Previous: 283.4s -> Now: {t2 - t0:.1f}s")
