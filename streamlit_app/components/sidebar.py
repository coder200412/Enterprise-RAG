"""
Sidebar component — user info, navigation, and logout.
"""
import streamlit as st
from streamlit_app.components.auth import get_user_info, logout


CLEARANCE_LABELS = {1: "Employee", 2: "Manager", 3: "Admin"}
CLEARANCE_COLORS = {1: "🟢", 2: "🟡", 3: "🔴"}


def render_sidebar():
    """Render the sidebar with user info and navigation."""
    user = get_user_info()
    role = user.get("role", {})
    clearance = role.get("clearance_level", 1)
    role_name = role.get("name", "unknown")

    with st.sidebar:
        st.markdown("## 🏢 Enterprise RAG")
        st.markdown("---")

        # User info card
        st.markdown(f"### 👤 {user.get('username', 'Unknown')}")
        st.markdown(f"**Role:** {CLEARANCE_COLORS.get(clearance, '⚪')} {role_name.title()}")
        st.markdown(f"**Clearance:** Level {clearance}/3")
        st.markdown(f"**Email:** {user.get('email', 'N/A')}")

        st.markdown("---")

        # Access level visualization
        st.markdown("### 📊 Your Access")
        for level in range(1, 4):
            label = CLEARANCE_LABELS.get(level, f"Level {level}")
            if level <= clearance:
                st.markdown(f"✅ **{label}** documents")
            else:
                st.markdown(f"🔒 ~~{label} documents~~")

        st.markdown("---")

        # Logout
        if st.button("🚪 Logout", use_container_width=True):
            logout()
