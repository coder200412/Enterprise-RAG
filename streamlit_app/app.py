"""
Enterprise RAG — Main Streamlit Application
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import streamlit as st

st.set_page_config(
    page_title="Enterprise RAG",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for premium look
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    }

    /* Header styling */
    .main-header {
        text-align: center;
        padding: 3rem 0 2rem;
    }
    .main-header h1 {
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .main-header p {
        color: #aaa;
        font-size: 1.1rem;
    }

    /* Card styling */
    .feature-card {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 0.5rem 0;
        backdrop-filter: blur(10px);
        transition: transform 0.2s, border-color 0.2s;
    }
    .feature-card:hover {
        transform: translateY(-2px);
        border-color: rgba(102, 126, 234, 0.5);
    }
    .feature-card h3 {
        color: #fff;
        margin-bottom: 0.5rem;
    }
    .feature-card p {
        color: #bbb;
        font-size: 0.9rem;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }

    /* Button styling */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        font-weight: 600;
        transition: opacity 0.2s;
    }
    .stButton > button[kind="primary"]:hover {
        opacity: 0.9;
    }

    /* Chat styling */
    .stChatMessage {
        background: rgba(255,255,255,0.03);
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.06);
    }

    /* Input styling */
    .stTextInput > div > div > input {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 8px;
        color: #fff;
    }
</style>
""", unsafe_allow_html=True)

from streamlit_app.components.auth import is_authenticated, render_login_form

if not is_authenticated():
    render_login_form()
else:
    from streamlit_app.components.sidebar import render_sidebar
    render_sidebar()

    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.markdown("# 🏢 Enterprise RAG")
    st.markdown("*Secure Corporate Document Intelligence with RBAC*")
    st.markdown('</div>', unsafe_allow_html=True)

    # Feature cards
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="feature-card">
            <h3>💬 Smart Chat</h3>
            <p>Ask questions about company documents. AI-powered answers with source citations.</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="feature-card">
            <h3>🔐 RBAC Security</h3>
            <p>Role-based access control ensures you only see documents you're authorized for.</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="feature-card">
            <h3>🛡️ AI Guardrails</h3>
            <p>Multi-layered safety filters prevent prompt injection and data leakage.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 👉 Navigate to **Chat**, **Documents**, or **Admin** from the sidebar pages.")
