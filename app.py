"""
app.py
Streamlit front-end for the Vaishno Devi Yatra Booking Agent prototype.
Run locally with: streamlit run app.py

This version presents a premium, travel-platform interface inspired by the reference design,
while preserving 100% of the underlying AI, coordinator, intent-routing, recommendation,
itinerary, weather, and Playwright RPA booking backend.
"""

import json
import os
import re
import uuid
from datetime import datetime, timedelta

import streamlit as st
import streamlit.components.v1 as components

import db
import explore_data
import payment
import yatra_info
from agents import coordinator
from data_gen import build_database


def fmt_time(hhmm):
    """Formats a 24-hour 'HH:MM' string as 12-hour with AM/PM, e.g. '06:00' -> '6:00 AM'."""
    try:
        t = datetime.strptime(str(hhmm), "%H:%M")
        hour_12 = t.hour % 12 or 12
        return f"{hour_12}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"
    except (ValueError, TypeError):
        return str(hhmm)


def _strip_markdown_for_speech(text):
    """Removes markdown formatting so the spoken text sounds natural."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#_`]", "", text)
    return text


def render_voice_input(key="voice_input_main"):
    """Renders a mic button using browser Web Speech API."""
    html = f"""
    <html><body style="margin:0; background:transparent;">
    <div style="font-family:'Plus Jakarta Sans',sans-serif; display:flex; align-items:center; gap:8px;">
      <select id="lang_{key}" style="border-radius:8px; border:1px solid #E5D2AD; padding:5px 10px; font-size:0.8rem; background:#FBF9F4; color:#2A2020;">
        <option value="en-IN">English</option>
        <option value="hi-IN">हिंदी (Hindi)</option>
        <option value="pa-IN">ਪੰਜਾਬੀ (Punjabi)</option>
        <option value="ur-IN">اردو (Urdu)</option>
      </select>
      <button id="mic_{key}" onclick="startListen_{key}()" style="
          display:flex; align-items:center; gap:6px; background:#58111A; border:1px solid #B8860B; color:#FBF9F4;
          font-weight:700; border-radius:999px; padding:6px 18px; font-size:0.82rem; cursor:pointer;
          transition: all 0.15s ease;
      " onmouseover="this.style.background='#7A1926'" onmouseout="this.style.background='#58111A'">
        🎤 Speak Your Query
      </button>
      <span id="status_{key}" style="font-size:0.78rem; color:#6B5C5C;"></span>
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
    components.html(html, height=44)


