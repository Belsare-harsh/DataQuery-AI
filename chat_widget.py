import time
import uuid
import requests
import streamlit as st

# Production webhook URL (via ngrok tunnel to local n8n)
WEBHOOK_URL = "https://apochromatic-sigrid-nondistractive.ngrok-free.dev/webhook/dashboard-chat"

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


def _inject_chat_css():
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

    /* ── History list rows ── */
    .chat-history-item {{
        font-size: 12px; padding: 6px 8px; border-radius: 8px; cursor: pointer;
        color: {TEXT_DARK}; margin-bottom: 2px;
    }}
    .chat-history-item.active {{ background: #EFF6FF; color: {BLUE}; font-weight: 700; }}
    </style>
    """, unsafe_allow_html=True)


def _init_state():
    if "chat_sessions" not in st.session_state:
        st.session_state.chat_sessions = {}
    if "current_chat_id" not in st.session_state:
        st.session_state.current_chat_id = None
    if "feedback" not in st.session_state:
        st.session_state.feedback = {}
    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None
    if "show_history" not in st.session_state:
        st.session_state.show_history = False

    if st.session_state.current_chat_id is None:
        _new_chat()


def _new_chat():
    chat_id = str(uuid.uuid4())
    st.session_state.chat_sessions[chat_id] = {"title": "New chat", "messages": []}
    st.session_state.current_chat_id = chat_id
    st.session_state.show_history = False


def _current_session():
    return st.session_state.chat_sessions[st.session_state.current_chat_id]


def _call_webhook(question: str) -> str:
    try:
        response = requests.post(WEBHOOK_URL, json={"chatInput": question}, timeout=60)
        response.raise_for_status()
        data = response.json()
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
            "Make sure:\n- n8n is running\n- The workflow is Active\n- The ngrok tunnel is still live"
        )
    except requests.exceptions.Timeout:
        return "❌ The request timed out. Try asking a simpler question."
    except Exception as e:
        return f"❌ Request failed: {type(e).__name__}: {e}"


def show_chat():
    _inject_chat_css()
    _init_state()

    total_unread = sum(len(s["messages"]) for s in st.session_state.chat_sessions.values())
    label = "💬 Ask the Data Assistant" + (f" ({total_unread})" if total_unread else "")

    with st.popover(label, use_container_width=True):

        # ── Top bar: title, New Chat, History toggle, Clear ──
        h1, h2, h3 = st.columns([2.2, 1, 1], vertical_alignment="center")
        with h1:
            st.markdown(
                f"<div style='font-family:Manrope,sans-serif; font-weight:800; font-size:15px; "
                f"color:{TEXT_DARK}; letter-spacing:-0.2px;'>🤖 AI Assistant</div>",
                unsafe_allow_html=True,
            )
        with h2:
            if st.button("🕐 History", key="toggle_history", use_container_width=True):
                st.session_state.show_history = not st.session_state.show_history
                st.rerun()
        with h3:
            if st.button("➕ New", key="new_chat_btn", use_container_width=True):
                _new_chat()
                st.rerun()

        # ── History panel (list of past sessions) ──
        if st.session_state.show_history:
            st.markdown(
                "<div style='font-size:10px; font-weight:700; color:#9CA3AF; text-transform:uppercase; "
                "letter-spacing:0.06em; margin:6px 0 4px 2px;'>Past conversations</div>",
                unsafe_allow_html=True,
            )
            sessions_sorted = list(st.session_state.chat_sessions.items())[::-1]
            if not sessions_sorted or all(not s["messages"] for _, s in sessions_sorted):
                st.markdown(
                    f"<div style='font-size:11.5px; color:{TEXT_MUTED}; padding:4px 2px 8px 2px;'>"
                    "No past conversations yet.</div>",
                    unsafe_allow_html=True,
                )
            for chat_id, session in sessions_sorted:
                if not session["messages"]:
                    continue
                is_active = chat_id == st.session_state.current_chat_id
                cols = st.columns([5, 1])
                with cols[0]:
                    if st.button(
                        f"{'🟦' if is_active else '⬜'} {session['title']}",
                        key=f"switch_{chat_id}", use_container_width=True,
                    ):
                        st.session_state.current_chat_id = chat_id
                        st.session_state.show_history = False
                        st.rerun()
                with cols[1]:
                    if st.button("🗑️", key=f"del_{chat_id}"):
                        del st.session_state.chat_sessions[chat_id]
                        if st.session_state.current_chat_id == chat_id:
                            st.session_state.current_chat_id = None
                            _new_chat()
                        st.rerun()
            st.markdown("<hr style='margin:6px 0;'>", unsafe_allow_html=True)

        session = _current_session()

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
                for i, sq in enumerate(SUGGESTED_QUESTIONS):
                    if st.button(sq, key=f"suggest_{i}", type="secondary"):
                        st.session_state.pending_question = sq
                        st.rerun()

            for idx, msg in enumerate(session["messages"]):
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    st.markdown(f'<div class="chat-timestamp">{msg.get("time", "")}</div>', unsafe_allow_html=True)

                    if msg["role"] == "assistant" and not msg["content"].startswith("❌"):
                        fb_key = f"{st.session_state.current_chat_id}_{idx}"
                        current = st.session_state.feedback.get(fb_key)
                        c1, c2, _ = st.columns([1, 1, 8])
                        with c1:
                            if st.button("👍" if current != "up" else "✅", key=f"up_{fb_key}"):
                                st.session_state.feedback[fb_key] = "up"
                                st.rerun()
                        with c2:
                            if st.button("👎" if current != "down" else "✅", key=f"down_{fb_key}"):
                                st.session_state.feedback[fb_key] = "down"
                                st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

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