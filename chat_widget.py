import os
import time
import uuid

import requests
import streamlit as st

# ── Configuration ─────────────────────────────────────────────────────
def _get_webhook_url() -> str:
    try:
        return st.secrets["chatbot"]["webhook_url"]
    except Exception:
        return os.environ.get("CHATBOT_WEBHOOK_URL", "")


WEBHOOK_URL = _get_webhook_url()
REQUEST_TIMEOUT_SECONDS = 60

# ── Design tokens (kept in sync with the dashboard's own style) ───────
BLUE = "#2563EB"
BORDER = "#EAECF0"
TEXT_DARK = "#0F172A"
TEXT_MUTED = "#6B7280"

SUGGESTED_QUESTIONS = [
    "What's our total revenue this month?",
    "Which partner generates the most revenue?",
    "How many open engineering issues do we have?",
    "What's our SLA breach rate?",
]


def _inject_chat_css() -> None:
    """Injects CSS to style the chat popover, bubbles, and input to match
    the dashboard's Manrope/blue-accent design system."""
    st.markdown(f"""
    <style>
    [data-testid="stPopover"] > button {{
        width: 100%;
        border-radius: 10px !important;
        border: 1px solid {BORDER} !important;
        background: white !important;
        color: {TEXT_DARK} !important;
        font-family: 'Manrope', sans-serif;
        font-weight: 700;
        font-size: 13px;
        padding: 10px 14px !important;
        box-shadow: 0 1px 3px rgba(16,24,40,0.05);
    }}
    [data-testid="stPopover"] > button:hover {{
        border-color: {BLUE} !important; color: {BLUE} !important;
    }}
    [data-testid="stPopoverBody"] {{
        width: 400px !important;
        font-family: 'Manrope', sans-serif;
    }}

    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="stChatMessageContent"] {{
        background: {BLUE}; color: white; border-radius: 14px 14px 4px 14px;
        padding: 10px 14px; font-size: 13px; line-height: 1.5;
    }}
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) [data-testid="stChatMessageContent"] {{
        background: white; border: 1px solid {BORDER}; border-radius: 14px 14px 14px 4px;
        padding: 10px 14px; font-size: 13px; line-height: 1.55; color: {TEXT_DARK};
        box-shadow: 0 1px 2px rgba(16,24,40,0.04);
    }}
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) table {{
        font-size: 12px; border-collapse: collapse; width: 100%; margin-top: 6px;
    }}
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) th {{
        background: #F8FAFC; color: {TEXT_MUTED}; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.03em; font-size: 10px; padding: 6px 8px; border-bottom: 1px solid {BORDER}; text-align: left;
    }}
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) td {{
        padding: 6px 8px; border-bottom: 1px solid #F1F5F9;
    }}

    .chat-scroll-container {{
        border: 1px solid {BORDER}; border-radius: 12px; background: #FBFCFD; padding: 10px 12px;
    }}

    [data-testid="stChatInput"] textarea {{
        font-family: 'Manrope', sans-serif; font-size: 13px;
        border-radius: 999px !important; border: 1px solid {BORDER} !important;
    }}

    .chat-empty-state {{
        text-align: center; color: {TEXT_MUTED}; font-size: 12px;
        font-family: 'Manrope', sans-serif; padding: 12px 8px 4px 8px;
    }}

    .chat-timestamp {{
        font-size: 10px; color: {TEXT_MUTED}; margin-top: 2px; font-family: 'Manrope', sans-serif;
    }}

    .typing-dots {{ display: inline-flex; gap: 4px; padding: 6px 4px; }}
    .typing-dots span {{
        width: 6px; height: 6px; border-radius: 50%; background: {TEXT_MUTED};
        animation: typing-bounce 1.2s infinite ease-in-out;
    }}
    .typing-dots span:nth-child(2) {{ animation-delay: 0.15s; }}
    .typing-dots span:nth-child(3) {{ animation-delay: 0.3s; }}
    @keyframes typing-bounce {{
        0%, 60%, 100% {{ transform: translateY(0); opacity: 0.5; }}
        30% {{ transform: translateY(-4px); opacity: 1; }}
    }}

    .stButton > button[kind="secondary"] {{
        border-radius: 999px !important; font-size: 11.5px !important; padding: 4px 12px !important;
        border: 1px solid {BORDER} !important; color: {TEXT_DARK} !important; background: #F8FAFC !important;
    }}
    .stButton > button[kind="secondary"]:hover {{
        border-color: {BLUE} !important; color: {BLUE} !important; background: #EFF6FF !important;
    }}

    div[data-testid="column"] .stButton > button {{
        padding: 2px 6px !important; font-size: 11px !important; min-height: 0 !important;
    }}
    </style>
    """, unsafe_allow_html=True)


def _init_state() -> None:
    """Initializes all session-state keys used by the chat widget."""
    st.session_state.setdefault("chat_sessions", {})
    st.session_state.setdefault("current_chat_id", None)
    st.session_state.setdefault("pending_question", None)
    st.session_state.setdefault("show_history", False)

    if st.session_state.current_chat_id is None:
        _new_chat()


def _new_chat() -> None:
    """Starts a fresh conversation, preserving prior ones in history."""
    chat_id = str(uuid.uuid4())
    st.session_state.chat_sessions[chat_id] = {"title": "New chat", "messages": []}
    st.session_state.current_chat_id = chat_id
    st.session_state.show_history = False


def _current_session() -> dict:
    return st.session_state.chat_sessions[st.session_state.current_chat_id]


