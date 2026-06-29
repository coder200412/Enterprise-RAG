"""
HTTP client for communicating with the FastAPI backend.
Handles JWT token attachment and error formatting.
"""
import os
import requests
from typing import Optional


"""
In-Memory Mock HTTP client for Streamlit deployment.
Simulates all backend API calls using Streamlit session state.
This allows the frontend to run stand-alone online for recruiters,
showcasing all RBAC security levels, guardrail blocks, and audit logs.
"""
import streamlit as st
import datetime
from typing import Optional


"""
In-Memory Mock HTTP client for Streamlit deployment.
Simulates all backend API calls using Streamlit session state.
This allows the frontend to run stand-alone online for recruiters,
showcasing all RBAC security levels, guardrail blocks, and audit logs.
"""
import streamlit as st
import datetime
from typing import Optional


# Initialize mock data in session state if not already done
def init_mock_state():
    if "mock_users" not in st.session_state:
        st.session_state.mock_users = {
            1: {"id": 1, "username": "admin", "email": "admin@company.com", "role": {"name": "admin", "clearance_level": 3}},
            2: {"id": 2, "username": "manager1", "email": "manager1@company.com", "role": {"name": "manager", "clearance_level": 2}},
            3: {"id": 3, "username": "employee1", "email": "employee1@company.com", "role": {"name": "employee", "clearance_level": 1}}
        }
    
    if "mock_documents" not in st.session_state:
        st.session_state.mock_documents = [
            {
                "id": 1,
                "filename": "ISO27001_Compliance_Policy.pdf",
                "file_type": "pdf",
                "clearance_level": 1,
                "department": "general",
                "uploaded_by_username": "admin",
                "status": "ready",
                "version": 1,
                "chunk_count": 142,
                "tags": "Technical, Legal",
                "uploaded_at": "2026-06-29T10:00:00Z"
            },
            {
                "id": 2,
                "filename": "Q3_Financial_Projections.xlsx",
                "file_type": "xlsx",
                "clearance_level": 2,
                "department": "Finance",
                "uploaded_by_username": "manager1",
                "status": "ready",
                "version": 1,
                "chunk_count": 48,
                "tags": "Finance",
                "uploaded_at": "2026-06-29T11:30:00Z"
            },
            {
                "id": 3,
                "filename": "Employee_Performance_Reviews_2025.pdf",
                "file_type": "pdf",
                "clearance_level": 3,
                "department": "HR",
                "uploaded_by_username": "admin",
                "status": "ready",
                "version": 1,
                "chunk_count": 86,
                "tags": "HR, Draft",
                "uploaded_at": "2026-06-29T12:00:00Z"
            }
        ]
        
    if "mock_sessions" not in st.session_state:
        st.session_state.mock_sessions = [
            {"session_id": 1, "title": "ISO 27001 Security Standard", "created_at": "2026-06-29T14:00:00Z"}
        ]
        
    if "mock_messages" not in st.session_state:
        st.session_state.mock_messages = {
            1: [
                {"role": "user", "content": "What is the data retention policy under ISO 27001?"},
                {
                    "role": "assistant",
                    "content": "According to Section 8 of the ISO 27001 Compliance Policy, corporate data must be retained based on its classification level: standard communications are archived for 3 years, while financial logs and security trails are kept for 7 years. You can check the details in [ISO27001_Compliance_Policy.pdf: Page 14].",
                    "sources": [{"document": "ISO27001_Compliance_Policy.pdf", "page": 14, "rerank_score": 0.94}],
                    "flags": []
                }
            ]
        }
        
    if "mock_audit_logs" not in st.session_state:
        st.session_state.mock_audit_logs = [
            {
                "id": 1,
                "username": "admin",
                "query": "What is the data retention policy under ISO 27001?",
                "response_summary": "According to Section 8 of the ISO 27001 Compliance Policy, corporate data must be...",
                "timestamp": "2026-06-29T14:20:00Z",
                "guardrail_flags": "[]",
                "latency_ms": 120
            },
            {
                "id": 2,
                "username": "employee1",
                "query": "Show me the employee salary records for Q1",
                "response_summary": "⚠️ Query blocked: Insufficient clearance level for HR documents.",
                "timestamp": "2026-06-29T14:25:00Z",
                "guardrail_flags": "['RBAC Denial']",
                "latency_ms": 45
            }
        ]

    if "mock_feedbacks" not in st.session_state:
        st.session_state.mock_feedbacks = [
            {
                "id": 1,
                "timestamp": "2026-06-29T14:30:00Z",
                "query": "Who is the HR manager?",
                "answer": "The HR manager is Sarah Connor.",
                "score": -1,
                "correction": "Sarah Connor retired in May, the new HR manager is John Miller."
            }
        ]


