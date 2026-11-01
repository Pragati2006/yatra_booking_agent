import axios from 'axios';

// Base URL: Fallback to proxy or direct local FastAPI server
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
  timeout: 45000, // 45s for LLM / tool chains
});

// Centralized API Functions
export const sendChat = async (messageData) => {
  const payload = typeof messageData === 'string'
    ? { message: messageData }
    : {
        message: messageData.message,
        session_id: messageData.session_id || null,
        current_request: messageData.current_request || null,
        current_itinerary: messageData.current_itinerary || null,
        last_tourism_place: messageData.last_tourism_place || null,
        last_itinerary_context: messageData.last_itinerary_context || null,
        pending_options: messageData.pending_options || null,
      };

  const response = await client.post('/api/chat', payload);
  return response.data;
};

export const getChatHistory = async (sessionId) => {
  if (!sessionId) return { session_id: null, messages: [] };
  const response = await client.get(`/api/chat/history/${encodeURIComponent(sessionId)}`);
  return response.data;
};

export const searchYatra = async (searchData) => {
  const payload = typeof searchData === 'string'
    ? { message: searchData }
    : {
        message: searchData.message,
        session_id: searchData.session_id || null,
        current_request: searchData.current_request || null,
        current_itinerary: searchData.current_itinerary || null,
        last_itinerary_context: searchData.last_itinerary_context || null,
        pending_options: searchData.pending_options || null,
      };

  const response = await client.post('/api/yatra/', payload);
  return response.data;
};

export const getAccommodation = async (accommodationData) => {
  const payload = {
    check_in_date: accommodationData.check_in_date,
    category: accommodationData.category || null,
    min_rooms: accommodationData.min_rooms || 1,
  };

  const response = await client.post('/api/yatra/accommodation', payload);
  return response.data;
};

export const getSightseeing = async (category = null) => {
  const payload = {
    category: category || null,
  };

  const response = await client.post('/api/yatra/sightseeing', payload);
  return response.data;
};

export const generateItinerary = async (itineraryData) => {
  const payload = {
    option: itineraryData.option,
    hotel: itineraryData.hotel || null,
    hotel_nights: itineraryData.hotel_nights !== undefined ? itineraryData.hotel_nights : 2,
    sightseeing_places: itineraryData.sightseeing_places || [],
    request: itineraryData.request || null,
  };

  const response = await client.post('/api/yatra/itinerary', payload);
  return response.data;
};

export const confirmBooking = async (confirmData) => {
  const payload = {
    option: confirmData.option,
    pax: confirmData.pax || 1,
    user_name: confirmData.user_name || 'Guest-User',
    hotel: confirmData.hotel || null,
    hotel_nights: confirmData.hotel_nights !== undefined ? confirmData.hotel_nights : 2,
    sightseeing_places: confirmData.sightseeing_places || [],
    human_authorized: confirmData.human_authorized === true,
    session_id: confirmData.session_id || null,
    plan_version: confirmData.plan_version || null,
  };

  const response = await client.post('/api/yatra/confirm', payload);
  return response.data;
};

export const runRPA = async (rpaData) => {
  const payload = {
    user_name: rpaData.user_name || 'Guest-User',
    pax_count: rpaData.pax_count || 1,
    transport_text: rpaData.transport_text,
    slot_text: rpaData.slot_text,
    total_price: parseFloat(rpaData.total_price || 0),
    headless: rpaData.headless !== false,
    session_id: rpaData.session_id || null,
    plan_version: rpaData.plan_version || null,
    human_authorized: rpaData.human_authorized === true,
  };

  const response = await client.post('/api/yatra/rpa', payload);
  return response.data;
};

export const getTourism = async (query, lastPlace = null) => {
  const response = await client.post('/api/tourism/', {
    query,
    last_tourism_place: lastPlace,
  });
  return response.data;
};

export const getWeather = async (location = 'Katra') => {
  const response = await client.post('/api/weather/', { location });
  return response.data;
};

export const authorizePlan = async (authData) => {
  const payload = {
    session_id: authData.session_id,
    plan_version: authData.plan_version,
    user_confirmation: authData.user_confirmation || 'Confirm booking',
  };

  const response = await client.post('/api/yatra/authorize', payload);
  return response.data;
};

export const checkHealth = async () => {
  const response = await client.get('/api/health');
  return response.data;
};

export const checkRPAAvailability = async (availabilityData = {}) => {
  const payload = {
    date: availabilityData.date || '2026-10-20',
    category: availabilityData.category || null,
    headless: availabilityData.headless !== false,
  };
  const response = await client.post('/api/yatra/rpa/availability', payload);
  return response.data;
};