def _call_webhook(question: str) -> str:
    """Sends a question to the n8n Text-to-SQL webhook and returns the
    formatted answer, or a user-friendly error message on failure."""
    if not WEBHOOK_URL:
        return (
            "⚠️ No webhook URL configured. Set `chatbot.webhook_url` in "
            "`.streamlit/secrets.toml` or the `CHATBOT_WEBHOOK_URL` "
            "environment variable."
        )

    try:
        response = requests.post(
            WEBHOOK_URL,
            json={"chatInput": question},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()

        # The n8n "Respond to Webhook" node may return a list with one item.
        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        return (
            data.get("answer")
            or data.get("output")
            or data.get("response")
            or data.get("text")
            or str(data)
        )

    except requests.exceptions.ConnectionError:
        return (
            "❌ Can't reach the chatbot service.\n\n"
            "Make sure:\n- n8n is running\n- The workflow is Active\n- The tunnel/domain is reachable"
        )
    except requests.exceptions.Timeout:
        return "❌ The request timed out. Try asking a simpler question."
    except Exception as e:  # noqa: BLE001 — surfaced directly to the user
        return f"❌ Request failed: {type(e).__name__}: {e}"


def show_chat() -> None:
    """Renders the chat popover. Call this once, typically inside
    `st.sidebar`, so it persists across all dashboard tabs."""
    _inject_chat_css()
    _init_state()

    total_messages = sum(len(s["messages"]) for s in st.session_state.chat_sessions.values())
    label = "💬 Ask the Data Assistant" + (f" ({total_messages})" if total_messages else "")

    with st.popover(label, use_container_width=True):

        # ── Top bar: title, History toggle, New Chat ──
        col_title, col_history, col_new = st.columns([2.2, 1, 1], vertical_alignment="center")
        with col_title:
            st.markdown(
                f"<div style='font-family:Manrope,sans-serif; font-weight:800; font-size:15px; "
                f"color:{TEXT_DARK}; letter-spacing:-0.2px;'>🤖 AI Assistant</div>",
                unsafe_allow_html=True,
            )
        with col_history:
            if st.button("🕐 History", key="toggle_history", use_container_width=True):
                st.session_state.show_history = not st.session_state.show_history
                st.rerun()
        with col_new:
            if st.button("➕ New", key="new_chat_btn", use_container_width=True):
                _new_chat()
                st.rerun()

        # ── History panel: switch between or delete past conversations ──
        if st.session_state.show_history:
            st.markdown(
                "<div style='font-size:10px; font-weight:700; color:#9CA3AF; text-transform:uppercase; "
                "letter-spacing:0.06em; margin:6px 0 4px 2px;'>Past conversations</div>",
                unsafe_allow_html=True,
            )
            sessions_sorted = list(st.session_state.chat_sessions.items())[::-1]
            has_any_history = any(s["messages"] for _, s in sessions_sorted)

            if not has_any_history:
                st.markdown(
                    f"<div style='font-size:11.5px; color:{TEXT_MUTED}; padding:4px 2px 8px 2px;'>"
                    "No past conversations yet.</div>",
                    unsafe_allow_html=True,
                )

            for chat_id, session in sessions_sorted:
                if not session["messages"]:
                    continue
                is_active = chat_id == st.session_state.current_chat_id
                col_switch, col_delete = st.columns([5, 1])
                with col_switch:
                    if st.button(
                        f"{'🟦' if is_active else '⬜'} {session['title']}",
                        key=f"switch_{chat_id}", use_container_width=True,
                    ):
                        st.session_state.current_chat_id = chat_id
                        st.session_state.show_history = False
                        st.rerun()
                with col_delete:
                    if st.button("🗑️", key=f"delete_{chat_id}"):
                        del st.session_state.chat_sessions[chat_id]
                        if st.session_state.current_chat_id == chat_id:
                            st.session_state.current_chat_id = None
                            _new_chat()
                        st.rerun()
            st.markdown("<hr style='margin:6px 0;'>", unsafe_allow_html=True)

        session = _current_session()

        # ── Fixed-height, internally-scrolling message history ──
        history_box = st.container(height=320, border=False)
        with history_box:
            st.markdown('<div class="chat-scroll-container">', unsafe_allow_html=True)

            if not session["messages"]:
                st.markdown(
                    '<div class="chat-empty-state">Ask about revenue, subscriptions, engineering '
                    'issues, or anything else on the dashboard.</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    "<div style='font-size:10px; font-weight:700; color:#9CA3AF; "
                    "text-transform:uppercase; letter-spacing:0.06em; margin:8px 0 6px 2px;'>Try asking</div>",
                    unsafe_allow_html=True,
                )
                for i, suggestion in enumerate(SUGGESTED_QUESTIONS):
                    if st.button(suggestion, key=f"suggest_{i}", type="secondary"):
                        st.session_state.pending_question = suggestion
                        st.rerun()

            for msg in session["messages"]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    st.markdown(
                        f'<div class="chat-timestamp">{msg.get("time", "")}</div>',
                        unsafe_allow_html=True,
                    )

            st.markdown('</div>', unsafe_allow_html=True)

        # ── Input (stays pinned below the scrollable history) ──
        question = st.chat_input("Ask your dashboard...")
        if st.session_state.pending_question:
            question = st.session_state.pending_question
            st.session_state.pending_question = None

        if question:
            session["messages"].append({
                "role": "user", "content": question, "time": time.strftime("%I:%M %p")
            })
            if session["title"] == "New chat":
                session["title"] = question[:32] + ("..." if len(question) > 32 else "")

            with history_box:
                with st.chat_message("assistant"):
                    st.markdown(
                        '<div class="typing-dots"><span></span><span></span><span></span></div>',
                        unsafe_allow_html=True,
                    )

            answer = _call_webhook(question)
            session["messages"].append({
                "role": "assistant", "content": answer, "time": time.strftime("%I:%M %p")
            })
            st.rerun()
