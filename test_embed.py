"""Quick test: embed a single string via Ollama and report timing."""
import json
import urllib.request
import time

start = time.time()
payload = json.dumps({"model": "nomic-embed-text", "input": ["test embedding"]}).encode()
req = urllib.request.Request(
    "http://localhost:11434/api/embed",
    data=payload,
    headers={"Content-Type": "application/json"},
)
r = urllib.request.urlopen(req, timeout=60)
data = json.loads(r.read().decode())
elapsed = time.time() - start
embs = data.get("embeddings", [])
print(f"Embedding OK in {elapsed:.1f}s, vector dim={len(embs[0]) if embs else 'NONE'}")

# Now test a batch of 10
start2 = time.time()
texts = [f"This is test chunk number {i} for embedding." for i in range(10)]
payload2 = json.dumps({"model": "nomic-embed-text", "input": texts}).encode()
req2 = urllib.request.Request(
    "http://localhost:11434/api/embed",
    data=payload2,
    headers={"Content-Type": "application/json"},
)
r2 = urllib.request.urlopen(req2, timeout=120)
data2 = json.loads(r2.read().decode())
elapsed2 = time.time() - start2
embs2 = data2.get("embeddings", [])
print(f"Batch of 10 OK in {elapsed2:.1f}s, got {len(embs2)} embeddings")
