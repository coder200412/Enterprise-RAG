"""
HTTP client for communicating with the FastAPI backend.
Handles JWT token attachment and error formatting.
"""
import requests
from typing import Optional


API_BASE_URL = "http://localhost:8000"


class APIClient:
    """HTTP client wrapper for the Enterprise RAG API."""

    def __init__(self):
        self.token: Optional[str] = None
        self.base_url = API_BASE_URL

    def set_token(self, token: str):
        self.token = token

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _handle_response(self, response: requests.Response) -> dict:
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise Exception("Authentication failed. Please log in again.")
        elif response.status_code == 403:
            raise Exception("Access denied. Insufficient permissions.")
        elif response.status_code == 422:
            detail = response.json().get("detail", "Validation error")
            raise Exception(f"Invalid input: {detail}")
        else:
            detail = response.json().get("detail", response.text)
            raise Exception(f"API Error ({response.status_code}): {detail}")

    # ── Auth Methods ──────────────────────────────────────────

    def login(self, username: str, password: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/auth/login",
            json={"username": username, "password": password},
        )
        data = self._handle_response(resp)
        self.token = data["access_token"]
        return data

    def get_me(self) -> dict:
        resp = requests.get(f"{self.base_url}/auth/me", headers=self._headers())
        return self._handle_response(resp)

    def logout(self) -> dict:
        resp = requests.post(f"{self.base_url}/auth/logout", headers=self._headers())
        data = self._handle_response(resp)
        self.token = None
        return data

    def register_user(self, username: str, email: str, password: str, role: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/auth/register",
            json={
                "username": username,
                "email": email,
                "password": password,
                "role_name": role,
            },
            headers=self._headers(),
        )
        return self._handle_response(resp)

    def list_users(self) -> list:
        resp = requests.get(f"{self.base_url}/auth/users", headers=self._headers())
        return self._handle_response(resp)

    def list_roles(self) -> list:
        resp = requests.get(f"{self.base_url}/auth/roles", headers=self._headers())
        return self._handle_response(resp)

    def update_user_role(self, user_id: int, role_name: str) -> dict:
        resp = requests.put(
            f"{self.base_url}/auth/users/{user_id}/role",
            json={"role_name": role_name},
            headers=self._headers(),
        )
        return self._handle_response(resp)

    # ── Document Methods ──────────────────────────────────────

    def upload_document(self, file, clearance_level: int, department: str) -> dict:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        resp = requests.post(
            f"{self.base_url}/documents/upload",
            files={"file": (file.name, file, "application/octet-stream")},
            data={"clearance_level": clearance_level, "department": department},
            headers=headers,
            timeout=600,  # 10 minutes safety net — batch embedding is fast but very large files may need it
        )
        return self._handle_response(resp)

    def list_documents(self) -> dict:
        resp = requests.get(f"{self.base_url}/documents/", headers=self._headers())
        return self._handle_response(resp)

    def delete_document(self, doc_id: int) -> dict:
        resp = requests.delete(
            f"{self.base_url}/documents/{doc_id}", headers=self._headers()
        )
        return self._handle_response(resp)

    # ── Chat Methods ──────────────────────────────────────────

    def query(self, question: str, department: str = None, session_id: int = None) -> dict:
        payload = {"question": question}
        if department:
            payload["department"] = department
        if session_id:
            payload["session_id"] = session_id
        resp = requests.post(
            f"{self.base_url}/chat/query",
            json=payload,
            headers=self._headers(),
        )
        return self._handle_response(resp)

    def get_chat_history(self, limit: int = 20) -> list:
        resp = requests.get(
            f"{self.base_url}/chat/history?limit={limit}",
            headers=self._headers(),
        )
        return self._handle_response(resp)

    # ── Session Methods ───────────────────────────────────────

    def create_session(self, title: str = "New Chat") -> dict:
        resp = requests.post(
            f"{self.base_url}/chat/sessions",
            json={"title": title},
            headers=self._headers(),
        )
        return self._handle_response(resp)

    def list_sessions(self) -> list:
        resp = requests.get(
            f"{self.base_url}/chat/sessions",
            headers=self._headers(),
        )
        return self._handle_response(resp)

    def delete_session(self, session_id: int) -> dict:
        resp = requests.delete(
            f"{self.base_url}/chat/sessions/{session_id}",
            headers=self._headers(),
        )
        return self._handle_response(resp)

    def get_session_messages(self, session_id: int) -> list:
        resp = requests.get(
            f"{self.base_url}/chat/sessions/{session_id}/messages",
            headers=self._headers(),
        )
        return self._handle_response(resp)

    # ── Admin Methods ─────────────────────────────────────────

    def get_admin_audit_logs(self, limit: int = 50) -> list:
        resp = requests.get(
            f"{self.base_url}/chat/admin/audit-logs?limit={limit}",
            headers=self._headers(),
        )
        return self._handle_response(resp)

    # ── System Methods ────────────────────────────────────────

    def health_check(self) -> dict:
        resp = requests.get(f"{self.base_url}/health")
        return self._handle_response(resp)
