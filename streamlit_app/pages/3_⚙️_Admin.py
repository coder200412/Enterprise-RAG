"""
Admin Dashboard — User management, system stats, and audit logs.
"""
import streamlit as st

st.set_page_config(page_title="Admin — Enterprise RAG", page_icon="⚙️", layout="wide")

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

st.markdown("## ⚙️ Admin Dashboard")

if clearance < 3:
    st.error("🔒 **Access Denied** — This page requires Admin access.")
    st.stop()

st.markdown("Manage users, view system statistics, and review audit logs.")
st.markdown("---")

# ── System Stats ─────────────────────────────────────────────
st.markdown("### 📊 System Overview")

col1, col2, col3, col4 = st.columns(4)

try:
    health = client.health_check()
    vector_stats = health.get("vector_store", {})

    users_list = client.list_users()
    docs_data = client.list_documents()

    with col1:
        st.metric("👥 Total Users", len(users_list))
    with col2:
        st.metric("📄 Total Documents", docs_data.get("total", 0))
    with col3:
        st.metric("🧩 Vector Chunks", vector_stats.get("total_chunks", 0))
    with col4:
        st.metric("💚 API Status", health.get("status", "unknown").title())
except Exception as e:
    st.warning(f"Could not load stats: {str(e)}")
    users_list = []
    docs_data = {"documents": [], "total": 0}

st.markdown("---")

# ── User Management ──────────────────────────────────────────
st.markdown("### 👥 User Management")

tab1, tab2 = st.tabs(["📋 Users List", "➕ Add User"])

with tab1:
    if users_list:
        for u in users_list:
            u_role = u.get("role", {})
            clearance_badge = {1: "🟢", 2: "🟡", 3: "🔴"}.get(u_role.get("clearance_level", 1), "⚪")

            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

            with col1:
                st.markdown(f"**{u['username']}**")
                st.caption(u["email"])
            with col2:
                st.markdown(f"{clearance_badge} {u_role.get('name', 'N/A').title()}")
            with col3:
                status = "🟢 Active" if u.get("is_active") else "🔴 Inactive"
                st.markdown(status)
            with col4:
                # Role change dropdown (don't allow self-demotion)
                if u["id"] != user.get("id"):
                    try:
                        roles = client.list_roles()
                        role_names = [r["name"] for r in roles]
                        current_idx = role_names.index(u_role.get("name", "employee")) if u_role.get("name") in role_names else 0

                        new_role = st.selectbox(
                            "Role",
                            role_names,
                            index=current_idx,
                            key=f"role_{u['id']}",
                            label_visibility="collapsed",
                        )
                        if new_role != u_role.get("name"):
                            if st.button("Save", key=f"save_{u['id']}", type="primary"):
                                try:
                                    client.update_user_role(u["id"], new_role)
                                    st.success(f"Updated {u['username']} to {new_role}")
                                    st.rerun()
                                except Exception as e:
                                    st.error(str(e))
                    except Exception:
                        st.caption("—")
                else:
                    st.caption("(You)")

            st.markdown("---")
    else:
        st.info("No users found.")

with tab2:
    st.markdown("#### Create New User")
    with st.form("register_form"):
        new_username = st.text_input("Username")
        new_email = st.text_input("Email")
        new_password = st.text_input("Password", type="password")

        try:
            roles = client.list_roles()
            role_options = [r["name"] for r in roles]
        except Exception:
            role_options = ["employee", "manager", "admin"]

        new_role = st.selectbox("Role", role_options)

        if st.form_submit_button("Create User", type="primary", use_container_width=True):
            if new_username and new_email and new_password:
                try:
                    result = client.register_user(new_username, new_email, new_password, new_role)
                    st.success(f"✅ User **{result['username']}** created successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {str(e)}")
            else:
                st.warning("Please fill in all fields.")

st.markdown("---")

# ── Audit Logs & Analytics ────────────────────────────────────
st.markdown("### 📝 Query Audit Logs & Analytics")
st.caption("System-wide monitoring of user queries, response latency, and security guardrail alerts.")

try:
    logs = client.get_admin_audit_logs(limit=50)
    if logs:
        # Compute metrics
        total_queries = len(logs)
        latencies = [log["latency_ms"] for log in logs if log.get("latency_ms") is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        blocked_queries = sum(
            1 for log in logs
            if any(term in log.get("response_summary", "") for term in ["[BLOCKED", "[OFF-TOPIC"])
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📈 Queries Monitored", total_queries)
        with col2:
            st.metric("⚡ Avg Response Latency", f"{avg_latency:.0f} ms")
        with col3:
            st.metric("🛡️ Guardrail Blocks", blocked_queries)

        # Charts Section
        col_c1, col_c2 = st.columns([2, 1])
        with col_c1:
            st.markdown("##### ⚡ Response Latency History (ms)")
            # Plot chronologically (oldest to newest)
            latency_history = [log.get("latency_ms", 0) for log in reversed(logs)]
            st.line_chart(latency_history, height=180)
        
        with col_c2:
            st.markdown("##### 🛡️ Guardrail Status")
            status_counts = {"Safe": total_queries - blocked_queries, "Blocked": blocked_queries}
            st.bar_chart(status_counts, height=180)

        # Detailed Logs list
        st.markdown("##### 🔍 System Audit Trail")
        for entry in logs:
            flags = entry.get("guardrail_flags", "")
            has_flags = flags and flags != "[]" and flags != '""'
            flag_badge = " 🛡️" if has_flags else ""

            # Format list entry header
            user_lbl = f"👤 {entry['username']}"
            time_lbl = f"🕐 {entry['timestamp'][11:19]}"
            latency_lbl = f"⚡ {entry.get('latency_ms', 0)}ms"
            title = f"{user_lbl} | {time_lbl} | {latency_lbl} | {entry['query'][:50]}...{flag_badge}"

            with st.expander(title):
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.markdown(f"**User:** `{entry['username']}`")
                    st.markdown(f"**Timestamp:** `{entry['timestamp'][:19].replace('T', ' ')}`")
                with col_info2:
                    st.markdown(f"**Latency:** `{entry.get('latency_ms', 0)} ms`")

                st.markdown(f"**User Query:**")
                st.code(entry['query'], language="text")
                st.markdown(f"**Response Excerpt:**")
                st.info(entry['response_summary'])
                if has_flags:
                    st.warning(f"⚠️ Guardrail Flags Triggered: {flags}")
    else:
        st.info("No queries logged yet.")
except Exception as e:
    st.warning(f"Could not load audit logs: {str(e)}")
