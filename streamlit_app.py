import streamlit as st
import requests
import os
from dotenv import load_dotenv

def get_config(key, default=None):
    load_dotenv()
    try:
        # First try to get from Streamlit secrets (works in both local and deployed environments)
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        # for local testing use environment variables from .env file
        return os.getenv(key, default)
        

# ── Config ──────────────────────────────────────────────────────────────────
N8N_WEBHOOK_URL = get_config("N8N_WEBHOOK_URL")
if not N8N_WEBHOOK_URL:
    st.error("Webhook URL not configured. Please set N8N_WEBHOOK_URL in Streamlit secrets.")
    st.stop()
N8N_AUTH_TOKEN = get_config("N8N_AUTH_TOKEN")
if not N8N_AUTH_TOKEN:
    st.error("Auth token not configured. Please set N8N_AUTH_TOKEN in Streamlit secrets.")
    st.stop()

# set default agent language in session state (persists across runs)
if "agent_language" not in st.session_state:
    st.session_state.agent_language = "en"

LANGUAGES = {
    "en": "English",
    "de": "German",
    "es": "Spanish",
    "fr": "French",
}

URGENCY_COLOURS = {
    "critical":  "🔴",
    "escalation":"🟠",
    "high":      "🟡",
    "medium":    "🔵",
    "low":       "🟢",
}

SENTIMENT_ICONS = {
    "frustrated": "😤",
    "neutral":    "😐",
    "positive":   "😊",
}

# ── Page setup ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Personio Support Copilot",
    layout="centered",
)

# ── Minimal custom CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Reduce top/bottom padding */
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1rem;
    }
    /* Reduce spacing between widgets */
    div[data-testid="stForm"] {
        gap: 0.5rem;
    }
    /* Tighten checkbox spacing */
    div[data-testid="stCheckbox"] {
        margin-bottom: -0.5rem;
    }
    /* Reduce caption spacing */
    [data-testid="stCaptionContainer"] {
        margin-top: -0.3rem;
    }
    /* card-style containers */
    .ss-card {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        border-left: 4px solid #0e7c7b;
    }
    .ss-card-warn {
        border-left-color: #e05c00;
    }
    .ss-label {
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #6b7280;
        margin-bottom: 0.25rem;
    }
    .ss-draft {
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        padding: 0.85rem 1rem;
        font-size: 0.92rem;
        line-height: 1.6;
        white-space: pre-wrap;
    }
    .ss-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-right: 0.4rem;
        background: #e5e7eb;
        color: #374151;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.1rem;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────
st.title("Personio Support Copilot")
st.caption("AI-assisted ticket triage for Personio Support")

# Initialize submission state to prevent multiple submissions while waiting for response
if "is_submitting" not in st.session_state:
    st.session_state.is_submitting = False

# ── Input form ───────────────────────────────────────────────────────────────
with st.form("ticket_form"):
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        ticket_id = st.text_input(
            "Ticket ID",
            placeholder="e.g. 12345",
            help="Enter the Zendesk ticket ID"
        )
    with col2:
        st.markdown("")
    with col3:
        # ── Agent settings (persist in session)
        st.session_state.agent_language = st.selectbox(
            "Your language",
            options=list(LANGUAGES.keys()),
            format_func=lambda x: LANGUAGES[x],
            index=list(LANGUAGES.keys()).index(st.session_state.agent_language),
            key="lang_select",
            help="Set your preferred language for agent-facing outputs (e.g. draft, next steps)"
        )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        subcol1,subcol2 = st.columns([0.4, 0.6])
        with subcol1:
            st.markdown("**Options**") 
        with subcol2:
            st.text("",help="Choose what to include in the analysis results")
    with col2:
        include_draft = st.checkbox("Draft response", value=True)
    with col3:
        include_next_steps = st.checkbox("Next steps", value=True)
    with col4:
        include_escalation = st.checkbox("Escalation analysis",value=False)

    # options as toggles instead of checkboxes (more compact, but less clear)
    # include_draft = col2.toggle("Draft response", value=True)
    # include_next_steps = col3.toggle("Next steps", value=True)
    # include_escalation = col4.toggle("Escalation analysis", value=False)

    submitted = st.form_submit_button(
        "Analyze ticket →",
        use_container_width=True,
        type="primary"
    )

