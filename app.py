"""
app.py
Streamlit front-end for the Vaishno Devi Yatra Booking Agent prototype.
Run locally with: streamlit run app.py

This version presents a premium, travel-platform interface inspired by the reference design,
with FULLY FUNCTIONAL NAVIGATION (Home, Darshan Bookings, Yatra Guide, Packages, Hotels,
Transport, Help, AI Assistant, My Account, Search) while preserving 100% of the underlying AI,
coordinator, intent-routing, recommendation, itinerary, weather, hotel database, and Playwright RPA booking backend.
"""

import base64
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
    """Removes markdown formatting and HTML tags so the spoken text sounds natural."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#_`]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@st.cache_data
def get_image_base64(path):
    """Encodes a local image file to a base64 Data URL for CSS background or HTML img tag."""
    if path and os.path.exists(path):
        try:
            with open(path, "rb") as f:
                data = f.read()
            ext = path.split(".")[-1].lower() if "." in path else "jpeg"
            mime = "image/jpeg" if ext in ["jpg", "jpeg"] else f"image/{ext}"
            return f"data:{mime};base64,{base64.b64encode(data).decode()}"
        except Exception:
            return ""
    return ""


def render_voice_input(key="voice_input_main"):
    """Renders a mic button using browser Web Speech API with direct handoff to AI Assistant input."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
      body {{
        margin: 0;
        padding: 0;
        background: transparent;
        overflow: hidden;
        font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
      }}
      .voice-container {{
        display: flex;
        flex-direction: column;
        gap: 3px;
        width: 100%;
        box-sizing: border-box;
      }}
      .control-row {{
        display: flex;
        align-items: center;
        gap: 6px;
        width: 100%;
        box-sizing: border-box;
      }}
      select.lang-select {{
        flex: 0 0 auto;
        width: 105px;
        max-width: 35%;
        border-radius: 8px;
        border: 1px solid #E5D2AD;
        padding: 5px 6px;
        font-size: 0.78rem;
        background: #FBF9F4;
        color: #2A2020;
        box-sizing: border-box;
        outline: none;
        font-weight: 500;
      }}
      button.voice-btn {{
        flex: 1 1 auto;
        min-width: 0;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 5px;
        background: #58111A;
        border: 1.5px solid #B8860B;
        color: #FBF9F4;
        font-weight: 700;
        border-radius: 999px;
        padding: 6px 12px;
        font-size: 0.78rem;
        cursor: pointer;
        transition: all 0.18s ease;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        box-shadow: 0 2px 6px rgba(88,17,26,0.12);
      }}
      button.voice-btn:hover {{
        background: #7A1926;
      }}
      button.voice-btn.listening {{
        background: #8B1E2F !important;
        border-color: #E5D2AD !important;
      }}
      button.voice-btn.processing {{
        background: #3D0810 !important;
        border-color: #C5A059 !important;
      }}
      .status-line {{
        font-size: 0.72rem;
        color: #6B5C5C;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-height: 15px;
        line-height: 15px;
        padding-left: 2px;
      }}
    </style>
    </head>
    <body>
    <div class="voice-container">
      <div class="control-row">
        <select id="lang_{key}" class="lang-select" title="Choose spoken language">
          <option value="en-IN">English</option>
          <option value="hi-IN">Hindi (हिंदी)</option>
          <option value="pa-IN">Punjabi (ਪੰਜਾਬੀ)</option>
          <option value="ur-IN">Urdu (اردو)</option>
        </select>
        <button id="mic_{key}" class="voice-btn" onclick="toggleListen_{key}()">
          🎙️ Speak Your Query
        </button>
      </div>
      <div id="status_{key}" class="status-line"></div>
    </div>
    <script>
    (function() {{
      var key = "{key}";
      var btn = document.getElementById('mic_' + key);
      var statusEl = document.getElementById('status_' + key);
      var langSelect = document.getElementById('lang_' + key);
      var recognition = null;
      var isListening = false;
      var clearTimer = null;

      function setStatus(msg, color) {{
        if (!statusEl) return;
        statusEl.textContent = msg || '';
        statusEl.style.color = color || '#6B5C5C';
        if (clearTimer) clearTimeout(clearTimer);
        if (msg) {{
          clearTimer = setTimeout(function() {{
            if (statusEl.textContent === msg) {{
              statusEl.textContent = '';
            }}
          }}, 4500);
        }}
      }}

      function setButtonState(state, text) {{
        if (!btn) return;
        btn.className = 'voice-btn ' + state;
        btn.innerHTML = text;
      }}

      function resetButton() {{
        isListening = false;
        setButtonState('', '🎙️ Speak Your Query');
      }}

      function submitToParent(text) {{
        try {{
          var pDoc = window.parent.document;
          if (!pDoc) return false;

          // 1. Try stChatInput textarea (View 8 AI Assistant, View 2 Darshan Bookings)
          var textarea = pDoc.querySelector('textarea[data-testid="stChatInputTextArea"]');
          if (textarea) {{
            var proto = window.parent.HTMLTextAreaElement.prototype;
            var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
            if (setter) {{
              setter.call(textarea, text);
            }} else {{
              textarea.value = text;
            }}
            textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
            textarea.dispatchEvent(new Event('change', {{ bubbles: true }}));

            setTimeout(function() {{
              var submitBtn = pDoc.querySelector('button[data-testid="stChatInputSubmitButton"]');
              if (submitBtn) {{
                submitBtn.disabled = false;
                submitBtn.click();
              }} else {{
                textarea.dispatchEvent(new KeyboardEvent('keydown', {{
                  key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true
                }}));
              }}
            }}, 80);
            return true;
          }}

          // 2. Try Form text input (View 1 Home Page)
          var input = pDoc.querySelector('input[aria-label="Home AI Query"]') ||
                      pDoc.querySelector('div[data-testid="stForm"] input[type="text"]') ||
                      pDoc.querySelector('input[data-testid="stTextInput"]');
          if (input) {{
            var inProto = window.parent.HTMLInputElement.prototype;
            var inSetter = Object.getOwnPropertyDescriptor(inProto, 'value').set;
            if (inSetter) {{
              inSetter.call(input, text);
            }} else {{
              input.value = text;
            }}
            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
            input.dispatchEvent(new Event('change', {{ bubbles: true }}));

            setTimeout(function() {{
              var form = input.closest('form');
              var submitBtn = form ? form.querySelector('button[type="submit"]') : null;
              if (submitBtn) {{
                submitBtn.click();
              }} else {{
                input.dispatchEvent(new KeyboardEvent('keydown', {{
                  key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true
                }}));
              }}
            }}, 80);
            return true;
          }}
        }} catch(err) {{
          console.warn('Direct DOM submit error:', err);
        }}
        return false;
      }}

      function handleTranscript(transcript) {{
        if (!transcript || !transcript.trim()) {{
          setStatus("Sorry, I couldn't understand that. Please try again.", '#8B1E2F');
          resetButton();
          return;
        }}

        var clean = transcript.trim();
        // State 3: ⏳ Processing...
        setButtonState('processing', '⏳ Processing...');
        setStatus('Heard: "' + clean + '"', '#58111A');

        // Direct submission to active chat/form input
        var submitted = submitToParent(clean);

        if (!submitted) {{
          // Retry after 120ms
          setTimeout(function() {{
            var retryOk = submitToParent(clean);
            if (!retryOk) {{
              try {{
                var url = new URL(window.parent.location.href);
                url.searchParams.set('voice_input', clean);
                url.searchParams.set('voice_ts', Date.now());
                window.parent.location.href = url.href;
              }} catch(e) {{
                setStatus("Could not auto-submit voice query.", '#8B1E2F');
              }}
            }}
          }}, 120);
        }}

        // Always reset button out of Processing state after 1.2s so it never hangs
        setTimeout(function() {{
          resetButton();
        }}, 1200);
      }}

      window['toggleListen_' + key] = function() {{
        var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {{
          setStatus('Voice input not supported in this browser. Please use Chrome, Edge, or Safari.', '#8B1E2F');
          return;
        }}

        if (isListening && recognition) {{
          try {{ recognition.stop(); }} catch(e) {{}}
          resetButton();
          setStatus('');
          return;
        }}

        try {{
          recognition = new SR();
          recognition.lang = langSelect ? langSelect.value : 'en-IN';
          recognition.interimResults = false;
          recognition.maxAlternatives = 1;

          recognition.onstart = function() {{
            isListening = true;
            // State 2: 🎧 Listening...
            setButtonState('listening', '🎧 Listening...');
            setStatus('Listening for speech...', '#8C6D3B');
          }};

          recognition.onresult = function(event) {{
            isListening = false;
            if (event.results && event.results[0] && event.results[0][0]) {{
              var text = event.results[0][0].transcript;
              handleTranscript(text);
            }} else {{
              setStatus("Sorry, I couldn't understand that. Please try again.", '#8B1E2F');
              resetButton();
            }}
          }};

          recognition.onerror = function(event) {{
            isListening = false;
            resetButton();
            if (event.error === 'no-speech') {{
              setStatus("Sorry, I couldn't hear that. Please try again.", '#6B5C5C');
            }} else if (event.error === 'not-allowed') {{
              setStatus("Microphone permission was denied. Please allow mic access.", '#8B1E2F');
            }} else {{
              setStatus("Sorry, I couldn't understand that. Please try again.", '#8B1E2F');
            }}
          }};

          recognition.onend = function() {{
            if (isListening) {{
              resetButton();
            }}
          }};

          recognition.start();
        }} catch(err) {{
          console.error('Speech recognition start failed:', err);
          setStatus("Microphone could not be started. Please try again.", '#8B1E2F');
          resetButton();
        }}
      }};
    }})();
    </script>
    </body></html>
    """
    components.html(html, height=52)


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


@st.cache_data
def resolve_place_image_path(img_val):
    if not img_val:
        return None
    if os.path.exists(img_val):
        return img_val
    base_name = os.path.basename(img_val)
    candidates = [
        os.path.join("assets", "images", "places", base_name),
        os.path.join("assets", "places", base_name),
        os.path.join("assets", "images", base_name),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def render_place_image(place, height_px=180):
    """Shows place photo or themed gradient placeholder."""
    img_val = place.get("image") or place.get("image_file", "")
    found_path = resolve_place_image_path(img_val)

    if found_path:
        st.image(found_path, use_container_width=True)
    else:
        st.markdown(
            f'<div style="height:{height_px}px; background:linear-gradient(135deg, #58111A 0%, #3D0810 100%); border-radius:10px; display:flex; align-items:center; justify-content:center; color:#E5D2AD; font-size:1.5rem;">🔱</div>',
            unsafe_allow_html=True,
        )


def render_place_detail_view(place_name):
    """Renders instant, structured place detail page with zero LLM/network overhead."""
    place = explore_data.get_place_by_name(place_name)
    if not place:
        for p in explore_data.get_places():
            if p["name"].lower() == place_name.lower():
                place = p
                break
    if not place:
        st.warning(f"Destination details for '{place_name}' could not be found.")
        if st.button("← Back to all destinations", key="back_from_missing"):
            st.session_state.selected_explore_place = None
            st.rerun()
        return

    # Back button & companion query shortcut
    top_c1, top_c2 = st.columns([3, 4])
    with top_c1:
        if st.button("← Back to all destinations", key="btn_back_to_destinations", use_container_width=True):
            st.session_state.selected_explore_place = None
            st.rerun()
    with top_c2:
        if st.button(f"Ask AI Companion about {place['name']} 💬", key=f"btn_ask_ai_{place['name']}", use_container_width=True):
            set_active_nav("AI Assistant")
            _process_trip_input(f"Tell me about {place['name']}")

    with st.container(border=True):
        st.markdown(
            f"""
            <div style="margin-bottom:12px;">
                <span style="background:#58111A; color:#FDFBF7; padding:4px 12px; border-radius:999px; font-size:0.75rem; font-weight:700; text-transform:uppercase; letter-spacing:0.04em;">{place.get('category', 'Attraction')}</span>
                <span style="background:#F5ECDA; color:#58111A; border:1px solid #E5D2AD; padding:4px 12px; border-radius:999px; font-size:0.75rem; font-weight:600; margin-left:6px;">📍 {place.get('region', 'Jammu & Kashmir')}</span>
                <span style="background:#F5ECDA; color:#58111A; border:1px solid #E5D2AD; padding:4px 12px; border-radius:999px; font-size:0.75rem; font-weight:600; margin-left:6px;">⏱️ {place.get('distance', '')}</span>
            </div>
            <div style="font-family:'Cinzel',serif; font-size:1.8rem; font-weight:800; color:#3D0810; margin-bottom:14px; line-height:1.2;">
                {place['name']}
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_img, col_info = st.columns([1.3, 2.7])
        with col_img:
            render_place_image(place, height_px=260)
            if place.get("video_search"):
                st.markdown(
                    f'<div style="margin-top:10px;"><a href="{place["video_search"]}" target="_blank" style="display:inline-flex; align-items:center; gap:6px; background:#F5ECDA; border:1px solid #E5D2AD; color:#58111A; padding:6px 14px; border-radius:999px; font-size:0.8rem; font-weight:700; text-decoration:none;">▶ Watch Video Guide on YouTube ↗</a></div>',
                    unsafe_allow_html=True,
                )

        with col_info:
            st.markdown("##### 📌 Overview")
            st.write(place.get("description", ""))

            if place.get("location_route"):
                st.markdown(f"📍 **Location & Route:** {place['location_route']}")

            info_c1, info_c2 = st.columns(2)
            with info_c1:
                st.markdown(
                    f"""
                    <div style="background:#FDFBF7; border:1px solid #E5D2AD; padding:10px 14px; border-radius:10px; margin-top:6px;">
                        <div style="font-size:0.75rem; font-weight:700; color:#B8860B; text-transform:uppercase;">Timings</div>
                        <div style="font-size:0.95rem; font-weight:600; color:#2A2020;">{place.get('timings', 'Open daily')}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with info_c2:
                st.markdown(
                    f"""
                    <div style="background:#FDFBF7; border:1px solid #E5D2AD; padding:10px 14px; border-radius:10px; margin-top:6px;">
                        <div style="font-size:0.75rem; font-weight:700; color:#B8860B; text-transform:uppercase;">Entry Fee</div>
                        <div style="font-size:0.95rem; font-weight:600; color:#2A2020;">{place.get('entry_fee', 'Free')}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        if place.get("historical_background"):
            st.write("")
            with st.container(border=True):
                st.markdown("##### 📜 Historical Background & Pilgrim Heritage")
                st.write(place["historical_background"])

        local_note = explore_data.get_local_travel_note(place.get("category", ""))
        if local_note:
            st.caption(f"🚗 **Local Travel Advisory:** {local_note}")


def _render_personalized_recommendation_dashboard(rec, msg, i, key_prefix="home"):
    """Renders the modern premium travel-planning dashboard card for AI recommendations."""
    content = msg.get("content", "")
    prof = rec.get("profile") or {}
    pax = prof.get("pax", 1)
    group_type = str(prof.get("group_type", "solo")).title()
    duration = prof.get("duration_days", 4)
    travel_style = str(prof.get("travel_style", "balanced")).title()
    trip_focus = str(prof.get("trip_focus", "devotional")).title()
    budget = str(prof.get("budget_preference", "comfortable")).title()

    # 0. Check for Edit Summary badge (e.g. from Phase D modifications)
    if "✨ Trip Updated:" in content:
        edit_line = content.split("---")[0].strip()
        if edit_line:
            st.markdown(
                f"""
                <div style="background:#FFF9F0; border:1px solid #B8860B; color:#58111A; padding:8px 16px; border-radius:10px; font-size:0.86rem; font-weight:600; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
                    {edit_line}
                </div>
                """,
                unsafe_allow_html=True,
            )

    # 1. HEADER CARD
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #58111A 0%, #3D0810 100%); border: 1.5px solid #B8860B; border-radius: 14px; padding: 14px 20px; color: #FFFFFF; margin-bottom: 14px; box-shadow: 0 4px 12px rgba(88, 17, 26, 0.12);">
            <div style="font-family:'Cinzel',serif; font-weight:800; font-size:1.15rem; letter-spacing:0.04em; color:#FBF9F4; display:flex; align-items:center; gap:8px;">
                <span>✨</span> YOUR PERSONALIZED YATRA PLAN
            </div>
            <div style="font-size:0.82rem; color:#E5D2AD; margin-top:3px; font-weight:500;">
                Designed around your travel preferences
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. TRIP SNAPSHOT
    st.markdown(
        f"""
        <div style="margin-bottom: 14px;">
            <div style="font-family:'Plus Jakarta Sans',sans-serif; font-size:0.75rem; font-weight:800; letter-spacing:0.08em; color:#8C6D3B; text-transform:uppercase; margin-bottom:8px;">
                TRIP SNAPSHOT
            </div>
            <div style="display:flex; flex-wrap:wrap; gap:8px;">
                <span style="display:inline-flex; align-items:center; gap:5px; background:#FBF9F4; border:1px solid #E5D2AD; color:#4A151C; padding:5px 12px; border-radius:999px; font-size:0.82rem; font-weight:700;">👤 {pax} {'Pilgrim' if pax == 1 else 'Pilgrims'}</span>
                <span style="display:inline-flex; align-items:center; gap:5px; background:#FBF9F4; border:1px solid #E5D2AD; color:#4A151C; padding:5px 12px; border-radius:999px; font-size:0.82rem; font-weight:700;">🧳 {group_type}</span>
                <span style="display:inline-flex; align-items:center; gap:5px; background:#FBF9F4; border:1px solid #E5D2AD; color:#4A151C; padding:5px 12px; border-radius:999px; font-size:0.82rem; font-weight:700;">📅 {duration} Days</span>
                <span style="display:inline-flex; align-items:center; gap:5px; background:#FBF9F4; border:1px solid #E5D2AD; color:#4A151C; padding:5px 12px; border-radius:999px; font-size:0.82rem; font-weight:700;">🚶 {travel_style} Pace</span>
                <span style="display:inline-flex; align-items:center; gap:5px; background:#FBF9F4; border:1px solid #E5D2AD; color:#4A151C; padding:5px 12px; border-radius:999px; font-size:0.82rem; font-weight:700;">🙏 {trip_focus}</span>
                <span style="display:inline-flex; align-items:center; gap:5px; background:#FBF9F4; border:1px solid #E5D2AD; color:#4A151C; padding:5px 12px; border-radius:999px; font-size:0.82rem; font-weight:700;">💰 {budget}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3. YOUR RECOMMENDED APPROACH
    st.markdown(
        """
        <div style="font-family:'Cinzel',serif; font-weight:700; color:#58111A; font-size:0.98rem; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
            <span>✨</span> Recommended Approach
        </div>
        """,
        unsafe_allow_html=True,
    )
    bullets = rec.get("approach_bullets") or []
    c1_txt = bullets[0] if len(bullets) > 0 else "2 dedicated days for trek, darshan, and Bhairavnath Temple."
    c2_txt = bullets[1] if len(bullets) > 1 else "Explore scenic places around Katra and nearby foothills."
    c3_txt = bullets[2] if len(bullets) > 2 else "Optional hill stations & nature spots with flexible rest buffers."

    app_cols = st.columns(3)
    with app_cols[0]:
        st.markdown(
            f"""
            <div style="background:#FFFFFF; border:1px solid #E5D2AD; border-radius:12px; padding:12px 14px; min-height:105px; box-shadow:0 2px 6px rgba(88,17,26,0.03); box-sizing:border-box;">
                <div style="font-family:'Cinzel',serif; font-weight:800; font-size:0.86rem; color:#58111A; margin-bottom:5px; letter-spacing:0.02em;">
                    🙏 YATRA & DARSHAN
                </div>
                <div style="font-size:0.8rem; color:#4A2E18; line-height:1.4;">
                    {c1_txt}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with app_cols[1]:
        st.markdown(
            f"""
            <div style="background:#FFFFFF; border:1px solid #E5D2AD; border-radius:12px; padding:12px 14px; min-height:105px; box-shadow:0 2px 6px rgba(88,17,26,0.03); box-sizing:border-box;">
                <div style="font-family:'Cinzel',serif; font-weight:800; font-size:0.86rem; color:#58111A; margin-bottom:5px; letter-spacing:0.02em;">
                    🌄 LOCAL EXPLORING
                </div>
                <div style="font-size:0.8rem; color:#4A2E18; line-height:1.4;">
                    {c2_txt}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with app_cols[2]:
        st.markdown(
            f"""
            <div style="background:#FFFFFF; border:1px solid #E5D2AD; border-radius:12px; padding:12px 14px; min-height:105px; box-shadow:0 2px 6px rgba(88,17,26,0.03); box-sizing:border-box;">
                <div style="font-family:'Cinzel',serif; font-weight:800; font-size:0.86rem; color:#58111A; margin-bottom:5px; letter-spacing:0.02em;">
                    🚶 FLEXIBLE PACE
                </div>
                <div style="font-size:0.8rem; color:#4A2E18; line-height:1.4;">
                    {c3_txt}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 4. RECOMMENDED PLACES ("Places You May Love")
    st.markdown(
        """
        <div style="font-family:'Cinzel',serif; font-weight:700; color:#58111A; font-size:0.98rem; margin-top:14px; margin-bottom:8px; display:flex; align-items:center; gap:6px;">
            <span>📍</span> Places You May Love
        </div>
        """,
        unsafe_allow_html=True,
    )
    sug_places = rec.get("suggested_places") or []
    raw_places = sug_places[:3] if sug_places else explore_data.get_places()[:3]
    places_to_show = []
    for rp in raw_places:
        if isinstance(rp, str):
            found = next((p for p in explore_data.get_places() if p["name"].lower() == rp.lower()), None)
            places_to_show.append(found if found else {"name": rp, "category": "Holy Shrine", "distance": "Nearby", "description": rp})
        elif isinstance(rp, dict):
            places_to_show.append(rp)
    if not places_to_show:
        places_to_show = explore_data.get_places()[:3]

    p_cols = st.columns(len(places_to_show))
    for p_idx, sp in enumerate(places_to_show):
        with p_cols[p_idx]:
            with st.container(border=True):
                render_place_image(sp, height_px=115)
                st.markdown(
                    f"""
                    <div style="font-family:'Cinzel',serif; font-weight:800; font-size:0.92rem; color:#58111A; margin-top:6px; min-height:26px;">
                        🛕 {sp['name']}
                    </div>
                    <div style="font-size:0.76rem; color:#8C6D3B; font-weight:600; margin-bottom:4px;">
                        {sp.get('category', 'Holy Shrine')} · {sp.get('distance', 'Nearby')}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                desc = sp.get('description', '')
                if len(desc) > 85:
                    desc = desc[:82] + '...'
                st.caption(desc)
                if st.button(f"Explore {sp['name']} →", key=f"{key_prefix}_{i}_exp_{sp['name']}", use_container_width=True):
                    st.session_state.selected_explore_place = sp["name"]
                    st.session_state.selected_destination = sp["name"]
                    st.session_state.last_tourism_place = sp["name"]
                    _sync_state_to_cache()
                    _process_trip_input(f"Tell me about {sp['name']}")

    # 5. "WHY THIS PLAN FITS YOU"
    reasoning = rec.get("reasoning", "")
    st.markdown(
        f"""
        <div style="background:#FFF9F0; border:1px solid #E5D2AD; border-left:4px solid #B8860B; border-radius:10px; padding:12px 18px; margin-top:12px; margin-bottom:12px;">
            <div style="font-family:'Cinzel',serif; font-weight:800; font-size:0.86rem; color:#58111A; letter-spacing:0.04em; margin-bottom:4px; display:flex; align-items:center; gap:6px;">
                <span>💡</span> WHY THIS PLAN FITS YOU
            </div>
            <div style="font-size:0.84rem; color:#4A2E18; line-height:1.5;">
                {reasoning}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 6. BUDGET NOTE
    budget_note = rec.get("budget_note", "Final cost depends on available transport and stay options.")
    st.markdown(
        f"""
        <div style="background:#FFFFFF; border:1px dashed #E5D2AD; border-radius:8px; padding:8px 14px; margin-bottom:14px;">
            <div style="font-size:0.82rem; color:#4A2E18;">
                💰 <b>BUDGET:</b> <span style="color:#58111A; font-weight:700;">{budget}</span> · <i>{budget_note}</i>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 7. NEXT ACTIONS
    st.markdown(
        """
        <div style="font-family:'Cinzel',serif; font-weight:700; color:#58111A; font-size:0.92rem; margin-bottom:8px;">
            What would you like to do next?
        </div>
        """,
        unsafe_allow_html=True,
    )
    act_c1, act_c2 = st.columns(2)
    with act_c1:
        with st.container(border=True):
            st.markdown(
                """
                <div style="font-family:'Cinzel',serif; font-weight:800; font-size:0.88rem; color:#58111A;">
                    🗓️ BUILD MY ITINERARY
                </div>
                <div style="font-size:0.78rem; color:#6B5C5C; margin-top:2px; margin-bottom:8px;">
                    Create a day-by-day customized Yatra plan
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Generate Itinerary →", key=f"{key_prefix}_{i}_btn_gen_itin", use_container_width=True):
                _process_trip_input("Show full itinerary")
    with act_c2:
        with st.container(border=True):
            st.markdown(
                """
                <div style="font-family:'Cinzel',serif; font-weight:800; font-size:0.88rem; color:#58111A;">
                    🚆 FIND TRAVEL OPTIONS
                </div>
                <div style="font-size:0.78rem; color:#6B5C5C; margin-top:2px; margin-bottom:8px;">
                    Search available transport & darshan slots to Katra
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Search Travel →", key=f"{key_prefix}_{i}_btn_search_travel", use_container_width=True):
                set_active_nav("Darshan Bookings")
                st.rerun()

    # 8. NO-AVAILABILITY MESSAGE / TRANSPORT AVAILABILITY (Separated)
    plan = msg.get("plan") or {}
    plan_status = plan.get("status") or st.session_state.get("booking_search_status")
    if plan_status in ("NO_AVAILABILITY", "NO_COMBINATION"):
        st.markdown(
            """
            <div style="background:#FFF9F2; border:1.5px solid #DFD2BC; border-radius:12px; padding:12px 18px; margin-top:14px; margin-bottom:8px;">
                <div style="font-family:'Cinzel',serif; font-weight:800; font-size:0.88rem; color:#58111A; margin-bottom:4px; display:flex; align-items:center; gap:6px;">
                    <span>ℹ️</span> TRAVEL OPTIONS NOT FOUND
                </div>
                <div style="font-size:0.82rem; color:#4A2E18; line-height:1.45; margin-bottom:6px;">
                    No verified transport combinations were found for the selected date and route.
                </div>
                <div style="font-size:0.8rem; color:#6B5C5C; line-height:1.4;">
                    <b>Try:</b><br/>
                    • Another travel date (e.g. next week)<br/>
                    • Another transport mode (train, flight, or bus)<br/>
                    • A supported departure hub
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Change Search 🔍", key=f"{key_prefix}_{i}_btn_change_search", use_container_width=True):
            set_active_nav("Darshan Bookings")
            st.rerun()
    elif plan_status == "PLAN_READY":
        opt_count = len(plan.get("options", []))
        st.markdown(
            f"""
            <div style="background:#F2F9F3; border:1px solid #C3E6CB; border-radius:10px; padding:9px 14px; margin-top:12px; font-size:0.82rem; color:#155724; font-weight:600; display:flex; align-items:center; gap:6px;">
                <span>✓</span> Verified Travel Options Ready: <b>{opt_count} options</b> available in Darshan Bookings
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_assistant_chat_message(msg, i, key_prefix="home"):
    """Unified assistant message renderer supporting rich recommendation dashboard cards and structured text."""
    content = msg.get("content", "")
    rec = msg.get("recommendation")

    is_rec_msg = (
        bool(rec)
        or "PERSONALIZED TRIP RECOMMENDATION" in content
        or "YOUR PERSONALIZED YATRA PLAN" in content
        or ("TRIP SNAPSHOT" in content and "Recommended Approach" in content)
        or ("Trip Profile" in content and "Recommended Approach" in content)
    )

    if not rec and is_rec_msg:
        req = msg.get("request") or st.session_state.get("trip_request")
        if req:
            try:
                rec = coordinator.get_trip_recommendation(req)
            except Exception:
                rec = None

    with st.container(border=True):
        st.markdown(
            '<div style="font-family:\'Cinzel\',serif; font-weight:700; color:#58111A; font-size:0.92rem; margin-bottom:8px; display:flex; align-items:center; gap:6px;"><span>🔱</span> AI Companion</div>',
            unsafe_allow_html=True,
        )

        if is_rec_msg and rec:
            _render_personalized_recommendation_dashboard(rec, msg, i, key_prefix)
        else:
            st.markdown(content, unsafe_allow_html=True)

    speech_content = content
    if is_rec_msg and rec:
        prof = rec.get("profile") or {}
        speech_content = f"Jai Mata Di! Here is your personalized yatra plan for {prof.get('pax', 1)} pilgrims for {prof.get('duration_days', 4)} days. {rec.get('reasoning', '')}"
    render_speak_button(speech_content, key=f"speak_{key_prefix}_{i}")


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
    initial_sidebar_state="expanded",
)

# One-time database setup (cached across reruns)
@st.cache_resource
def _init_databases_once():
    build_database()
    return True

_init_databases_once()

API_KEY = get_api_key()
BASE_URL = get_base_url()

MODE_LABEL = {"flight": "Flight", "train": "Train", "bus": "Bus"}

# --- HERO IMAGE BASE64 REFERENCE ---
HERO_IMG_PATH_CANDIDATES = [
    os.path.join("assets", "images", "places", "vaishno devi.jpg"),
    os.path.join("assets", "images", "places", "vaishno_devi.jpg"),
    os.path.join("assets", "images", "vaishno_devi_hero.jpg"),
]
HERO_IMG_PATH = None
for candidate in HERO_IMG_PATH_CANDIDATES:
    if os.path.exists(candidate):
        HERO_IMG_PATH = candidate
        break
if not HERO_IMG_PATH:
    HERO_IMG_PATH = os.path.join("assets", "images", "places", "vaishno devi.jpg")

hero_b64 = get_image_base64(HERO_IMG_PATH)
if hero_b64:
    hero_css_bg = f"""background-color: #2D050B;
        background-image: 
            linear-gradient(to right, rgba(40, 6, 12, 0.48) 0%, rgba(40, 6, 12, 0.38) 28%, rgba(40, 6, 12, 0.18) 55%, rgba(40, 6, 12, 0.04) 80%, transparent 100%),
            url('{hero_b64}');
        background-size: cover;
        background-position: center center;
        background-repeat: no-repeat;"""
else:
    hero_css_bg = "background: linear-gradient(135deg, #3D0810 0%, #58111A 55%, #2A0409 100%);"

# --- STYLING: Premium Indian Pilgrimage Travel Platform ---
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,700;0,800;1,700&display=swap');

    :root {{
        --bg-main: #FDFBF7;
        --card-bg: #FFFFFF;
        --burgundy-dark: #3D0810;
        --burgundy: #58111A;
        --burgundy-light: #7A1926;
        --gold-primary: #B8860B;
        --gold-accent: #C5A059;
        --gold-subtle: #F5ECDA;
        --gold-border: #E5D2AD;
        --text-dark: #2A2020;
        --text-muted: #6B5C5C;
        --border-subtle: #EBE1D0;
        --shadow-elevation: 0 12px 36px rgba(88, 17, 26, 0.10);
    }}

    html, body, [class*="css"] {{
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 15px;
        color: var(--text-dark);
        background-color: var(--bg-main);
    }}

    .stApp {{
        background-color: var(--bg-main);
    }}

    header[data-testid="stHeader"] {{
        background: transparent !important;
    }}

    .block-container {{
        max-width: 1240px;
        padding-top: 0.6rem;
        padding-bottom: 3rem;
    }}

    /* --- LUXURY SINGLE HORIZONTAL NAVBAR --- */
    .luxury-nav-container {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #FFFFFF;
        border: 1.5px solid var(--gold-border);
        border-radius: 22px;
        padding: 0.6rem 1.6rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 4px 16px rgba(88, 17, 26, 0.05);
        height: 68px;
        box-sizing: border-box;
        width: 100%;
    }}

    .nav-brand-area {{
        display: flex;
        align-items: center;
        gap: 10px;
        flex-shrink: 0;
        margin-right: 1.5rem;
    }}

    .nav-trident-logo {{
        font-size: 1.8rem;
        color: var(--gold-primary);
        line-height: 1;
    }}

    .nav-brand-text {{
        display: flex;
        flex-direction: column;
        line-height: 1.05;
    }}

    .brand-top-text {{
        font-family: 'Cinzel', serif;
        font-weight: 800;
        font-size: 1.05rem;
        letter-spacing: 0.04em;
        color: var(--burgundy);
    }}

    .brand-bottom-text {{
        font-family: 'Cinzel', serif;
        font-weight: 700;
        font-size: 0.78rem;
        letter-spacing: 0.16em;
        color: var(--burgundy);
    }}

    .brand-ai-badge {{
        background: var(--gold-accent);
        color: #FFFFFF;
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.62rem;
        font-weight: 800;
        padding: 1px 5px;
        border-radius: 4px;
        margin-left: 2px;
    }}

    .nav-links-area {{
        display: flex;
        align-items: center;
        gap: 1.4rem;
        flex-grow: 1;
        justify-content: flex-start;
    }}

    .nav-link-item {{
        color: var(--burgundy) !important;
        font-weight: 600;
        font-size: 0.88rem;
        text-decoration: none !important;
        padding: 4px 2px;
        border-bottom: 2.5px solid transparent;
        transition: all 0.15s ease;
        white-space: nowrap;
        cursor: pointer;
    }}

    .nav-link-item:hover {{
        color: var(--gold-primary) !important;
        border-bottom: 2.5px solid var(--gold-accent);
    }}

    .nav-link-item.active {{
        color: var(--burgundy) !important;
        font-weight: 800;
        border-bottom: 2.5px solid var(--gold-accent);
    }}

    .nav-right-area {{
        display: flex;
        align-items: center;
        gap: 12px;
        flex-shrink: 0;
        margin-left: 1rem;
    }}

    .nav-account-pill {{
        background: #F8F4EC;
        border: 1px solid var(--gold-border);
        color: var(--burgundy) !important;
        font-weight: 700;
        font-size: 0.8rem;
        padding: 6px 14px;
        border-radius: 999px;
        text-decoration: none !important;
        display: flex;
        align-items: center;
        gap: 6px;
        white-space: nowrap;
        transition: all 0.15s ease;
    }}

    .nav-account-pill:hover {{
        background: #F2E8D5;
        border-color: var(--gold-accent);
        color: var(--burgundy-dark) !important;
    }}

    .nav-search-btn {{
        background: #F8F4EC;
        border: 1px solid var(--gold-border);
        border-radius: 50%;
        width: 36px;
        height: 36px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.95rem;
        color: var(--burgundy) !important;
        text-decoration: none !important;
        transition: all 0.15s ease;
    }}

    .nav-search-btn:hover {{
        background: #F2E8D5;
        border-color: var(--gold-accent);
        transform: scale(1.05);
    }}

    /* HERO BANNER - FULL PHOTOGRAPH WITH SUBTLE OVERLAY */
    .hero-banner-wrap {{
        position: relative;
        {hero_css_bg}
        border-radius: 24px;
        padding: 3.8rem 3.8rem 7.5rem 3.8rem;
        color: #FFFFFF;
        margin-bottom: 0rem;
        min-height: 480px;
        box-sizing: border-box;
        border: 1px solid rgba(197, 160, 89, 0.32);
        box-shadow: 0 16px 40px rgba(0, 0, 0, 0.22);
        overflow: hidden;
    }}

    .hero-text-container {{
        position: relative;
        z-index: 2;
        max-width: 580px;
    }}

    .hero-badge-accent {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(30, 5, 10, 0.50);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(229, 195, 120, 0.5);
        color: #F8EEDB;
        font-size: 0.82rem;
        font-weight: 700;
        padding: 5px 14px;
        border-radius: 999px;
        margin-bottom: 1.15rem;
        letter-spacing: 0.04em;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.35);
    }}

    .hero-main-heading {{
        font-family: 'Playfair Display', 'Cinzel', serif;
        font-size: 3.3rem;
        font-weight: 800;
        letter-spacing: 0.02em;
        line-height: 1.14;
        margin-bottom: 0.85rem;
    }}

    .hero-heading-gold {{
        color: #E5C378;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.95), 0 4px 14px rgba(0, 0, 0, 0.85), 0 8px 24px rgba(0, 0, 0, 0.65);
    }}

    .hero-heading-white {{
        color: #FFFFFF;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.95), 0 4px 14px rgba(0, 0, 0, 0.85), 0 8px 24px rgba(0, 0, 0, 0.65);
    }}

    .hero-sub-heading {{
        font-size: 1.12rem;
        color: #F8EEDB;
        font-weight: 500;
        line-height: 1.5;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.95), 0 4px 12px rgba(0, 0, 0, 0.8);
        margin-bottom: 0.4rem;
        max-width: 560px;
    }}

    .hero-devotional-pill, .hero-mantra-box {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: rgba(254, 252, 248, 0.92);
        backdrop-filter: blur(6px);
        border: 1.5px solid var(--gold-accent);
        border-radius: 999px;
        padding: 7px 22px;
        margin-top: 1.15rem;
        font-family: 'Cinzel', serif, sans-serif;
        font-size: 0.98rem;
        font-weight: 700;
        color: var(--burgundy-dark);
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
        letter-spacing: 0.05em;
        text-align: center;
    }}

    /* FLOATING YATRA SEARCH WIDGET CARD */
    div.st-key-hero_search_card,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.search-card-marker) {{
        position: relative !important;
        z-index: 20 !important;
        margin-top: -5.6rem !important;
        margin-bottom: 2.8rem !important;
        margin-left: auto !important;
        margin-right: auto !important;
        max-width: 1140px !important;
        background: #F8F5EC !important;
        border: 1.5px solid var(--gold-border) !important;
        border-radius: 20px !important;
        padding: 1.4rem 2rem 1.2rem 2rem !important;
        box-shadow: 0 16px 40px rgba(45, 6, 11, 0.12) !important;
    }}

    div.st-key-hero_search_card > div,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.search-card-marker) > div {{
        background: transparent !important;
    }}

    div.st-key-hero_search_card .stSelectbox label,
    div.st-key-hero_search_card .stTextInput label,
    div.st-key-hero_search_card .stDateInput label,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.search-card-marker) label {{
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.88rem !important;
        color: #4A151C !important;
        margin-bottom: 4px !important;
    }}

    div.st-key-hero_search_card div[data-baseweb="select"] > div,
    div.st-key-hero_search_card div[data-baseweb="input"] > div,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.search-card-marker) div[data-baseweb="select"] > div,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.search-card-marker) div[data-baseweb="input"] > div {{
        border-radius: 10px !important;
        border-color: #DFD2BC !important;
        background-color: #FFFFFF !important;
        min-height: 42px !important;
    }}

    div.st-key-hero_search_card div[data-testid="stButton"] button,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.search-card-marker) div[data-testid="stButton"] button {{
        background: linear-gradient(135deg, #B8860B 0%, #9E7408 100%) !important;
        color: #FFFFFF !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.92rem !important;
        letter-spacing: 0.04em !important;
        border: none !important;
        border-radius: 10px !important;
        min-height: 42px !important;
        padding: 0.65rem 1.4rem !important;
        box-shadow: 0 4px 14px rgba(184, 134, 11, 0.32) !important;
        transition: all 0.2s ease !important;
    }}

    div.st-key-hero_search_card div[data-testid="stButton"] button:hover,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.search-card-marker) div[data-testid="stButton"] button:hover {{
        background: linear-gradient(135deg, #C5A059 0%, #B8860B 100%) !important;
        box-shadow: 0 6px 18px rgba(184, 134, 11, 0.45) !important;
        transform: translateY(-1px) !important;
    }}

    /* DESTINATION CARDS */
    .dest-card-title {{
        font-family: 'Playfair Display', serif;
        font-weight: 700;
        font-size: 1.25rem;
        color: var(--burgundy);
        margin-bottom: 2px;
    }}

    .dest-card-sub {{
        font-weight: 600;
        font-size: 0.85rem;
        color: var(--gold-primary);
        margin-bottom: 8px;
    }}

    .dest-card-desc {{
        font-size: 0.84rem;
        color: var(--text-dark);
        line-height: 1.45;
        margin-bottom: 12px;
    }}

    .section-title-wrap {{
        margin-top: 1.6rem;
        margin-bottom: 1.2rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid var(--gold-subtle);
    }}

    .section-main-heading {{
        font-family: 'Cinzel', serif;
        font-weight: 800;
        font-size: 1.55rem;
        color: var(--burgundy);
        letter-spacing: 0.03em;
        margin-bottom: 4px;
    }}

    .section-sub-heading {{
        font-size: 0.88rem;
        color: var(--text-muted);
    }}

    .option-card-wrap {{
        background: #FFFFFF;
        border: 1px solid var(--gold-border);
        border-radius: 14px;
        padding: 20px 24px;
        margin-bottom: 16px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.03);
    }}

    .option-card-recommended {{
        border: 2px solid var(--gold-primary);
        background: #FFFCF7;
    }}

    .badge-rec {{
        display: inline-block; background: var(--gold-primary); color: #FFFFFF;
        font-size: 0.72rem; font-weight: 700; padding: 3px 12px; border-radius: 12px; text-transform: uppercase;
        margin-left: 8px;
    }}

    div[data-testid="stVerticalBlockBorderWrapper"] {{
        border-radius: 16px !important;
        border: 1px solid var(--gold-border) !important;
        box-shadow: 0 4px 14px rgba(88, 17, 26, 0.04) !important;
        background: #FFFFFF !important;
    }}

    .luxury-footer {{
        margin-top: 4rem;
        padding-top: 2.4rem;
        padding-bottom: 2rem;
        border-top: 2px solid var(--gold-border);
        text-align: center;
        color: var(--text-muted);
        font-size: 0.88rem;
    }}

    /* --- SIDEBAR RESPONSIVE & OVERFLOW CONTROL --- */
    section[data-testid="stSidebar"] {{
        min-width: 350px !important;
        max-width: 400px !important;
        width: 360px !important;
        background-color: var(--bg-main) !important;
        border-right: 1.5px solid var(--gold-border) !important;
    }}

    section[data-testid="stSidebar"] > div:first-child {{
        padding: 1.2rem 1rem !important;
        box-sizing: border-box !important;
        overflow-x: hidden !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stChatInput"] {{
        max-width: 100% !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stChatInput"] textarea {{
        max-width: 100% !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }}

    section[data-testid="stSidebar"] iframe {{
        max-width: 100% !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }}

    @media (max-width: 900px) {{
        .hero-banner-wrap {{
            padding: 2.5rem 2rem 6.5rem 2rem;
            min-height: 440px;
        }}
        .hero-main-heading {{
            font-size: 2.4rem;
        }}
        .hero-text-container {{
            max-width: 100%;
        }}
        div.st-key-hero_search_card,
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.search-card-marker) {{
            margin-top: -4.5rem !important;
            padding: 1.2rem 1.2rem !important;
        }}
        section[data-testid="stSidebar"] {{
            min-width: 280px !important;
            width: 100% !important;
        }}
    }}

    @media (max-width: 600px) {{
        .hero-banner-wrap {{
            padding: 2rem 1.2rem 5.5rem 1.2rem;
            min-height: 400px;
        }}
        .hero-main-heading {{
            font-size: 1.85rem;
        }}
        .hero-sub-heading {{
            font-size: 0.96rem;
        }}
        .hero-devotional-pill, .hero-mantra-box {{
            font-size: 0.88rem;
            padding: 6px 16px;
        }}
        div.st-key-hero_search_card,
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.search-card-marker) {{
            margin-top: -3.5rem !important;
        }}
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --- SESSION STATE INITIALIZATION & SERVER-SIDE PERSISTENCE ---
if "_GLOBAL_SESSION_CACHE" not in globals():
    _GLOBAL_SESSION_CACHE = {}

PERSISTENT_STATE_KEYS = [
    "messages",
    "trip_request",
    "pending_options",
    "selected_option",
    "hotel_decision",
    "sightseeing_decision",
    "itinerary_confirmed",
    "last_tourism_place",
    "selected_destination",
    "selected_explore_place",
    "itinerary",
    "last_itinerary_context",
    "selected_hotel",
    "selected_accommodation",
    "current_intent",
    "booking_search_status",
]

# Preserve guest identity from query_params across browser navigations
if "guest" in st.query_params and st.query_params["guest"]:
    st.session_state.guest_id = str(st.query_params["guest"])
elif "guest_id" not in st.session_state:
    st.session_state.guest_id = "Guest-" + uuid.uuid4().hex[:5].upper()

st.query_params["guest"] = st.session_state.guest_id
guest_id = st.session_state.guest_id

if guest_id not in _GLOBAL_SESSION_CACHE:
    _GLOBAL_SESSION_CACHE[guest_id] = {
        "messages": [{"role": "assistant", "content": coordinator.get_greeting()}],
        "trip_request": None,
        "pending_options": None,
        "selected_option": None,
        "hotel_decision": None,
        "sightseeing_decision": None,
        "itinerary_confirmed": False,
        "last_tourism_place": None,
        "selected_destination": None,
        "selected_explore_place": None,
        "itinerary": None,
        "last_itinerary_context": None,
        "selected_hotel": None,
        "selected_accommodation": None,
        "current_intent": None,
        "booking_search_status": None,
    }

user_cache = _GLOBAL_SESSION_CACHE[guest_id]

# Safe initialization and restoration pattern
if "active_nav" not in st.session_state:
    st.session_state.active_nav = "Home"

if "show_search" not in st.session_state:
    st.session_state.show_search = False

for k in PERSISTENT_STATE_KEYS:
    if k not in st.session_state:
        st.session_state[k] = user_cache.get(k)
    elif k == "messages":
        # If session_state was reset by a tab reload to single greeting but user_cache has conversation:
        if len(st.session_state.messages) <= 1 and len(user_cache.get("messages", [])) > 1:
            st.session_state.messages = list(user_cache["messages"])
    elif st.session_state[k] is None and user_cache.get(k) is not None:
        st.session_state[k] = user_cache[k]


def _sync_state_to_cache():
    """Persists conversational and booking state to server-side cache for current guest."""
    gid = st.session_state.get("guest_id")
    if gid and gid in _GLOBAL_SESSION_CACHE:
        for k in PERSISTENT_STATE_KEYS:
            if k in st.session_state:
                _GLOBAL_SESSION_CACHE[gid][k] = st.session_state[k]


def set_active_nav(nav_name):
    """Sets active navigation safely, syncing both session_state and query_params."""
    st.session_state.active_nav = nav_name
    st.session_state._last_synced_nav = nav_name
    st.session_state.current_intent = None
    st.query_params["nav"] = nav_name
    _sync_state_to_cache()


# --- Centralized Input Processor (Preserves existing AI logic 100%) ---
def _process_trip_input(user_text):
    st.session_state.messages.append({"role": "user", "content": user_text})
    current_req = st.session_state.get("trip_request")
    current_itin = st.session_state.get("itinerary")
    last_place = st.session_state.get("selected_destination") or st.session_state.get("last_tourism_place")
    last_itin_ctx = st.session_state.get("last_itinerary_context")
    intent = coordinator.detect_intent(user_text)
    spinner_label = (
        "Looking up yatra information..."
        if intent == "TOURISM"
        else ("Updating your day-by-day itinerary..." if intent == "ITINERARY" else "Checking slots, flights, trains and buses...")
    )
    pending_opts = st.session_state.get("pending_options")
    try:
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
    except Exception as exc:
        err_msg = f"🙏 **Jai Mata Di!** I encountered an issue processing your query: {str(exc)}. Please try again."
        st.session_state.messages.append({
            "role": "assistant",
            "content": err_msg,
            "recommendation": None,
            "plan": None,
            "request": current_req,
        })
        _sync_state_to_cache()
        st.rerun()
        return
    st.session_state.messages.append({
        "role": "assistant",
        "content": result["reply"],
        "recommendation": result.get("recommendation"),
        "plan": result.get("plan"),
        "request": result.get("request"),
    })

    res_intent = result.get("intent") or intent
    st.session_state.current_intent = res_intent

    if result.get("last_tourism_place"):
        st.session_state.last_tourism_place = result["last_tourism_place"]
        st.session_state.selected_destination = result["last_tourism_place"]

    if result.get("last_itinerary_context"):
        st.session_state.last_itinerary_context = result["last_itinerary_context"]

    if result.get("itinerary") is not None:
        st.session_state.itinerary = result["itinerary"]

    if res_intent == "TOURISM":
        _sync_state_to_cache()
        st.rerun()
        return

    if res_intent in ("WEATHER", "ITINERARY"):
        _sync_state_to_cache()
        st.rerun()
        return

    if result.get("request") is not None:
        st.session_state.trip_request = result["request"]
    plan = result.get("plan") or {}
    plan_status = plan.get("status")
    st.session_state.booking_search_status = plan_status
    if plan_status == "PLAN_READY":
        st.session_state.pending_options = {"pax": plan["pax"], "options": plan["options"]}
    else:
        st.session_state.pending_options = None
    _sync_state_to_cache()
    st.rerun()


# --- VOICE & EXTERNAL QUERY PROCESSING HANDLER ---
# Processes spoken voice queries whether arriving via query_params or session state
voice_to_process = None

if "voice_input" in st.query_params and st.query_params["voice_input"]:
    v_raw = st.query_params["voice_input"]
    if isinstance(v_raw, list):
        v_raw = v_raw[0] if v_raw else ""
    raw_voice = str(v_raw).strip()
    try:
        del st.query_params["voice_input"]
        if "voice_ts" in st.query_params:
            del st.query_params["voice_ts"]
    except Exception:
        pass
    if raw_voice:
        voice_to_process = raw_voice

if not voice_to_process:
    for v_key in ["pending_voice_query", "voice_text", "spoken_query", "voice_transcript"]:
        if st.session_state.get(v_key):
            val = str(st.session_state.pop(v_key)).strip()
            if val:
                voice_to_process = val
                break

if voice_to_process:
    _process_trip_input(voice_to_process)


# --- SECTION 1: ONE SINGLE HORIZONTAL TOP NAVIGATION BAR ---
if "nav" in st.query_params:
    selected_nav = st.query_params["nav"]
    valid_navs = ["Home", "Darshan Bookings", "Yatra Guide", "Packages", "Hotels", "Transport", "Help", "AI Assistant", "My Account"]
    if selected_nav in valid_navs:
        if st.session_state.get("_last_synced_nav") != selected_nav:
            st.session_state.active_nav = selected_nav
            st.session_state._last_synced_nav = selected_nav
            st.session_state.current_intent = None
else:
    st.query_params["nav"] = st.session_state.active_nav
    st.session_state._last_synced_nav = st.session_state.active_nav

if "toggle_search" in st.query_params:
    st.session_state.show_search = not st.session_state.get("show_search", False)
    try:
        del st.query_params["toggle_search"]
    except Exception:
        pass

current_nav = st.session_state.get("active_nav", "Home")
guest_q = f"&guest={st.session_state.guest_id}"

nav_html = f"""
<div class="luxury-nav-container">
    <div class="nav-brand-area">
        <span class="nav-trident-logo">🔱</span>
        <div class="nav-brand-text">
            <span class="brand-top-text">VAISHNO DEVI</span>
            <span class="brand-bottom-text">YATRA <span class="brand-ai-badge">AI</span></span>
        </div>
    </div>
    <div class="nav-links-area">
        <a href="?nav=Home{guest_q}" target="_self" class="nav-link-item {'active' if current_nav == 'Home' else ''}">Home</a>
        <a href="?nav=Darshan+Bookings{guest_q}" target="_self" class="nav-link-item {'active' if current_nav == 'Darshan Bookings' else ''}">Darshan Bookings</a>
        <a href="?nav=Yatra+Guide{guest_q}" target="_self" class="nav-link-item {'active' if current_nav == 'Yatra Guide' else ''}">Yatra Guide</a>
        <a href="?nav=Packages{guest_q}" target="_self" class="nav-link-item {'active' if current_nav == 'Packages' else ''}">Packages</a>
        <a href="?nav=Hotels{guest_q}" target="_self" class="nav-link-item {'active' if current_nav == 'Hotels' else ''}">Hotels</a>
        <a href="?nav=Transport{guest_q}" target="_self" class="nav-link-item {'active' if current_nav == 'Transport' else ''}">Transport</a>
        <a href="?nav=Help{guest_q}" target="_self" class="nav-link-item {'active' if current_nav == 'Help' else ''}">Help</a>
        <a href="?nav=AI+Assistant{guest_q}" target="_self" class="nav-link-item {'active' if current_nav == 'AI Assistant' else ''}">AI Assistant</a>
    </div>
    <div class="nav-right-area">
        <a href="?nav=My+Account{guest_q}" target="_self" class="nav-account-pill">
            <span>👤</span> {st.session_state.guest_id}
        </a>
        <a href="?toggle_search=1{guest_q}" target="_self" class="nav-search-btn">
            🔍
        </a>
    </div>
</div>
"""
st.markdown(nav_html, unsafe_allow_html=True)

# --- TOP SEARCH EXPANDER ---
if st.session_state.get("show_search"):
    with st.container(border=True):
        st.markdown("### 🔍 Search Destinations & Yatra Guidance")
        search_query = st.text_input("Type any destination, temple, route, or topic (e.g. Patnitop, Shiv Khori, Aarti timings, Bhopal train)...", key="top_search_input")
        if search_query:
            all_places = explore_data.get_places()
            matches = [p for p in all_places if search_query.lower() in p["name"].lower() or search_query.lower() in p["description"].lower()]
            if matches:
                st.markdown(f"**Found {len(matches)} matching destination(s):**")
                m_cols = st.columns(min(3, len(matches)))
                for m_idx, m_place in enumerate(matches):
                    with m_cols[m_idx % 3]:
                        render_place_image(m_place, height_px=120)
                        st.write(f"**{m_place['name']}**")
                        st.caption(f"{m_place['category']} · {m_place['distance']}")
                        if st.button(f"Explore {m_place['name']}", key=f"search_m_{m_idx}", use_container_width=True):
                            st.session_state.selected_explore_place = m_place["name"]
                            st.session_state.selected_destination = m_place["name"]
                            st.session_state.last_tourism_place = m_place["name"]
                            st.session_state.show_search = False
                            set_active_nav("Home")
                            _sync_state_to_cache()
                            st.rerun()
            else:
                st.info(f"No direct place match for '{search_query}'. Would you like to ask the AI assistant?")
                if st.button(f"Ask AI Companion about '{search_query}'", key="ask_search_ai", use_container_width=True):
                    set_active_nav("AI Assistant")
                    _process_trip_input(search_query)


# =====================================================================
# VIEW 1: HOME PAGE
# =====================================================================
if st.session_state.active_nav == "Home":
    st.markdown(
        """
        <div class="hero-banner-wrap">
            <div class="hero-text-container">
                <div class="hero-badge-accent"><span>🔱</span> AI-Powered Yatra Companion</div>
                <h1 class="hero-main-heading">
                    <span class="hero-heading-gold">DIVINE JOURNEYS,</span><br/>
                    <span class="hero-heading-white">POWERED BY AI.</span>
                </h1>
                <p class="hero-sub-heading">Plan Your Vaishno Devi Yatra with Personalized Ease.</p>
                <div class="hero-devotional-pill">॥ ॐ ऐं ह्रीं क्लीं चामुण्डायै विच्चे ॥</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # FLOATING YATRA SEARCH WIDGET CARD
    with st.container(key="hero_search_card", border=True):
        st.markdown('<span class="search-card-marker" style="display:none;"></span>', unsafe_allow_html=True)

        col1, col2, col3 = st.columns([3, 3, 3])
        with col1:
            origin_options = [
                "Jammu (JAI)",
                "Delhi (DEL)",
                "Bhopal (BHO)",
                "Jaipur (JAI)",
                "Lucknow (LKO)",
                "Mumbai (BOM)",
                "Pune (PNQ)",
                "Chandigarh (IXC)",
                "Amritsar (ATQ)",
                "Dehradun (DED)",
                "Ahmedabad (AMD)",
                "Indore (IDR)",
                "Surat (STV)",
                "Kochi (COK)",
            ]
            search_from = st.selectbox("From", origin_options, index=0, key="widget_from")
        with col2:
            st.text_input("Destination", value="Katra (VND)", disabled=True, key="widget_to")
        with col3:
            today = datetime.now().date()
            search_date = st.date_input("Date", value=today + timedelta(days=7), min_value=today, key="widget_date")

        col4, col5, col6 = st.columns([3, 3, 3])
        with col4:
            search_pax = st.selectbox("Travellers", ["1 Adult", "2 Adults", "3 Adults", "4 Adults", "5 Adults", "6+ Adults"], index=1, key="widget_pax")
        with col5:
            search_mode = st.selectbox("Mode: Flight / Train / Road", ["Train", "Flight", "Bus"], index=0, key="widget_mode")
        with col6:
            st.markdown('<div style="height: 28px;"></div>', unsafe_allow_html=True)
            if st.button("SEARCH YOUR YATRA →", key="btn_widget_search", use_container_width=True):
                pax_num = re.search(r"\d+", search_pax)
                pax_val = pax_num.group(0) if pax_num else "2"
                origin_clean = search_from.split("(")[0].strip()
                date_str = search_date.strftime("%d %b %Y")
                query_text = f"{pax_val} people from {origin_clean} by {search_mode.lower()} on {date_str} for VIP darshan"
                st.session_state.trip_request = None
                st.session_state.pending_options = None
                st.session_state.selected_option = None
                st.session_state.hotel_decision = None
                st.session_state.sightseeing_decision = None
                st.session_state.itinerary_confirmed = False
                _sync_state_to_cache()
                set_active_nav("Darshan Bookings")
                _process_trip_input(query_text)

    # =================================================================
    # SECTION: AI YATRA COMPANION (Integrated Home Page Assistant)
    # =================================================================
    st.markdown(
        """
        <div class="section-title-wrap" style="margin-top: 2rem;">
            <div class="section-main-heading">AI Yatra Companion</div>
            <div class="section-sub-heading">Your personal guide for holy darshan slots, direct & connecting travel, Katra stays, weather & J&K exploration</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown(
            """
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #E5D2AD; padding-bottom:10px; margin-bottom:14px;">
                <div style="font-family:'Cinzel',serif; font-weight:800; font-size:1.15rem; color:#58111A; display:flex; align-items:center; gap:8px;">
                    <span>🔱</span> Vaishno Devi AI Companion
                </div>
                <div style="background:#F5ECDA; color:#58111A; border:1px solid #E5D2AD; font-size:0.75rem; font-weight:700; padding:4px 10px; border-radius:999px;">
                    ● Active Companion
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Render conversation history (Shared session state with AI Assistant page)
        for i, msg in enumerate(st.session_state.messages):
            if msg["role"] == "user":
                st.markdown(
                    f'<div style="background:#F5ECDA; border:1px solid #E5D2AD; padding:10px 16px; border-radius:14px; margin-bottom:10px; max-width:82%; margin-left:auto; color:#2A2020; font-size:0.92rem;"><b>You:</b> {msg["content"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                render_assistant_chat_message(msg, i, key_prefix="home")

        # Quick prompt chips if conversation is starting
        if len(st.session_state.messages) <= 1:
            st.markdown("<div style='font-size:0.8rem; font-weight:700; color:#8C6D3B; margin: 8px 0 4px 0;'>Suggested questions:</div>", unsafe_allow_html=True)
            chip_col1, chip_col2, chip_col3, chip_col4 = st.columns(4)
            with chip_col1:
                if st.button("Scenic places around Katra", key="chip_sg_places", use_container_width=True):
                    _process_trip_input("What places can I visit around Katra?")
            with chip_col2:
                if st.button("Weather forecast in Katra", key="chip_weather_katra", use_container_width=True):
                    _process_trip_input("What is the weather in Katra next week?")
            with chip_col3:
                if st.button("Trains from Delhi to Katra", key="chip_trains_delhi", use_container_width=True):
                    _process_trip_input("Show me trains from Delhi to Katra")
            with chip_col4:
                if st.button("Hotels near Ban Ganga", key="chip_hotels_bg", use_container_width=True):
                    _process_trip_input("What hotels are available in Katra?")

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        # Voice input & Text submission row
        v_col, in_col = st.columns([1.6, 5])
        with v_col:
            render_voice_input("home_assistant_voice")
        with in_col:
            with st.form(key="home_assistant_form", clear_on_submit=True):
                t_input_col, t_send_col = st.columns([4.2, 1])
                with t_input_col:
                    home_ai_text = st.text_input(
                        "Home AI Query",
                        placeholder="Type your query (e.g., 'What places can I visit around Katra?')...",
                        label_visibility="collapsed",
                        key="home_ai_text_input",
                    )
                with t_send_col:
                    home_ai_submit = st.form_submit_button("Send ➔", use_container_width=True)
                if home_ai_submit and home_ai_text:
                    _process_trip_input(home_ai_text)

    # FEATURED DESTINATIONS
    st.markdown(
        """
        <div class="section-title-wrap">
            <div class="section-main-heading">Featured Destinations</div>
            <div class="section-sub-heading">Explore revered temples, mountain caves, and Himalayan retreats across Jammu & Kashmir</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    featured_places = [
        {
            "name": "Katra",
            "tagline": "The Gateway",
            "description": "Base town for the sacred 13 km trek to Shri Mata Vaishno Devi Bhawan, nestled at the foot of Trikuta hills.",
            "category": "Pilgrimage Base",
            "image": "assets/images/places/vaishno devi.jpg",
            "image_file": "assets/images/places/vaishno devi.jpg",
        },
        {
            "name": "Bhairavnath Temple",
            "tagline": "The Steep Climb",
            "description": "Sacred shrine at 6,600 ft. Tradition holds the pilgrimage is complete only after visiting Bhairavnath shrine.",
            "category": "Sacred Shrine",
            "image": "assets/images/places/Bhairavnath Temple.png",
            "image_file": "assets/images/places/Bhairavnath Temple.png",
        },
        {
            "name": "Patnitop",
            "tagline": "Hill Station Charm",
            "description": "Scenic Himalayan hill station with dense pine forests, lush meadows, and panoramic Chenab valley vistas.",
            "category": "Hill Station",
            "image": "assets/images/places/Patnitop.jpg",
            "image_file": "assets/images/places/Patnitop.jpg",
        },
        {
            "name": "Kashmir Valley",
            "tagline": "Paradise Found",
            "description": "Explore Srinagar's Dal Lake, Gulmarg's snow gondola, and Pahalgam's pristine alpine streams.",
            "category": "Valley & Snow",
            "image": "assets/images/places/Dal Lake.jpg",
            "image_file": "assets/images/places/Dal Lake.jpg",
        },
    ]

    f_cols = st.columns(2)
    for idx, fp in enumerate(featured_places):
        with f_cols[idx % 2]:
            with st.container():
                c_img, c_info = st.columns([1.3, 2.7])
                with c_img:
                    render_place_image(fp, height_px=140)
                with c_info:
                    st.markdown(f'<div class="dest-card-title">{fp["name"]}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="dest-card-sub">{fp["tagline"]} · {fp["category"]}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="dest-card-desc">{fp["description"]}</div>', unsafe_allow_html=True)
                    if st.button(f"Explore {fp['name']} →", key=f"btn_feat_{fp['name']}", use_container_width=True):
                        st.session_state.selected_explore_place = fp["name"]
                        st.session_state.selected_destination = fp["name"]
                        st.session_state.last_tourism_place = fp["name"]
                        _sync_state_to_cache()
                        st.rerun()

    # EXPLORE JAMMU & KASHMIR
    st.markdown(
        """
        <div class="section-title-wrap">
            <div class="section-main-heading">Explore Jammu & Kashmir</div>
            <div class="section-sub-heading">Discover the beauty, culture and experiences across Jammu & Kashmir.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("selected_explore_place"):
        render_place_detail_view(st.session_state.selected_explore_place)
    else:
        tab_jammu, tab_kashmir = st.tabs(["⛰️ Jammu", "🏞️ Kashmir"])

        all_places = explore_data.get_places()

        with tab_jammu:
            jammu_places = [p for p in all_places if p.get("region") != "Kashmir" and p.get("category") != "Kashmir"]
            j_cols = st.columns(3)
            for idx, place in enumerate(jammu_places):
                with j_cols[idx % 3]:
                    with st.container(border=True):
                        render_place_image(place, height_px=140)
                        st.markdown(f"**{place['name']}**")
                        st.caption(f"{place['category']} · {place['distance']}")
                        st.write(place["description"][:120] + "...")
                        if st.button(f"Explore {place['name']} →", key=f"home_j_{place['name']}", use_container_width=True):
                            st.session_state.selected_explore_place = place["name"]
                            st.session_state.selected_destination = place["name"]
                            st.session_state.last_tourism_place = place["name"]
                            _sync_state_to_cache()
                            st.rerun()

        with tab_kashmir:
            kashmir_places = [p for p in all_places if p.get("region") == "Kashmir" or p.get("category") == "Kashmir"]
            k_cols = st.columns(2)
            for idx, place in enumerate(kashmir_places):
                with k_cols[idx % 2]:
                    with st.container(border=True):
                        render_place_image(place, height_px=150)
                        st.markdown(f"**{place['name']}**")
                        st.caption(f"{place['category']} · {place['distance']}")
                        if place.get("location_route"):
                            st.caption(f"📍 **Location & Route:** {place['location_route']}")
                        st.write(place["description"])
                        if st.button(f"Explore {place['name']} →", key=f"home_k_{place['name']}", use_container_width=True):
                            st.session_state.selected_explore_place = place["name"]
                            st.session_state.selected_destination = place["name"]
                            st.session_state.last_tourism_place = place["name"]
                            _sync_state_to_cache()
                            st.rerun()


# =====================================================================
# VIEW 2: DARSHAN BOOKINGS & TRIP PLANNER
# =====================================================================
elif st.session_state.active_nav == "Darshan Bookings":
    st.markdown("### 🔱 Vaishno Devi Darshan & Yatra Slot Booking")
    st.caption("Select your preferred Darshan category, travel date, and slot timing.")

    # Determine active booking stage for step tracker
    if st.session_state.get("_last_confirmed_booking_id"):
        current_step_num = 7
    elif st.session_state.selected_option and st.session_state.itinerary_confirmed:
        current_step_num = 6
    elif (
        st.session_state.selected_option
        and st.session_state.hotel_decision is not None
        and st.session_state.sightseeing_decision is not None
    ):
        current_step_num = 5
    elif (
        st.session_state.selected_option
        and st.session_state.hotel_decision is not None
        and st.session_state.sightseeing_decision is None
    ):
        current_step_num = 4
    elif st.session_state.selected_option and st.session_state.hotel_decision is None:
        current_step_num = 3
    elif st.session_state.pending_options:
        current_step_num = 2
    else:
        current_step_num = 1

    steps_meta = [
        (1, "Search"),
        (2, "Travel & Slots"),
        (3, "Accommodation"),
        (4, "Sightseeing"),
        (5, "Itinerary"),
        (6, "Review & Auth"),
        (7, "RPA Confirmation"),
    ]

    is_info_query = st.session_state.get("current_intent") in ("TOURISM", "WEATHER", "ITINERARY")

    if not is_info_query:
        pills_html = []
        for s_idx, s_lbl in steps_meta:
            is_cur = s_idx == current_step_num
            is_past = s_idx < current_step_num
            bg_col = "#58111A" if is_cur else ("#2E7D32" if is_past else "#F4EBD9")
            txt_col = "#FFFFFF" if (is_cur or is_past) else "#6B5C5C"
            b_weight = "700" if is_cur else "600"
            prefix = "✓ " if is_past else f"{s_idx}. "
            pills_html.append(
                f'<div style="background:{bg_col}; color:{txt_col}; font-weight:{b_weight}; padding:5px 11px; border-radius:999px; font-size:0.75rem; white-space:nowrap; border:1px solid #D5C29D;">'
                f'{prefix}STEP {s_idx} — {s_lbl}</div>'
            )

        st.markdown(
            '<div style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:18px; align-items:center;">'
            + "".join(pills_html)
            + "</div>",
            unsafe_allow_html=True,
        )

        # Render Active Trip Summary Card if active plan is ready
        has_active_plan = (
            st.session_state.pending_options
            or st.session_state.selected_option
            or st.session_state.get("booking_search_status") == "PLAN_READY"
        )
        if st.session_state.trip_request and has_active_plan:
            req = st.session_state.trip_request
            origin_disp = req.get("origin") or "Jammu"
            duration_disp = req.get("duration_days") or 3
            pax_disp = req.get("pax") or 1
            mode_disp = (req.get("mode") or "Train").title()
            category_disp = req.get("category") or "Normal Darshan"
            style_disp = (req.get("travel_style") or "Balanced").title()

            st.markdown(
                f"""
                <div style="background:#FFFCF7; border:2px solid var(--gold-border); border-radius:16px; padding:18px 22px; margin-bottom:22px; box-shadow:0 4px 12px rgba(88,17,26,0.06);">
                    <div style="font-family:'Cinzel',serif; font-weight:800; color:var(--burgundy); font-size:1.1rem; margin-bottom:8px;">
                        ✨ Active Trip Plan: {origin_disp} → Katra ({duration_disp} Days)
                    </div>
                    <div style="display:flex; gap:24px; flex-wrap:wrap; font-size:0.92rem; color:var(--text-dark);">
                        <div><b>Origin:</b> {origin_disp}</div>
                        <div><b>Pilgrims:</b> {pax_disp}</div>
                        <div><b>Travel Mode:</b> {mode_disp}</div>
                        <div><b>Darshan:</b> {category_disp}</div>
                        <div><b>Travel Style:</b> {style_disp}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # --- Render Assistant Chat Messages Stream ---
    st.markdown("#### Yatra Assistant Conversation")
    for i, msg in enumerate(st.session_state.messages):
        if msg["role"] == "user":
            st.markdown(
                f'<div style="background:#F5ECDA; border:1px solid #E5D2AD; padding:12px 18px; border-radius:14px; margin-bottom:12px; max-width:82%; margin-left:auto; box-shadow:0 2px 6px rgba(0,0,0,0.02);"><b>You:</b> {msg["content"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            render_assistant_chat_message(msg, i, key_prefix="darshan")

    if is_info_query:
        # When an unrelated tourism/weather/itinerary query was just processed:
        # Keep booking state preserved in session, but isolate booking UI completely.
        if st.session_state.selected_option or st.session_state.pending_options:
            st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)
            col_ret1, col_ret2 = st.columns([3, 1.2])
            with col_ret1:
                st.info("ℹ️ You have an active booking search saved in this session.")
            with col_ret2:
                if st.button("👉 Return to Booking Flow", key="ret_booking_flow_btn", use_container_width=True):
                    st.session_state.current_intent = None
                    _sync_state_to_cache()
                    st.rerun()
    else:
        # --- Step 2: Options Selection ---
        if st.session_state.pending_options:
            bundle = st.session_state.pending_options
            pax, options = bundle["pax"], bundle["options"]
            st.markdown("### Available Travel & Slot Combinations")
            for i, opt in enumerate(options):
                tr = opt.get("transport") or opt.get("flight")
                s = opt["slot"]
                mode = tr.get("mode") or "flight"
                is_flight = mode == "flight"
                label = "Flight + Road Transfer" if is_flight else MODE_LABEL.get(mode, mode.title())
                is_rec = i == 0
                card_cls = "option-card-wrap option-card-recommended" if is_rec else "option-card-wrap"
                rec_tag = '<span class="badge-rec">Recommended</span>' if is_rec else ""

                st.markdown(
                    f"""
                    <div class="{card_cls}">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <div style="font-family:'Cinzel',serif; font-weight:800; font-size:1.1rem; color:#58111A;">
                                Option {i + 1} — {label} {rec_tag}
                            </div>
                            <div style="font-weight:800; font-size:1.25rem; color:#58111A;">
                                Total: ₹{opt["total_price"]}
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if is_flight:
                    transfer_msg = tr.get(
                        "transfer_note",
                        "Direct flight to Katra is not available. This option flies to Jammu, followed by a local taxi/bus transfer to Katra."
                    )
                    st.markdown(
                        f"""
                        <div style="background:#FFF9F0; border:1px solid #E5D2AD; border-radius:10px; padding:10px 14px; margin-bottom:12px; font-size:0.86rem; color:#4A2E18;">
                            ℹ️ <b>Connecting Journey Note:</b> {transfer_msg}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                c1, c2 = st.columns(2)
                with c1:
                    if is_flight:
                        st.write(f"**Flight:** {tr.get('operator', '-')} ({tr.get('transport_no', '-')})")
                        st.write(f"**Flight Sector:** {tr['origin']} → Jammu Airport")
                        st.write(f"**Departure:** {tr['travel_date']} at {fmt_time(tr['departure_time'])}")
                        st.write(f"**Connecting Transfer:** Jammu Airport → Katra ({tr.get('transfer_mode', 'Taxi / Bus')})")
                        st.caption(f"Road Transfer: {tr.get('transfer_distance', 'approx. 44-55 km')}, {tr.get('transfer_duration', 'approx. 1-1.5 hours by road')}")
                    else:
                        st.write(f"**Transport:** {tr.get('operator', '-')} ({tr.get('transport_no', '-')})")
                        st.write(f"**Route:** {tr['origin']} → {tr['destination']}")
                        st.write(f"**Departure:** {tr['travel_date']} at {fmt_time(tr['departure_time'])}")
                        if tr.get("route_note"):
                            st.caption(f"Note: {tr['route_note']}")
                with c2:
                    st.write(f"**Yatra Slot:** {s['category']}")
                    st.write(f"**Slot Date/Time:** {s['slot_date']} at {fmt_time(s['slot_time'])}")
                    st.write(f"**Pilgrims:** {pax}")

                if st.button(f"Select Option {i + 1}", key=f"sel_opt_{i}", use_container_width=True):
                    st.session_state.selected_option = {"pax": pax, "option": opt}
                    st.session_state.pending_options = None
                    st.session_state._last_confirmed_booking_id = None
                    _sync_state_to_cache()
                    st.rerun()

        # --- Step 3: Accommodation Selection (Inside Booking Workflow) ---
        elif st.session_state.selected_option and st.session_state.hotel_decision is None:
            st.markdown("### 🏨 Step 3: Choose Your Accommodation in Katra")
            st.caption("Select your verified Katra hotel stay directly within your Yatra booking. Accommodation booking is demonstrated through the project prototype.")

            bundle = st.session_state.selected_option
            opt = bundle["option"]
            tr = opt.get("transport") or opt.get("flight") or {}
            checkin_d = tr.get("travel_date") or datetime.now().date().isoformat()

            # Retrieve hotels for the travel date from database
            hotels_list = db.search_hotels(checkin_d)
            if not hotels_list:
                hotels_list = db.search_hotels(datetime.now().date().isoformat())
            if not hotels_list:
                try:
                    import pandas as pd
                    hdf = pd.read_csv("data/hotels_live.csv")
                    hotels_list = hdf.drop_duplicates(subset=["name"]).to_dict("records")
                except Exception:
                    hotels_list = []

            # Display currently selected accommodation banner if user already picked one
            cur_acc = st.session_state.get("selected_accommodation") or st.session_state.get("selected_hotel")
            if cur_acc:
                st.markdown(
                    f"""
                    <div style="background:#FFF9F0; border:1.8px solid #B8860B; border-radius:14px; padding:16px 20px; margin-bottom:18px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <div style="font-size:0.8rem; font-weight:700; color:#8C6D3B; text-transform:uppercase; letter-spacing:0.05em;">Selected Accommodation</div>
                                <div style="font-family:'Cinzel',serif; font-weight:800; font-size:1.22rem; color:#58111A; margin-top:2px;">
                                    🏨 {cur_acc.get('name', 'Hotel')}
                                </div>
                                <div style="font-size:0.88rem; color:#4A2E18; margin-top:4px;">
                                    Location: <b>Katra Base</b> · Category: <b>{cur_acc.get('category', 'Standard')}</b> · Price: <b>₹{cur_acc.get('price_per_night', 0)} / night</b> · Rooms: <b>{cur_acc.get('rooms_available', 'Available')}</b>
                                </div>
                            </div>
                            <div style="font-size:1.5rem; color:#B8860B;">✓</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Action bar: Confirm & Continue, Skip, or Reselect Travel
            act_c1, act_c2, act_c3 = st.columns([2.8, 2.5, 1.5])
            with act_c1:
                confirm_label = f"Confirm Accommodation ({cur_acc['name']}) →" if cur_acc else "Confirm Accommodation & Continue →"
                if st.button(confirm_label, key="confirm_hotel_stay", use_container_width=True, disabled=not cur_acc):
                    st.session_state.hotel_decision = cur_acc
                    st.session_state.selected_hotel = cur_acc
                    st.session_state.selected_accommodation = cur_acc
                    _sync_state_to_cache()
                    st.rerun()
            with act_c2:
                if st.button("Skip Accommodation (Day Trip / Self Stay) →", key="skip_hotel_btn", use_container_width=True):
                    st.session_state.hotel_decision = {}
                    st.session_state.selected_hotel = None
                    st.session_state.selected_accommodation = None
                    _sync_state_to_cache()
                    st.rerun()
            with act_c3:
                if st.button("← Reselect Travel", key="reselect_opt_btn", use_container_width=True):
                    cur_req = st.session_state.get("trip_request")
                    if cur_req:
                        rep_plan = coordinator.legacy_agent.build_plan(cur_req)
                        if rep_plan.get("status") == "PLAN_READY":
                            st.session_state.pending_options = {"pax": rep_plan["pax"], "options": rep_plan["options"]}
                    st.session_state.selected_option = None
                    _sync_state_to_cache()
                    st.rerun()

            # Filter controls for accommodation
            f_col1, f_col2 = st.columns([2, 4])
            with f_col1:
                cat_filter = st.selectbox("Category Filter", ["All Categories", "Budget", "Mid-Range", "Premium"], key="acc_cat_filter")
            with f_col2:
                search_hotel_kw = st.text_input("Search Hotel by name", placeholder="Search hotel...", key="acc_kw_filter")

            filtered_hotels = hotels_list
            if cat_filter != "All Categories":
                filtered_hotels = [h for h in filtered_hotels if h.get("category") == cat_filter]
            if search_hotel_kw:
                filtered_hotels = [h for h in filtered_hotels if search_hotel_kw.lower() in h.get("name", "").lower()]

            # Render hotel cards in 3 columns
            h_cols = st.columns(3)
            for idx, h in enumerate(filtered_hotels):
                amenities = {
                    "Budget": "Clean AC/Non-AC Rooms · Free Wi-Fi · 24h Hot Water",
                    "Mid-Range": "Deluxe AC Rooms · Pure Veg Restaurant · Elevator · Yatra Shuttle",
                    "Premium": "Luxury Mountain View Suites · Multi-Cuisine Dining · Darshan Concierge",
                }.get(h.get("category"), "Comfortable Stay · Clean Rooms · Hot Water")

                is_sel = cur_acc and cur_acc.get("name") == h.get("name")

                with h_cols[idx % 3]:
                    with st.container(border=True):
                        st.markdown(
                            f"""
                            <div style="font-family:'Cinzel',serif; font-weight:800; font-size:1.05rem; color:#58111A; min-height:48px;">
                                {h['name']}
                            </div>
                            <div style="font-size:0.82rem; color:#8C6D3B; font-weight:600; margin-bottom:4px;">
                                {h.get('category', 'Standard')} · Katra Base
                            </div>
                            <div style="font-size:1.15rem; font-weight:800; color:#58111A; margin-bottom:6px;">
                                ₹{h['price_per_night']} <span style="font-size:0.75rem; font-weight:500; color:#666;">/ night</span>
                            </div>
                            <div style="font-size:0.78rem; color:#555; margin-bottom:10px; min-height:36px; line-height:1.4;">
                                {amenities}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        btn_txt = "SELECTED ✓" if is_sel else "SELECT & BOOK"
                        if st.button(btn_txt, key=f"btn_book_acc_{idx}_{h.get('id', idx)}", use_container_width=True):
                            st.session_state.selected_accommodation = h
                            st.session_state.selected_hotel = h
                            _sync_state_to_cache()
                            st.rerun()

        # --- Step 4: Sightseeing Choice (All destinations available) ---
        elif (
            st.session_state.selected_option
            and st.session_state.hotel_decision is not None
            and st.session_state.sightseeing_decision is None
        ):
            st.markdown("### 🌄 Step 4: Add Sightseeing Places Across Jammu & Kashmir")
            st.caption("Select destinations to visit around Katra and J&K during your pilgrimage. All available destinations from the tourism dataset are accessible below.")

            places = coordinator.get_sightseeing_places()
            # Ensure unique by name
            seen_p = set()
            unique_places = []
            for p in places:
                if p["name"] not in seen_p:
                    seen_p.add(p["name"])
                    unique_places.append(p)

            # Search & Filter bar
            f1, f2 = st.columns([3, 2])
            with f1:
                sg_search = st.text_input("🔍 Search Sightseeing Destinations", placeholder="Search by name, cave, temple, lake, fort, hill station...", key="sg_all_search")
            with f2:
                region_opts = ["All Destinations", "Katra Trek & Shrines", "Jammu City & Heritage", "Hill Stations & Nature", "Kashmir Valley"]
                sg_region_filter = st.selectbox("Category Filter", region_opts, key="sg_all_region_filter")

            # Filter places based on search and region
            filtered_places = unique_places
            if sg_search:
                filtered_places = [
                    p for p in filtered_places
                    if sg_search.lower() in p["name"].lower()
                    or sg_search.lower() in p.get("category", "").lower()
                    or sg_search.lower() in p.get("description", "").lower()
                ]

            if sg_region_filter == "Katra Trek & Shrines":
                filtered_places = [p for p in filtered_places if p.get("category") in ("On the trek route", "Nearby temple", "Pilgrimage Base")]
            elif sg_region_filter == "Jammu City & Heritage":
                filtered_places = [p for p in filtered_places if p.get("region") == "Jammu" or p.get("category") in ("Jammu city", "Nature / heritage")]
            elif sg_region_filter == "Hill Stations & Nature":
                filtered_places = [p for p in filtered_places if p.get("category") in ("Hill station", "Hill station / adventure", "Nature")]
            elif sg_region_filter == "Kashmir Valley":
                filtered_places = [p for p in filtered_places if p.get("region") == "Kashmir" or p.get("category") == "Kashmir"]

            # Retain any previously picked items in session_state
            if "_picked_sightseeing_set" not in st.session_state:
                st.session_state._picked_sightseeing_set = set(st.session_state.get("sightseeing_decision") or [])

            st.markdown(f"**Showing {len(filtered_places)} of {len(unique_places)} available sightseeing destinations:**")

            # Multi-selection checkboxes in 3 columns
            sg_cols = st.columns(3)
            for idx, p in enumerate(filtered_places):
                p_name = p["name"]
                init_val = p_name in st.session_state._picked_sightseeing_set
                with sg_cols[idx % 3]:
                    with st.container(border=True):
                        chk_val = st.checkbox(
                            f"**{p_name}**",
                            value=init_val,
                            key=f"sg_all_chk_{p_name}",
                            help=p.get("description", ""),
                        )
                        if chk_val:
                            st.session_state._picked_sightseeing_set.add(p_name)
                        else:
                            st.session_state._picked_sightseeing_set.discard(p_name)

                        st.caption(f"{p.get('category', 'Attraction')} · {p.get('distance', 'Nearby')}")
                        desc_snip = p.get("description", "")
                        if len(desc_snip) > 100:
                            desc_snip = desc_snip[:97] + "..."
                        st.write(desc_snip)

            picked_list = list(st.session_state._picked_sightseeing_set)
            st.write("")
            st.markdown(
                f"""
                <div style="background:#FFF9F0; border:1px solid #E5D2AD; border-radius:10px; padding:10px 16px; margin-bottom:14px; font-size:0.9rem; color:#4A2E18;">
                    <b>Selected Places ({len(picked_list)}):</b> {', '.join(picked_list) if picked_list else 'None selected (Holy Yatra direct darshan)'}
                </div>
                """,
                unsafe_allow_html=True,
            )

            col_sg_go, col_sg_back = st.columns([3, 1.2])
            with col_sg_go:
                if st.button(f"Proceed to Timeline Itinerary ({len(picked_list)} places) →", key="confirm_sg", use_container_width=True):
                    st.session_state.sightseeing_decision = picked_list
                    _sync_state_to_cache()
                    st.rerun()
            with col_sg_back:
                if st.button("← Back to Accommodation", key="back_to_hotel_btn", use_container_width=True):
                    st.session_state.hotel_decision = None
                    _sync_state_to_cache()
                    st.rerun()

        # --- Step 5: Day-Wise Timeline Itinerary ---
        elif (
            st.session_state.selected_option
            and st.session_state.hotel_decision is not None
            and st.session_state.sightseeing_decision is not None
            and not st.session_state.itinerary_confirmed
        ):
            bundle = st.session_state.selected_option
            pax, opt = bundle["pax"], bundle["option"]
            itinerary = coordinator.build_final_itinerary(
                opt,
                hotel=st.session_state.selected_hotel,
                hotel_nights=2,
                sightseeing_places=st.session_state.sightseeing_decision,
                request=st.session_state.get("trip_request"),
            )
            st.markdown("### Customized Day-Wise Itinerary")
            for day in itinerary:
                with st.container(border=True):
                    st.markdown(f"**DAY {day['day_number']:02d}** · {day['date']} — **{day['title']}**")
                    for act in day["activities"]:
                        st.write(f"- {act}")
            c_itin_fwd, c_itin_bck = st.columns([3, 1.2])
            with c_itin_fwd:
                if st.button("Proceed to Review & Booking Authorization →", key="conf_itin_btn", use_container_width=True):
                    st.session_state.itinerary_confirmed = True
                    _sync_state_to_cache()
                    st.rerun()
            with c_itin_bck:
                if st.button("← Back to Sightseeing", key="back_to_sg_btn", use_container_width=True):
                    st.session_state.sightseeing_decision = None
                    _sync_state_to_cache()
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
                if tr.get("mode") == "flight":
                    st.write(f"**Transport:** {tr['origin']} → Jammu Airport via {tr.get('operator', '-')} ({tr.get('transport_no', '-')}) + Road Transfer to Katra ({tr.get('transfer_mode', 'Taxi / Bus')})")
                else:
                    st.write(f"**Transport:** {tr['origin']} → {tr['destination']} via {tr.get('operator', '-')}")
                st.write(f"**Yatra Slot:** {s['category']} on {s['slot_date']}")
                st.write(f"**Pilgrims:** {pax}")
                if st.session_state.selected_hotel:
                    st.write(f"**Hotel Stay:** {st.session_state.selected_hotel.get('name')} ({st.session_state.selected_hotel.get('category')}) — ₹{st.session_state.selected_hotel.get('price_per_night')}/night")
                if st.session_state.sightseeing_decision:
                    st.write(f"**Sightseeing Destinations:** {', '.join(st.session_state.sightseeing_decision)}")
                st.write(f"**Total Price:** ₹{grand_total}")

            if st.button("← Back to Itinerary", key="back_to_itin_btn"):
                st.session_state.itinerary_confirmed = False
                _sync_state_to_cache()
                st.rerun()

            st.markdown("#### Human Authorization Gate")
            rpa_auth = st.checkbox("I confirm details & authorize AI RPA agent to execute booking", value=True, key="rpa_chk")
            run_rpa = st.checkbox("Run Playwright RPA visual automation demonstration", value=True, key="run_rpa_chk")

            paid = payment.render_payment_form("Total mock payment amount:", grand_total)
            if paid:
                if not rpa_auth:
                    st.error("Human authorization required. Please check the authorization box above.")
                else:
                    rpa_info = None
                    trans_label = f"{tr['origin']} → Jammu Airport + Road Transfer to Katra" if tr.get("mode") == "flight" else f"{tr['origin']} → Katra"
                    if run_rpa:
                        with st.spinner("Playwright RPA Agent executing mock booking..."):
                            rpa_info = coordinator.execute_rpa_demo(
                                user_name=st.session_state.guest_id,
                                pax_count=pax,
                                transport_text=trans_label,
                                slot_text=s["category"],
                                total_price=grand_total,
                                headless=True,
                            )
                    booking_id, blessing = coordinator.confirm_booking(
                        opt, pax, st.session_state.guest_id, hotel=st.session_state.selected_hotel, hotel_nights=2, sightseeing_places=st.session_state.sightseeing_decision
                    )
                    st.balloons()
                    st.success(f"{blessing}\n\nConfirmation Ref: **{booking_id}**")
                    st.session_state._last_confirmed_booking_id = booking_id
                    st.session_state.pending_options = None
                    st.session_state.selected_option = None
                    _sync_state_to_cache()

        elif st.session_state.trip_request and not st.session_state.selected_option and not st.session_state.pending_options:
            req = st.session_state.trip_request
            supported_hubs = db.get_distinct_origins()
            st.markdown(
                f"""
                <div style="background:#FFF9F2; border:1.5px solid #E5D2AD; border-radius:14px; padding:18px 22px; margin-bottom:18px;">
                    <div style="font-family:'Cinzel',serif; font-weight:800; color:var(--burgundy); font-size:1.05rem; margin-bottom:8px;">
                        ℹ️ No Direct Matching Combinations for Selected Date & Route
                    </div>
                    <div style="font-size:0.92rem; color:var(--text-dark); line-height:1.6;">
                        We could not find matching verified transport and darshan slots for <b>{req.get('origin', 'your city')}</b> on <b>{req.get('start_date', 'selected date')}</b> ({str(req.get('mode', 'transport')).title()}).
                        <br/><br/>
                        <b>How to proceed:</b>
                        <br/>• Try searching a different date in the chat box below (e.g., <i>"check from {req.get('origin', 'Delhi')} for next week"</i>).
                        <br/>• Try another mode of transport (e.g., <i>"check flight options from {req.get('origin', 'Delhi')}"</i> or <i>"check buses"</i>).
                        <br/>• Supported prototype hubs with daily direct connectivity: <b>{', '.join(supported_hubs)}</b>.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Chat Input Box
    st.write("")
    render_voice_input("darshan_chat_voice")
    if prompt := st.chat_input("Ask Yatra AI — e.g., '4 people from Bhopal next week by train for VIP darshan'"):
        _process_trip_input(prompt)


# =====================================================================
# VIEW 3: YATRA GUIDE & ESSENTIALS
# =====================================================================
elif st.session_state.active_nav == "Yatra Guide":
    st.markdown("### 📖 Complete Vaishno Devi Yatra Guide & Pilgrim Essentials")
    st.caption("Essential information, Aarti schedules, registration rules, routes, packing advice, and emergency helplines.")

    g_col1, g_col2 = st.columns(2)
    with g_col1:
        with st.container(border=True):
            st.markdown("#### 🔱 Aarti Timings & Darshan Windows")
            aarti = yatra_info.get_aarti_timings()
            st.write(f"**Morning Aarti:** {aarti['morning']['start']} – {aarti['morning']['end']}")
            st.write(f"**Evening Aarti (Summer):** {aarti['evening_summer']['start']} – {aarti['evening_summer']['end']}")
            st.write(f"**Evening Aarti (Winter):** {aarti['evening_winter']['start']} – {aarti['evening_winter']['end']}")
            st.caption("Note: Darshan line movement pauses briefly during holy Aarti rituals.")

        with st.container(border=True):
            st.markdown("#### 🪪 Mandatory RFID Yatra Registration")
            reg = yatra_info.get_registration_info()
            st.write(f"**Cost:** {reg['cost']} (Mandatory for all pilgrims)")
            st.write(reg["mandatory_note"])
            st.markdown("**Counters:** Katra Railway Station, Bus Stand, Chowk, and Online Shrine Board Portal.")

    with g_col2:
        with st.container(border=True):
            st.markdown("#### 🚶‍♂️ Trek Route Options to Bhawan")
            for route in yatra_info.get_route_options():
                st.markdown(f"**{route['name']}** ({route['distance']}) — {route['duration']}")

        with st.container(border=True):
            st.markdown("#### 🎒 Clothing & Packing Guidance")
            packing = yatra_info.get_packing_guidance()
            st.write("**Recommended:**", ", ".join(packing["recommended"]))
            st.write("**Restricted Items:**", ", ".join(packing["commonly_restricted"]))

    st.markdown("#### 📞 Official Helpline & Emergency Cells")
    st.info("Shri Mata Vaishno Devi Shrine Board Helpline: **01991-232820** · Emergency Cell: **1800-180-7777**")


# =====================================================================
# VIEW 4: PACKAGES (CURATED TRIP OPTIONS)
# =====================================================================
elif st.session_state.active_nav == "Packages":
    st.markdown("### 🎁 Curated Yatra Packages & Pilgrimage Tours")
    st.caption("Pre-planned AI-curated itineraries generated from authentic transport and slot inventory.")

    packages = [
        {
            "title": "Vaishno Devi Express Darshan Yatra",
            "duration": "3 Days / 2 Nights",
            "cities": "Delhi / Jammu → Katra → Bhawan",
            "price": "₹2,450 – ₹4,200 per person",
            "highlights": "Direct express transport, reserved Yatra slot, Ban Ganga rest points, Bhairavnath Temple visit.",
            "query": "2 people from Delhi by train for 3 days VIP darshan",
        },
        {
            "title": "Vaishno Devi + Patnitop Hill Station Retreat",
            "duration": "5 Days / 4 Nights",
            "cities": "Bhopal / Delhi → Katra → Patnitop",
            "price": "₹5,200 – ₹8,500 per person",
            "highlights": "Holy Bhawan Darshan followed by 2 days in Himalayan pine meadows of Patnitop & Nathatop.",
            "query": "2 people from Bhopal for 5 days VIP darshan with Patnitop",
        },
        {
            "title": "Vaishno Devi + Shiv Khori Cave Expedition",
            "duration": "4 Days / 3 Nights",
            "cities": "Jaipur / Lucknow → Katra → Ransoo",
            "price": "₹3,800 – ₹6,100 per person",
            "highlights": "Sacred Bhawan Darshan plus excursion to Shiv Khori limestone cave and Baba Dhansar waterfall.",
            "query": "2 people from Jaipur for 4 days VIP darshan with Shiv Khori",
        },
        {
            "title": "Vaishno Devi + Grand Kashmir Valley Discovery",
            "duration": "7 Days / 6 Nights",
            "cities": "Mumbai / Pune → Katra → Srinagar → Gulmarg",
            "price": "₹12,500 – ₹18,900 per person",
            "highlights": "Complete Yatra Darshan combined with Srinagar Dal Lake Shikara ride and Gulmarg snow gondola.",
            "query": "2 people from Mumbai for 7 days VIP darshan with Kashmir",
        },
    ]

    pkg_cols = st.columns(2)
    for p_idx, pkg in enumerate(packages):
        with pkg_cols[p_idx % 2]:
            with st.container(border=True):
                st.markdown(f"#### {pkg['title']}")
                st.markdown(f"**Duration:** {pkg['duration']} · **Route:** {pkg['cities']}")
                st.markdown(f"**Est. Price:** {pkg['price']}")
                st.write(pkg["highlights"])
                if st.button(f"Book / Plan {pkg['title']} →", key=f"pkg_btn_{p_idx}", use_container_width=True):
                    st.session_state.trip_request = None
                    st.session_state.pending_options = None
                    st.session_state.selected_option = None
                    st.session_state.hotel_decision = None
                    st.session_state.sightseeing_decision = None
                    st.session_state.itinerary_confirmed = False
                    _sync_state_to_cache()
                    set_active_nav("Darshan Bookings")
                    _process_trip_input(pkg["query"])


# =====================================================================
# VIEW 5: HOTELS & ACCOMMODATION
# =====================================================================
elif st.session_state.active_nav == "Hotels":
    st.markdown("### 🏨 Hotels & Pilgrimage Stays in Katra & J&K")
    st.caption("Browse verified accommodations from the project dataset with real-time room availability.")

    h_col1, h_col2, h_col3 = st.columns([3, 3, 3])
    with h_col1:
        hotel_loc = st.selectbox("Search Location", ["Katra", "Jammu", "Srinagar", "Gulmarg", "Patnitop"], index=0, key="hotel_loc_sel")
    with h_col2:
        hotel_cat = st.selectbox("Category Filter", ["All Categories", "Budget", "Mid-Range", "Premium"], index=0, key="hotel_cat_sel")
    with h_col3:
        today_iso = datetime.now().date().isoformat()
        checkin_date = st.date_input("Check-in Date", value=datetime.now().date() + timedelta(days=7), key="hotel_date_in")

    selected_cat = None if hotel_cat == "All Categories" else hotel_cat
    hotels_list = db.search_hotels(today_iso, category=selected_cat)

    if hotels_list:
        st.markdown(f"**Showing {len(hotels_list)} available property options:**")
        hotel_cols = st.columns(3)
        for idx, h in enumerate(hotels_list[:9]):
            with hotel_cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"**{h['name']}**")
                    st.caption(f"{h['category']} · Katra Region")
                    st.markdown(f"**Price:** ₹{h['price_per_night']} / night")
                    st.write(f"🛏️ Rooms Available: **{h['rooms_available']}**")
                    if st.button(f"Select {h['name']}", key=f"sel_h_{idx}", use_container_width=True):
                        st.session_state.selected_hotel = h
                        _sync_state_to_cache()
                        st.success(f"Selected {h['name']} for your trip package!")
    else:
        st.info("No hotels matching criteria found. Default Katra properties available.")


# =====================================================================
# VIEW 6: TRANSPORT & ROUTE PLANNING
# =====================================================================
elif st.session_state.active_nav == "Transport":
    st.markdown("### 🚆 Transport & Route Planning Search")
    st.caption("Search direct trains, flights, and buses, or connecting hub options (e.g. Bhopal → Delhi → Katra).")

    t_col1, t_col2, t_col3 = st.columns(3)
    with t_col1:
        t_origin = st.selectbox("Origin City", db.get_distinct_origins(), index=0, key="trans_orig_sel")
    with t_col2:
        t_mode = st.selectbox("Travel Mode", ["Train", "Flight", "Bus"], index=0, key="trans_mode_sel")
    with t_col3:
        t_date = st.date_input("Travel Date", value=datetime.now().date() + timedelta(days=7), key="trans_date_sel")

    if st.button("SEARCH TRANSPORT AVAILABILITY →", key="btn_search_trans", use_container_width=True):
        date_str = t_date.strftime("%d %b %Y")
        query_text = f"2 people from {t_origin} by {t_mode.lower()} on {date_str} for VIP darshan"
        st.session_state.trip_request = None
        st.session_state.pending_options = None
        st.session_state.selected_option = None
        st.session_state.hotel_decision = None
        st.session_state.sightseeing_decision = None
        st.session_state.itinerary_confirmed = False
        _sync_state_to_cache()
        set_active_nav("Darshan Bookings")
        _process_trip_input(query_text)


# =====================================================================
# VIEW 7: HELP & FAQ
# =====================================================================
elif st.session_state.active_nav == "Help":
    st.markdown("### ❓ Pilgrim Help & Frequently Asked Questions")
    st.caption("Everything you need to know about planning your yatra, darshan rules, transport, and AI features.")

    with st.expander("How does the AI Yatra Assistant plan my trip?"):
        st.write("Our AI system coordinates multiple specialized agents (Transport, Slot Recommendation, Day-by-Day Itinerary, Weather, and Tourism Knowledge) to assemble a complete personalized itinerary.")

    with st.expander("How do connecting routes work for cities like Bhopal, Surat, or Kochi?"):
        st.write("If direct transport to Katra is not available on your travel date, our engine automatically constructs a connecting itinerary via major transit hubs (e.g. Delhi, Mumbai, or Ahmedabad) using verified dataset inventory.")

    with st.expander("What is the Human Authorization Gate for bookings?"):
        st.write("Before any booking is confirmed or executed by the Playwright RPA automation agent, you must explicitly check the authorization gate box to grant permission.")

    with st.expander("How do I use voice search in my native language?"):
        st.write("Click the '🎤 Speak Your Query' button next to any chat input box. You can select English, Hindi, Punjabi, or Urdu to speak your query directly.")


# =====================================================================
# VIEW 8: CONVERSATIONAL AI ASSISTANT
# =====================================================================
elif st.session_state.active_nav == "AI Assistant":
    st.markdown("### 🔱 Vaishno Devi AI Assistant")
    st.caption("Ask any question about yatra planning, transport, weather, darshan, or itinerary updates.")

    for i, msg in enumerate(st.session_state.messages):
        if msg["role"] == "user":
            st.markdown(
                f'<div style="background:#F5ECDA; border:1px solid #E5D2AD; padding:12px 18px; border-radius:14px; margin-bottom:12px; max-width:82%; margin-left:auto;"><b>You:</b> {msg["content"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            render_assistant_chat_message(msg, i, key_prefix="ai_tab")

    st.write("")
    render_voice_input("ai_tab_voice")
    if prompt := st.chat_input("Ask Yatra AI — e.g., 'What is the weather in Katra next week?'"):
        _process_trip_input(prompt)


# =====================================================================
# VIEW 9: MY ACCOUNT & BOOKING HISTORY
# =====================================================================
elif st.session_state.active_nav == "My Account":
    st.markdown("### 👤 Guest Session & Booking History")
    st.write(f"**Session Identity:** `{st.session_state.guest_id}`")

    if st.session_state.selected_hotel:
        st.info(f"Selected Hotel Stay: **{st.session_state.selected_hotel.get('name')}** ({st.session_state.selected_hotel.get('category')}) — ₹{st.session_state.selected_hotel.get('price_per_night')}/night")

    bookings = db.list_bookings(user_name=st.session_state.guest_id)
    if bookings:
        st.markdown("#### Your Confirmed Bookings")
        for b in bookings:
            with st.container(border=True):
                st.markdown(f"**Booking Ref:** `{b['booking_id']}` · Status: **{b['status']}**")
                st.write(f"**Transport:** {b.get('origin')} → {b.get('destination')} via {b.get('transport_operator')} ({b.get('transport_no')})")
                st.write(f"**Yatra Slot:** {b.get('category')} on {b.get('slot_date')} at {fmt_time(b.get('slot_time'))}")
                if b.get("hotel_name"):
                    st.write(f"**Hotel:** {b.get('hotel_name')} ({b.get('hotel_category')})")
                st.write(f"**Pilgrims:** {b.get('pax_count')} · **Total Paid:** ₹{b.get('total_price')}")
    else:
        st.info("No bookings confirmed yet in this session. Start a trip search to book your yatra!")


# --- FLOATING SIDEBAR AI WIDGET ---
with st.sidebar:
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #58111A 0%, #3D0810 100%); padding: 14px 18px; border-radius: 14px; color: #FFFFFF; border: 1px solid #B8860B; margin-bottom: 14px;">
            <div style="font-family:'Cinzel',serif; font-weight:800; font-size:1.05rem; display:flex; align-items:center; gap:8px;">
                <span>🔱</span> VAISHNO DEVI AI
            </div>
            <div style="font-size:0.75rem; color:#E5D2AD; margin-top:2px;">AI | Online Companion</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Active Session: **" + st.session_state.guest_id + "**")
    bookings = db.list_bookings(user_name=st.session_state.guest_id)
    if bookings:
        st.markdown("**Your Bookings:**")
        for b in bookings:
            st.write(f"- `{b['booking_id']}` · {b['status']} · ₹{b['total_price']}")
        st.divider()

    st.markdown("#### 🔱 AI Companion Launcher")
    st.caption("The primary AI Companion is integrated directly on the Home page.")
    if st.button("💬 Open AI Assistant Page", key="side_to_ai_page", use_container_width=True):
        set_active_nav("AI Assistant")
        st.rerun()
    if st.button("🏠 View Home AI Companion", key="side_to_home_ai", use_container_width=True):
        set_active_nav("Home")
        st.rerun()

    st.divider()
    st.caption(f"Engine: {'GPT-OSS Active' if API_KEY else 'Rule-Based System'}")


# --- LUXURY FOOTER ---
st.markdown(
    """
    <div class="luxury-footer">
        <div style="font-family:'Cinzel',serif; font-weight:800; font-size:1.2rem; color:#58111A; margin-bottom:6px;">
            🔱 VAISHNO DEVI YATRA AI
        </div>
        <div>Divine Journeys, Powered by AI · Jammu & Kashmir Tourism Companion</div>
        <div style="margin-top:10px; font-weight:700; color:#3D0810;">
            Official Shrine Board Helpline: 01991-232820 · Emergency Cell: 1800-180-7777
        </div>
        <div style="margin-top:8px; font-size:0.8rem; color:#807070;">
            © 2026 Vaishno Devi Yatra AI Project. Designed for seamless pilgrimage booking and discovery.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Sync latest state to server-side cache for current guest
_sync_state_to_cache()