def render_speak_button(text, key):
    """Renders small 'Listen'/'Stop' icon buttons for Web Speech TTS."""
    clean_text = _strip_markdown_for_speech(text)
    safe_text = json.dumps(clean_text)
    html = f"""
    <html><body style="margin:0; background:transparent;">
    <div style="font-family:'Plus Jakarta Sans',sans-serif; display:flex; gap:6px; background:transparent;">
      <button onclick="speak_{key}()" style="
          display:flex; align-items:center; gap:5px; background:#3D0810; border:1px solid #B8860B; color:#FBF9F4;
          font-weight:600; border-radius:999px; padding:5px 14px; font-size:0.76rem; cursor:pointer;
          transition: all 0.15s ease;
      " onmouseover="this.style.background='#58111A'" onmouseout="this.style.background='#3D0810'">
        🔊 Listen Aloud
      </button>
      <button onclick="if(window.speechSynthesis) window.speechSynthesis.cancel();" style="
          display:flex; align-items:center; gap:5px; background:#F5ECDA; border:1px solid #E5D2AD; color:#58111A;
          font-weight:600; border-radius:999px; padding:5px 14px; font-size:0.76rem; cursor:pointer;
          transition: all 0.15s ease;
      " onmouseover="this.style.background='#E5D2AD'" onmouseout="this.style.background='#F5ECDA'">
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
    """Shows place photo or themed gradient placeholder."""
    img_path = os.path.join("assets", "places", place.get("image_file", ""))
    if place.get("image_file") and os.path.exists(img_path):
        st.image(img_path, use_container_width=True)
    else:
        st.markdown(
            f"""
            <div style="height:{height_px}px; border-radius:12px; margin-bottom:0.6rem;
                        background: linear-gradient(135deg, #58111A 0%, #3D0810 60%, #1A0407 100%);
                        border: 1px solid #E5D2AD;
                        display:flex; align-items:center; justify-content:center;">
                <span style="font-size:2.4rem; color:#B8860B; opacity:0.8;">📍</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def get_api_key():
    try:
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    return os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")


def get_base_url():
    try:
        if "OPENAI_BASE_URL" in st.secrets:
            return st.secrets["OPENAI_BASE_URL"]
    except Exception:
        pass
    return os.environ.get("OPENAI_BASE_URL")


# Page Setup
st.set_page_config(
    page_title="Vaishno Devi Yatra AI — Divine Journeys, Powered by AI",
    page_icon="🔱",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# One-time database setup
with st.spinner("Initializing yatra, transport & slot databases..."):
    build_database()

API_KEY = get_api_key()
BASE_URL = get_base_url()

MODE_LABEL = {"flight": "Flight", "train": "Train", "bus": "Bus"}

# --- STYLING: Premium Indian Pilgrimage Travel Platform (Matching Reference Design) ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,700;0,800;1,700&display=swap');

    :root {
        --bg-main: #FDFBF7;
        --card-bg: #FFFFFF;
        --burgundy-dark: #3D0810;
        --burgundy: #58111A;
        --burgundy-light: #7A1926;
        --gold-primary: #B8860B;
        --gold-accent: #C09A3E;
        --gold-subtle: #F5ECDA;
        --gold-border: #E5D2AD;
        --text-dark: #2A2020;
        --text-muted: #6B5C5C;
        --border-subtle: #EBE1D0;
        --shadow-elevation: 0 10px 30px rgba(88, 17, 26, 0.08);
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 15px;
        color: var(--text-dark);
        background-color: var(--bg-main);
    }

    .stApp {
        background-color: var(--bg-main);
    }

    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    .block-container {
        max-width: 1240px;
        padding-top: 0.8rem;
        padding-bottom: 3rem;
    }

    /* --- TOP NAVIGATION BAR --- */
    .luxury-navbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #FBF9F4;
        border: 1px solid var(--gold-border);
        border-radius: 16px;
        padding: 0.75rem 1.6rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.03);
    }

    .nav-brand-group {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .trident-icon {
        font-size: 1.8rem;
        color: var(--gold-primary);
        line-height: 1;
    }

    .nav-brand-title {
        display: flex;
        flex-direction: column;
        line-height: 1.05;
    }

    .brand-top {
        font-family: 'Cinzel', serif;
        font-weight: 800;
        font-size: 1.1rem;
        letter-spacing: 0.04em;
        color: var(--burgundy);
    }

    .brand-bottom {
        font-family: 'Cinzel', serif;
        font-weight: 700;
        font-size: 0.82rem;
        letter-spacing: 0.16em;
        color: var(--burgundy);
    }

    .ai-badge-text {
        background: var(--gold-accent);
        color: #FFFFFF;
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.65rem;
        font-weight: 800;
        padding: 1px 5px;
        border-radius: 4px;
        margin-left: 2px;
    }

    .nav-center-links {
        display: flex;
        align-items: center;
        gap: 22px;
    }

    .nav-link {
        color: var(--text-dark);
        font-weight: 600;
        font-size: 0.88rem;
        text-decoration: none;
        padding-bottom: 3px;
        border-bottom: 2px solid transparent;
        transition: all 0.15s ease;
    }

    .nav-link.active, .nav-link:hover {
        color: var(--burgundy);
        border-bottom-color: var(--gold-primary);
    }

    .nav-link.placeholder-link {
        color: #A09090;
        cursor: not-allowed;
    }

    .nav-right-actions {
        display: flex;
        align-items: center;
        gap: 14px;
    }

    .account-btn {
        background: var(--gold-subtle);
        border: 1px solid var(--gold-border);
        color: var(--burgundy);
        font-weight: 700;
        font-size: 0.82rem;
        padding: 6px 16px;
        border-radius: 999px;
        cursor: pointer;
    }

    .search-icon-btn {
        font-size: 1.1rem;
        color: var(--burgundy);
        cursor: pointer;
    }

    /* --- HERO BANNER (Matching Reference Image) --- */
    .hero-container {
        position: relative;
        background: linear-gradient(125deg, #3D0810 0%, #58111A 45%, #2A0409 100%);
        border-radius: 24px;
        padding: 3.2rem 3rem 5.5rem 3rem;
        color: #FFFFFF;
        margin-bottom: 0rem; /* Overlapped by search widget */
        border: 1px solid rgba(184, 134, 11, 0.3);
        box-shadow: var(--shadow-elevation);
        overflow: hidden;
    }

    .hero-container::before {
        content: '';
        position: absolute;
        top: 0; left: 0; bottom: 0; width: 35%;
        background-image: radial-gradient(rgba(184, 134, 11, 0.15) 1px, transparent 0);
        background-size: 18px 18px;
        opacity: 0.6;
        pointer-events: none;
    }

    .hero-badge-tag {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(184, 134, 11, 0.22);
        border: 1px solid rgba(229, 210, 173, 0.4);
        color: #FDF8EC;
        font-size: 0.85rem;
        font-weight: 700;
        padding: 5px 14px;
        border-radius: 999px;
        margin-bottom: 1.2rem;
    }

    .hero-main-title {
        font-family: 'Playfair Display', serif;
        font-size: 2.8rem;
        font-weight: 800;
        letter-spacing: 0.02em;
        line-height: 1.18;
        color: #FFFFFF;
        margin-bottom: 0.8rem;
        max-width: 680px;
    }

    .hero-sub-title {
        font-size: 1.1rem;
        color: #E8D5B7;
        font-weight: 400;
        margin-bottom: 1.8rem;
        max-width: 620px;
    }

    /* --- FLOATING YATRA SEARCH WIDGET --- */
    .search-card-wrapper {
        position: relative;
        z-index: 10;
        margin-top: -3.2rem;
        margin-bottom: 2.4rem;
        padding: 0 1rem;
    }

    .search-card-inner {
        background: #FFFFFF;
        border: 2px solid var(--gold-border);
        border-radius: 20px;
        padding: 1.8rem 2rem;
        box-shadow: 0 12px 35px rgba(88, 17, 26, 0.12);
    }

    .search-card-header {
        font-family: 'Cinzel', serif;
        font-weight: 700;
        font-size: 1.05rem;
        color: var(--burgundy);
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Buttons Override */
    .stButton button, div[data-testid="stFormSubmitButton"] button {
        border-radius: 10px !important;
        font-weight: 700 !important;
        transition: all 0.18s ease !important;
        border: 1px solid var(--gold-primary) !important;
        color: #FFFFFF !important;
        background: var(--gold-primary) !important;
        padding: 0.65rem 1.4rem !important;
        box-shadow: 0 3px 10px rgba(184, 134, 11, 0.25) !important;
    }
    .stButton button:hover, div[data-testid="stFormSubmitButton"] button:hover {
        background: var(--gold-accent) !important;
        border-color: var(--gold-accent) !important;
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(184, 134, 11, 0.35) !important;
    }

    /* Option & Detail Cards */
    .option-card-wrap {
        background: #FFFFFF;
        border: 1px solid var(--gold-border);
        border-radius: 14px;
        padding: 20px 24px;
        margin-bottom: 16px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.03);
    }
    .option-card-recommended {
        border: 2px solid var(--gold-primary);
        background: #FFFCF7;
    }
    .badge-rec {
        display: inline-block; background: var(--gold-primary); color: #FFFFFF;
        font-size: 0.72rem; font-weight: 700; padding: 3px 12px; border-radius: 12px; text-transform: uppercase;
        margin-left: 8px;
    }

    /* Containers */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 14px !important;
        border: 1px solid var(--gold-border) !important;
        box-shadow: 0 3px 10px rgba(0,0,0,0.03) !important;
        background: #FFFFFF !important;
    }

    /* Floating AI Widget (Bottom Right) */
    .floating-ai-box {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 9999;
        background: #FFFFFF;
        border: 2px solid var(--gold-border);
        border-radius: 16px;
        padding: 10px 18px;
        box-shadow: 0 8px 24px rgba(88, 17, 26, 0.18);
        display: flex;
        align-items: center;
        gap: 10px;
        cursor: pointer;
    }

    .floating-ai-badge {
        background: var(--burgundy);
        color: #FFFFFF;
        font-weight: 800;
        font-size: 0.85rem;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    /* Footer */
    .luxury-footer {
        margin-top: 4rem;
        padding-top: 2.2rem;
        border-top: 1px solid var(--gold-border);
        text-align: center;
        color: var(--text-muted);
        font-size: 0.85rem;
    }

    @media (max-width: 768px) {
        .nav-center-links { display: none; }
        .hero-main-title { font-size: 2rem; }
        .search-card-wrapper { margin-top: -1.5rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Session state guest & messages initialization ---
if "guest_id" not in st.session_state:
    st.session_state.guest_id = "Guest-" + uuid.uuid4().hex[:5].upper()

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": coordinator.get_greeting()}]
if "trip_request" not in st.session_state:
    st.session_state.trip_request = None
if "pending_options" not in st.session_state:
    st.session_state.pending_options = None
if "selected_option" not in st.session_state:
    st.session_state.selected_option = None
if "hotel_decision" not in st.session_state:
    st.session_state.hotel_decision = None
if "sightseeing_decision" not in st.session_state:
    st.session_state.sightseeing_decision = None
if "itinerary_confirmed" not in st.session_state:
    st.session_state.itinerary_confirmed = False
if "last_tourism_place" not in st.session_state:
    st.session_state.last_tourism_place = None
if "itinerary" not in st.session_state:
    st.session_state.itinerary = None
if "last_itinerary_context" not in st.session_state:
    st.session_state.last_itinerary_context = None


# --- Centralized Input Processor (Preserves existing AI logic 100%) ---
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


# --- SECTION 1: TOP NAVIGATION BAR ---
st.markdown(
    f"""
    <div class="luxury-navbar">
        <div class="nav-brand-group">
            <span class="trident-icon">🔱</span>
            <div class="nav-brand-title">
                <span class="brand-top">VAISHNO DEVI</span>
                <span class="brand-bottom">YATRA <span class="ai-badge-text">AI</span></span>
            </div>
        </div>
        <div class="nav-center-links">
            <span class="nav-link active">Home</span>
            <span class="nav-link">Darshan Bookings</span>
            <span class="nav-link">Yatra Guide</span>
            <span class="nav-link">Packages</span>
            <span class="nav-link placeholder-link" title="Accommodation planning coming in future phase">Hotels</span>
            <span class="nav-link">Transport</span>
            <span class="nav-link">Help</span>
            <span class="nav-link">AI Assistant</span>
        </div>
        <div class="nav-right-actions">
            <button class="account-btn">👤 {st.session_state.guest_id}</button>
            <span class="search-icon-btn">🔍</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- SECTION 2: HERO SECTION ---
st.markdown(
    """
    <div class="hero-container">
        <div class="hero-badge-tag">🔱 AI-Powered Yatra Platform</div>
        <h1 class="hero-main-title">DIVINE JOURNEYS,<br/>POWERED BY AI.</h1>
        <p class="hero-sub-title">Plan Your Vaishno Devi Yatra with Personalized Ease.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- SECTION 3: FLOATING YATRA SEARCH WIDGET ---
st.markdown('<div class="search-card-wrapper"><div class="search-card-inner">', unsafe_allow_html=True)
st.markdown('<div class="search-card-header">🚩 Plan & Search Yatra Options</div>', unsafe_allow_html=True)

col_from, col_to, col_date = st.columns([2.5, 2.5, 2.5])
with col_from:
    origin_cities = ["Jammu", "Bhopal", "Delhi", "Jaipur", "Lucknow", "Mumbai", "Amritsar", "Chandigarh"]
    search_from = st.selectbox("From (Origin)", origin_cities, index=0, key="widget_from")
with col_to:
    search_to = st.text_input("Destination", value="Katra (VND) / Vaishno Devi", disabled=True, key="widget_to")
with col_date:
    today = datetime.now().date()
    search_date = st.date_input("Date of Travel", value=today + timedelta(days=7), min_value=today, key="widget_date")

col_pax, col_mode, col_btn = st.columns([2.5, 2.5, 2.5])
with col_pax:
    search_pax = st.selectbox("Travellers", ["1 Pilgrim", "2 Pilgrims", "3 Pilgrims", "4 Pilgrims", "5 Pilgrims", "6+ Pilgrims"], index=1, key="widget_pax")
with col_mode:
    search_mode = st.selectbox("Mode: Flight / Train / Road", ["Train", "Flight", "Bus"], index=0, key="widget_mode")
with col_btn:
    st.write("") # Spacing alignment
    if st.button("SEARCH YOUR YATRA →", key="btn_widget_search", use_container_width=True):
        pax_num = re.search(r"\d+", search_pax)
        pax_val = pax_num.group(0) if pax_num else "2"
        date_str = search_date.strftime("%d %b %Y")
        query_text = f"{pax_val} people from {search_from} by {search_mode.lower()} on {date_str} for VIP darshan"
        _process_trip_input(query_text)

st.markdown('</div></div>', unsafe_allow_html=True)


# --- SECTION 7: FLOATING AI ASSISTANT (Bottom Right) ---
with st.sidebar:
    st.markdown("### 🔱 Vaishno Devi AI Assistant")
    st.caption("Active Session: " + st.session_state.guest_id)
    st.divider()
    bookings = db.list_bookings(user_name=st.session_state.guest_id)
    if bookings:
        st.markdown("**Your Bookings:**")
        for b in bookings:
            st.write(f"- `{b['booking_id']}` · {b['status']} · ₹{b['total_price']}")
        st.divider()
    st.caption(f"Engine: {'GPT-OSS Active' if API_KEY else 'English Rule-Based System'}")

# --- MAIN TABS: SEARCH RESULTS / DISCOVERY / YATRA GUIDE ---
tab_trip, tab_destinations, tab_guide = st.tabs([
    "📍 Yatra Planner & Booking",
    "🏞️ Featured Destinations (J&K)",
    "📖 Yatra Guide & Essentials"
])

with tab_trip:
    # Render Active Trip Summary Card if active
    if st.session_state.trip_request:
        req = st.session_state.trip_request
        st.markdown(
            f"""
            <div style="background:#FFFCF7; border:2px solid var(--gold-border); border-radius:14px; padding:16px 20px; margin-bottom:20px;">
                <div style="font-family:'Cinzel',serif; font-weight:700; color:var(--burgundy); font-size:1.05rem; margin-bottom:6px;">
                    ✨ Active Trip Plan: {req.get('origin', 'Jammu')} → Katra ({req.get('duration_days', 3)} Days)
                </div>
                <div style="display:flex; gap:20px; flex-wrap:wrap; font-size:0.9rem; color:var(--text-dark);">
                    <div><b>Origin:</b> {req.get('origin', '-')}</div>
                    <div><b>Pilgrims:</b> {req.get('pax', 1)}</div>
                    <div><b>Travel Mode:</b> {req.get('mode', 'Train').title()}</div>
                    <div><b>Darshan:</b> {req.get('category', 'Normal Darshan')}</div>
                    <div><b>Travel Style:</b> {req.get('travel_style', 'Balanced').title()}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # --- Render Assistant Chat Log ---
    for i, msg in enumerate(st.session_state.messages):
        if msg["role"] == "user":
            st.markdown(f'<div style="background:#F5ECDA; border:1px solid #E5D2AD; padding:12px 18px; border-radius:12px; margin-bottom:10px; max-width:80%; margin-left:auto;"><b>You:</b> {msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#FFFFFF; border:1px solid #E5D2AD; padding:14px 20px; border-radius:12px; margin-bottom:10px; box-shadow:0 2px 8px rgba(0,0,0,0.02);"><b>AI Assistant:</b><br/>{msg["content"]}</div>', unsafe_allow_html=True)
            render_speak_button(msg["content"], key=f"speak_{i}")

    # --- Step 2: Options Selection ---
    if st.session_state.pending_options:
        bundle = st.session_state.pending_options
        pax, options = bundle["pax"], bundle["options"]
        st.markdown("### Available Travel & Slot Combinations")
        for i, opt in enumerate(options):
            tr = opt.get("transport") or opt.get("flight")
            s = opt["slot"]
            mode = tr.get("mode", "flight")
            label = MODE_LABEL.get(mode, mode.title())
            is_rec = (i == 0)
            card_cls = "option-card-wrap option-card-recommended" if is_rec else "option-card-wrap"
            rec_tag = '<span class="badge-rec">Recommended</span>' if is_rec else ''

            st.markdown(
                f"""
                <div class="{card_cls}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="font-family:'Cinzel',serif; font-weight:700; font-size:1.05rem; color:#58111A;">
                            Option {i + 1} — {label} {rec_tag}
                        </div>
                        <div style="font-weight:800; font-size:1.2rem; color:#58111A;">
                            Total: ₹{opt["total_price"]}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Transport:** {tr.get('operator', '-')} ({tr.get('transport_no', '-')})")
                st.write(f"**Route:** {tr['origin']} → {tr['destination']}")
                st.write(f"**Departure:** {tr['travel_date']} at {fmt_time(tr['departure_time'])}")
            with col2:
                st.write(f"**Yatra Slot:** {s['category']}")
                st.write(f"**Slot Date/Time:** {s['slot_date']} at {fmt_time(s['slot_time'])}")
                st.write(f"**Pilgrims:** {pax}")

            if st.button(f"Select Option {i + 1}", key=f"sel_opt_{i}", use_container_width=True):
                st.session_state.selected_option = {"pax": pax, "option": opt}
                st.session_state.pending_options = None
                st.rerun()

    # --- Step 3: Hotel Stay (Optional / Placeholder) ---
    elif st.session_state.selected_option and st.session_state.hotel_decision is None:
        st.markdown("### Accommodation Guidance in Katra")
        st.caption("Hotel selection is supported as a visual feature — continue or select hotel options.")
        if st.button("Continue to Sightseeing", key="skip_hotel_btn", use_container_width=True):
            st.session_state.hotel_decision = {}
            st.rerun()

    # --- Step 4: Sightseeing Choice ---
    elif st.session_state.selected_option and st.session_state.hotel_decision is not None and st.session_state.sightseeing_decision is None:
        st.markdown("### Add Sightseeing Places Around Katra")
        places = coordinator.get_sightseeing_places()
        picked = []
        for p in places[:4]:
            if st.checkbox(f"**{p['name']}** ({p['category']} · {p['distance']})", key=f"sg_{p['name']}"):
                picked.append(p["name"])
        if st.button("Proceed to Timeline Itinerary", key="confirm_sg", use_container_width=True):
            st.session_state.sightseeing_decision = picked
            st.rerun()

    # --- Step 5: Day-Wise Timeline Itinerary ---
    elif st.session_state.selected_option and st.session_state.hotel_decision is not None and st.session_state.sightseeing_decision is not None and not st.session_state.itinerary_confirmed:
        bundle = st.session_state.selected_option
        pax, opt = bundle["pax"], bundle["option"]
        itinerary = coordinator.build_final_itinerary(
            opt, hotel=None, hotel_nights=0, sightseeing_places=st.session_state.sightseeing_decision, request=st.session_state.get("trip_request")
        )
        st.markdown("### Customized Day-Wise Itinerary")
        for day in itinerary:
            with st.container(border=True):
                st.markdown(f"**DAY {day['day_number']:02d}** · {day['date']} — **{day['title']}**")
                for act in day["activities"]:
                    st.write(f"- {act}")
        if st.button("Proceed to Review & Booking Authorization", key="conf_itin_btn", use_container_width=True):
            st.session_state.itinerary_confirmed = True
            st.rerun()

    # --- Step 6: Review & Human-in-the-Loop Confirmation Gate ---
    elif st.session_state.selected_option:
        bundle = st.session_state.selected_option
        pax, opt = bundle["pax"], bundle["option"]
        tr = opt.get("transport") or opt.get("flight")
        s = opt["slot"]
        grand_total = opt["total_price"]

        st.markdown("### Review & Authorize Booking")
        with st.container(border=True):
            st.write(f"**Transport:** {tr['origin']} → {tr['destination']} via {tr.get('operator', '-')}")
            st.write(f"**Yatra Slot:** {s['category']} on {s['slot_date']}")
            st.write(f"**Pilgrims:** {pax}")
            st.write(f"**Total Price:** ₹{grand_total}")

        st.markdown("#### Human Authorization Gate")
        rpa_auth = st.checkbox("I confirm details & authorize AI RPA agent to execute booking", value=True, key="rpa_chk")
        run_rpa = st.checkbox("Run Playwright RPA visual automation demonstration", value=True, key="run_rpa_chk")

        paid = payment.render_payment_form("Total mock payment amount:", grand_total)
        if paid:
            if not rpa_auth:
                st.error("Human authorization required. Please check the authorization box above.")
            else:
                rpa_info = None
                if run_rpa:
                    with st.spinner("Playwright RPA Agent executing mock booking..."):
                        rpa_info = coordinator.execute_rpa_demo(
                            user_name=st.session_state.guest_id,
                            pax_count=pax,
                            transport_text=f"{tr['origin']} → Katra",
                            slot_text=s['category'],
                            total_price=grand_total,
                            headless=True,
                        )
                booking_id, blessing = coordinator.confirm_booking(opt, pax, st.session_state.guest_id)
                st.balloons()
                st.success(f"{blessing}\n\nConfirmation Ref: **{booking_id}**")
                st.session_state.pending_options = None
                st.session_state.selected_option = None

    # Chat Input Box
    st.write("")
    render_voice_input()
    if prompt := st.chat_input("Ask Yatra AI — e.g., '4 people from Bhopal next week by train'"):
        _process_trip_input(prompt)


# --- SECTION 5 & 6: FEATURED DESTINATIONS & J&K EXPLORATION ---
with tab_destinations:
    st.markdown("### Featured Destinations across Jammu & Kashmir")
    st.caption("Select any destination to inspect verified facts, timings, entry fees, and video guides.")

    all_places = explore_data.get_places()
    cols = st.columns(3)
    for idx, place in enumerate(all_places):
        with cols[idx % 3]:
            with st.container(border=True):
                render_place_image(place, height_px=140)
                st.markdown(f"**{place['name']}**")
                st.caption(f"{place['category']} · {place['distance']}")
                st.write(place["description"][:110] + "...")
                
                c1, c2 = st.columns(2)
                with c1:
                    with st.expander("History"):
                        st.write(place["historical_background"])
                with c2:
                    if st.button("Explore with AI", key=f"exp_ai_{place['name']}", use_container_width=True):
                        _process_trip_input(f"Tell me about {place['name']}")


# --- SECTION 6: YATRA GUIDE & ESSENTIALS ---
with tab_guide:
    st.markdown("### Yatra Essentials & Pilgrim Guidance")
    
    with st.expander("Aarti Timings (Darshan Pauses During Windows)"):
        aarti = yatra_info.get_aarti_timings()
        st.write(f"**Morning:** {aarti['morning']['start']} – {aarti['morning']['end']}")
        st.write(f"**Evening (Summer):** {aarti['evening_summer']['start']} – {aarti['evening_summer']['end']}")
        st.write(f"**Evening (Winter):** {aarti['evening_winter']['start']} – {aarti['evening_winter']['end']}")

    with st.expander("Mandatory Yatra Registration"):
        reg = yatra_info.get_registration_info()
        st.write(f"**Cost:** {reg['cost']}")
        st.write(reg["mandatory_note"])

    with st.expander("Route Options to Bhawan"):
        for route in yatra_info.get_route_options():
            st.markdown(f"**{route['name']}** ({route['distance']}) — {route['duration']}")

    with st.expander("Packing Guidance"):
        packing = yatra_info.get_packing_guidance()
        st.write("**Recommended:**", ", ".join(packing["recommended"]))
        st.write("**Restricted:**", ", ".join(packing["commonly_restricted"]))


# --- SECTION 8: LUXURY FOOTER ---
st.markdown(
    """
    <div class="luxury-footer">
        <div style="font-family:'Cinzel',serif; font-weight:800; font-size:1.15rem; color:#58111A; margin-bottom:4px;">
            🔱 VAISHNO DEVI YATRA AI
        </div>
        <div>Divine Journeys, Powered by AI · Jammu & Kashmir Tourism Companion</div>
        <div style="margin-top:8px; font-weight:700; color:#3D0810;">
            Official Shrine Board Helpline: 01991-232820 · Emergency Cell: 1800-180-7777
        </div>
        <div style="margin-top:8px; font-size:0.78rem; color:#908080;">
            © 2026 Vaishno Devi Yatra AI Project. Designed for seamless pilgrimage booking and discovery.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
