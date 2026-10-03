"""
app.py
Streamlit front-end for the Vaishno Devi Yatra Booking Agent prototype.
Run locally with: streamlit run app.py

This version is chat-first: there's no dropdown search form and no
login/sign-up gate. A pilgrim just starts typing (in whatever language
they like) and the multi-agent system in agents/ takes it from there.
"""

import json
import os
import re
import uuid
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

import db
import explore_data
import payment
import yatra_info
from agents import coordinator
from data_gen import build_database


def fmt_time(hhmm):
    """Formats a 24-hour 'HH:MM' string as 12-hour with AM/PM, e.g. '06:00' -> '6:00 AM'.
    Built manually rather than with %-I/%#I strftime flags, since those aren't
    portable between Windows and Mac/Linux."""
    try:
        t = datetime.strptime(str(hhmm), "%H:%M")
        hour_12 = t.hour % 12 or 12
        return f"{hour_12}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"
    except (ValueError, TypeError):
        return str(hhmm)


def _strip_markdown_for_speech(text):
    """Removes markdown formatting so the spoken text sounds natural
    instead of reading out asterisks and emoji-heavy symbols."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#_`]", "", text)
    return text


def render_voice_input(key="voice_input_main"):
    """Renders a mic button that uses the browser's built-in speech
    recognition (Web Speech API) to transcribe speech in the selected
    language, then feeds it back to Python.

    HOW THE BRIDGE WORKS (and why it's built this way): Streamlit's
    simple components.html() renders an isolated iframe with no return
    channel to Python - that round-trip normally requires building a
    full custom component with its own frontend build, which is a much
    bigger undertaking. The practical, commonly-used workaround: once
    speech is transcribed, the iframe writes it into the page's URL
    query string (via history.replaceState, not a full navigation) and
    reloads. Streamlit reads query params fresh on every run via
    st.query_params, and reconnects to the SAME session (session_state
    is preserved across a same-tab reload), so this doesn't lose the
    conversation. This is the most experimental piece of this app -
    it depends on browser speech-recognition support (best in Chrome/
    Edge; not supported in Firefox as of this writing) and should be
    tested carefully."""
    html = f"""
    <html><body style="margin:0; background:transparent;">
    <div style="font-family:'Inter',sans-serif; display:flex; align-items:center; gap:8px;">
      <select id="lang_{key}" style="border-radius:8px; border:1px solid #E8C874; padding:4px 8px; font-size:0.78rem; background:#FFF3E2; color:#3B1F1F;">
        <option value="en-IN">English</option>
        <option value="hi-IN">हिंदी (Hindi)</option>
        <option value="pa-IN">ਪੰਜਾਬੀ (Punjabi)</option>
        <option value="ur-IN">اردو (Urdu)</option>
      </select>
      <button id="mic_{key}" onclick="startListen_{key}()" style="
          display:flex; align-items:center; gap:6px; background:#6E1423; border:none; color:#FFF3E2;
          font-weight:700; border-radius:999px; padding:6px 16px; font-size:0.82rem; cursor:pointer;
          transition: all 0.15s ease;
      " onmouseover="this.style.background='#A61B29'" onmouseout="this.style.background='#6E1423'">
        🎤 Speak your trip
      </button>
      <span id="status_{key}" style="font-size:0.78rem; color:#8A6857;"></span>
    </div>
    <script>
      function startListen_{key}() {{
        var statusEl = document.getElementById('status_{key}');
        var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {{
          statusEl.textContent = 'Voice input not supported in this browser (try Chrome/Edge).';
          return;
        }}
        var lang = document.getElementById('lang_{key}').value;
        var recognition = new SR();
        recognition.lang = lang;
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        statusEl.textContent = '🔴 Listening...';
        recognition.start();

        recognition.onresult = function(event) {{
          var text = event.results[0][0].transcript;
          statusEl.textContent = 'Heard: ' + text;
          var url = new URL(window.parent.location.href);
          url.searchParams.set('voice_input', text);
          url.searchParams.set('voice_ts', Date.now());
          window.parent.history.replaceState(null, '', url);
          setTimeout(function() {{ window.parent.location.reload(); }}, 400);
        }};
        recognition.onerror = function(event) {{
          statusEl.textContent = 'Could not hear that (' + event.error + '). Try again.';
        }};
        recognition.onend = function() {{
          if (statusEl.textContent === '🔴 Listening...') {{ statusEl.textContent = ''; }}
        }};
      }}
    </script>
    </body></html>
    """
    components.html(html, height=42)


def render_speak_button(text, key):
    """Renders small 'Listen'/'Stop' icon buttons that use the browser's
    built-in text-to-speech (Web Speech API) to read the message aloud.
    No API key, no cost, works entirely client-side.

    Two things were fixed here from an earlier version:
    1. The component's background was opaque white, so it rendered as a
       visually disconnected box on top of the page's themed background.
       Now explicitly transparent so it blends in.
    2. On many browsers (notably Chrome), calling speechSynthesis.speak()
       before the voice list has finished loading silently does nothing -
       no error, no sound. This warms up getVoices() and waits for the
       voiceschanged event (with a timeout fallback) before speaking,
       which is the standard fix for that issue."""
    clean_text = _strip_markdown_for_speech(text)
    safe_text = json.dumps(clean_text)
    html = f"""
    <html><body style="margin:0; background:transparent;">
    <div style="font-family:'Inter',sans-serif; display:flex; gap:6px; background:transparent;">
      <button onclick="speak_{key}()" style="
          display:flex; align-items:center; gap:5px; background:#3B1F1F; border:none; color:#FFF3E2;
          font-weight:600; border-radius:999px; padding:5px 13px; font-size:0.76rem; cursor:pointer;
          transition: all 0.15s ease;
      " onmouseover="this.style.background='#6E1423'" onmouseout="this.style.background='#3B1F1F'">
        🔊 Listen
      </button>
      <button onclick="if(window.speechSynthesis) window.speechSynthesis.cancel();" style="
          display:flex; align-items:center; gap:5px; background:#F5E7D3; border:none; color:#6E1423;
          font-weight:600; border-radius:999px; padding:5px 13px; font-size:0.76rem; cursor:pointer;
          transition: all 0.15s ease;
      " onmouseover="this.style.background='#E8C874'" onmouseout="this.style.background='#F5E7D3'">
        ⏹ Stop
      </button>
    </div>
    <script>
      function speak_{key}() {{
        if (!window.speechSynthesis) return;
        window.speechSynthesis.cancel();
        var text = {safe_text};
        function doSpeak() {{
          var u = new SpeechSynthesisUtterance(text);
          u.rate = 0.95;
          window.speechSynthesis.speak(u);
        }}
        var voices = window.speechSynthesis.getVoices();
        if (voices.length === 0) {{
          window.speechSynthesis.onvoiceschanged = doSpeak;
          window.speechSynthesis.getVoices();
          setTimeout(doSpeak, 300);
        }} else {{
          doSpeak();
        }}
      }}
    </script>
    </body></html>
    """
    components.html(html, height=38)


def render_place_image(place, height_px=180):
    """Shows the place's real photo if it exists at assets/places/<file>,
    otherwise a themed gradient placeholder with an icon - so the app
    looks complete even before every photo has been added."""
    img_path = os.path.join("assets", "places", place.get("image_file", ""))
    if place.get("image_file") and os.path.exists(img_path):
        st.image(img_path, use_container_width=True)
    else:
        st.markdown(
            f"""
            <div style="height:{height_px}px; border-radius:14px; margin-bottom:0.6rem;
                        background: linear-gradient(135deg, #C2374A 0%, #6E1423 60%, #3B1F1F 100%);
                        display:flex; align-items:center; justify-content:center;">
                <span style="font-size:2.6rem; opacity:0.55;">📍</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def get_api_key():
    """Looks for an OPENAI_API_KEY or ANTHROPIC_API_KEY in Streamlit secrets or env vars.
    Returns None if neither is set - the app falls back to rule-based English parsing."""
    try:
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    return os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")


def get_base_url():
    """Looks for OPENAI_BASE_URL (for local OSS models like Ollama, LM Studio, vLLM)."""
    try:
        if "OPENAI_BASE_URL" in st.secrets:
            return st.secrets["OPENAI_BASE_URL"]
    except Exception:
        pass
    return os.environ.get("OPENAI_BASE_URL")



st.set_page_config(page_title="Vaishno Devi Yatra Agent", page_icon="🛕", layout="wide")

# --- Custom styling for Vaishno Devi Yatra AI (Travel Platform Aesthetic) ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Playfair+Display:wght@700;800&display=swap');

    :root {
        --bg-main: #FAF7F2;
        --card-bg: #FFFFFF;
        --burgundy-dark: #4A0D17;
        --burgundy: #6E1423;
        --burgundy-light: #A61B29;
        --gold-accent: #D4AF37;
        --gold-subtle: #FDF8EC;
        --gold-border: #E8C874;
        --text-primary: #1F1717;
        --text-muted: #665757;
        --border-color: #E8E0D2;
        --shadow-sm: 0 2px 8px rgba(110, 20, 35, 0.04);
        --shadow-md: 0 6px 20px rgba(110, 20, 35, 0.08);
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 15px;
        color: var(--text-primary);
        background-color: var(--bg-main);
    }

    .stApp {
        background-color: var(--bg-main);
    }

    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    .block-container {
        max-width: 1200px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }

    /* --- TOP NAVIGATION BAR --- */
    .travel-navbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #FFFFFF;
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 0.8rem 1.4rem;
        margin-bottom: 1.5rem;
        box-shadow: var(--shadow-sm);
    }

    .nav-brand {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .nav-logo {
        font-size: 1.8rem;
        background: var(--gold-subtle);
        border: 1px solid var(--gold-border);
        width: 44px;
        height: 44px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .nav-title-group {
        display: flex;
        flex-direction: column;
        line-height: 1.1;
    }

    .nav-title-main {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-weight: 800;
        font-size: 1.15rem;
        color: var(--burgundy);
        letter-spacing: 0.03em;
    }

    .nav-title-sub {
        font-size: 0.72rem;
        font-weight: 700;
        color: var(--gold-accent);
        letter-spacing: 0.18em;
    }

    .nav-links {
        display: flex;
        align-items: center;
        gap: 24px;
    }

    .nav-item {
        color: var(--text-muted);
        text-decoration: none;
        font-weight: 600;
        font-size: 0.9rem;
        transition: color 0.15s ease;
    }

    .nav-item:hover, .nav-item.active {
        color: var(--burgundy);
    }

    .nav-user {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .user-pill {
        background: var(--gold-subtle);
        border: 1px solid var(--gold-border);
        color: #5C4314;
        font-size: 0.8rem;
        font-weight: 700;
        padding: 5px 14px;
        border-radius: 999px;
    }

    /* --- HERO BANNER --- */
    .hero-banner {
        position: relative;
        background: linear-gradient(135deg, #4A0D17 0%, #6E1423 50%, #3B1F1F 100%);
        border-radius: 20px;
        padding: 2.8rem 2.4rem;
        color: #FFFFFF;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(110, 20, 35, 0.18);
        overflow: hidden;
    }

    .hero-banner::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -10%;
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba(212, 175, 55, 0.25) 0%, rgba(110, 20, 35, 0) 70%);
        border-radius: 50%;
        pointer-events: none;
    }

    .hero-badge {
        display: inline-block;
        background: rgba(212, 175, 55, 0.2);
        border: 1px solid rgba(212, 175, 55, 0.4);
        color: #FDF8EC;
        font-size: 0.78rem;
        font-weight: 700;
        padding: 4px 14px;
        border-radius: 999px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 1rem;
    }

    .hero-title {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 2.4rem;
        font-weight: 800;
        color: #FFFFFF;
        line-height: 1.25;
        margin-bottom: 0.8rem;
        max-width: 780px;
    }

    .hero-subtitle {
        font-size: 1.05rem;
        color: #F3E9D2;
        font-weight: 400;
        line-height: 1.5;
        max-width: 720px;
        margin-bottom: 1.6rem;
    }

    .capability-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
        margin-top: 1rem;
    }
    @media (max-width: 768px) {
        .capability-grid { grid-template-columns: 1fr; }
        .nav-links { display: none; }
        .hero-title { font-size: 1.8rem; }
    }

    .cap-card {
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 12px;
        padding: 1rem 1.2rem;
    }

    .cap-title {
        font-weight: 700;
        font-size: 0.85rem;
        color: #FDF8EC;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }

    .cap-desc {
        font-size: 0.85rem;
        color: #E8D9C5;
        font-weight: 400;
    }

    /* Step Pills */
    .step-pill {
        display: inline-block; padding: 7px 16px; border-radius: 20px;
        font-size: 0.82rem; font-weight: 700; margin-right: 8px; margin-bottom: 1.2rem;
        transition: all 0.2s ease;
    }
    .step-active {
        background: var(--burgundy);
        color: #FFFFFF;
        box-shadow: 0 4px 12px rgba(110,20,35,0.3);
    }
    .step-done { background: var(--gold-subtle); color: #5C4314; border: 1px solid #E2D3B1; }
    .step-inactive { background: #EFE8DC; color: #918275; }

    /* Buttons */
    .stButton button, div[data-testid="stFormSubmitButton"] button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.15s ease !important;
        border: 1px solid var(--burgundy) !important;
        color: #FFFFFF !important;
        background: var(--burgundy) !important;
        padding: 0.55rem 1.2rem !important;
        box-shadow: 0 2px 6px rgba(110,20,35,0.2) !important;
    }
    .stButton button:hover, div[data-testid="stFormSubmitButton"] button:hover {
        background: var(--burgundy-light) !important;
        border-color: var(--burgundy-light) !important;
        transform: translateY(-1px);
        box-shadow: 0 5px 14px rgba(110,20,35,0.3) !important;
    }

    /* Secondary / outline buttons */
    button[kind="secondary"] {
        background: #FFFFFF !important;
        color: var(--burgundy) !important;
        border: 1px solid var(--border-color) !important;
    }

    /* Option Cards */
    .option-card-wrap {
        background: #FFFFFF;
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 18px 22px;
        margin-bottom: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.03);
    }
    .option-card-recommended {
        border: 2px solid var(--gold-accent);
        background: #FFFDF9;
    }
    .badge-rec {
        display: inline-block; background: var(--gold-accent); color: #FFFFFF;
        font-size: 0.72rem; font-weight: 700; padding: 2px 10px; border-radius: 12px; text-transform: uppercase;
        margin-left: 8px;
    }

    /* Containers */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px !important;
        border: 1px solid var(--border-color) !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.03) !important;
        background: var(--card-bg) !important;
    }

    /* Tabs */
    button[data-baseweb="tab"] { font-size: 1rem !important; font-weight: 700 !important; color: var(--text-muted) !important; }
    button[data-baseweb="tab"][aria-selected="true"] { color: var(--burgundy) !important; }
    div[data-baseweb="tab-highlight"] { background-color: var(--burgundy) !important; height: 3px !important; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #F5EFE6 !important;
        border-right: 1px solid var(--border-color) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- One-time DB setup ---
with st.spinner("Setting up mock yatra, flight, train & bus data..."):
    build_database()

API_KEY = get_api_key()
BASE_URL = get_base_url()

MODE_LABEL = {"flight": "Flight", "train": "Train", "bus": "Bus"}

# --- Session state guest initialization ---
guest_name = st.session_state.get("guest_id", "Guest-" + uuid.uuid4().hex[:5].upper())
if "guest_id" not in st.session_state:
    st.session_state.guest_id = guest_name

# --- STAGE 1: Top Navigation Header ---
st.markdown(
    f"""
    <div class="travel-navbar">
        <div class="nav-brand">
            <div class="nav-logo">🛕</div>
            <div class="nav-title-group">
                <span class="nav-title-main">VAISHNO DEVI</span>
                <span class="nav-title-sub">YATRA AI</span>
            </div>
        </div>
        <div class="nav-links">
            <span class="nav-item active">Plan Yatra</span>
            <span class="nav-item">Explore J&K</span>
            <span class="nav-item">Yatra Guide</span>
            <span class="nav-item">Helpline</span>
        </div>
        <div class="nav-user">
            <span class="user-pill">👤 {guest_name}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- STAGE 2: Travel Platform Hero Banner ---
st.markdown(
    """
    <div class="hero-banner">
        <div class="hero-badge">✨ AI-Powered Tourism & Pilgrimage Platform</div>
        <h1 class="hero-title">Plan Your Sacred Vaishno Devi Yatra with AI</h1>
        <p class="hero-subtitle">
            Plan travel from any city, search verified transport and darshan slots, discover Jammu & Kashmir destinations, 
            and generate personalized day-by-day itineraries with 24/7 intelligent assistance.
        </p>
        <div class="capability-grid">
            <div class="cap-card">
                <div class="cap-title">1. Smart Yatra Booking</div>
                <div class="cap-desc">Flights, trains, buses + darshan slots</div>
            </div>
            <div class="cap-card">
                <div class="cap-title">2. J&K Tourism Discovery</div>
                <div class="cap-desc">Katra, Patnitop, Kashmir & history</div>
            </div>
            <div class="cap-card">
                <div class="cap-title">3. Dynamic Itineraries</div>
                <div class="cap-desc">Custom day-by-day travel timelines</div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)




# --- Helper: Centralized Trip Input Processor ---
def _process_trip_input(user_text):
    st.session_state.messages.append({"role": "user", "content": user_text})
    current_req = st.session_state.get("trip_request")
    current_itin = st.session_state.get("itinerary")
    last_place = st.session_state.get("last_tourism_place")
    last_itin_ctx = st.session_state.get("last_itinerary_context")
    intent = coordinator.detect_intent(user_text)
    spinner_label = (
        "Looking up yatra information..."
        if intent == "TOURISM"
        else ("Updating your day-by-day itinerary..." if intent == "ITINERARY" else "Checking slots, flights, trains and buses...")
    )
    pending_opts = st.session_state.get("pending_options")
    with st.spinner(spinner_label):
        result = coordinator.route_message(
            user_text,
            current_request=current_req,
            current_itinerary=current_itin,
            last_tourism_place=last_place,
            last_itinerary_context=last_itin_ctx,
            pending_options=pending_opts,
            api_key=API_KEY,
            base_url=BASE_URL,
        )
    st.session_state.messages.append({"role": "assistant", "content": result["reply"]})

    if result.get("last_tourism_place"):
        st.session_state.last_tourism_place = result["last_tourism_place"]

    if result.get("last_itinerary_context"):
        st.session_state.last_itinerary_context = result["last_itinerary_context"]

    if result.get("itinerary") is not None:
        st.session_state.itinerary = result["itinerary"]

    if result.get("intent") == "TOURISM":
        st.rerun()
        return

    if result.get("request") is not None:
        st.session_state.trip_request = result["request"]
    plan = result.get("plan") or {}
    if plan.get("status") == "PLAN_READY":
        st.session_state.pending_options = {"pax": plan["pax"], "options": plan["options"]}
    st.rerun()


# --- STAGE 3: Quick Yatra Search Card Widget ---
st.markdown("### 🔍 Quick Yatra Search & Travel Planner")
st.caption("Select your travel details to generate available flight, train, bus & darshan options instantly.")

with st.container(border=True):
    col_from, col_to, col_pax, col_mode, col_darshan = st.columns([2, 2, 1.5, 1.5, 2])
    with col_from:
        search_from = st.selectbox("From (Origin City)", ["Delhi", "Bhopal", "Mumbai", "Amritsar", "Jammu", "Chandigarh"], key="qs_from")
    with col_to:
        search_to = st.text_input("Destination", value="Vaishno Devi / Katra", disabled=True, key="qs_to")
    with col_pax:
        search_pax = st.number_input("Pilgrims", min_value=1, max_value=10, value=2, key="qs_pax")
    with col_mode:
        search_mode = st.selectbox("Travel Mode", ["Train", "Flight", "Bus"], key="qs_mode")
    with col_darshan:
        search_darshan = st.selectbox("Darshan Preference", ["VIP Darshan", "Normal Darshan"], key="qs_darshan")

    if st.button("🔍 Search Yatra Options with AI", key="btn_quick_search", use_container_width=True):
        qs_query = f"{search_pax} people from {search_from} by {search_mode.lower()} for {search_darshan}"
        _process_trip_input(qs_query)

st.write("")

# --- Sidebar ---
with st.sidebar:
    st.markdown(
        f"""
        <div style="background: #FFFFFF; border: 1px solid #EBE3D5; border-radius: 12px;
                    padding: 1.1rem 1.2rem; margin-bottom: 1rem; box-shadow: 0 2px 8px rgba(0,0,0,0.03);">
            <div style="color: #6E1423; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;">
                Vaishno Devi Yatra AI
            </div>
            <div style="color: #2B2222; font-size: 1.1rem; font-weight: 700; margin-top: 4px;">
                {st.session_state.guest_id}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Temporary session identity — no login required.")
    st.divider()

    st.markdown("#### Booking History")
    bookings = db.list_bookings(user_name=st.session_state.guest_id)
    if not bookings:
        st.info("No bookings yet — start a conversation to plan your yatra.")
    for b in bookings:
        with st.expander(f"{b['booking_id']} · {b['status']}"):
            st.write(f"**Name:** {b['user_name']}")
            st.write(f"**Passengers:** {b['pax_count']}")
            st.write(f"**Yatra:** {b.get('category', '-')} on {b.get('slot_date', '-')}")
            mode = b.get("transport_mode", "-")
            st.write(f"**Transport:** {MODE_LABEL.get(mode, 'Transport')} {b.get('transport_no', '-')} ({b.get('origin', '-')})")
            if b.get("hotel_name") and str(b.get("hotel_name")) != "nan":
                st.write(f"**Hotel:** {b.get('hotel_name')} ({b.get('hotel_category', '-')}), {b.get('hotel_nights', '-')} night(s)")
            if b.get("sightseeing_places") and str(b.get("sightseeing_places")) != "nan":
                st.write(f"**Sightseeing:** {b.get('sightseeing_places')}")
            st.write(f"**Total:** ₹{b['total_price']}")

    st.divider()
    with st.expander("System & Developer Status"):
        st.caption(f"LLM Engine: {'GPT-OSS Active' if API_KEY else 'English Rule-Based Mode'}")
        if BASE_URL:
            st.caption(f"Base URL: {BASE_URL}")


def render_steps(current):
    labels = [
        "1. Request", "2. Options", "3. Stay",
        "4. Sightseeing", "5. Itinerary", "6. Confirm",
    ]
    html = ""
    for i, label in enumerate(labels, start=1):
        cls = "step-active" if i == current else ("step-done" if i < current else "step-inactive")
        html += f'<span class="step-pill {cls}">{label}</span>'
    st.markdown(html, unsafe_allow_html=True)


def _reset_flow():
    st.session_state.pending_options = None
    st.session_state.selected_option = None
    st.session_state.hotel_decision = None
    st.session_state.sightseeing_decision = None
    st.session_state.itinerary_confirmed = False
    st.session_state.trip_request = None


# --- Top-level tabs ---
tab_book, tab_explore = st.tabs(["Plan & Book Your Yatra", "Explore Jammu & Kashmir Destinations"])

with tab_book:
    if st.session_state.selected_option and st.session_state.hotel_decision is not None and st.session_state.sightseeing_decision is not None and st.session_state.itinerary_confirmed:
        current_step = 6
    elif st.session_state.selected_option and st.session_state.hotel_decision is not None and st.session_state.sightseeing_decision is not None:
        current_step = 5
    elif st.session_state.selected_option and st.session_state.hotel_decision is not None:
        current_step = 4
    elif st.session_state.selected_option:
        current_step = 3
    elif st.session_state.pending_options:
        current_step = 2
    else:
        current_step = 1
    render_steps(current_step)

    # --- STAGE 6: Active Trip Plan Summary Card ---
    if st.session_state.trip_request:
        req = st.session_state.trip_request
        st.markdown(
            f"""
            <div style="background:#FFFDF9; border:2px solid #E8C874; border-radius:14px; padding:14px 18px; margin-bottom:16px;">
                <div style="font-weight:700; color:#6E1423; font-size:1.02rem; margin-bottom:4px;">
                    ✈️ Active Trip Plan Summary
                </div>
                <div style="display:flex; gap:16px; flex-wrap:wrap; font-size:0.88rem; color:#2B2222;">
                    <div><b>Origin:</b> {req.get('origin', '-')}</div>
                    <div><b>Duration:</b> {req.get('duration_days', '-')} Days</div>
                    <div><b>Pilgrims:</b> {req.get('pax', 1)}</div>
                    <div><b>Mode:</b> {req.get('mode', 'Train').title()}</div>
                    <div><b>Darshan:</b> {req.get('category', 'Normal Darshan')}</div>
                    <div><b>Travel Style:</b> {req.get('travel_style', 'Balanced').title()}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --- Render Conversation ---
    for i, msg in enumerate(st.session_state.messages):
        if msg["role"] == "user":
            st.markdown(f'<div class="user-bubble-wrap"><div class="user-bubble">{msg["content"]}</div></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="assistant-block-wrap"><div class="assistant-block">{msg["content"]}</div></div>', unsafe_allow_html=True)
            render_speak_button(msg["content"], key=f"speak_msg_{i}")

    # --- STEP 2: Structured Option Cards ---
    if st.session_state.pending_options:
        bundle = st.session_state.pending_options
        pax = bundle["pax"]
        options = bundle["options"]

        st.markdown(f"### Available Travel Options")
        st.caption(f"Found {len(options)} options matching your dates and passenger count ({pax} pilgrims).")

        for i, opt in enumerate(options):
            tr = opt.get("transport") or opt.get("flight")
            s = opt["slot"]
            mode = tr.get("mode", "flight")
            label = MODE_LABEL.get(mode, mode.title())
            is_recommended = (i == 0)

            card_class = "option-card-wrap option-card-recommended" if is_recommended else "option-card-wrap"
            rec_badge = '<span class="badge-rec">Recommended · Best Value</span>' if is_recommended else ''

            st.markdown(
                f"""
                <div class="{card_class}">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                        <div style="font-family:'Plus Jakarta Sans',sans-serif; font-weight:700; font-size:1.05rem; color:#6E1423;">
                            Option {i + 1} — {label} {rec_badge}
                        </div>
                        <div style="font-family:'Plus Jakarta Sans',sans-serif; font-weight:800; font-size:1.2rem; color:#6E1423;">
                            Total: ₹{opt["total_price"]}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Transport ({label})**")
                st.write(f"**Provider:** {tr.get('operator', '-')} ({tr.get('transport_no', '-')})")
                st.write(f"**Route:** {tr['origin']} → {tr['destination']}")
                st.write(f"**Departure:** {tr['travel_date']} at {fmt_time(tr['departure_time'])}")
                st.write(f"**Fare:** ₹{tr['price']} / person")
            with col2:
                st.markdown("**Yatra Slot**")
                st.write(f"**Category:** {s['category']}")
                st.write(f"**Slot Time:** {s['slot_date']} at {fmt_time(s['slot_time'])}")
                st.write(f"**Fee:** ₹{s['price']} / person")
                st.write(f"**Passengers:** {pax} pilgrims")

            if mode == "flight":
                st.caption("Flight arrives at Jammu Airport — onward taxi leg to Katra (~1.5 hrs) is included in timing buffers.")
            else:
                st.caption(f"Arrives directly into Katra station/stand — no extra onward leg required.")

            with st.expander("View details"):
                st.json({
                    "Mode": label, "Operator": tr.get("operator", "-"), "Number": tr.get("transport_no", "-"),
                    "Route": f"{tr['origin']} → {tr['destination']}", "Date": tr["travel_date"],
                    "Departure": fmt_time(tr["departure_time"]), "Duration": f"{tr.get('duration_mins', '-')} min",
                    "Yatra Slot Category": s["category"], "Slot Date": s["slot_date"], "Slot Time": fmt_time(s["slot_time"]),
                })

            if st.button(f"Select option {i + 1}", key=f"select_opt_{i}", use_container_width=True):
                st.session_state.selected_option = {"pax": pax, "option": opt}
                st.session_state.pending_options = None
                st.rerun()

            st.write("")

        if st.button("Start over", key="restart_from_step2"):
            _reset_flow()
            st.rerun()

    # --- STEP 3: Accommodation in Katra ---
    elif st.session_state.selected_option and st.session_state.hotel_decision is None:
        bundle = st.session_state.selected_option
        pax, opt = bundle["pax"], bundle["option"]
        tr = opt.get("transport") or opt.get("flight")
        s = opt["slot"]
        check_in_default = tr["travel_date"]

        st.markdown("### Accommodation in Katra")
        st.caption("Add a hotel stay in Katra to complete your itinerary, or continue without hotel booking.")

        taxi = explore_data.get_taxi_info()
        with st.container(border=True):
            st.markdown(f"**Local Transport Guidance:** {taxi['route']} ({taxi['distance']}, {taxi['duration']})")
            for opt_taxi in taxi["options"]:
                st.write(f"- {opt_taxi['vehicle']} ({opt_taxi['capacity']}): {opt_taxi['fare_range']}")

        want_hotel = st.radio("Would you like to add a hotel stay?", ["No, skip this step", "Yes, view available hotels"], horizontal=True, key="hotel_radio")
        col1, col2 = st.columns(2)
        with col1:
            hotel_category_choice = st.selectbox("Hotel Category", ["Any", "Budget", "Mid-Range", "Premium"], key="hotel_cat")
        with col2:
            nights = st.number_input("Nights of Stay", min_value=1, max_value=7, value=1, key="hotel_nights_input")

        if want_hotel == "No, skip this step":
            if st.button("Continue", key="skip_hotel", use_container_width=True):
                st.session_state.hotel_decision = {}
                st.rerun()
        else:
            if st.button("Search hotels", key="search_hotels_btn", use_container_width=True):
                hotels = coordinator.get_hotel_options(
                    check_in_default,
                    category=None if hotel_category_choice == "Any" else hotel_category_choice,
                )
                st.session_state["_hotel_results"] = {"hotels": hotels, "nights": nights}

            hotel_results = st.session_state.get("_hotel_results")
            if hotel_results:
                hotels, nights = hotel_results["hotels"], hotel_results["nights"]
                if not hotels:
                    st.warning("No hotels found for that category. Try 'Any' category or continue.")
                else:
                    for h in hotels[:5]:
                        with st.container(border=True):
                            st.markdown(f"**{h['name']}** · {h['category']}")
                            st.write(f"₹{h['price_per_night']}/night · {nights} night(s) → ₹{h['price_per_night'] * nights} total")
                            if st.button(f"Select {h['name']}", key=f"select_hotel_{h['id']}", use_container_width=True):
                                st.session_state.hotel_decision = {"hotel": h, "nights": nights}
                                st.session_state.pop("_hotel_results", None)
                                st.rerun()

        if st.button("Back to options", key="back_to_step2_from_hotel"):
            st.session_state.selected_option = None
            st.rerun()

    # --- STEP 4: Sightseeing ---
    elif st.session_state.selected_option and st.session_state.hotel_decision is not None and st.session_state.sightseeing_decision is None:
        bundle = st.session_state.selected_option
        pax, opt = bundle["pax"], bundle["option"]

        st.markdown("### Discover Places Around Katra & Jammu")
        st.caption("Select places to visit after darshan. Recommendations include verified history, entry fees, and video links.")

        want_sightseeing = st.radio(
            "Add sightseeing to itinerary?",
            ["No, skip sightseeing", "Yes, choose places"],
            horizontal=True,
            key="sightseeing_radio",
        )

        if want_sightseeing == "No, skip sightseeing":
            if st.button("Continue", key="skip_sightseeing", use_container_width=True):
                st.session_state.sightseeing_decision = []
                st.rerun()
        else:
            categories = ["All"] + explore_data.get_categories()
            chosen_cat = st.selectbox("Category Filter", categories, key="sightseeing_cat_filter")
            places = coordinator.get_sightseeing_places(None if chosen_cat == "All" else chosen_cat)

            picked = []
            for p in places:
                with st.container(border=True):
                    render_place_image(p, height_px=140)
                    checked = st.checkbox(
                        f"**{p['name']}** · {p['category']} ({p['distance']})",
                        key=f"sight_{p['name']}",
                    )
                    st.caption(p["description"])
                    st.caption(f"Timings: {p.get('timings', 'Not confirmed')} · Entry: {p.get('entry_fee', 'Not confirmed')}")
                    with st.expander("Historical Background"):
                        st.write(p["historical_background"])
                    st.markdown(f"[Watch Video Search Guide]({p['video_search']})")
                    if checked:
                        picked.append(p["name"])

            if st.button("Continue with selected places", key="confirm_sightseeing", use_container_width=True):
                st.session_state.sightseeing_decision = picked
                st.rerun()

        if st.button("Back", key="back_to_step3_from_sightseeing"):
            st.session_state.hotel_decision = None
            st.rerun()

    # --- STEP 5: Timeline Day-Card Itinerary ---
    elif st.session_state.selected_option and st.session_state.hotel_decision is not None and st.session_state.sightseeing_decision is not None and not st.session_state.itinerary_confirmed:
        bundle = st.session_state.selected_option
        pax, opt = bundle["pax"], bundle["option"]
        hotel_choice = st.session_state.hotel_decision or {}
        hotel = hotel_choice.get("hotel")
        hotel_nights = hotel_choice.get("nights", 0)
        sightseeing_places = st.session_state.sightseeing_decision or []

        itinerary = coordinator.build_final_itinerary(
            opt, hotel=hotel, hotel_nights=hotel_nights, sightseeing_places=sightseeing_places, request=st.session_state.get("trip_request")
        )

        st.markdown("### Day-Wise Itinerary")
        st.caption("Your customized day-by-day travel schedule based on your exact transport and darshan choices.")

        for day in itinerary:
            with st.container(border=True):
                st.markdown(
                    f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span style="background:#6E1423; color:#FFF; font-weight:700; font-size:0.78rem; padding:3px 12px; border-radius:12px; text-transform:uppercase;">
                            DAY {day['day_number']:02d}
                        </span>
                        <span style="color:#6C5D5D; font-size:0.88rem; font-weight:600;">{day['date']}</span>
                    </div>
                    <div style="font-family:'Plus Jakarta Sans',sans-serif; font-weight:700; font-size:1.1rem; color:#2B2222; margin-bottom:8px;">
                        {day['title']}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                for a in day["activities"]:
                    st.write(f"- {a}")

        if st.button("Continue to review", key="confirm_itinerary", use_container_width=True):
            st.session_state.itinerary_confirmed = True
            st.rerun()

        if st.button("Back", key="back_to_step4_from_itinerary"):
            st.session_state.sightseeing_decision = None
            st.rerun()

    # --- STEP 6: Review & Authorize Booking ---
    elif st.session_state.selected_option:
        bundle = st.session_state.selected_option
        pax, opt = bundle["pax"], bundle["option"]
        tr = opt.get("transport") or opt.get("flight")
        s = opt["slot"]
        mode = tr.get("mode", "flight")
        label = MODE_LABEL.get(mode, mode.title())
        hotel_choice = st.session_state.hotel_decision or {}
        hotel = hotel_choice.get("hotel")
        hotel_nights = hotel_choice.get("nights", 0)
        hotel_cost = (hotel["price_per_night"] * hotel_nights) if hotel else 0
        grand_total = opt["total_price"] + hotel_cost
        sightseeing_places = st.session_state.sightseeing_decision or []

        st.markdown("### Review & Authorize Booking")
        st.caption("Verify your booking summary and authorize AI execution.")

        with st.container(border=True):
            st.write(f"**Transport:** {label} via {tr.get('operator', '-')} ({tr.get('transport_no', '-')}) · {tr['origin']} → {tr['destination']} ({tr['travel_date']})")
            st.write(f"**Yatra Slot:** {s['category']} · {s['slot_date']} at {fmt_time(s['slot_time'])}")
            st.write(f"**Passengers:** {pax} pilgrims")
            if hotel:
                st.write(f"**Accommodation:** {hotel['name']} ({hotel['category']}) · {hotel_nights} night(s) · ₹{hotel_cost}")
            else:
                st.write("**Accommodation:** None added")
            if sightseeing_places:
                st.write(f"**Sightseeing:** {', '.join(sightseeing_places)}")

        with st.container(border=True):
            st.markdown("#### Human Authorization")
            rpa_auth = st.checkbox("I confirm details & authorize AI RPA agent to execute booking", value=True, key="chk_rpa_auth")
            run_rpa = st.checkbox("Run Playwright RPA visual automation demonstration", value=True, key="chk_run_rpa")

        paid = payment.render_payment_form("Total amount for this booking:", grand_total)

        if paid:
            if not rpa_auth:
                st.error("Human authorization required. Please check the authorization box above.")
            else:
                rpa_info = None
                if run_rpa:
                    with st.spinner("Playwright RPA Agent executing mock booking workflow..."):
                        rpa_info = coordinator.execute_rpa_demo(
                            user_name=st.session_state.guest_id,
                            pax_count=pax,
                            transport_text=f"{label} {tr.get('operator', '-')} {tr.get('transport_no', '')} from {tr['origin']}",
                            slot_text=f"{s['category']} on {s['slot_date']} at {s['slot_time']}",
                            total_price=grand_total,
                            headless=True,
                        )

                booking_id, blessing = coordinator.confirm_booking(
                    opt, pax, st.session_state.guest_id,
                    hotel=hotel, hotel_nights=hotel_nights,
                    sightseeing_places=sightseeing_places,
                )
                st.balloons()

                rpa_msg = ""
                if rpa_info and rpa_info.get("status") == "SUCCESS":
                    rpa_msg = f"\n\nPlaywright RPA Execution: Verified via browser agent (Ref: `{rpa_info['booking_id']}`)."

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": f"{blessing}\n\nYour confirmation ID is **{booking_id}**.{rpa_msg} Total paid (mock): ₹{grand_total}.",
                    }
                )

                if rpa_info and rpa_info.get("screenshot_path") and os.path.exists(rpa_info["screenshot_path"]):
                    st.session_state["last_rpa_screenshot"] = rpa_info["screenshot_path"]

                _reset_flow()
                st.rerun()

        if st.button("Back", key="back_to_step5"):
            st.session_state.itinerary_confirmed = False
            st.rerun()

    # --- STEP 1 / STAGE 5: Conversational AI Assistant & Prompt Chips ---
    else:
        st.markdown("### 💬 Ask Yatra AI Travel Assistant")
        st.caption("Ask questions, plan custom trips, edit your itinerary, or check weather in natural language.")

        st.markdown("##### Popular Assistant Prompts:")
        chip_cols = st.columns(5)
        with chip_cols[0]:
            if st.button("Plan 5 days from Bhopal", key="chip_bhopal", use_container_width=True):
                _process_trip_input("Plan a 5-day trip from Bhopal")
        with chip_cols[1]:
            if st.button("Places around Katra", key="chip_katra", use_container_width=True):
                _process_trip_input("What places can I visit around Katra?")
        with chip_cols[2]:
            if st.button("About Bhairavnath", key="chip_bhairav", use_container_width=True):
                _process_trip_input("Tell me about Bhairavnath")
        with chip_cols[3]:
            if st.button("Show Itinerary", key="chip_itin", use_container_width=True):
                _process_trip_input("Show my itinerary")
        with chip_cols[4]:
            if st.button("Katra Weather", key="chip_weather", use_container_width=True):
                _process_trip_input("What's the weather in Katra?")

        incoming_voice_text = st.query_params.get("voice_input")
        if incoming_voice_text:
            st.query_params.pop("voice_input", None)
            st.query_params.pop("voice_ts", None)
            _process_trip_input(incoming_voice_text)

        render_voice_input()
        if prompt := st.chat_input("Ask Yatra AI — e.g., '4 people from Bhopal next week by train for VIP darshan'"):
            _process_trip_input(prompt)


# --- STAGE 4 & 6: Explore J&K Destinations & Yatra Essentials ---
with tab_explore:
    st.subheader("Explore Jammu & Kashmir Destinations")
    st.caption("Discover top destinations across Jammu & Kashmir with instant AI guidance.")

    if "selected_explore_place" not in st.session_state:
        st.session_state.selected_explore_place = None

    if st.session_state.selected_explore_place:
        p = explore_data.get_place_by_name(st.session_state.selected_explore_place)
        if st.button("Back to all places", key="back_to_places_grid"):
            st.session_state.selected_explore_place = None
            st.rerun()

        with st.container(border=True):
            render_place_image(p, height_px=260)
            st.markdown(f'<div style="font-size:1.4rem; font-weight:800; color:#6E1423;">{p["name"]}</div>', unsafe_allow_html=True)
            st.markdown(f'**Category:** {p["category"]} · **Distance:** {p["distance"]}', unsafe_allow_html=True)
            st.write("")
            st.write(p["description"])

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Timings:** {p.get('timings', 'Not confirmed')}")
            with col2:
                st.markdown(f"**Entry:** {p.get('entry_fee', 'Not confirmed')}")

            st.markdown("**Historical Background**")
            st.write(p["historical_background"])

            st.markdown(f"[Watch Video Guide]({p['video_search']})")
            st.caption(f"Local Travel Note: {explore_data.get_local_travel_note(p['category'])}")

            if st.button(f"Ask AI about {p['name']}", key=f"ask_ai_detail_{p['name']}", use_container_width=True):
                _process_trip_input(f"Tell me about {p['name']}")

    else:
        categories = ["All"] + explore_data.get_categories()
        chosen = st.selectbox("Filter by Category", categories, key="explore_tab_cat_filter")
        places = explore_data.get_places(None if chosen == "All" else chosen)

        cols = st.columns(3)
        for i, p in enumerate(places):
            with cols[i % 3]:
                with st.container(border=True):
                    render_place_image(p, height_px=120)
                    st.markdown(f'<div style="font-weight:700; font-size:1rem; color:#6E1423;">{p["name"]}</div>', unsafe_allow_html=True)
                    st.markdown(f'<span style="font-size:0.78rem; color:#665757;">{p["category"]} · {p["distance"]}</span>', unsafe_allow_html=True)
                    st.caption(p["description"][:110] + "...")
                    
                    c_btn1, c_btn2 = st.columns(2)
                    with c_btn1:
                        if st.button("Details", key=f"view_{p['name']}", use_container_width=True):
                            st.session_state.selected_explore_place = p["name"]
                            st.rerun()
                    with c_btn2:
                        if st.button("Ask AI", key=f"ask_ai_{p['name']}", use_container_width=True):
                            _process_trip_input(f"Tell me about {p['name']}")

    st.divider()

    st.subheader("Yatra Essentials & Pilgrim Guidance")
    st.caption("Official guidelines, route maps, and pilgrim safety advice.")

    with st.expander("Aarti Timings (Darshan Pauses During These Windows)"):
        aarti = yatra_info.get_aarti_timings()
        st.write(f"**Morning:** {aarti['morning']['start']} – {aarti['morning']['end']} ({aarti['morning']['note']})")
        st.write(f"**Evening (Summer, Apr–Sep):** {aarti['evening_summer']['start']} – {aarti['evening_summer']['end']}")
        st.write(f"**Evening (Winter, Oct–Mar):** {aarti['evening_winter']['start']} – {aarti['evening_winter']['end']}")
        st.caption(aarti["general_note"])

    with st.expander("Yatra Registration (Mandatory Requirement)"):
        reg = yatra_info.get_registration_info()
        st.write(f"**Cost:** {reg['cost']}")
        st.caption(reg["mandatory_note"])
        st.markdown("**How to register:**")
        for step in reg["how_to_register"]:
            st.write(f"- {step}")
        st.markdown("**What you'll need:**")
        for item in reg["what_youll_need"]:
            st.write(f"- {item}")
        st.warning(reg["reminder"])

    with st.expander("Route Options to Bhawan"):
        for route in yatra_info.get_route_options():
            st.markdown(f"**{route['name']}** · {route['distance']} · {route['duration']}")
            st.caption(route["path"])
            st.write(route["notes"])
            st.divider()

    with st.expander("Packing Guidance"):
        packing = yatra_info.get_packing_guidance()
        st.caption(packing["disclaimer"])
        st.markdown("**Recommended:**")
        for item in packing["recommended"]:
            st.write(f"- {item}")
        st.markdown("**Commonly Restricted:**")
        for item in packing["commonly_restricted"]:
            st.write(f"- {item}")

    with st.expander("Free Facilities Along Route"):
        for fac in yatra_info.get_facilities():
            st.write(f"**{fac['name']}** — {fac['note']}")

    with st.expander("Official Yatra Helpline"):
        helpline = yatra_info.get_helpline()
        st.write(f"**{helpline['official_yatra_helpline']}**")
        st.caption(helpline["note"])

    st.divider()

    st.subheader("Getting from Jammu to Katra")
    taxi = explore_data.get_taxi_info()
    with st.container(border=True):
        st.markdown(f"**Route:** {taxi['route']} ({taxi['distance']}, {taxi['duration']})")
        for opt_taxi in taxi["options"]:
            st.write(f"- {opt_taxi['vehicle']} ({opt_taxi['capacity']}): {opt_taxi['fare_range']}")
        st.caption(taxi["note"])


# --- STAGE 8: Modern Travel Platform Footer ---
st.markdown(
    """
    <div style="margin-top:4rem; padding-top:2rem; border-top:1px solid #E8E0D2; text-align:center; color:#665757; font-size:0.85rem;">
        <div style="font-family:'Playfair Display',serif; font-weight:800; font-size:1.2rem; color:#6E1423; margin-bottom:4px;">
            VAISHNO DEVI YATRA AI
        </div>
        <div>Your Intelligent Pilgrimage & Jammu Kashmir Tourism Companion</div>
        <div style="margin-top:10px; font-weight:600; color:#4A0D17;">
            Official Helpline: 01991-232820 · Emergency Yatra Cell: 1800-180-7777
        </div>
        <div style="margin-top:8px; font-size:0.78rem; color:#998888;">
            © 2026 Vaishno Devi Yatra AI Project. Built for seamless pilgrimage and tourism discovery across Jammu & Kashmir.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