// Week 8: User-Controlled Workflow API functions
export const startRPAWorkflow = async (workflowData) => {
  const payload = {
    session_id: workflowData.session_id,
    user_name: workflowData.user_name || 'Guest-Pilgrim',
    pax_count: workflowData.pax_count || 1,
    transport_text: workflowData.transport_text || 'Train',
    slot_text: workflowData.slot_text || 'Morning Darshan',
    total_price: parseFloat(workflowData.total_price || 0),
    checkpoint_mode: workflowData.checkpoint_mode || null,
    headless: workflowData.headless !== false,
    plan_version: workflowData.plan_version || null,
    human_authorized: workflowData.human_authorized === true,
  };
  const response = await client.post('/api/yatra/rpa/workflow/start', payload);
  return response.data;
};

export const getRPAWorkflowStatus = async (workflowId, sessionId) => {
  const response = await client.get(`/api/yatra/rpa/workflow/${encodeURIComponent(workflowId)}?session_id=${encodeURIComponent(sessionId)}`);
  return response.data;
};

export const resumeRPAWorkflow = async (resumeData) => {
  const payload = {
    session_id: resumeData.session_id,
    workflow_id: resumeData.workflow_id,
    user_confirmed_action: resumeData.user_confirmed_action === true,
    manual_input_value: resumeData.manual_input_value || null,
    simulate_manual_clearance: resumeData.simulate_manual_clearance === true,
    headless: resumeData.headless !== false,
  };
  const response = await client.post('/api/yatra/rpa/workflow/resume', payload);
  return response.data;
};

export const cancelRPAWorkflow = async (cancelData) => {
  const payload = {
    session_id: cancelData.session_id,
    workflow_id: cancelData.workflow_id,
    reason: cancelData.reason || 'Cancelled by user',
  };
  const response = await client.post('/api/yatra/rpa/workflow/cancel', payload);
  return response.data;
};

// ==============================================================================
// WEEK 9: OPTIONAL PASSWORDLESS EMAIL AUTHENTICATION & USER DATA APIs
// ==============================================================================

export const requestOtp = async (email) => {
  const response = await client.post('/api/auth/request-otp', { email });
  return response.data;
};

export const verifyOtp = async (email, otpCode) => {
  const response = await client.post('/api/auth/verify-otp', { email, otp_code: otpCode });
  return response.data;
};

export const getAuthMe = async () => {
  const response = await client.get('/api/auth/me');
  return response.data;
};

export const logout = async () => {
  const response = await client.post('/api/auth/logout');
  return response.data;
};

export const saveItinerary = async (title, itinerary) => {
  const response = await client.post('/api/auth/save-itinerary', { title, itinerary });
  return response.data;
};

export const getSavedItineraries = async () => {
  const response = await client.get('/api/auth/saved-itineraries');
  return response.data;
};

export const deleteSavedItinerary = async (itineraryId) => {
  const response = await client.delete(`/api/auth/saved-itinerary/${encodeURIComponent(itineraryId)}`);
  return response.data;
};

export const saveConversation = async (title, messages) => {
  const response = await client.post('/api/auth/save-conversation', { title, messages });
  return response.data;
};

export const getSavedConversations = async () => {
  const response = await client.get('/api/auth/saved-conversations');
  return response.data;
};

export const deleteSavedConversation = async (conversationId) => {
  const response = await client.delete(`/api/auth/saved-conversation/${encodeURIComponent(conversationId)}`);
  return response.data;
};

export const getSavedBookings = async () => {
  const response = await client.get('/api/auth/saved-bookings');
  return response.data;
};

export const getSavedBooking = async (bookingId) => {
  const response = await client.get(`/api/auth/saved-bookings/${encodeURIComponent(bookingId)}`);
  return response.data;
};

export const saveBooking = async (bookingData) => {
  const response = await client.post('/api/auth/save-booking', bookingData);
  return response.data;
};

export const transferConversation = async (sessionId, title = null) => {
  const response = await client.post('/api/auth/transfer-conversation', { session_id: sessionId, title });
  return response.data;
};

export const transferTrip = async (sessionId, title = null) => {
  const response = await client.post('/api/auth/transfer-trip', { session_id: sessionId, title });
  return response.data;
};

export const transferBooking = async (bookingId, sessionId = null) => {
  const response = await client.post('/api/auth/transfer-booking', { booking_id: bookingId, session_id: sessionId });
  return response.data;
};

export const getUserProfile = async () => {
  const response = await client.get('/api/auth/profile');
  return response.data;
};

export default {
  sendChat,
  searchYatra,
  getAccommodation,
  getSightseeing,
  generateItinerary,
  authorizePlan,
  confirmBooking,
  runRPA,
  checkRPAAvailability,
  startRPAWorkflow,
  getRPAWorkflowStatus,
  resumeRPAWorkflow,
  cancelRPAWorkflow,
  getTourism,
  getWeather,
  checkHealth,
  requestOtp,
  verifyOtp,
  getAuthMe,
  logout,
  saveItinerary,
  getSavedItineraries,
  deleteSavedItinerary,
  saveConversation,
  getSavedConversations,
  deleteSavedConversation,
  getSavedBookings,
  getSavedBooking,
  saveBooking,
  transferConversation,
  transferTrip,
  transferBooking,
  getUserProfile,
};

