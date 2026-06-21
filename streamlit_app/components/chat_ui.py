"""
Chat UI components for Streamlit.
"""
import streamlit as st


def render_message(role: str, content: str, sources: list = None, flags: list = None):
    """Render a chat message with optional sources and guardrail flags."""
    with st.chat_message(role, avatar="🤖" if role == "assistant" else "👤"):
        st.markdown(content)

        # Show sources
        if sources:
            with st.expander("📄 Sources", expanded=False):
                for src in sources:
                    doc_name = src.get("document", "Unknown")
                    page = src.get("page", "")
                    page_text = f" — Page {page}" if page else ""
                    st.markdown(f"• **{doc_name}**{page_text}")

        # Show guardrail warnings
        if flags:
            for flag in flags:
                st.warning(f"🛡️ {flag}", icon="⚠️")


def render_chat_history():
    """Render all messages in the chat history."""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        render_message(
            role=msg["role"],
            content=msg["content"],
            sources=msg.get("sources"),
            flags=msg.get("flags"),
        )


def add_message(role: str, content: str, sources: list = None, flags: list = None):
    """Add a message to the chat history."""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.session_state.messages.append({
        "role": role,
        "content": content,
        "sources": sources or [],
        "flags": flags or [],
    })
