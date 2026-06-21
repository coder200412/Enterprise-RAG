"""
Document Management Page — Upload, view, and manage documents.
"""
import streamlit as st

st.set_page_config(page_title="Documents — Enterprise RAG", page_icon="📄", layout="wide")

from streamlit_app.components.auth import is_authenticated, render_login_form, get_api_client, get_user_info
from streamlit_app.components.sidebar import render_sidebar

if not is_authenticated():
    render_login_form()
    st.stop()

render_sidebar()

user = get_user_info()
role = user.get("role", {})
clearance = role.get("clearance_level", 1)
client = get_api_client()

st.markdown("## 📄 Document Management")
st.markdown("Upload and manage corporate documents. Documents are indexed and made searchable through the chat.")
st.markdown("---")

# ── Upload Section (Manager+ only) ──────────────────────────
if clearance >= 2:
    with st.expander("📤 Upload New Document", expanded=False):
        uploaded_file = st.file_uploader(
            "Choose a PDF or Excel file",
            type=["pdf", "xlsx", "xls"],
            help="Supported formats: PDF, Excel (.xlsx, .xls)"
        )

        col1, col2 = st.columns(2)
        with col1:
            doc_clearance = st.selectbox(
                "🔒 Clearance Level",
                options=[1, 2, 3],
                format_func=lambda x: {1: "1 — Employee (All staff)", 2: "2 — Manager (Confidential)", 3: "3 — Admin (Top Secret)"}[x],
                help="Set the minimum clearance level required to access this document"
            )
        with col2:
            department = st.text_input(
                "🏢 Department",
                value="general",
                help="Tag this document with a department for filtering"
            )

        if uploaded_file and st.button("🚀 Upload & Process", type="primary", use_container_width=True):
            progress_bar = st.progress(0, text="Preparing upload...")
            status_area = st.empty()

            try:
                # Stage 1: Validate file (10%)
                status_area.info("📋 **Step 1/5** — Validating file...")
                progress_bar.progress(10, text="10% — Validating file...")
                import time
                import urllib.request as _urllib_req
                file_size_mb = uploaded_file.size / (1024 * 1024)
                file_ext = uploaded_file.name.rsplit(".", 1)[-1].lower()
                if file_ext not in ("pdf", "xlsx", "xls"):
                    status_area.error(f"❌ Unsupported file type: .{file_ext}")
                    progress_bar.progress(0, text="Upload failed")
                    st.stop()

                # Check Ollama is running (prevents hanging at 30%)
                try:
                    with _urllib_req.urlopen("http://localhost:11434/", timeout=3):
                        pass
                except Exception:
                    progress_bar.progress(0, text="❌ Ollama not running")
                    status_area.error(
                        "❌ **Ollama is not running!** The embedding service at `localhost:11434` is unreachable.\n\n"
                        "**To fix this:**\n"
                        "1. Open a new terminal\n"
                        "2. Run: `set OLLAMA_LLM_LIBRARY=cpu` then `ollama serve`\n"
                        "3. Wait for Ollama to start, then try uploading again"
                    )
                    st.stop()
                time.sleep(0.3)

                # Stage 2: Upload & process on server (30%)
                # This is the BLOCKING call — the backend parses, chunks, and embeds
                status_area.warning(
                    f"⏳ **Step 2/5** — Uploading **{uploaded_file.name}** ({file_size_mb:.1f} MB) and processing on server...\n\n"
                    f"_This includes parsing, chunking, and creating embeddings. "
                    f"On CPU this can take **1–3 minutes** for large files. Please wait..._"
                )
                progress_bar.progress(30, text=f"30% — Processing on server (please wait)...")

                result = client.upload_document(uploaded_file, doc_clearance, department)

                # Stage 3: Parsing (50%) — already done on backend, update UI
                status_area.info(f"📖 **Step 3/5** — Document parsed successfully")
                progress_bar.progress(50, text="50% — Document parsed...")
                time.sleep(0.3)

                # Stage 4: Embedding (70%)
                chunk_count = result.get("chunk_count", 0)
                status_area.info(f"🔢 **Step 4/5** — Created {chunk_count} text chunks and embeddings")
                progress_bar.progress(70, text=f"70% — {chunk_count} chunks embedded...")
                time.sleep(0.3)

                # Stage 5: Indexing complete (90%)
                status_area.info("🗂️ **Step 5/5** — Indexed in vector database")
                progress_bar.progress(90, text="90% — Indexed in vector database...")
                time.sleep(0.3)

                # Done (100%)
                progress_bar.progress(100, text="100% — Complete! ✅")
                status_area.empty()
                st.success(
                    f"✅ **{result['filename']}** uploaded and processed successfully!\n\n"
                    f"- **Chunks created:** {chunk_count}\n"
                    f"- **Clearance level:** {doc_clearance}\n"
                    f"- **Department:** {department}\n"
                    f"- **Status:** {result.get('status', 'ready')}"
                )
                time.sleep(1)
                st.rerun()

            except Exception as e:
                error_msg = str(e)
                progress_bar.progress(0, text="❌ Upload failed")
                status_area.empty()
                st.error(f"❌ Upload failed: {error_msg}")