class APIClient:
    """Mock API client performing operations in-memory via Streamlit session state."""

    def __init__(self):
        init_mock_state()
        self.token = st.session_state.get("token", None)

    def set_token(self, token: str):
        self.token = token

    # ── Auth Methods ──────────────────────────────────────────

    def login(self, username: str, password: str) -> dict:
        users_db = {
            "admin": {"id": 1, "password": "admin123"},
            "manager1": {"id": 2, "password": "manager123"},
            "employee1": {"id": 3, "password": "employee123"},
        }
        
        username_lower = username.strip().lower()
        if username_lower in users_db and password == users_db[username_lower]["password"]:
            user_id = users_db[username_lower]["id"]
            user_info = st.session_state.mock_users[user_id]
            st.session_state.token = f"mock-jwt-token-{username_lower}"
            self.token = st.session_state.token
            return {
                "access_token": self.token,
                "user": user_info
            }
        else:
            raise Exception("Invalid username or password. Use demo credentials shown below.")

    def get_me(self) -> dict:
        if not self.token:
            raise Exception("Not authenticated")
        username = self.token.replace("mock-jwt-token-", "")
        for u in st.session_state.mock_users.values():
            if u["username"] == username:
                return u
        raise Exception("User session not found")

    def logout(self) -> dict:
        self.token = None
        return {"status": "success"}

    def register_user(self, username: str, email: str, password: str, role: str) -> dict:
        user_ids = list(st.session_state.mock_users.keys())
        new_id = max(user_ids) + 1 if user_ids else 1
        clearance_levels = {"employee": 1, "manager": 2, "admin": 3}
        role_info = {
            "name": role,
            "clearance_level": clearance_levels.get(role.lower(), 1)
        }
        
        new_user = {
            "id": new_id,
            "username": username,
            "email": email,
            "role": role_info
        }
        st.session_state.mock_users[new_id] = new_user
        return new_user

    def list_users(self) -> list:
        return list(st.session_state.mock_users.values())

    def list_roles(self) -> list:
        return [
            {"id": 1, "name": "employee", "clearance_level": 1, "description": "Standard employee access."},
            {"id": 2, "name": "manager", "clearance_level": 2, "description": "Manager access. Can upload documents."},
            {"id": 3, "name": "admin", "clearance_level": 3, "description": "Administrator access. Full permissions."}
        ]

    def update_user_role(self, user_id: int, role_name: str) -> dict:
        user_id = int(user_id)
        if user_id in st.session_state.mock_users:
            clearance_levels = {"employee": 1, "manager": 2, "admin": 3}
            st.session_state.mock_users[user_id]["role"] = {
                "name": role_name,
                "clearance_level": clearance_levels.get(role_name.lower(), 1)
            }
            return st.session_state.mock_users[user_id]
        raise Exception("User not found")

    # ── Document Methods ──────────────────────────────────────

    def upload_document(self, file, clearance_level: int, department: str) -> dict:
        doc_ids = [d["id"] for d in st.session_state.mock_documents]
        new_id = max(doc_ids) + 1 if doc_ids else 1
        user_info = self.get_me()
        
        new_doc = {
            "id": new_id,
            "filename": file.name,
            "file_type": file.name.split(".")[-1] if "." in file.name else "pdf",
            "clearance_level": int(clearance_level),
            "department": department,
            "uploaded_by_username": user_info["username"],
            "status": "ready",
            "version": 1,
            "chunk_count": 34,
            "tags": "Uploaded, New",
            "uploaded_at": datetime.datetime.now().isoformat()
        }
        st.session_state.mock_documents.append(new_doc)
        return new_doc

    def list_documents(self) -> dict:
        user_info = self.get_me()
        user_clearance = user_info["role"]["clearance_level"]
        
        # Filter documents based on user clearance level
        visible_docs = [
            d for d in st.session_state.mock_documents
            if d["clearance_level"] <= user_clearance
        ]
        return {
            "documents": visible_docs,
            "total": len(visible_docs)
        }

    def get_document_page_preview(self, filename: str, page: int) -> dict:
        # Predefined preview pages
        previews = {
            "ISO27001_Compliance_Policy.pdf": {
                1: "ISO 27001 Compliance Statement: The company maintains information security policies approved by management...",
                14: "[Section 8: Data Retention] Standard communications and operational chat files are kept for 3 years. Financial records, compliance audit logs, and access database tables must be retained for 7 years on write-once, read-many (WORM) storage. All logs are encrypted under AES-256."
            },
            "Q3_Financial_Projections.xlsx": {
                1: "Columns: Department | Projected Budget | Actual Spent | Variance\nFinance | $450,000 | $412,000 | -$38,000\nHR | $120,000 | $124,500 | +$4,500\nEngineering | $1,200,000 | $1,180,000 | -$20,000\nSales & Ops | $850,000 | $892,000 | +$42,000\n\nQ3 Net Targets: Maintain margin of 24.5% across all centers."
            },
            "Employee_Performance_Reviews_2025.pdf": {
                1: "Confidential HR Records: Performance assessment metrics, salary revisions, and management reviews for corporate leadership teams. Restrict access to clearance Level 3 (Admin).",
                2: "[Page 2] Executive Feedback: admin (Rating: Exceeds Expectations). manager1 (Rating: Meets Expectations). employee1 (Rating: Meets Expectations). All salaries adjusted in alignment with standard Q1 performance criteria."
            }
        }
        
        content = previews.get(filename, {}).get(int(page), f"This is page {page} of the file '{filename}'. The system parsed the file in-memory and retrieved this text block.")
        return {
            "filename": filename,
            "page": page,
            "content": content
        }

    def delete_document(self, doc_id: int) -> dict:
        doc_id = int(doc_id)
        st.session_state.mock_documents = [
            d for d in st.session_state.mock_documents if d["id"] != doc_id
        ]
        return {"message": "Document deleted successfully"}

    # ── Chat Methods ──────────────────────────────────────────

    def query(self, question: str, department: str = None, session_id: int = None) -> dict:
        user_info = self.get_me()
        user_clearance = user_info["role"]["clearance_level"]
        username = user_info["username"]
        
        q_lower = question.lower()
        guardrail_flags = []
        sources = []
        
        # ── 1. Input Guardrails (PII filter simulation - Presidio Integration) ──────────
        pii_keywords = {
            "ssn": "US_SSN",
            "social security": "US_SSN",
            "credit card": "CREDIT_CARD",
            "passport": "PASSPORT"
        }
        
        detected_entity = None
        for key, val in pii_keywords.items():
            if key in q_lower:
                detected_entity = val
                break
                
        # Simulate active email or phone mapping in input
        import re
        has_email = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", question)
        has_phone = re.search(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", question)
        
        if detected_entity or has_email or has_phone:
            # Anonymization simulation
            anonymized_query = question
            pii_type = detected_entity or ("EMAIL_ADDRESS" if has_email else "PHONE_NUMBER")
            placeholder = f"<{pii_type}_1>"
            
            if has_email:
                anonymized_query = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", placeholder, anonymized_query)
            elif has_phone:
                anonymized_query = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", placeholder, anonymized_query)
            elif detected_entity:
                # Mock replace words
                anonymized_query = f"Query scrubbed under Presidio policy: What is standard security for user {placeholder}?"
            
            answer = (
                f"🛡️ **Microsoft Presidio Anonymizer Enabled**\n\n"
                f"• **Original Query**: `\"{question}\"`\n"
                f"• **Scrubbed Query (sent to LLM)**: `\"{anonymized_query}\"`\n\n"
                f"**[LLM Response]**: The corporate policy forbids querying raw personal identifier fields. "
                f"To protect privacy, the text has been scrubbed. For security clearance inquiries, "
                f"please contact compliance@company.com."
            )
            guardrail_flags.append("PII Scrubbed (Presidio)")
            self._log_audit(username, question, "Scrubbed PII input via Microsoft Presidio.", "['PII Anonymized']")
            return {
                "answer": answer,
                "sources": [],
                "guardrail_flags": guardrail_flags,
                "context_found": False
            }
            
        # ── 2. Topic Guardrail simulation ────────────────────────────────────────
        off_topic_keywords = ["recipe", "game", "movie", "football", "song", "joke", "code a snake game"]
        if any(ot in q_lower for ot in off_topic_keywords):
            answer = "⚠️ Query blocked: Off-topic query detected. The system is configured to only assist with corporate documents and operations. Non-work topics are restricted."
            guardrail_flags.append("Off-Topic Query Restricted")
            self._log_audit(username, question, answer[:100], "['Off-Topic Blocked']")
            return {
                "answer": answer,
                "sources": [],
                "guardrail_flags": guardrail_flags,
                "context_found": False
            }

        # ── 3. RBAC Filtering & Search simulation ────────────────────────────────
        # Employee asks about Admin or Manager content
        if "salary" in q_lower or "performance review" in q_lower or "feedback" in q_lower:
            if user_clearance < 3:
                answer = "⚠️ Access Denied: You do not have the required clearance level (Level 3 - Admin) to view employee performance reviews or salary adjustments."
                guardrail_flags.append("RBAC Clearance Restrict")
                self._log_audit(username, question, answer[:100], "['RBAC Denial']")
                return {
                    "answer": answer,
                    "sources": [],
                    "guardrail_flags": guardrail_flags,
                    "context_found": False
                }
            else:
                answer = "Based on Employee_Performance_Reviews_2025.pdf, executive reviews for 2025 indicate ratings: admin is rated 'Exceeds Expectations', and both manager1 and employee1 have met expectations. Salaries have been aligned with standard Q1 performance criteria."
                sources.append({"document": "Employee_Performance_Reviews_2025.pdf", "page": 2, "rerank_score": 0.96})

        elif "budget" in q_lower or "financial" in q_lower or "spending" in q_lower:
            if user_clearance < 2:
                answer = "⚠️ Access Denied: You do not have the required clearance level (Level 2 - Manager) to view company financial strategy or department budgets."
                guardrail_flags.append("RBAC Clearance Restrict")
                self._log_audit(username, question, answer[:100], "['RBAC Denial']")
                return {
                    "answer": answer,
                    "sources": [],
                    "guardrail_flags": guardrail_flags,
                    "context_found": False
                }
            else:
                answer = "According to Q3_Financial_Projections.xlsx, the department budgets and actuals are as follows:\n- **Finance**: Budget $450k, Spent $412k (saving $38k).\n- **Engineering**: Budget $1.2M, Spent $1.18M (saving $20k).\n- **HR**: Budget $120k, Spent $124.5k (over budget by $4.5k).\n- **Sales & Ops**: Budget $850k, Spent $892k (over budget by $42k).\nThe company net margin target remains at 24.5%."
                sources.append({"document": "Q3_Financial_Projections.xlsx", "page": 1, "rerank_score": 0.95})

        elif "retention" in q_lower or "iso" in q_lower or "compliance" in q_lower or "encryption" in q_lower:
            answer = "Section 8 of the ISO 27001 Compliance Policy documents that standard operational data and chat history are retained for 3 years. Financial records, compliance logs, and transactional databases must be kept for 7 years on write-once, read-many (WORM) storage. All backup databases are encrypted under AES-256."
            sources.append({"document": "ISO27001_Compliance_Policy.pdf", "page": 14, "rerank_score": 0.94})
            
        elif "owner" in q_lower or "belongs to" in q_lower or "who manages" in q_lower:
            # Simulate Graph RAG query for entity relationships
            answer = (
                "🕸️ **Graph RAG Relationship Retrieved**:\n"
                "- `Q3_Financial_Projections.xlsx` (Document) -> BELONGS_TO -> `Finance` (Department)\n"
                "- `Finance` (Department) -> MANAGED_BY -> `manager1` (User)\n\n"
                "According to the corporate database graph, the Q3 Financial Projections file is owned by the Finance Department and managed by manager1."
            )
            sources.append({"document": "Q3_Financial_Projections.xlsx", "page": 1, "rerank_score": 0.88})
            guardrail_flags.append("Graph RAG Traversal")
        else:
            answer = f"I've searched your authorized corporate documents. For general compliance, standard data is encrypted. The primary security reference is the ISO 27001 Compliance Policy. If you have specific questions about department budgets or performance, please use terms like 'budget' or 'performance review' (if authorized for your role)."
            sources.append({"document": "ISO27001_Compliance_Policy.pdf", "page": 1, "rerank_score": 0.72})

        # Save to mock message database
        if session_id and session_id in st.session_state.mock_messages:
            history = st.session_state.mock_messages[session_id]
            # Only append user message if it's not already the last one (prevents duplicate appends)
            if not history or history[-1]["role"] != "user" or history[-1]["content"] != question:
                history.append({"role": "user", "content": question})
            history.append({
                "role": "assistant",
                "content": answer,
                "sources": sources,
                "flags": guardrail_flags
            })

        self._log_audit(username, question, answer[:150], str(guardrail_flags))

        return {
            "answer": answer,
            "sources": sources,
            "guardrail_flags": guardrail_flags,
            "context_found": len(sources) > 0
        }

    def submit_feedback(self, query: str, answer: str, score: int, correction: str = None) -> dict:
        new_id = len(st.session_state.mock_feedbacks) + 1
        st.session_state.mock_feedbacks.insert(0, {
            "id": new_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "query": query,
            "answer": answer,
            "score": score,
            "correction": correction
        })
        return {"status": "success"}

    def get_feedbacks(self) -> list:
        return st.session_state.mock_feedbacks

    def _log_audit(self, username: str, query: str, response_summary: str, flags: str):
        new_id = len(st.session_state.mock_audit_logs) + 1
        st.session_state.mock_audit_logs.insert(0, {
            "id": new_id,
            "username": username,
            "query": query,
            "response_summary": response_summary,
            "timestamp": datetime.datetime.now().isoformat(),
            "guardrail_flags": flags,
            "latency_ms": 115 if "Denied" not in response_summary else 35
        })

    def get_chat_history(self, limit: int = 20) -> list:
        user_info = self.get_me()
        user_logs = [
            log for log in st.session_state.mock_audit_logs
            if log["username"] == user_info["username"]
        ]
        return user_logs[:limit]

    # ── Session Methods ───────────────────────────────────────

    def create_session(self, title: str = "New Chat") -> dict:
        new_id = len(st.session_state.mock_sessions) + 1
        new_sess = {
            "session_id": new_id,
            "title": title,
            "created_at": datetime.datetime.now().isoformat()
        }
        st.session_state.mock_sessions.insert(0, new_sess)
        st.session_state.mock_messages[new_id] = []
        return new_sess

    def list_sessions(self) -> list:
        return st.session_state.mock_sessions

    def delete_session(self, session_id: int) -> dict:
        session_id = int(session_id)
        st.session_state.mock_sessions = [
            s for s in st.session_state.mock_sessions if s["session_id"] != session_id
        ]
        if session_id in st.session_state.mock_messages:
            del st.session_state.mock_messages[session_id]
        return {"status": "success"}

    def delete_last_message(self, session_id: int) -> dict:
        session_id = int(session_id)
        if session_id in st.session_state.mock_messages:
            messages = st.session_state.mock_messages[session_id]
            if messages:
                # Remove last assistant-user pair if applicable, or just the last message
                last_msg = messages[-1]
                to_remove = 1
                if last_msg["role"] == "assistant" and len(messages) > 1:
                    prev_msg = messages[-2]
                    if prev_msg["role"] == "user":
                        to_remove = 2
                
                st.session_state.mock_messages[session_id] = messages[:-to_remove]
                return {"status": "success", "deleted_count": to_remove}
        return {"status": "success", "deleted_count": 0}

    def get_session_messages(self, session_id: int) -> list:
        session_id = int(session_id)
        return st.session_state.mock_messages.get(session_id, [])

    # ── Admin Methods ─────────────────────────────────────────

    def get_admin_audit_logs(self, limit: int = 50) -> list:
        return st.session_state.mock_audit_logs[:limit]

    # ── System Methods ────────────────────────────────────────

    def health_check(self) -> dict:
        return {
            "status": "healthy",
            "service": "Mock Enterprise RAG API",
            "vector_store": {"total_chunks": 276, "name": "mock_enterprise_docs"}
        }



