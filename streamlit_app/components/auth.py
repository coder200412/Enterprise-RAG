"""
Authentication components for Streamlit — login form and session management.
"""
import streamlit as st
from streamlit_app.utils.api_client import APIClient


def get_api_client() -> APIClient:
    """Get or create the API client from session state."""
    if "api_client" not in st.session_state:
        st.session_state.api_client = APIClient()
    if "token" in st.session_state and st.session_state.token:
        st.session_state.api_client.set_token(st.session_state.token)
    return st.session_state.api_client


def is_authenticated() -> bool:
    """Check if user is logged in."""
    return st.session_state.get("authenticated", False)


def get_user_info() -> dict:
    """Get the current user's info from session state."""
    return st.session_state.get("user_info", {})


def render_login_form():
    """Render the login form with a premium design."""
    st.markdown("""
    <style>
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
        }
        .login-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        .login-header h1 {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }
        .login-header p {
            color: #888;
            font-size: 0.9rem;
        }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-header">', unsafe_allow_html=True)
        st.markdown("# 🔐 Enterprise RAG")
        st.markdown("*Secure Document Intelligence*")
        st.markdown('</div>', unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("👤 Username", placeholder="Enter your username")
            password = st.text_input("🔑 Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

            if submitted:
                if not username or not password:
                    st.error("Please enter both username and password.")
                    return

                try:
                    client = get_api_client()
                    data = client.login(username, password)
                    st.session_state.authenticated = True
                    st.session_state.token = data["access_token"]
                    st.session_state.user_info = data["user"]
                    st.success(f"Welcome back, {data['user']['username']}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {str(e)}")

        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; color: #888; font-size: 0.8rem;">
            <b>Demo Credentials:</b><br>
            Admin: admin / admin123<br>
            Manager: manager1 / manager123<br>
            Employee: employee1 / employee123
        </div>
        """, unsafe_allow_html=True)


def logout():
    """Clear session state, invoke backend token revocation, and log out."""
    try:
        client = get_api_client()
        client.logout()
    except Exception:
        pass  # Fail gracefully if token already invalid/expired

    for key in ["authenticated", "token", "user_info", "api_client", "messages", "current_session_id", "chat_messages"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()