else:
    st.info("📝 You need **Manager** or higher access to upload documents.")

st.markdown("---")

# ── Document List ────────────────────────────────────────────
st.markdown("### 📋 Available Documents")
st.markdown(f"*Showing documents for your clearance level ({clearance}/3)*")

try:
    data = client.list_documents()
    documents = data.get("documents", [])

    if not documents:
        st.info("No documents available. Upload some documents to get started!")
    else:
        for doc in documents:
            clearance_badge = {1: "🟢 Employee", 2: "🟡 Manager", 3: "🔴 Admin"}.get(doc["clearance_level"], "⚪ Unknown")

            # Status config: (icon, label, progress_pct, color)
            status_config = {
                "ready":      ("✅", "Processed",  100, "#22c55e"),
                "processing": ("⏳", "Processing",  50, "#f59e0b"),
                "error":      ("❌", "Failed",       0, "#ef4444"),
            }
            s_icon, s_label, s_pct, s_color = status_config.get(doc["status"], ("❓", "Unknown", 0, "#888"))

            with st.container():
                col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 1, 1])

                with col1:
                    st.markdown(f"**📄 {doc['filename']}**")
                with col2:
                    st.markdown(f"🔒 {clearance_badge}")
                with col3:
                    st.markdown(f"🏢 {doc['department']}")
                with col4:
                    st.markdown(f"{s_icon} {s_label}")
                with col5:
                    if clearance >= 3:  # Admin can delete
                        if st.button("🗑️", key=f"del_{doc['id']}", help="Delete document"):
                            try:
                                client.delete_document(doc["id"])
                                st.success(f"Deleted {doc['filename']}")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))

                # Mini progress bar showing processing status
                bar_width = max(s_pct, 2)  # minimum visible width
                st.markdown(
                    f"""<div style="display:flex; align-items:center; gap:8px; margin: 4px 0 2px;">
                        <div style="flex:1; background:rgba(255,255,255,0.08); border-radius:6px; height:8px; overflow:hidden;">
                            <div style="width:{bar_width}%; height:100%; background:{s_color}; border-radius:6px; transition: width 0.5s;"></div>
                        </div>
                        <span style="color:{s_color}; font-size:0.75rem; font-weight:600; min-width:35px;">{s_pct}%</span>
                    </div>""",
                    unsafe_allow_html=True
                )
                st.markdown(f"<small style='color:#888'>Chunks: {doc['chunk_count']} | Uploaded: {doc['uploaded_at'][:10]}</small>", unsafe_allow_html=True)
                st.markdown("---")

except Exception as e:
    st.error(f"Failed to load documents: {str(e)}")

