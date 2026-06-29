"""
Chat Page — Interact with the RAG-powered document assistant.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import streamlit as st

st.set_page_config(page_title="Chat — Enterprise RAG", page_icon="💬", layout="wide")

from streamlit_app.components.auth import is_authenticated, render_login_form, get_api_client
from streamlit_app.components.sidebar import render_sidebar
from streamlit_app.components.chat_ui import render_message

if not is_authenticated():
    render_login_form()
    st.stop()

render_sidebar()

client = get_api_client()

# ── Session Management Sidebar ───────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("### 💬 Chat Sessions")

# Initialize session state variables
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# Fetch active sessions
try:
    sessions = client.list_sessions()
except Exception as e:
    sessions = []
    st.sidebar.error(f"Could not load sessions: {e}")

# "New Chat" button
if st.sidebar.button("➕ New Chat", use_container_width=True):
    try:
        new_sess = client.create_session()
        st.session_state.current_session_id = new_sess["session_id"]
        st.session_state.chat_messages = []
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Error creating chat: {e}")

# Render session items
if sessions:
    st.sidebar.markdown("Recent conversations:")
    for sess in sessions:
        col_btn, col_del = st.sidebar.columns([4, 1])

        # Highlight active session
        btn_type = "primary" if st.session_state.current_session_id == sess["session_id"] else "secondary"

        with col_btn:
            if st.button(sess["title"], key=f"sess_{sess['session_id']}", use_container_width=True, type=btn_type):
                st.session_state.current_session_id = sess["session_id"]
                # Load messages
                try:
                    msgs = client.get_session_messages(sess["session_id"])
                    st.session_state.chat_messages = msgs
                except Exception:
                    st.session_state.chat_messages = []
                st.rerun()

        with col_del:
            if st.button("🗑️", key=f"del_{sess['session_id']}", use_container_width=True):
                try:
                    client.delete_session(sess["session_id"])
                    if st.session_state.current_session_id == sess["session_id"]:
                        st.session_state.current_session_id = None
                        st.session_state.chat_messages = []
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Error: {e}")
else:
    st.sidebar.caption("No recent conversations.")

# If no session selected, select the first one or auto-create one
if st.session_state.current_session_id is None and sessions:
    st.session_state.current_session_id = sessions[0]["session_id"]
    try:
        st.session_state.chat_messages = client.get_session_messages(sessions[0]["session_id"])
    except Exception:
        st.session_state.chat_messages = []
    st.rerun()

# Show preview sidebar if active
preview_active = "preview_data" in st.session_state and st.session_state.preview_data is not None

if preview_active:
    col_chat, col_preview = st.columns([2, 1])
else:
    col_chat, col_preview = st.columns([1, 0.01])

with col_chat:
    st.markdown("## 💬 Document Chat")
    st.markdown("Ask questions about company documents. Your access level determines what information you can see.")
    st.markdown("---")

    # Render active session messages
    if st.session_state.chat_messages:
        for idx, msg in enumerate(st.session_state.chat_messages):
            render_message(
                role=msg["role"],
                content=msg["content"],
                sources=msg.get("sources"),
                flags=msg.get("flags"),
            )
            
            # Render feedback buttons for assistant messages
            if msg["role"] == "assistant" and "blocked" not in msg["content"].lower() and "denied" not in msg["content"].lower():
                col_up, col_down, _ = st.columns([1.5, 1.5, 7])
                
                with col_up:
                    if st.button("👍 Good", key=f"up_{idx}", use_container_width=True):
                        # Find the preceding user query
                        user_query = st.session_state.chat_messages[idx-1]["content"] if idx > 0 else "N/A"
                        client.submit_feedback(user_query, msg["content"], 1)
                        st.toast("Thank you for your feedback!", icon="👍")
                        
                with col_down:
                    if st.button("👎 Poor", key=f"down_{idx}", use_container_width=True):
                        st.session_state[f"show_correction_{idx}"] = True
                        st.rerun()
                        
                # Correction input form
                if st.session_state.get(f"show_correction_{idx}", False):
                    with st.form(key=f"correction_form_{idx}"):
                        correction = st.text_area("Suggest a corrected answer for this query:", placeholder="Type what the correct answer should be...")
                        submit_col, cancel_col = st.columns([2, 8])
                        with submit_col:
                            submitted = st.form_submit_button("Submit")
                        if submitted:
                            user_query = st.session_state.chat_messages[idx-1]["content"] if idx > 0 else "N/A"
                            client.submit_feedback(user_query, msg["content"], -1, correction)
                            st.session_state[f"show_correction_{idx}"] = False
                            st.toast("Correction recorded!", icon="✅")
                            st.rerun()

    else:
        st.info("Start a conversation by typing your question below.")

    # Chat input
    if prompt := st.chat_input("Ask a question about company documents..."):
        # If no session active, auto-create one first
        if st.session_state.current_session_id is None:
            try:
                new_sess = client.create_session()
                st.session_state.current_session_id = new_sess["session_id"]
            except Exception as e:
                st.error(f"Failed to create chat session: {e}")
                st.stop()

        # Display user message immediately
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        render_message("user", prompt)

        # Query the RAG API
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Searching authorized documents..."):
                try:
                    result = client.query(prompt, session_id=st.session_state.current_session_id)

                    answer = result.get("answer", "No response received.")
                    sources = result.get("sources", [])
                    flags = result.get("guardrail_flags", [])

                    # Display the answer
                    st.markdown(answer)

                    # Show sources
                    if sources:
                        with st.expander("📄 Sources", expanded=False):
                            for src in sources:
                                doc_name = src.get("document", "Unknown")
                                page = src.get("page", "")
                                page_text = f" — Page {page}" if page else ""
                                st.markdown(f"• **{doc_name}**{page_text}")

                    # Show guardrail flags
                    if flags:
                        for flag in flags:
                            st.warning(f"🛡️ {flag}", icon="⚠️")

                    # Save to session messages
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources,
                        "flags": flags,
                    })
                    st.rerun()

                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_messages.append({"role": "assistant", "content": error_msg})

if preview_active:
    with col_preview:
        st.markdown("### 📄 Citation Preview")
        preview_doc = st.session_state.preview_data["document"]
        preview_page = st.session_state.preview_data["page"]
        
        st.markdown(f"**Document:** `{preview_doc}`")
        if preview_page:
            st.markdown(f"**Page:** `{preview_page}`")
            
        if st.button("Close Preview [x]", use_container_width=True):
            st.session_state.preview_data = None
            st.rerun()
            
        st.markdown("---")
        
        # Load citation page content from API
        with st.spinner("Loading citation content..."):
            try:
                preview_result = client.get_document_page_preview(preview_doc, preview_page or 1)
                content = preview_result.get("content", "No content found.")
                st.info(content)
            except Exception as e:
                st.error(f"Could not load citation content: {e}")
