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
    """Looks for an Anthropic API key in Streamlit secrets (for the
    deployed app) or an environment variable (for local runs). Returns
    None if neither is set - the app still works fully in that case,
    just with rule-based (English-only) parsing instead of the
    LLM-powered multilingual conversational agent."""
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass
    return os.environ.get("ANTHROPIC_API_KEY")


st.set_page_config(page_title="Vaishno Devi Yatra Agent", page_icon="🛕", layout="wide")

# --- Custom styling ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700;800;900&family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --maroon-dark: #6E1423;
        --maroon: #A61B29;
        --maroon-light: #C2374A;
        --gold: #C9A227;
        --gold-light: #E8C874;
        --cream: #FDF6EC;
        --cream-card: #FFFFFF;
        --text-dark: #3B1F1F;
        --text-muted: #8A6857;
    }

    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; font-size: 16px; }
    h1, h2, h3 { font-family: 'Poppins', sans-serif; letter-spacing: -0.01em; }
    p, li, span, label { line-height: 1.55; }

    /* Subtle devotional background texture - soft repeating diya/dot motif, very low opacity */
    .stApp {
        background-color: var(--cream);
        background-image:
            radial-gradient(circle at 4px 4px, rgba(166,27,41,0.05) 1.5px, transparent 0);
        background-size: 26px 26px;
    }

    .block-container { max-width: 1240px; padding-top: 1.6rem; padding-bottom: 3rem; }
    body { overflow-x: hidden; }

    /* Gold top strip - a small premium touch many devotional/temple sites use */
    .top-strip {
        height: 6px; width: 100%;
        background: linear-gradient(90deg, var(--maroon-dark), var(--gold), var(--maroon-dark));
        border-radius: 999px; margin-bottom: 1.2rem;
    }

    /* ---------- Hero ---------- */
    .hero-wrap {
        border-radius: 26px; overflow: hidden; margin-bottom: 1.4rem;
        box-shadow: 0 14px 36px rgba(110,20,35,0.28);
        position: relative;
    }
    .hero-title {
        font-family: 'Poppins', sans-serif; font-weight: 900;
        font-size: 2.5rem; margin: 1.1rem 0 0.3rem 0; color: var(--maroon-dark);
    }
    .hero-sub { font-size: 1.12rem; font-weight: 500; max-width: 660px; color: var(--text-muted); }

    /* ---------- Feature stat row ---------- */
    .stat-row { display: flex; gap: 14px; margin: 1.1rem 0 1.8rem 0; flex-wrap: wrap; }
    .stat-card {
        flex: 1; min-width: 160px;
        background: linear-gradient(160deg, #FFFFFF 0%, #FFF3DE 100%);
        border: 1px solid var(--gold-light); border-radius: 18px;
        padding: 1.1rem 1.2rem; box-shadow: 0 6px 18px rgba(201,162,39,0.16);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .stat-card:hover { transform: translateY(-3px); box-shadow: 0 10px 24px rgba(201,162,39,0.28); }
    .stat-card .stat-num { font-family:'Poppins',sans-serif; font-weight:800; font-size:1.6rem; color: var(--maroon); }
    .stat-card .stat-label { font-size:0.86rem; color: var(--text-muted); font-weight:600; margin-top:2px; }

    /* ---------- Chat ---------- */
    .stChatMessage { border-radius: 18px; }
    div[data-testid="stChatMessage"] { padding: 8px 4px; }
    [data-testid="stChatMessageContent"] p { font-size: 1.03rem; }
    div[data-testid="stChatInput"] {
        border: 2px solid var(--gold-light) !important; border-radius: 16px !important;
        box-shadow: 0 4px 16px rgba(110,20,35,0.08) !important;
    }
    div[data-testid="stChatInput"] textarea { font-size: 1.03rem !important; }
    div[data-testid="stChatInput"]:focus-within {
        border-color: var(--maroon) !important; box-shadow: 0 4px 20px rgba(166,27,41,0.22) !important;
    }

    /* ---------- Step pills ---------- */
    .step-pill {
        display: inline-block; padding: 8px 19px; border-radius: 999px;
        font-size: 0.85rem; font-weight: 700; margin-right: 8px; margin-bottom: 1.2rem;
        transition: all 0.25s ease;
    }
    .step-active {
        background: linear-gradient(135deg, var(--maroon-light) 0%, var(--maroon-dark) 100%);
        color: #FFFFFF; box-shadow: 0 5px 16px rgba(110,20,35,0.45);
        transform: scale(1.04);
    }
    .step-done { background: var(--gold-light); color: #5c3a22; }
    .step-inactive { background: #F5E7D3; color: #a88a6f; }

    /* ---------- Cards & badges ---------- */
    .plan-total { font-size: 1.28rem; font-weight: 800; color: var(--maroon); margin-top: 0.5rem; }
    .option-badge {
        display:inline-block; background: linear-gradient(135deg, var(--gold-light), var(--gold));
        color: #5c3a0f; font-weight:800; font-size:0.78rem; padding:4px 13px; border-radius:999px; margin-bottom:8px;
    }
    .best-badge {
        display:inline-block; background: linear-gradient(135deg, #2E9E5B, #1E8449); color:#fff; font-weight:700;
        font-size:0.75rem; padding:4px 12px; border-radius:999px; margin-left:6px;
    }
    .mode-badge {
        display:inline-block; font-weight:700; font-size:0.75rem; padding:4px 12px;
        border-radius:999px; margin-left:6px; background: linear-gradient(135deg, #2E4A66, #1B3040); color:#fff;
    }
    .place-card-title { font-weight:800; font-size:1.15rem; margin-bottom:3px; font-family:'Poppins',sans-serif; color: var(--maroon-dark); }
    .place-cat { color: var(--maroon); font-weight:700; font-size:0.8rem; }

    /* ---------- Every bordered container gets a premium card treatment + hover lift ---------- */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 18px !important;
        border: 1px solid #EEDDBF !important;
        box-shadow: 0 4px 14px rgba(110,20,35,0.06) !important;
        transition: transform 0.18s ease, box-shadow 0.18s ease !important;
        background: var(--cream-card) !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 26px rgba(110,20,35,0.14) !important;
    }
    div[data-testid="stExpander"] {
        border-radius: 14px !important; border: 1px solid var(--gold-light) !important;
        overflow: hidden;
    }
    div[data-testid="stExpander"] summary {
        font-weight: 700 !important; color: var(--maroon-dark) !important;
    }

    /* ---------- Buttons: EVERY button gets a real, colorful, interactive style ---------- */
    .stButton button, div[data-testid="stFormSubmitButton"] button {
        border-radius: 11px !important;
        font-weight: 700 !important;
        transition: all 0.18s ease !important;
        border: 2px solid var(--maroon) !important;
        color: var(--maroon-dark) !important;
        background: #FFFFFF !important;
    }
    .stButton button:hover, div[data-testid="stFormSubmitButton"] button:hover {
        background: #FDEEEF !important;
        border-color: var(--maroon-dark) !important;
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(166,27,41,0.22) !important;
    }
    button[kind="primary"] {
        background: linear-gradient(135deg, var(--maroon-light) 0%, var(--maroon-dark) 100%) !important;
        border: none !important;
        color: #FFFFFF !important;
        box-shadow: 0 5px 16px rgba(110,20,35,0.4) !important;
    }
    button[kind="primary"]:hover {
        box-shadow: 0 8px 22px rgba(110,20,35,0.55) !important;
        transform: translateY(-2px) scale(1.01);
        filter: brightness(1.06);
    }
    .stButton button:active, button[kind="primary"]:active { transform: translateY(0) scale(0.99); }

    /* Radio / checkbox / select accent color */
    div[role="radiogroup"] label span:first-child, [data-baseweb="checkbox"] span { accent-color: var(--maroon) !important; }
    div[data-baseweb="select"] > div { border-radius: 10px !important; border-color: var(--gold-light) !important; }

    /* ---------- Tabs ---------- */
    button[data-baseweb="tab"] { font-size: 1.04rem !important; font-weight: 700 !important; color: var(--text-muted) !important; }
    button[data-baseweb="tab"][aria-selected="true"] { color: var(--maroon-dark) !important; }
    div[data-baseweb="tab-highlight"] { background-color: var(--maroon) !important; height: 3px !important; }

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #FFF8EC 0%, #FCEBD1 100%);
        border-right: 1px solid var(--gold-light);
    }

    /* ---------- Devotional flourish: small diya flicker animation ---------- */
    @keyframes flicker {
        0%, 100% { opacity: 1; transform: scaleY(1); }
        50% { opacity: 0.75; transform: scaleY(0.92); }
    }
    .diya-flame { animation: flicker 1.6s ease-in-out infinite; transform-origin: bottom center; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown('<div class="top-strip"></div>', unsafe_allow_html=True)

# --- One-time DB setup. build_database() checks each dataset file
# individually and only (re)builds what's actually missing, so it's
# safe and cheap to call on every run. ---
with st.spinner("Setting up mock yatra, flight, train & bus data..."):
    build_database()

API_KEY = get_api_key()

MODE_ICON = {"flight": "✈️", "train": "🚆", "bus": "🚌"}
MODE_LABEL = {"flight": "Flight", "train": "Train", "bus": "Bus"}

# --- Hero banner (purely decorative graphic, no overlaid text - keeps everything readable) ---
st.markdown(
    """
    <div class="hero-wrap">
    <svg viewBox="0 0 1400 220" width="100%" style="display:block;">
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#C2374A"/>
          <stop offset="55%" stop-color="#8E1E2E"/>
          <stop offset="100%" stop-color="#6E1423"/>
        </linearGradient>
        <radialGradient id="glow" cx="50%" cy="35%" r="60%">
          <stop offset="0%" stop-color="#FFE9A8" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="#FFE9A8" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <rect width="1400" height="220" fill="url(#sky)"/>
      <rect width="1400" height="220" fill="url(#glow)"/>

      <!-- Om symbol watermark, subtle -->
      <text x="120" y="150" font-size="150" fill="#FFFFFF" opacity="0.06" font-family="serif">ॐ</text>

      <!-- Sun / divine light -->
      <circle cx="1230" cy="60" r="42" fill="#FFE9A8" opacity="0.85"/>
      <circle cx="1230" cy="60" r="60" fill="none" stroke="#FFE9A8" stroke-width="1.5" opacity="0.35"/>

      <!-- Hills -->
      <polygon points="0,220 220,90 400,220" fill="#5A101C" opacity="0.55"/>
      <polygon points="280,220 520,50 800,220" fill="#7A1826" opacity="0.75"/>
      <polygon points="650,220 860,95 1180,220" fill="#5A101C" opacity="0.55"/>
      <polygon points="1000,220 1220,65 1400,220" fill="#7A1826" opacity="0.75"/>

      <!-- Temple, gold accented -->
      <g>
        <rect x="630" y="165" width="130" height="55" fill="#FFF3E2" opacity="0.97"/>
        <polygon points="630,165 695,100 760,165" fill="#FFF3E2" opacity="0.97"/>
        <rect x="683" y="72" width="24" height="32" fill="#FFF3E2" opacity="0.97"/>
        <circle cx="695" cy="64" r="10" fill="#E8C874"/>
        <rect x="630" y="160" width="130" height="6" fill="#C9A227"/>
        <rect x="683" y="100" width="24" height="6" fill="#C9A227"/>
      </g>

      <!-- Diyas (lamps) along the base, with a flicker animation on the flames -->
      <g>
        <g transform="translate(380,196)"><rect x="-9" y="6" width="18" height="7" rx="3" fill="#C9A227"/><ellipse class="diya-flame" cx="0" cy="0" rx="3.5" ry="7" fill="#FFD873"/></g>
        <g transform="translate(460,200)"><rect x="-9" y="6" width="18" height="7" rx="3" fill="#C9A227"/><ellipse class="diya-flame" cx="0" cy="0" rx="3.5" ry="7" fill="#FFD873"/></g>
        <g transform="translate(940,200)"><rect x="-9" y="6" width="18" height="7" rx="3" fill="#C9A227"/><ellipse class="diya-flame" cx="0" cy="0" rx="3.5" ry="7" fill="#FFD873"/></g>
        <g transform="translate(1020,196)"><rect x="-9" y="6" width="18" height="7" rx="3" fill="#C9A227"/><ellipse class="diya-flame" cx="0" cy="0" rx="3.5" ry="7" fill="#FFD873"/></g>
      </g>
    </svg>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Hero text: real content, plain background, always readable ---
st.markdown('<div class="hero-title">🛕 Vaishno Devi Yatra Agent</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-sub" style="margin-bottom:1.4rem;">'
    "🙏 Your AI companion for planning a blessed, hassle-free pilgrimage — travel, darshan, "
    "stay & sightseeing, all in one conversation.</div>",
    unsafe_allow_html=True,
)

# --- Feature stat row ---
st.markdown(
    f"""
    <div class="stat-row">
        <div class="stat-card"><div class="stat-num">3</div><div class="stat-label">✈️🚆🚌 Travel modes compared</div></div>
        <div class="stat-card"><div class="stat-num">12+</div><div class="stat-label">🗺️ Curated places, with history</div></div>
        <div class="stat-card"><div class="stat-num">6</div><div class="stat-label">🪄 Guided planning steps</div></div>
        <div class="stat-card"><div class="stat-num">{"🌐" if API_KEY else "🇬🇧"}</div><div class="stat-label">{"Multilingual AI active" if API_KEY else "English rule-based mode"}</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not API_KEY:
    st.caption(
        "💬 Conversational mode: rule-based (English). Add an ANTHROPIC_API_KEY to enable "
        "full multilingual understanding — see README."
    )

# --- Session state ---
if "guest_id" not in st.session_state:
    # No sign-up required: each browser session gets a lightweight guest
    # identity, just so booking history has something to group by.
    st.session_state.guest_id = "Guest-" + uuid.uuid4().hex[:5].upper()

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": coordinator.get_greeting()}]
if "pending_options" not in st.session_state:
    st.session_state.pending_options = None
if "selected_option" not in st.session_state:
    st.session_state.selected_option = None
if "hotel_decision" not in st.session_state:
    st.session_state.hotel_decision = None  # None = not decided yet, {} = skipped, {...} = chosen
if "sightseeing_decision" not in st.session_state:
    st.session_state.sightseeing_decision = None  # None = not decided yet, [] = skipped, [names...] = chosen
if "itinerary_confirmed" not in st.session_state:
    st.session_state.itinerary_confirmed = False

# --- Sidebar ---
with st.sidebar:
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #C2374A 0%, #6E1423 100%); border-radius: 16px;
                    padding: 1.1rem 1.2rem; margin-bottom: 1rem; box-shadow: 0 4px 14px rgba(110,20,35,0.35);">
            <div style="color:#F8D9C4; font-size:0.78rem; font-weight:700; letter-spacing:0.03em;">CURRENT SESSION</div>
            <div style="color:#FFFFFF; font-size:1.15rem; font-weight:800; font-family:'Poppins',sans-serif;">👋 {st.session_state.guest_id}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("No sign-up needed — this is a temporary session identity.")
    st.divider()

    st.markdown("#### 📜 Booking history")
    bookings = db.list_bookings(user_name=st.session_state.guest_id)
    if not bookings:
        st.info("No bookings yet — start a conversation to plan your yatra!", icon="🙏")
    for b in bookings:
        with st.expander(f"{b['booking_id']} · {b['status']}"):
            st.write(f"**Name:** {b['user_name']}")
            st.write(f"**Pax:** {b['pax_count']}")
            st.write(f"**Yatra:** {b.get('category', '-')} on {b.get('slot_date', '-')}")
            mode = b.get("transport_mode", "-")
            icon = MODE_ICON.get(mode, "")
            st.write(f"**{icon} {MODE_LABEL.get(mode, 'Transport')}:** {b.get('transport_no', '-')} from {b.get('origin', '-')}")
            if b.get("hotel_name") and str(b.get("hotel_name")) != "nan":
                st.write(f"**🏨 Hotel:** {b.get('hotel_name')} ({b.get('hotel_category', '-')}), {b.get('hotel_nights', '-')} night(s)")
            if b.get("sightseeing_places") and str(b.get("sightseeing_places")) != "nan":
                st.write(f"**🗺️ Sightseeing:** {b.get('sightseeing_places')}")
            st.write(f"**Total:** ₹{b['total_price']}")


def render_steps(current):
    labels = [
        "1 · Tell us your trip", "2 · Review options", "3 · Add a stay",
        "4 · Sightseeing", "5 · Itinerary", "6 · Pay & confirm",
    ]
    html = ""
    for i, label in enumerate(labels, start=1):
        if i == current:
            cls = "step-active"
        elif i < current:
            cls = "step-done"
        else:
            cls = "step-inactive"
        html += f'<span class="step-pill {cls}">{label}</span>'
    st.markdown(html, unsafe_allow_html=True)


def _reset_flow():
    st.session_state.pending_options = None
    st.session_state.selected_option = None
    st.session_state.hotel_decision = None
    st.session_state.sightseeing_decision = None
    st.session_state.itinerary_confirmed = False


# --- Top-level tabs ---
tab_book, tab_explore = st.tabs(["🎫 Book your yatra", "🗺️ Explore Katra"])

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

    st.caption(
        "Prototype — bookings are simulated against mock data, not real yatra registration or "
        "airline/rail/bus systems. Payment is a simulated demo checkout."
    )

    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                render_speak_button(msg["content"], key=f"speak_msg_{i}")

    # --- STEP 2: selectable option cards, one per transport mode when possible ---
    if st.session_state.pending_options:
        bundle = st.session_state.pending_options
        pax = bundle["pax"]
        options = bundle["options"]

        with st.chat_message("assistant"):
            st.markdown(f"**Here are the top {len(options)} option(s) I found — pick one to continue:**")

            for i, opt in enumerate(options):
                tr, s = opt["flight"], opt["slot"]
                mode = tr.get("mode", "flight")
                icon = MODE_ICON.get(mode, "🚗")
                label = MODE_LABEL.get(mode, mode.title())

                with st.container(border=True):
                    badge_html = f'<span class="option-badge">Option {i + 1}</span><span class="mode-badge">{icon} {label}</span>'
                    if i == 0:
                        badge_html += '<span class="best-badge">💰 Cheapest</span>'
                    st.markdown(badge_html, unsafe_allow_html=True)

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**{icon} {label}**")
                        st.write(f"{tr.get('operator', '-')} {tr.get('transport_no', '')}")
                        st.write(f"{tr['origin']} → {tr['destination']}")
                        st.write(f"{tr['travel_date']} at {fmt_time(tr['departure_time'])}")
                        st.write(f"₹{tr['price']} / person")
                    with col2:
                        st.markdown("**🙏 Yatra slot**")
                        st.write(f"{s['category']}")
                        st.write(f"{s['slot_date']} at {fmt_time(s['slot_time'])}")
                        st.write(f"₹{s['price']} / person")

                    st.markdown(
                        f'<div class="plan-total">Total for {pax} pilgrim(s): ₹{opt["total_price"]}</div>',
                        unsafe_allow_html=True,
                    )

                    if mode == "flight":
                        st.caption(
                            "🚕 This flight lands at Jammu Airport — you'll then need onward transport to Katra "
                            "(~45-55 km, ~1.5-2 hrs). Taxi fare guidance and full details are in the next step."
                        )
                    else:
                        st.caption(f"✅ This {label.lower()} goes directly into Katra — no separate onward leg needed.")

                    with st.expander("View full details"):
                        st.write(f"**{label} details**")
                        st.json({
                            "Operator": tr.get("operator", "-"), "Number": tr.get("transport_no", "-"),
                            "Route": f"{tr['origin']} → {tr['destination']}", "Date": tr["travel_date"],
                            "Departure": fmt_time(tr["departure_time"]), "Duration": f"{tr.get('duration_mins', '-')} min",
                            "Seats left": tr["seats_available"], "Fare / person": f"₹{tr['price']}",
                        })
                        st.write("**Yatra slot details**")
                        st.json({
                            "Category": s["category"], "Date": s["slot_date"], "Time": fmt_time(s["slot_time"]),
                            "Seats left": s["seats_available"], "Fee / person": f"₹{s['price']}",
                        })

                    if st.button(f"Select option {i + 1}", key=f"select_opt_{i}", type="primary", use_container_width=True):
                        st.session_state.selected_option = {"pax": pax, "option": opt}
                        st.session_state.pending_options = None
                        st.rerun()

            if st.button("← Start over", key="restart_from_step2"):
                _reset_flow()
                st.rerun()

    # --- STEP 3: optional hotel stay in Katra, plus how-to-reach-Katra taxi info ---
    elif st.session_state.selected_option and st.session_state.hotel_decision is None:
        bundle = st.session_state.selected_option
        pax, opt = bundle["pax"], bundle["option"]
        tr, s = opt["flight"], opt["slot"]
        check_in_default = tr["travel_date"]

        with st.chat_message("assistant"):
            st.markdown("**Getting to Katra, and where to stay:**")

            taxi = explore_data.get_taxi_info()
            with st.container(border=True):
                st.markdown(f"🚕 **{taxi['route']}** · {taxi['distance']} · {taxi['duration']}")
                for opt_taxi in taxi["options"]:
                    st.write(f"- {opt_taxi['vehicle']} (up to {opt_taxi['capacity']}): {opt_taxi['fare_range']}")
                st.caption(taxi["note"])
                if tr.get("mode") != "flight":
                    st.caption(f"Note: since you're arriving in Katra directly by {MODE_LABEL.get(tr.get('mode'), 'this mode')}, you may not need this leg — it mainly applies to flight arrivals via Jammu Airport.")

            st.markdown("**🏨 Would you like to add a hotel stay in Katra?**")

            want_hotel = st.radio("Add a hotel?", ["No, skip this", "Yes, show me hotels"], horizontal=True, key="hotel_radio")
            col1, col2 = st.columns(2)
            with col1:
                hotel_category_choice = st.selectbox("Category", ["Any", "Budget", "Mid-Range", "Premium"], key="hotel_cat")
            with col2:
                nights = st.number_input("Nights", min_value=1, max_value=7, value=1, key="hotel_nights_input")

            if want_hotel == "No, skip this":
                if st.button("Continue", type="primary", key="skip_hotel", use_container_width=True):
                    st.session_state.hotel_decision = {}
                    st.rerun()
            else:
                if st.button("Show hotels", key="search_hotels_btn", use_container_width=True):
                    hotels = coordinator.get_hotel_options(
                        check_in_default,
                        category=None if hotel_category_choice == "Any" else hotel_category_choice,
                    )
                    st.session_state["_hotel_results"] = {"hotels": hotels, "nights": nights}

                hotel_results = st.session_state.get("_hotel_results")
                if hotel_results:
                    hotels, nights = hotel_results["hotels"], hotel_results["nights"]
                    if not hotels:
                        st.warning("No hotels found for that category on this date. Try 'Any' category or skip.")
                    else:
                        for h in hotels[:5]:
                            with st.container(border=True):
                                st.markdown(f"**{h['name']}** · {h['category']}")
                                st.write(f"₹{h['price_per_night']}/night · {nights} night(s) → ₹{h['price_per_night'] * nights} total")
                                st.caption(f"{h['rooms_available']} rooms left for check-in {check_in_default}")
                                if st.button(f"Select {h['name']}", key=f"select_hotel_{h['id']}", use_container_width=True):
                                    st.session_state.hotel_decision = {"hotel": h, "nights": nights}
                                    st.session_state.pop("_hotel_results", None)
                                    st.rerun()

            if st.button("← Back to options", key="back_to_step2_from_hotel"):
                st.session_state.pending_options = {"pax": pax, "options": [opt]}
                st.session_state.selected_option = None
                st.rerun()

    # --- STEP 4: optional sightseeing after darshan - now with real history + video links ---
    elif st.session_state.selected_option and st.session_state.hotel_decision is not None and st.session_state.sightseeing_decision is None:
        bundle = st.session_state.selected_option
        pax, opt = bundle["pax"], bundle["option"]

        with st.chat_message("assistant"):
            st.markdown("**Planning to visit any tourist places after darshan?**")
            st.caption("These places aren't bookable — just recommendations with history and local-travel guidance, so you can plan your time.")

            want_sightseeing = st.radio(
                "Interested in sightseeing after darshan?",
                ["No, skip this", "Yes, show me places"],
                horizontal=True,
                key="sightseeing_radio",
            )

            if want_sightseeing == "No, skip this":
                if st.button("Continue", type="primary", key="skip_sightseeing", use_container_width=True):
                    st.session_state.sightseeing_decision = []
                    st.rerun()
            else:
                categories = ["All"] + explore_data.get_categories()
                chosen_cat = st.selectbox("Filter by category", categories, key="sightseeing_cat_filter")
                places = coordinator.get_sightseeing_places(None if chosen_cat == "All" else chosen_cat)

                st.markdown("Select any places you'd like added to your itinerary:")
                picked = []
                for p in places:
                    with st.container(border=True):
                        render_place_image(p, height_px=140)
                        checked = st.checkbox(
                            f"**{p['name']}** · {p['category']} · {p['distance']}",
                            key=f"sight_{p['name']}",
                        )
                        st.caption(p["description"])
                        st.caption(f"🕐 {p.get('timings', 'Not confirmed')} · 🎟️ {p.get('entry_fee', 'Not confirmed')}")
                        with st.expander("📜 Historical background"):
                            st.write(p["historical_background"])
                        st.markdown(f"[▶️ Watch videos of {p['name']}]({p['video_search']})")
                        st.caption(f"🚕 Getting there: {explore_data.get_local_travel_note(p['category'])}")
                        if checked:
                            picked.append(p["name"])

                if st.button("Continue with selected places", type="primary", key="confirm_sightseeing", use_container_width=True):
                    st.session_state.sightseeing_decision = picked
                    st.rerun()

            if st.button("← Back", key="back_to_step3_from_sightseeing"):
                st.session_state.hotel_decision = None
                st.rerun()

    # --- STEP 5: day-wise itinerary, built by the ItineraryAgent ---
    elif st.session_state.selected_option and st.session_state.hotel_decision is not None and st.session_state.sightseeing_decision is not None and not st.session_state.itinerary_confirmed:
        bundle = st.session_state.selected_option
        pax, opt = bundle["pax"], bundle["option"]
        hotel_choice = st.session_state.hotel_decision or {}
        hotel = hotel_choice.get("hotel")
        hotel_nights = hotel_choice.get("nights", 0)
        sightseeing_places = st.session_state.sightseeing_decision or []

        itinerary = coordinator.build_final_itinerary(
            opt, hotel=hotel, hotel_nights=hotel_nights, sightseeing_places=sightseeing_places
        )

        with st.chat_message("assistant"):
            st.markdown("**🗓️ Here's your day-wise itinerary:**")
            for day in itinerary:
                with st.container(border=True):
                    st.markdown(f"**Day {day['day_number']} — {day['date']}**")
                    st.caption(day["title"])
                    for a in day["activities"]:
                        st.write(f"- {a}")

            st.caption("This itinerary is a planning guide based on your choices — actual timing may vary.")

            if st.button("Continue to payment", type="primary", key="confirm_itinerary", use_container_width=True):
                st.session_state.itinerary_confirmed = True
                st.rerun()

            if st.button("← Back", key="back_to_step4_from_itinerary"):
                st.session_state.sightseeing_decision = None
                st.rerun()

    # --- STEP 6: payment gateway, then confirm the booking ---
    elif st.session_state.selected_option:
        bundle = st.session_state.selected_option
        pax, opt = bundle["pax"], bundle["option"]
        tr, s = opt["flight"], opt["slot"]
        mode = tr.get("mode", "flight")
        icon = MODE_ICON.get(mode, "🚗")
        hotel_choice = st.session_state.hotel_decision or {}
        hotel = hotel_choice.get("hotel")
        hotel_nights = hotel_choice.get("nights", 0)
        hotel_cost = (hotel["price_per_night"] * hotel_nights) if hotel else 0
        grand_total = opt["total_price"] + hotel_cost
        sightseeing_places = st.session_state.sightseeing_decision or []

        with st.chat_message("assistant"):
            st.markdown("**Review & pay to confirm your booking:**")
            with st.container(border=True):
                st.write(f"{icon} {tr.get('operator', '-')} {tr.get('transport_no', '')} · {tr['origin']} → {tr['destination']} · {tr['travel_date']}")
                st.write(f"🙏 {s['category']} · {s['slot_date']} at {fmt_time(s['slot_time'])}")
                st.write(f"👥 {pax} pilgrim(s)")
                if hotel:
                    st.write(f"🏨 {hotel['name']} ({hotel['category']}) · {hotel_nights} night(s) · ₹{hotel_cost}")
                else:
                    st.write("🏨 No hotel added")
                if sightseeing_places:
                    st.write(f"🗺️ Planning to visit: {', '.join(sightseeing_places)}")
                else:
                    st.write("🗺️ No sightseeing planned")

            paid = payment.render_payment_form("Total for this booking:", grand_total)

            if paid:
                booking_id, blessing = coordinator.confirm_booking(
                    opt, pax, st.session_state.guest_id,
                    hotel=hotel, hotel_nights=hotel_nights,
                    sightseeing_places=sightseeing_places,
                )
                st.balloons()
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": f"{blessing}\n\nYour confirmation ID is **{booking_id}**. Total paid (mock): ₹{grand_total}.",
                    }
                )
                _reset_flow()
                st.rerun()

            if st.button("← Back", key="back_to_step5"):
                st.session_state.itinerary_confirmed = False
                st.rerun()

    # --- STEP 1: pure conversation - no form, just chat (typed or spoken) ---
    else:
        def _process_trip_input(user_text):
            st.session_state.messages.append({"role": "user", "content": user_text})
            with st.spinner("Checking slots, flights, trains & buses..."):
                result = coordinator.process_trip_message(user_text, api_key=API_KEY)
            plan = result["plan"]
            st.session_state.messages.append({"role": "assistant", "content": result["reply"]})
            if plan["status"] == "PLAN_READY":
                st.session_state.pending_options = {"pax": plan["pax"], "options": plan["options"]}
            st.rerun()

        # Handle a voice-transcribed message arriving via the query-param
        # bridge (see render_voice_input's docstring). Processed once,
        # then cleared, so a later rerun (e.g. clicking a button) doesn't
        # resubmit the same spoken message again.
        incoming_voice_text = st.query_params.get("voice_input")
        if incoming_voice_text:
            st.query_params.pop("voice_input", None)
            st.query_params.pop("voice_ts", None)
            _process_trip_input(incoming_voice_text)

        render_voice_input()
        if prompt := st.chat_input("Tell me about your trip — e.g. \"2 log Delhi se agle hafte, VIP darshan\" or \"Book 3 people from Mumbai next week\""):
            _process_trip_input(prompt)

with tab_explore:
    st.subheader("Yatra Essentials")
    st.caption("Real, cross-checked pilgrim information — see README for exact sourcing.")

    with st.expander("🪔 Aarti timings (darshan pauses during these windows)"):
        aarti = yatra_info.get_aarti_timings()
        st.write(f"**Morning:** {aarti['morning']['start']} – {aarti['morning']['end']} ({aarti['morning']['note']})")
        st.write(f"**Evening (summer, Apr–Sep):** {aarti['evening_summer']['start']} – {aarti['evening_summer']['end']}")
        st.write(f"**Evening (winter, Oct–Mar):** {aarti['evening_winter']['start']} – {aarti['evening_winter']['end']}")
        st.caption(aarti["general_note"])

    with st.expander("📝 Yatra registration (mandatory for everyone)"):
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

    with st.expander("🚶 Route options to Bhawan"):
        for route in yatra_info.get_route_options():
            st.markdown(f"**{route['name']}** · {route['distance']} · {route['duration']}")
            st.caption(route["path"])
            st.write(route["notes"])
            st.divider()

    with st.expander("🎒 Packing guidance"):
        packing = yatra_info.get_packing_guidance()
        st.caption(packing["disclaimer"])
        st.markdown("**Recommended:**")
        for item in packing["recommended"]:
            st.write(f"- {item}")
        st.markdown("**Commonly restricted:**")
        for item in packing["commonly_restricted"]:
            st.write(f"- {item}")

    with st.expander("🏥 Free facilities along the route"):
        for fac in yatra_info.get_facilities():
            st.write(f"**{fac['name']}** — {fac['note']}")

    with st.expander("📞 Official helpline"):
        helpline = yatra_info.get_helpline()
        st.write(f"**{helpline['official_yatra_helpline']}**")
        st.caption(helpline["note"])

    st.divider()

    st.subheader("Getting from Jammu to Katra")
    taxi = explore_data.get_taxi_info()
    with st.container(border=True):
        st.markdown(f"🚕 **{taxi['route']}** · {taxi['distance']} · {taxi['duration']}")
        for opt_taxi in taxi["options"]:
            st.write(f"- {opt_taxi['vehicle']} (up to {opt_taxi['capacity']}): {opt_taxi['fare_range']}")
        st.caption(taxi["note"])

    st.subheader("Places to see around Katra & Jammu")
    st.caption(
        "Informational only — not bookable through this app. Click any place to see full "
        "details: timings, entry fees, history, and a video link."
    )

    if "selected_explore_place" not in st.session_state:
        st.session_state.selected_explore_place = None

    if st.session_state.selected_explore_place:
        p = explore_data.get_place_by_name(st.session_state.selected_explore_place)
        if st.button("← Back to all places", key="back_to_places_grid"):
            st.session_state.selected_explore_place = None
            st.rerun()

        with st.container(border=True):
            render_place_image(p, height_px=260)
            st.markdown(f'<div class="place-card-title" style="font-size:1.5rem;">{p["name"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<span class="place-cat">{p["category"]}</span> · {p["distance"]}', unsafe_allow_html=True)
            st.write("")
            st.write(p["description"])

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**🕐 Timings**\n\n{p.get('timings', 'Not confirmed')}")
            with col2:
                st.markdown(f"**🎟️ Entry**\n\n{p.get('entry_fee', 'Not confirmed')}")

            st.markdown("**📜 Historical background**")
            st.write(p["historical_background"])

            st.markdown(f"[▶️ Watch videos of {p['name']}]({p['video_search']})")
            st.caption(f"🚕 Getting there: {explore_data.get_local_travel_note(p['category'])}")

    else:
        categories = ["All"] + explore_data.get_categories()
        chosen = st.selectbox("Filter by category", categories, key="explore_tab_cat_filter")
        places = explore_data.get_places(None if chosen == "All" else chosen)

        cols = st.columns(3)
        for i, p in enumerate(places):
            with cols[i % 3]:
                with st.container(border=True):
                    render_place_image(p, height_px=110)
                    st.markdown(f'<div class="place-card-title" style="font-size:0.95rem;">{p["name"]}</div>', unsafe_allow_html=True)
                    st.markdown(f'<span class="place-cat" style="font-size:0.7rem;">{p["category"]}</span>', unsafe_allow_html=True)
                    st.caption(p["distance"])
                    if st.button("View details", key=f"view_{p['name']}", use_container_width=True):
                        st.session_state.selected_explore_place = p["name"]
                        st.rerun()
