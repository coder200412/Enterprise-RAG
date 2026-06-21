"""
LLM-based guardrail utilizing LlamaGuard via Ollama.
"""
import urllib.request
import json
from app.config import settings

def check_llamaguard(query: str) -> tuple[bool, str]:
    """
    Check if a query violates safety guidelines using LlamaGuard via Ollama.
    Returns (blocked: bool, reason: str).
    """
    if not getattr(settings, "enable_llamaguard", False):
        return False, ""

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    headers = {"Content-Type": "application/json"}
    
    # LlamaGuard prompt context format
    payload = {
        "model": "llamaguard3:8b",
        "messages": [
            {"role": "user", "content": query}
        ],
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 15
        }
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            content = res_data.get("message", {}).get("content", "").strip().lower()

            if "unsafe" in content:
                # Extract classification category if provided
                lines = [line.strip() for line in content.split("\n") if line.strip()]
                reason = "Unsafe query detected by LlamaGuard"
                if len(lines) > 1:
                    reason = f"Unsafe content (LlamaGuard category: {lines[1]})"
                return True, reason

            return False, ""
    except Exception as e:
        print(f"[!] LlamaGuard check failed: {e}. Skipping check.")
        return False, ""
