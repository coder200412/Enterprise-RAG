# Zero-Setup Streamlit Deployment Guide

We have updated the Streamlit frontend client ([api_client.py](file:///d:/reg%20project/streamlit_app/utils/api_client.py)) to run as an in-memory standalone app for your recruiter demo. 

It replicates all backend API features (authentication, role-based access control, document management, chat sessions, and audit logging) directly inside the Streamlit container using secure session state. This makes your portfolio demo **100% reliable, fast (no backend cold starts), and completely free to host 24/7**.

---

## Interactive Features Showcase for Recruiters

When recruiters log in using the demo credentials, they will experience a high-fidelity simulation of the entire RAG pipeline:
1. **Role-Based Access Control (RBAC)**:
   * Log in as **Employee** (`employee1` / `employee123`): Only the General document (`ISO27001_Compliance_Policy.pdf`) is visible. Querying about budget or salaries will return a security clearance block.
   * Log in as **Manager** (`manager1` / `manager123`): Can view and query general and financial documents (`Q3_Financial_Projections.xlsx`).
   * Log in as **Admin** (`admin` / `admin123`): Has full access to view, upload, delete, and query all documents, including confidential HR records.
2. **AI Guardrails**:
   * **Topic Guard**: Asking off-topic questions (e.g., "how to build a snake game" or "chocolate cake recipe") triggers an off-topic guardrail block.
   * **PII Filter**: Typing sensitive keywords (like social security numbers or credit cards) triggers a PII warning block.
3. **Audit Log Monitoring**:
   * Log in as **Admin** and navigate to the **Admin** panel to view real-time system logs. Every chat query, clearance check, security flag, and execution latency is tracked in a tabular audit monitor.
4. **Document Previewer**:
   * Click **Preview** on any document to see the in-memory parsed text preview (with citation highlights).

---

## How to Deploy Online (Free in 1 Minute)

1. **Push your code to GitHub**:
   Ensure you commit the modified files (specifically [streamlit_app/utils/api_client.py](file:///d:/reg%20project/streamlit_app/utils/api_client.py) and the frontend [requirements.txt](file:///d:/reg%20project/streamlit_app/requirements.txt)).
2. **Go to Streamlit Community Cloud**:
   * Sign in to [share.streamlit.io](https://share.streamlit.io/) using your GitHub account.
3. **Configure and Deploy**:
   * Click **New app**.
   * Select your repository, branch, and set the **Main file path** to:
     `streamlit_app/app.py`
   * Click **Advanced settings** (highly recommended):
     * Set the **Requirements file path** to:
       `streamlit_app/requirements.txt`
       *(This tells Streamlit Cloud to only install the light frontend libraries, preventing build timeout errors from compiling database compilers/Chroma).*
4. **Deploy!**
   * Streamlit will compile the application in less than 30 seconds. Your live url (e.g. `https://your-app-name.streamlit.app`) is now ready to add to your resume!

---

## Resume Showcase Tips

Include this project under your experience or projects section:

* **Title**: Standalone Enterprise RAG Assistant with RBAC & Guardrails
* **Core Tech**: Streamlit, Python, Session State Mocking, Regex PII Sanitizers, Semantic Tagging.
* **Key Bullet Points**:
  - **Security & Access Control**: Designed a role-based access control (RBAC) RAG assistant interface that filters available context and blocks queries below user clearance levels.
  - **Input/Output Guardrails**: Coded multi-layered safety guardrails including a Topic Guard (blocking off-topic LLM requests) and PII filter (scrubbing sensitive keywords).
  - **Audit Monitoring**: Built an administrative audit dashboard tracking user activity logs, latency, and security flags for real-time compliance monitoring.
  - **Interactive Portfolio**: Deployed a fully self-contained portfolio demo on Streamlit Community Cloud for recruitment review with seeded employee, manager, and administrator credentials.
