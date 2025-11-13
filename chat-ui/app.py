import os
import requests
import streamlit as st

# -------------------------------------------------------
# Page Setup
# -------------------------------------------------------
st.set_page_config(
    page_title="Vijil + Phala Webinar Chat",
    page_icon="🔐",
    layout="wide",
)

API_BASE = os.getenv("CHAT_API_BASE", "https://your-server.com/v1")
API_KEY = os.getenv("CHAT_API_KEY", "")
MODEL = os.getenv("CHAT_MODEL", "your-model-id")


# -------------------------------------------------------
# Sidebar
# -------------------------------------------------------
st.sidebar.title("Settings")

api_base = st.sidebar.text_input("API Base URL", API_BASE)
model = st.sidebar.text_input("Model", MODEL)
api_key = st.sidebar.text_input("API Key (optional)", API_KEY, type="password")

if st.sidebar.button("Clear Chat"):
    st.session_state.messages = []
    st.session_state.last_audit = None


# -------------------------------------------------------
# Session State
# -------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_audit" not in st.session_state:
    st.session_state.last_audit = None


# -------------------------------------------------------
# Helper — Call Your Chat Endpoint
# -------------------------------------------------------
def call_chat(messages):
    url = api_base.rstrip("/") + "/chat/completions"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": messages,
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    # Assistant text
    assistant_text = data["choices"][0]["message"]["content"]

    # Optional: if your backend includes trust audit info
    audit_info = data.get("vijil_audit") or data.get("audit") or None

    return assistant_text, audit_info


# -------------------------------------------------------
# Layout Header
# -------------------------------------------------------
col_left, col_right = st.columns([3, 1.5])

with col_left:
    st.markdown("### 🔐 Vijil + Phala Webinar Demo")
    st.markdown(
        """
Chat with the agent running behind your `/chat/completions` endpoint.
This demonstrates the live endpoint used during the webinar.
"""
    )

with col_right:
    st.markdown("#### Latest Audit")
    audit = st.session_state.last_audit

    if not audit:
        st.caption("Run a message to see audit/trust info (if provided).")
    else:
        ts = audit.get("trust_score")
        if ts is not None:
            st.metric("Trust Score", f"{ts * 100:.1f} / 100")
        summary = audit.get("summary")
        if summary:
            st.markdown(f"**Summary:** {summary}")

        dims = audit.get("dimensions")
        if isinstance(dims, dict):
            st.markdown("**Dimensions:**")
            for dim, score in dims.items():
                st.progress(float(score), text=f"{dim}: {score*100:.0f}/100")


st.markdown("---")


# -------------------------------------------------------
# Chat Interface
# -------------------------------------------------------
st.markdown("### 💬 Chat")

# Show history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input at bottom
user_input = st.chat_input("Message the agent…")

if user_input:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Call backend
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                reply, audit_info = call_chat(st.session_state.messages)
                st.markdown(reply)
            except Exception as e:
                reply = f"Error: {e}"
                st.error(reply)

    # Save assistant reply
    st.session_state.messages.append({"role": "assistant", "content": reply})

    # Save audit if present
    if audit_info:
        st.session_state.last_audit = audit_info