# ── API call ─────────────────────────────────────────────────────────────────
if submitted:
    if not ticket_id.strip():
        st.error("Please enter a ticket ID.")
        st.stop()
 
    payload = {
        "ticket_id": ticket_id.strip(),
        "agent_language":      st.session_state.agent_language,
        "options": {
            "include_draft":       include_draft,
            "include_next_steps":  include_next_steps,
            "include_escalation":  include_escalation,
        }
    }
 
    headers = {
        "Content-Type":  "application/json",
        "X-Auth-Token":  N8N_AUTH_TOKEN,
    }
 
    error_message = None
    data = None
 
    with st.spinner("Analyzing ticket…"):
        try:
            response = requests.post(
                N8N_WEBHOOK_URL,
                json=payload,
                headers=headers,
                timeout=30,
            )
 
            # Handle specific HTTP errors with friendly messages
            if response.status_code == 401:
                error_message = "Authentication failed, please check with your system administrator to " \
                                "ensure your webhook credentials are correct."
            elif response.status_code == 403:
                error_message = "Access denied. Check your webhook credentials."
            elif response.status_code == 404:
                error_message = "Please try again in a moment the processing workflow can't be reached (n8n webhook)."
            elif response.status_code == 422:
                error_message = "Invalid request. Please check the ticket ID format."
            elif response.status_code == 429:
                error_message = "Too many requests. Please wait a moment and try again."
            elif response.status_code >= 500:
                error_message = "The automation service encountered an error. Please try again shortly."
            else:
                response.raise_for_status()
                data = response.json()
 
                # Check for application-level errors in response
                if data.get("success") is False:
                    error_message = data.get("error_message", "Analysis failed for an unknown reason.")
 
        except requests.exceptions.Timeout:
            error_message = "The request timed out after 30 seconds. The service may be busy — please try again."
        except requests.exceptions.ConnectionError:
            error_message = "Could not reach the automation service. Check your internet connection."
        except ValueError:
            error_message = "Received an unexpected response format from the service."
        except Exception as e:
            error_message = f"Unexpected error: {str(e)}"
 
    # ── Show error outside spinner so it doesn't keep spinning ───────────────
    if error_message:
        st.error(f"⚠️ {error_message}")
        st.caption("If this keeps happening please contact your system administrator.")
        st.stop()
 
    # ── Triage overview ─────────────────────────────────────────────────────── 
    detected_lang = data.get("detected_language", "")
    agent_lang    = data.get("agent_language", st.session_state.agent_language)
    urgency       = data.get("urgency", "")
    category      = data.get("category", "")
    sentiment     = data.get("sentiment", "")
    confidence    = data.get("confidence_score", 0)
    is_repeat     = data.get("is_repeat_contact", False)
 
    urgency_icon   = URGENCY_COLOURS.get(urgency, "⚪")
    sentiment_icon = SENTIMENT_ICONS.get(sentiment, "")
 
    # Title row with repeat contact warning
    # Compact header — everything in one tight block
    st.markdown(f"### Ticket #{ticket_id}")

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Urgency", f"{urgency_icon} {urgency.capitalize()}")
    with m2:
        st.metric("Category", f"{category.capitalize()}")
    with m3:
        st.metric("Sentiment", f"{sentiment_icon} {sentiment.capitalize()}")
    with m4:
        st.metric("Confidence", f"{int(confidence * 100)}%")
    with m5:
        if is_repeat:
            st.metric("Contact", "🔁 Repeat")
        else:
            st.metric("Contact", "✅ First")

    # Language info only when relevant
    if detected_lang != agent_lang:
        st.caption(
            f"🌐 Ticket: {LANGUAGES.get(detected_lang, detected_lang)} "
            f"· Your language: {LANGUAGES.get(agent_lang, agent_lang)}"
        )
    
    # ── Triage section ───────────────────────────────────────────────────────
    triage = data.get("triage", {})
    agent_response = data.get("agent_response", {})

    # Compact summary card only — no separate recommended action
    if triage.get("summary"):
        st.markdown(
            f'<div class="ss-card">'
            f'<div class="ss-label">Summary ({LANGUAGES.get(agent_lang, agent_lang)})</div>'
            f'{triage["summary"]}'
            f'</div>',
            unsafe_allow_html=True
        )

    if include_escalation and triage.get("escalation_analysis"):
        st.markdown(
            f'<div class="ss-card ss-card-warn">'
            f'<div class="ss-label">Escalation analysis ({LANGUAGES.get(agent_lang, agent_lang)})</div>'
            f'⚠️ {triage["escalation_analysis"]}'
            f'</div>',
            unsafe_allow_html=True
        )

    # ── Next steps ───────────────────────────────────────────────────────────
    agent_response = data.get("agent_response", {})
    next_steps = agent_response.get("next_steps", [])
 
    if include_next_steps and next_steps:
        steps_html = "".join([
            f"<p style='margin:0.25rem 0'><strong>{i+1}.</strong> {step}</p>"
            for i, step in enumerate(next_steps)
        ])
        st.markdown(
            f'<div class="ss-card">'
            f'<div class="ss-label">Next steps ({LANGUAGES.get(agent_lang, agent_lang)})</div>'
            f'{steps_html}'
            f'</div>',
            unsafe_allow_html=True
        )
 
    # ── Draft response ───────────────────────────────────────────────────────
    draft = agent_response.get("draft")

    if include_draft and draft:
        st.markdown(
            f'<div class="ss-label">Draft response '
            f'({LANGUAGES.get(detected_lang, detected_lang)} — sending to customer)</div>',
            unsafe_allow_html=True
        )
        st.code(draft, language="", wrap_lines=True)

        if detected_lang != agent_lang:
            agent_draft = agent_response.get("draft_agent_language")
            if agent_draft:
                st.markdown(
                    f'<div class="ss-card" style="margin-top:0.5rem">'
                    f'<div class="ss-label">Draft in your language '
                    f'({LANGUAGES.get(agent_lang, agent_lang)})</div>'
                    f'{agent_draft}'
                    f'</div>',
                    unsafe_allow_html=True
                )
            else:
                st.caption("Agent language translation not available — please try again.")
 
    st.caption(f"Ticket #{ticket_id} · Analyzed in {LANGUAGES.get(agent_lang, agent_lang)}")