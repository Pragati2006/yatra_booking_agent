import React, { useState, useRef, useEffect } from 'react';
import { sendChat, getChatHistory } from '../services/api';

const DEFAULT_GREETING = {
  id: 'default-greeting',
  role: 'assistant',
  content: '🙏 **Jai Mata Di!** Welcome to the Maa Vaishno Devi Pilgrim Companion. How may I assist you with your sacred yatra planning, travel routes, weather, or tourist destinations across Katra and Jammu?',
  created_at: null,
};

const createLocalMessageId = () => `local-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
const getNowIsoString = () => new Date().toISOString();

export default function AIChat({ 
  onNavigateToBooking, 
  initialMessage = null, 
  compact = false,
  onExplorePlace = null,
  sharedTripRequest = null,
  sharedSessionId = null,
  sharedPlanVersion = 1,
  onTripUpdated = null,
  onSwitchToForm = null,
}) {
  const [messages, setMessages] = useState(() => {
    try {
      const targetSessionId = sharedSessionId || sessionStorage.getItem('yatra_session_id');
      const savedMsgSessionId = sessionStorage.getItem('yatra_chat_messages_session_id');
      if (targetSessionId && savedMsgSessionId && targetSessionId !== savedMsgSessionId) {
        return [DEFAULT_GREETING];
      }
      const saved = sessionStorage.getItem('yatra_chat_messages');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed.map((m) => ({ ...m, isPending: false }));
        }
      }
    } catch {
      // ignore
    }
    return [DEFAULT_GREETING];
  });
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [historyError, setHistoryError] = useState(false);
  const [historyRetryCount, setHistoryRetryCount] = useState(0);
  const [micState, setMicState] = useState('idle'); // 'idle' | 'listening' | 'processing'
  const [micStatus, setMicStatus] = useState('');
  const [selectedLang, setSelectedLang] = useState('en-IN');
  const [chatState, setChatState] = useState(() => {
    try {
      const saved = sessionStorage.getItem('yatra_chat_state');
      if (saved) return JSON.parse(saved);
    } catch {
      // ignore
    }
    return {
      session_id: sharedSessionId || sessionStorage.getItem('yatra_session_id') || null,
      plan_version: sharedPlanVersion || parseInt(sessionStorage.getItem('yatra_plan_version') || '1', 10),
      current_request: sharedTripRequest || null,
      current_itinerary: null,
      feasible_places: [],
      infeasible_places: [],
      last_tourism_place: null,
      last_itinerary_context: null,
      pending_options: null,
    };
  });

  const [prevSharedProps, setPrevSharedProps] = useState({
    planVersion: sharedPlanVersion,
    tripRequest: sharedTripRequest,
  });

  if (
    sharedPlanVersion !== prevSharedProps.planVersion ||
    sharedTripRequest !== prevSharedProps.tripRequest
  ) {
    setPrevSharedProps({
      planVersion: sharedPlanVersion,
      tripRequest: sharedTripRequest,
    });
    setChatState((prev) => ({
      ...prev,
      plan_version: sharedPlanVersion || prev.plan_version,
      current_request: sharedTripRequest ? { ...(prev.current_request || {}), ...sharedTripRequest } : prev.current_request,
    }));
  }

  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isExpanded) {
        setIsExpanded(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isExpanded]);

  const escapeHtml = (str) => {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  };

  const formatInline = (text) => {
    return text
      .replace(/`([^`]+)`/g, '<code style="background: rgba(184, 134, 11, 0.1); padding: 2px 5px; border-radius: 4px; font-family: monospace; font-size: 0.88em; color: var(--burgundy);">$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong style="color: var(--burgundy); font-weight: 700;">$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/_([^_]+)_/g, '<em>$1</em>');
  };

  const formatMarkdown = (rawText) => {
    if (!rawText) return '';
    const safeText = escapeHtml(rawText);
    const lines = safeText.split('\n');

    let html = '';
    let inUl = false;
    let inOl = false;

    const closeLists = () => {
      if (inUl) {
        html += '</ul>';
        inUl = false;
      }
      if (inOl) {
        html += '</ol>';
        inOl = false;
      }
    };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();

      if (!trimmed) {
        closeLists();
        continue;
      }

      // Horizontal dividers: --- or ***
      if (/^---+$/.test(trimmed) || /^\*\*\*+$/.test(trimmed)) {
        closeLists();
        html += '<hr style="border: none; border-top: 1px solid var(--gold-border); margin: 12px 0;" />';
        continue;
      }

      // Headings: ###, ##, #
      const h3Match = trimmed.match(/^###\s+(.*)$/);
      if (h3Match) {
        closeLists();
        html += `<h4 style="font-family: var(--font-serif); font-size: 0.98rem; font-weight: 800; color: var(--burgundy); margin: 10px 0 4px;">${formatInline(h3Match[1])}</h4>`;
        continue;
      }

      const h2Match = trimmed.match(/^##\s+(.*)$/);
      if (h2Match) {
        closeLists();
        html += `<h3 style="font-family: var(--font-serif); font-size: 1.08rem; font-weight: 800; color: var(--burgundy); margin: 12px 0 6px;">${formatInline(h2Match[1])}</h3>`;
        continue;
      }

      const h1Match = trimmed.match(/^#\s+(.*)$/);
      if (h1Match) {
        closeLists();
        html += `<h2 style="font-family: var(--font-serif); font-size: 1.16rem; font-weight: 800; color: var(--burgundy); margin: 14px 0 6px;">${formatInline(h1Match[1])}</h2>`;
        continue;
      }

      // Unordered list item: •, -, or *
      const ulMatch = trimmed.match(/^[•\-*]\s+(.*)$/);
      if (ulMatch) {
        if (inOl) {
          html += '</ol>';
          inOl = false;
        }
        if (!inUl) {
          html += '<ul style="margin: 4px 0 6px 1.25rem; padding-left: 0; list-style-type: disc;">';
          inUl = true;
        }
        html += `<li style="margin-bottom: 3px; line-height: 1.45;">${formatInline(ulMatch[1])}</li>`;
        continue;
      }

      // Ordered list item: 1. 2. etc.
      const olMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
      if (olMatch) {
        if (inUl) {
          html += '</ul>';
          inUl = false;
        }
        if (!inOl) {
          html += '<ol style="margin: 4px 0 6px 1.25rem; padding-left: 0;">';
          inOl = true;
        }
        html += `<li style="margin-bottom: 3px; line-height: 1.45;">${formatInline(olMatch[2])}</li>`;
        continue;
      }

      // Normal paragraph
      closeLists();
      html += `<p style="margin: 0 0 6px 0; line-height: 1.55;">${formatInline(trimmed)}</p>`;
    }

    closeLists();
    return html;
  };

  const messagesEndRef = useRef(null);
  const latestMessageRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const textareaRef = useRef(null);
  const isSubmittingRef = useRef(false);
  const recognitionRef = useRef(null);
  const historyLoadedSessionRef = useRef(null);
  const currentSessionIdRef = useRef(sharedSessionId || sessionStorage.getItem('yatra_session_id') || null);
  const activeFetchRequestIdRef = useRef(0);
  const isFetchingHistoryRef = useRef(false);
  const pendingMessageIdsRef = useRef(new Set());
  const isNearBottomRef = useRef(true);

  const handleMessagesScroll = () => {
    const el = messagesContainerRef.current;
    if (el) {
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      isNearBottomRef.current = distanceFromBottom < 80;
    }
  };

  // Synchronize active session prop changes & prevent stale transcript retention across session boundaries
  useEffect(() => {
    if (sharedSessionId && sharedSessionId !== currentSessionIdRef.current) {
      currentSessionIdRef.current = sharedSessionId;
      historyLoadedSessionRef.current = null;
      isFetchingHistoryRef.current = false;
      pendingMessageIdsRef.current.clear();
      setHistoryError(false);
      activeFetchRequestIdRef.current += 1;

      // Immediately clear prior session transcript to avoid cross-session contamination
      setMessages([DEFAULT_GREETING]);
      setChatState((prev) => ({
        ...prev,
        session_id: sharedSessionId,
        plan_version: sharedPlanVersion || 1,
        current_request: sharedTripRequest ? { ...(prev.current_request || {}), ...sharedTripRequest } : null,
        current_itinerary: null,
        feasible_places: [],
        infeasible_places: [],
        pending_options: null,
      }));
    }
  }, [sharedSessionId, sharedPlanVersion, sharedTripRequest]);

  // Robust session-aware history restoration
  useEffect(() => {
    const targetSessionId = sharedSessionId || chatState.session_id;
    if (!targetSessionId) return;
    if (historyLoadedSessionRef.current === targetSessionId) return;
    if (isFetchingHistoryRef.current) return;

    currentSessionIdRef.current = targetSessionId;
    isFetchingHistoryRef.current = true;
    const fetchId = ++activeFetchRequestIdRef.current;

    getChatHistory(targetSessionId)
      .then((res) => {
        isFetchingHistoryRef.current = false;
        // Guard against stale responses or unmounted/switched sessions
        if (activeFetchRequestIdRef.current !== fetchId) return;
        if (currentSessionIdRef.current !== targetSessionId) return;

        historyLoadedSessionRef.current = targetSessionId;
        setHistoryError(false);

        if (!res || !Array.isArray(res.messages)) {
          return;
        }

        const backendMsgs = res.messages;

        setMessages((prev) => {
          // If backend has no messages (new session or genuinely empty):
          if (backendMsgs.length === 0) {
            const isGreetingOnly = prev.length === 1 && prev[0].id === 'default-greeting';
            if (prev.length === 0 || isGreetingOnly) {
              return [DEFAULT_GREETING];
            }
            return prev;
          }

          // Format backend messages using their own stable IDs and metadata
          const formattedBackend = backendMsgs.map((m) => {
            const meta = m.metadata || {};
            return {
              id: m.id,
              role: m.role,
              content: m.content,
              recommendation: meta.recommendation || null,
              plan: meta.plan || null,
              request: meta.request || null,
              itinerary: meta.itinerary || meta.plan?.itinerary || null,
              feasible_places: meta.feasible_places || [],
              infeasible_places: meta.infeasible_places || [],
              created_at: m.created_at,
              persisted: true,
              isPending: false,
            };
          });

          // Hydrate preserved chatState from latest historical plan/request
          const latestPlanMsg = [...backendMsgs].reverse().find((m) => m.metadata && (m.metadata.plan || m.metadata.itinerary || m.metadata.request));
          if (latestPlanMsg && latestPlanMsg.metadata) {
            const lMeta = latestPlanMsg.metadata;
            setChatState((prev) => ({
              ...prev,
              session_id: targetSessionId,
              plan_version: lMeta.plan_version || prev.plan_version || 1,
              current_request: lMeta.request || prev.current_request,
              current_itinerary: lMeta.itinerary || lMeta.plan?.itinerary || prev.current_itinerary,
              feasible_places: lMeta.feasible_places || prev.feasible_places,
              infeasible_places: lMeta.infeasible_places || prev.infeasible_places,
              pending_options: lMeta.plan?.options || prev.pending_options,
              selected_option: lMeta.plan?.selected_option || prev.selected_option,
              hotel: lMeta.plan?.hotel || prev.hotel,
              budget_evaluation: lMeta.budget_evaluation || lMeta.plan?.budget_evaluation || prev.budget_evaluation,
            }));
          }

          // Check if user sent genuinely in-flight messages during history fetch
          // Only messages added during the current component lifecycle that are still pending
          const localPending = prev.filter(
            (p) => Boolean(p.isPending) && pendingMessageIdsRef.current.has(p.id)
          );

          if (localPending.length === 0) {
            return formattedBackend;
          }

          // Preserve the pending local messages at the end so they are not wiped out
          return [...formattedBackend, ...localPending];
        });
      })
      .catch((err) => {
        isFetchingHistoryRef.current = false;
        if (activeFetchRequestIdRef.current !== fetchId) return;
        if (currentSessionIdRef.current !== targetSessionId) return;
        console.warn('Failed to fetch chat history:', err);
        setHistoryError(true);
        // Do NOT mark historyLoadedSessionRef.current = targetSessionId on failure,
        // allowing deliberate retries.
      });

    return () => {
      isFetchingHistoryRef.current = false;
      if (activeFetchRequestIdRef.current === fetchId) {
        activeFetchRequestIdRef.current += 1;
      }
    };
  }, [sharedSessionId, chatState.session_id, historyRetryCount]);

  const handleRetryHistory = () => {
    setHistoryError(false);
    historyLoadedSessionRef.current = null;
    isFetchingHistoryRef.current = false;
    setHistoryRetryCount((c) => c + 1);
  };

  useEffect(() => {
    if (loading) {
      if (isNearBottomRef.current) {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }
      return;
    }

    if (messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      const isUser = lastMsg && lastMsg.role === 'user';
      if (isUser) {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      } else if (isNearBottomRef.current) {
        // Bring top of newly arrived assistant message comfortably into view
        latestMessageRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  }, [messages, loading]);

  const handleSend = async (textToSend) => {
    if (isSubmittingRef.current) return;
    const text = (textToSend || inputValue).trim();
    if (!text || loading) return;

    isSubmittingRef.current = true;
    setInputValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = '40px';
    }

    const userMsg = {
      id: createLocalMessageId(),
      role: 'user',
      content: text,
      created_at: getNowIsoString(),
      persisted: false,
      isPending: true,
    };
    pendingMessageIdsRef.current.add(userMsg.id);
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const data = await sendChat({
        message: text,
        session_id: chatState.session_id,
        current_request: chatState.current_request,
        current_itinerary: chatState.current_itinerary,
        last_tourism_place: chatState.last_tourism_place,
        last_itinerary_context: chatState.last_itinerary_context,
        pending_options: chatState.pending_options,
      });

      const feasiblePlaces = data.feasible_places || data.plan?.feasible_places || [];
      const infeasiblePlaces = data.infeasible_places || data.plan?.infeasible_places || [];

      const assistantMsg = {
        id: createLocalMessageId(),
        role: 'assistant',
        content: data.reply || '🙏 Jai Mata Di! How else can I assist your pilgrimage?',
        recommendation: data.recommendation || null,
        plan: data.plan || null,
        request: data.request || null,
        feasible_places: feasiblePlaces,
        infeasible_places: infeasiblePlaces,
        created_at: getNowIsoString(),
        persisted: false,
        isPending: false,
      };

      setMessages((prev) => [
        ...prev.map((m) => (m.id === userMsg.id ? { ...m, isPending: false } : m)),
        assistantMsg,
      ]);

      if (data.session_id) {
        historyLoadedSessionRef.current = data.session_id;
        currentSessionIdRef.current = data.session_id;
      }

      // Update preserved context
      setChatState((prev) => ({
        ...prev,
        session_id: data.session_id || prev.session_id,
        plan_version: data.plan_version || prev.plan_version || 1,
        current_request: data.reset === true ? null : ((data.request !== undefined && data.request !== null) ? data.request : prev.current_request),
        current_itinerary: data.reset === true ? null : ((data.itinerary !== undefined && data.itinerary !== null) ? data.itinerary : prev.current_itinerary),
        feasible_places: feasiblePlaces.length > 0 ? feasiblePlaces : prev.feasible_places,
        infeasible_places: infeasiblePlaces.length > 0 ? infeasiblePlaces : (data.plan ? [] : prev.infeasible_places),
        last_tourism_place: data.last_tourism_place || prev.last_tourism_place,
        last_itinerary_context: data.last_itinerary_context || prev.last_itinerary_context,
        pending_options: data.plan?.options ? data.plan.options : prev.pending_options,
        selected_option: data.plan?.selected_option || (data.plan?.options && data.plan.options[0]) || prev.selected_option || null,
        hotel: data.plan?.hotel || prev.hotel || null,
        budget_evaluation: data.budget_evaluation || data.plan?.budget_evaluation || prev.budget_evaluation || null,
      }));

      if (onTripUpdated) {
        onTripUpdated({
          request: (data.request !== undefined && data.request !== null) ? data.request : (data.reset === true ? null : chatState.current_request),
          plan: data.plan,
          session_id: data.session_id,
          plan_version: data.plan_version,
          itinerary: data.itinerary || data.plan?.itinerary,
          feasible_places: feasiblePlaces,
          infeasible_places: infeasiblePlaces,
          recommendation: data.recommendation,
          pending_options: data.plan?.options,
        });
      }
    } catch (err) {
      console.error('Chat error:', err);
      const isTimeout = err?.code === 'ECONNABORTED' || (err?.message && err.message.toLowerCase().includes('timeout'));
      const friendlyMessage = isTimeout
        ? '⏱️ **Request Timed Out:** The pilgrimage coordinator took longer than expected to respond. Please check your connection and try again.'
        : '🙏 **Connection Issue:** Unable to reach the pilgrimage service. Please verify the backend is running and try again.';
      setMessages((prev) => [
        ...prev.map((m) => (m.id === userMsg.id ? { ...m, isPending: false } : m)),
        {
          id: createLocalMessageId(),
          role: 'assistant',
          content: friendlyMessage,
          isError: true,
          failedQuery: text,
          created_at: getNowIsoString(),
          isPending: false,
        },
      ]);
    } finally {
      pendingMessageIdsRef.current.delete(userMsg.id);
      isSubmittingRef.current = false;
      setLoading(false);
    }
  };

  const handleSendRef = useRef(handleSend);
  useEffect(() => {
    handleSendRef.current = handleSend;
  });
  const lastInitialMessageRef = useRef(null);

  useEffect(() => {
    if (initialMessage && initialMessage !== lastInitialMessageRef.current) {
      lastInitialMessageRef.current = initialMessage;
      const timer = setTimeout(() => {
        handleSendRef.current?.(initialMessage);
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [initialMessage]);

  useEffect(() => {
    try {
      sessionStorage.setItem('yatra_chat_messages', JSON.stringify(messages));
      const activeSid = sharedSessionId || chatState.session_id;
      if (activeSid) {
        sessionStorage.setItem('yatra_chat_messages_session_id', activeSid);
      }
    } catch {}
  }, [messages, sharedSessionId, chatState.session_id]);

  useEffect(() => {
    try {
      sessionStorage.setItem('yatra_chat_state', JSON.stringify(chatState));
      if (chatState.session_id) {
        sessionStorage.setItem('yatra_session_id', chatState.session_id);
      }
      if (chatState.plan_version) {
        sessionStorage.setItem('yatra_plan_version', String(chatState.plan_version));
      }
    } catch {}
  }, [chatState]);

  // Web Speech API Voice Handler
  const toggleListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      setMicStatus('Voice input not supported in this browser. Please use Chrome, Edge, or Safari.');
      setTimeout(() => setMicStatus(''), 4000);
      return;
    }

    if (micState === 'listening' && recognitionRef.current) {
      recognitionRef.current.stop();
      setMicState('idle');
      setMicStatus('');
      return;
    }

    try {
      const recognition = new SR();
      recognition.lang = selectedLang;
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognitionRef.current = recognition;

      recognition.onstart = () => {
        setMicState('listening');
        setMicStatus('Listening for speech...');
      };

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setMicState('processing');
        setMicStatus(`Heard: "${transcript}"`);
        handleSend(transcript);
        setTimeout(() => {
          setMicState('idle');
          setMicStatus('');
        }, 1200);
      };

      recognition.onerror = (event) => {
        setMicState('idle');
        if (event.error === 'no-speech') {
          setMicStatus("Sorry, I couldn't hear that. Please try again.");
        } else if (event.error === 'not-allowed') {
          setMicStatus('Microphone permission was denied.');
        } else {
          setMicStatus("Sorry, I couldn't understand that. Please try again.");
        }
        setTimeout(() => setMicStatus(''), 4500);
      };

      recognition.onend = () => {
        if (micState === 'listening') {
          setMicState('idle');
        }
      };

      recognition.start();
    } catch (e) {
      console.error('Mic start error:', e);
      setMicState('idle');
      setMicStatus('Microphone could not be started.');
      setTimeout(() => setMicStatus(''), 4000);
    }
  };

  // Text-To-Speech
  const speakText = (text) => {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const clean = text.replace(/<[^>]+>/g, ' ').replace(/[*#_`]/g, '');
    const utter = new SpeechSynthesisUtterance(clean);
    utter.rate = 0.95;
    window.speechSynthesis.speak(utter);
  };

  const stopSpeaking = () => {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  };

  const renderRecommendationCard = (rec, msg) => {
    const prof = rec.profile || {};
    const pax = prof.pax || msg?.request?.pax || 1;
    const groupType = (prof.group_type || msg?.request?.group_type || 'Family').toUpperCase();
    const duration = prof.duration_days || msg?.request?.duration_days || 4;
    const pace = (prof.travel_style || msg?.request?.travel_style || 'Comfortable').toUpperCase();
    const budgetPref = (prof.budget_preference || msg?.request?.budget_preference || 'Comfortable').toUpperCase();

    // Estimated budget or cost when available from plan
    const grandTotal = msg?.plan?.budget_evaluation?.grand_total || msg?.budget_evaluation?.grand_total || null;
    const estTotalStr = grandTotal ? `₹${Math.round(grandTotal).toLocaleString('en-IN')}` : null;

    // One-line trip description
    const oneLineDesc = rec.tagline || rec.summary || (
      `A ${budgetPref.toLowerCase()} devotional trip with dedicated time for Darshan and sightseeing.`
    );

    const bullets = rec.approach_bullets || [
      'Dedicated time for trek, darshan, and Bhairavnath Temple.',
      'Explore scenic places around Katra and foothills.',
      'Flexible rest buffers with hill-station excursions.',
    ];
    const places = rec.suggested_places || [];

    const handleFindTravelOptions = () => {
      const planOpts = chatState.pending_options || msg?.plan?.options || null;
      const selOpt = chatState.selected_option || msg?.plan?.selected_option || (planOpts && planOpts.length > 0 ? planOpts[0] : null);
      const req = chatState.current_request || msg?.request || null;
      const itin = chatState.current_itinerary || msg?.itinerary || msg?.plan?.itinerary || null;
      const htl = chatState.hotel || msg?.plan?.hotel || null;
      const bgt = chatState.budget_evaluation || msg?.plan?.budget_evaluation || null;

      const navPayload = {
        sessionId: chatState.session_id || msg?.session_id,
        planVersion: chatState.plan_version || msg?.plan_version || 1,
        feasible_places: chatState.feasible_places?.length > 0 ? chatState.feasible_places : (msg?.feasible_places || []),
        infeasible_places: chatState.infeasible_places?.length > 0 ? chatState.infeasible_places : (msg?.infeasible_places || []),
        itinerary: itin,
        request: req,
        sightseeing_choice: req?.sightseeing_choice || null,
        options: planOpts,
        selected_option: selOpt,
        hotel: htl,
        budget_evaluation: bgt,
        planningMode: 'form',
        step: (planOpts && planOpts.length > 0) ? 2 : 1,
      };
      if (onSwitchToForm) {
        onSwitchToForm(navPayload);
      } else if (onNavigateToBooking) {
        onNavigateToBooking(navPayload);
      } else {
        handleSend('Find travel options to Katra');
      }
    };

    return (
      <div 
        data-testid="compact-personalized-plan-card"
        className="compact-plan-card"
        style={{
          marginTop: '0.6rem',
          width: '100%',
          boxSizing: 'border-box',
          background: '#FFFFFF',
          border: '1.5px solid #E5D2AD',
          borderRadius: '12px',
          padding: '12px 14px',
          boxShadow: '0 2px 8px rgba(88, 17, 26, 0.06)',
          overflow: 'hidden',
        }}
      >
        {/* Header & Title */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '6px',
          marginBottom: '8px',
        }}>
          <div style={{
            fontFamily: 'var(--font-serif)',
            fontWeight: 800,
            fontSize: '0.86rem',
            letterSpacing: '0.03em',
            color: 'var(--burgundy)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}>
            <span>✨</span> YOUR PERSONALIZED YATRA PLAN
          </div>
          {estTotalStr && (
            <div style={{
              fontSize: '0.78rem',
              fontWeight: 700,
              color: '#8A5D00',
              background: '#FFF8E7',
              padding: '2px 8px',
              borderRadius: '6px',
              border: '1px solid #E5D2AD',
            }}>
              Est. Total: {estTotalStr}
            </div>
          )}
        </div>

        {/* Badges: [4 Pilgrims] [4 Days] [Family] [Comfortable] */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '8px' }}>
          <span className="pill pill-gold" style={{ fontSize: '0.72rem', padding: '2px 8px' }}>
            👤 {pax} {pax === 1 ? 'Pilgrim' : 'Pilgrims'}
          </span>
          <span className="pill pill-gold" style={{ fontSize: '0.72rem', padding: '2px 8px' }}>
            📅 {duration} Days
          </span>
          <span className="pill pill-gold" style={{ fontSize: '0.72rem', padding: '2px 8px' }}>
            🧳 {groupType}
          </span>
          <span className="pill pill-gold" style={{ fontSize: '0.72rem', padding: '2px 8px' }}>
            🚶 {pace}
          </span>
        </div>

        {/* One-line trip description */}
        <div style={{
          fontSize: '0.82rem',
          color: 'var(--text-dark)',
          lineHeight: 1.45,
          marginBottom: '10px',
        }}>
          {oneLineDesc}
        </div>

        {/* Two Primary Action Buttons */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          <button 
            type="button"
            onClick={() => handleSend('Show full itinerary')}
            className="btn btn-primary"
            style={{
              flex: '1 1 140px',
              minHeight: '38px',
              padding: '0.45rem 0.8rem',
              fontSize: '0.78rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <span>🗓️</span> Explore Itinerary
          </button>
          <button 
            type="button"
            onClick={handleFindTravelOptions}
            className="btn btn-gold"
            style={{
              flex: '1 1 140px',
              minHeight: '38px',
              padding: '0.45rem 0.8rem',
              fontSize: '0.78rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            <span>🚆</span> Find Travel Options
          </button>
        </div>

        {/* Progressive Disclosure: Collapsed Details Section */}
        <details 
          data-testid="plan-card-progressive-details"
          style={{
            marginTop: '10px',
            background: '#FAF8F5',
            border: '1px solid #EAE0D0',
            borderRadius: '8px',
            padding: '6px 10px',
            fontSize: '0.76rem',
          }}
        >
          <summary style={{
            cursor: 'pointer',
            fontWeight: 600,
            color: 'var(--burgundy)',
            fontFamily: 'var(--font-serif)',
            userSelect: 'none',
            outline: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <span>🔍 View Detailed Strategy & Recommendations</span>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Details ▼</span>
          </summary>

          <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {/* Recommended Strategy Bullets */}
            <div>
              <div style={{ fontWeight: 700, color: 'var(--burgundy)', marginBottom: '3px' }}>
                Recommended Strategy:
              </div>
              <ul style={{ margin: 0, paddingLeft: '1.2rem', color: 'var(--text-dark)', lineHeight: 1.4 }}>
                <li><b>Darshan:</b> {bullets[0] || 'Dedicated darshan and Bhairavnath trek.'}</li>
                <li><b>Sightseeing:</b> {bullets[1] || 'Explore scenic places around Katra and foothills.'}</li>
                <li><b>Pace:</b> {bullets[2] || 'Flexible rest buffers with hill-station excursions.'}</li>
              </ul>
            </div>

            {/* Why This Plan Fits You */}
            {rec.reasoning && (
              <div style={{
                background: '#FFF9F0',
                borderLeft: '2px solid #B8860B',
                padding: '6px 8px',
                borderRadius: '4px',
                lineHeight: 1.4,
              }}>
                <b>Why this plan:</b> {rec.reasoning}
              </div>
            )}

            {/* Suggested Places */}
            {places.length > 0 && (
              <div>
                <div style={{ fontWeight: 700, color: 'var(--burgundy)', marginBottom: '4px' }}>
                  Suggested Places ({places.length}):
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {places.slice(0, 3).map((p, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => onExplorePlace ? onExplorePlace(p.name) : handleSend(`Tell me about ${p.name}`)}
                      className="btn btn-secondary"
                      style={{ padding: '3px 8px', fontSize: '0.72rem' }}
                    >
                      🛕 {p.name} →
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Itemized Cost Breakdown Trigger */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '4px' }}>
              <button
                type="button"
                onClick={() => handleSend('Show detailed cost breakdown')}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--burgundy)',
                  fontWeight: 600,
                  fontSize: '0.74rem',
                  cursor: 'pointer',
                  textDecoration: 'underline',
                  padding: '2px 4px',
                }}
              >
                💰 View Itemized Cost Breakdown →
              </button>
            </div>
          </div>
        </details>

        {/* No-availability Message / Warning Card (Preserved) */}
        {msg.plan && (msg.plan.status === 'NO_AVAILABILITY' || msg.plan.status === 'NO_COMBINATION') && (
          <div style={{
            background: '#FFF9F2',
            border: '1.5px solid #DFD2BC',
            borderRadius: '10px',
            padding: '10px 14px',
            marginTop: '10px',
          }}>
            <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '0.84rem', color: 'var(--burgundy)', marginBottom: '3px' }}>
              ℹ️ TRAVEL OPTIONS NOT FOUND
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-dark)', marginBottom: '4px' }}>
              No verified transport combinations were found for the selected date and route.
            </div>
            <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', lineHeight: 1.35 }}>
              <b>Try:</b> Another travel date (e.g. next week), another transport mode, or a supported departure hub.
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div 
      className={`aichat-container ${isExpanded ? 'aichat-expanded' : (compact ? 'aichat-compact' : 'aichat-standard')}`}
      style={{
        background: '#FFFFFF',
        border: '1.5px solid var(--gold-border)',
        borderRadius: '22px',
        boxShadow: isExpanded ? 'var(--shadow-lg)' : 'var(--shadow-md)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        height: isExpanded ? 'min(85vh, 900px)' : (compact ? '480px' : '580px'),
        maxHeight: isExpanded ? 'calc(100vh - 30px)' : undefined,
        transition: 'height 0.25s ease-out',
      }}
    >
      {/* Header */}
      <div style={{
        background: 'linear-gradient(135deg, #58111A 0%, #3D0810 100%)',
        padding: '0.9rem 1.4rem',
        color: '#FFFFFF',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1.5px solid var(--gold-primary)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '1.2rem' }}>🔱</span>
          <div>
            <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '0.96rem', letterSpacing: '0.03em' }}>
              Yatra AI Companion
            </div>
            <div style={{ fontSize: '0.72rem', color: '#E5D2AD' }}>
              Live Pilgrimage Planning & J&K Tourism Knowledge
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            data-testid="chat-expand-toggle-btn"
            onClick={() => setIsExpanded((prev) => !prev)}
            aria-label={isExpanded ? 'Collapse to standard view' : 'Expand reading view to 85vh'}
            aria-expanded={isExpanded}
            className="chat-expand-btn"
            style={{
              background: isExpanded ? 'var(--gold-primary)' : 'rgba(255, 255, 255, 0.12)',
              border: '1px solid var(--gold-border)',
              borderRadius: '999px',
              color: isExpanded ? '#2D050B' : '#FFFFFF',
              padding: '4px 10px',
              fontSize: '0.72rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
            title={isExpanded ? 'Collapse chat view (Esc)' : 'Expand to larger reading view (85vh)'}
          >
            <span>{isExpanded ? '↙ Standard View' : '⛶ Expand View'}</span>
          </button>
          <span className="pill pill-gold" style={{ fontSize: '0.7rem' }}>
            ● Online
          </span>
        </div>
      </div>

      {/* History Error Banner with Retry */}
      {historyError && (
        <div
          data-testid="chat-history-error-banner"
          style={{
            background: '#FFF8F6',
            borderBottom: '1px solid #F5C6CB',
            padding: '7px 16px',
            fontSize: '0.78rem',
            color: '#721C24',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}
        >
          <span>⚠️ Could not load earlier chat history.</span>
          <button
            type="button"
            data-testid="chat-history-retry-btn"
            onClick={handleRetryHistory}
            style={{
              background: '#C0392B',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '4px',
              padding: '3px 10px',
              fontSize: '0.74rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Retry
          </button>
        </div>
      )}

      {/* Messages Stream */}
      <div 
        ref={messagesContainerRef}
        onScroll={handleMessagesScroll}
        data-testid="chat-messages-stream"
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          padding: '1.2rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem',
          background: 'var(--bg-main)',
        }}
      >
        {messages.map((m, i) => {
          const isUser = m.role === 'user';
          const isLatest = i === messages.length - 1;
          const hasContent = Boolean(m.content && m.content.trim().length > 0);
          const hasRecommendation = Boolean(m.recommendation);
          const hasInfeasible = Boolean(m.infeasible_places && m.infeasible_places.length > 0);

          return (
            <div
              key={m.id || i}
              ref={isLatest ? latestMessageRef : null}
              data-testid={`chat-message-${m.role}-${i}`}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: isUser ? 'flex-end' : 'flex-start',
                maxWidth: isUser ? '82%' : '100%',
                width: isUser ? 'auto' : '100%',
                alignSelf: isUser ? 'flex-end' : 'flex-start',
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  background: isUser ? '#F5ECDA' : '#FFFFFF',
                  border: `1px solid ${isUser ? '#E5D2AD' : '#E5D2AD'}`,
                  borderRadius: '16px',
                  padding: '0.85rem 1.15rem',
                  color: 'var(--text-dark)',
                  boxShadow: '0 2px 6px rgba(0,0,0,0.03)',
                  width: isUser ? 'auto' : '100%',
                  minWidth: 0,
                  wordBreak: 'break-word',
                  overflowWrap: 'anywhere',
                }}
              >
                {!isUser && (
                  <div style={{
                    fontFamily: 'var(--font-serif)',
                    fontWeight: 800,
                    fontSize: '0.82rem',
                    color: 'var(--burgundy)',
                    marginBottom: '6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}>
                    <span>🔱</span> AI Companion
                  </div>
                )}

                {/* 1. Assistant Text Narrative / Content */}
                {hasContent && (
                  <div 
                    data-testid="chat-message-text"
                    style={{ fontSize: '0.9rem', lineHeight: 1.55 }}
                    dangerouslySetInnerHTML={{ __html: formatMarkdown(m.content) }}
                  />
                )}

                {/* 2. Sightseeing Advisory (when present) */}
                {hasInfeasible && (
                  <div
                    data-testid="chat-infeasible-advisory"
                    style={{
                      marginTop: hasContent ? '10px' : '0',
                      background: '#FFF8F6',
                      border: '1px solid #F5C6CB',
                      borderLeft: '3px solid #C0392B',
                      borderRadius: '8px',
                      padding: '8px 12px',
                      fontSize: '0.8rem',
                      color: '#721C24',
                    }}
                  >
                    <b>⚠️ Sightseeing Advisory:</b>{' '}
                    {m.infeasible_places.map((inf, idx) => {
                      const name = typeof inf === 'string' ? inf : (inf.place || inf.name);
                      const reason = typeof inf === 'object' ? inf.reason : null;
                      return (
                        <span key={idx}>
                          <b>{name}</b>
                          {reason ? ` (${reason})` : ''}
                          {idx < m.infeasible_places.length - 1 ? '; ' : ''}
                        </span>
                      );
                    })}
                  </div>
                )}

                {/* 3. Personalized Recommendation Card (when present) */}
                {hasRecommendation && (
                  <div 
                    data-testid="chat-recommendation-block"
                    style={{ marginTop: (hasContent || hasInfeasible) ? '14px' : '0' }}
                  >
                    {renderRecommendationCard(m.recommendation, m)}
                  </div>
                )}

                {/* 4. Recoverable Error Retry Button */}
                {m.isError && m.failedQuery && (
                  <div style={{ marginTop: '8px' }}>
                    <button
                      type="button"
                      data-testid="chat-message-retry-btn"
                      onClick={() => handleSend(m.failedQuery)}
                      disabled={loading}
                      className="btn btn-secondary"
                      style={{
                        padding: '4px 12px',
                        fontSize: '0.76rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        borderRadius: '6px',
                        border: '1px solid #C0392B',
                        color: '#721C24',
                        background: '#FFF5F5',
                        cursor: 'pointer',
                      }}
                    >
                      <span>🔄</span> Retry Message
                    </button>
                  </div>
                )}
              </div>

              {/* TTS Controls for Assistant */}
              {!isUser && (
                <div style={{ display: 'flex', gap: '6px', marginTop: '4px', paddingLeft: '4px' }}>
                  <button
                    onClick={() => speakText(m.content)}
                    style={{
                      background: 'none',
                      border: 'none',
                      fontSize: '0.74rem',
                      color: 'var(--burgundy)',
                      cursor: 'pointer',
                      fontWeight: 600,
                    }}
                  >
                    🔊 Listen
                  </button>
                  <button
                    onClick={stopSpeaking}
                    style={{
                      background: 'none',
                      border: 'none',
                      fontSize: '0.74rem',
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                    }}
                  >
                    ⏹ Stop
                  </button>
                </div>
              )}
            </div>
          );
        })}

        {loading && (
          <div 
            role="status" 
            aria-live="polite"
            style={{ 
              alignSelf: 'flex-start', 
              background: '#FFFFFF', 
              border: '1px solid #E5D2AD', 
              borderRadius: '16px', 
              padding: '0.75rem 1.1rem', 
              fontSize: '0.84rem', 
              color: 'var(--burgundy)', 
              display: 'flex', 
              alignItems: 'center', 
              gap: '10px',
              boxShadow: '0 2px 6px rgba(0,0,0,0.03)'
            }}
          >
            <span style={{ fontSize: '1rem' }}>🔱</span>
            <span style={{ fontWeight: 600 }}>Consulting Yatra Companion...</span>
            <div className="typing-dots" aria-hidden="true" style={{ display: 'inline-flex', gap: '4px', marginLeft: '4px' }}>
              <span className="dot-1" style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--burgundy)' }} />
              <span className="dot-2" style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--burgundy)' }} />
              <span className="dot-3" style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--burgundy)' }} />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} style={{ height: '8px', flexShrink: 0 }} />
      </div>

      {/* Suggested Prompt Chips */}
      {messages.length <= 2 && (
        <div style={{ flexShrink: 0, padding: '0.4rem 1rem', background: '#FFFFFF', borderTop: '1px solid var(--border-subtle)', display: 'flex', gap: '6px', overflowX: 'auto', whiteSpace: 'nowrap' }}>
          {[
            'Scenic places around Katra',
            'Weather forecast in Katra next week',
            'Trains from Delhi to Katra',
            'Hotels near Ban Ganga',
          ].map((promptText, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(promptText)}
              style={{
                background: 'var(--gold-subtle)',
                border: '1px solid var(--gold-border)',
                color: 'var(--burgundy)',
                borderRadius: '999px',
                padding: '4px 10px',
                fontSize: '0.74rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {promptText}
            </button>
          ))}
        </div>
      )}

      {/* Input Row */}
      <div style={{ flexShrink: 0, padding: '0.85rem 1rem', background: '#FFFFFF', borderTop: '1px solid var(--gold-border)' }}>
        <div className="chat-input-row">
          {/* Voice Input Section */}
          <div className="chat-voice-controls">
            <select
              value={selectedLang}
              onChange={(e) => setSelectedLang(e.target.value)}
              style={{ width: '92px', fontSize: '0.76rem', padding: '6px 4px', borderRadius: '8px' }}
              title="Select voice input language"
              aria-label="Select voice input language"
            >
              <option value="en-IN">English</option>
              <option value="hi-IN">Hindi (हिंदी)</option>
              <option value="pa-IN">Punjabi (ਪੰਜਾਬੀ)</option>
              <option value="ur-IN">Urdu (اردو)</option>
            </select>
            <button
              type="button"
              onClick={toggleListening}
              className={`btn ${micState === 'listening' ? 'btn-primary' : 'btn-outline'}`}
              style={{
                padding: '6px 12px',
                fontSize: '0.76rem',
                background: micState === 'listening' ? '#7A1926' : undefined,
                whiteSpace: 'nowrap',
              }}
              title="Speak your query"
              aria-label="Speak your query"
            >
              {micState === 'listening' ? '🎧 Listening...' : (micState === 'processing' ? '⏳ Processing...' : '🎙️ Speak')}
            </button>
          </div>

          {/* Multiline Textarea & Send Button */}
          <div style={{ display: 'flex', flex: 1, gap: '6px', alignItems: 'flex-end' }}>
            <textarea
              ref={textareaRef}
              id="chat-user-input"
              value={inputValue}
              onChange={(e) => {
                setInputValue(e.target.value);
                const el = e.target;
                el.style.height = 'auto';
                el.style.height = Math.min(el.scrollHeight, 100) + 'px';
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Ask Yatra AI (e.g. 'What places can I visit around Katra?')..."
              disabled={loading}
              className="chat-textarea"
              rows={1}
              aria-label="Ask Yatra AI your pilgrimage or tourism query"
            />
            <button
              type="button"
              data-testid="chat-send-btn"
              onClick={() => handleSend()}
              disabled={loading || !inputValue.trim()}
              className="btn btn-primary chat-send-btn"
              aria-label="Send message"
              aria-busy={loading}
            >
              {loading ? (
                <>
                  <span className="spinner" style={{ width: '12px', height: '12px', borderWidth: '2px', display: 'inline-block' }} />
                  <span>Thinking...</span>
                </>
              ) : (
                <span>Send ➔</span>
              )}
            </button>
          </div>
        </div>

        {/* Mic Status Note */}
        {micStatus && (
          <div style={{ fontSize: '0.72rem', color: 'var(--burgundy)', marginTop: '4px', paddingLeft: '4px' }}>
            {micStatus}
          </div>
        )}
      </div>
    </div>
  );
}

