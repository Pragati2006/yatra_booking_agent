import React, { useState, useEffect } from 'react';
import {
  getSavedItineraries,
  deleteSavedItinerary,
  getSavedConversations,
  deleteSavedConversation,
  getSavedBookings,
  getUserProfile,
  transferConversation,
  transferTrip,
} from '../services/api';
import { generatePilgrimPassPDF } from '../utils/pdfGenerator';

export default function SavedTripsModal({
  isOpen,
  onClose,
  user,
  onLoadItinerary,
  onLoadConversation,
}) {
  const [activeTab, setActiveTab] = useState('bookings'); // 'profile' | 'conversations' | 'itineraries' | 'bookings'
  const [itineraries, setItineraries] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [transferMsg, setTransferMsg] = useState('');
  const [selectedPass, setSelectedPass] = useState(null);

  const guestSessionId = typeof window !== 'undefined' ? sessionStorage.getItem('yatra_session_id') : null;

  const refreshAllData = async (isMounted) => {
    setLoading(true);
    setErrorMsg('');
    try {
      const [itinRes, convRes, bookRes, profRes] = await Promise.all([
        getSavedItineraries().catch(() => ({ itineraries: [] })),
        getSavedConversations().catch(() => ({ conversations: [] })),
        getSavedBookings().catch(() => ({ bookings: [] })),
        getUserProfile().catch(() => ({ profile: null })),
      ]);
      if (isMounted) {
        setItineraries(itinRes.itineraries || []);
        setConversations(convRes.conversations || []);
        setBookings(bookRes.bookings || []);
        setProfile(profRes.profile || null);
      }
    } catch (err) {
      if (isMounted) {
        setErrorMsg(err.message || 'Failed to load account records.');
      }
    } finally {
      if (isMounted) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    if (!isOpen || !user) return;
    let isMounted = true;
    refreshAllData(isMounted);
    return () => {
      isMounted = false;
    };
  }, [isOpen, user]);

  if (!isOpen) return null;

  const handleDeleteItinerary = async (id, title) => {
    if (!window.confirm(`Delete saved trip "${title}"?`)) return;
    try {
      await deleteSavedItinerary(id);
      setItineraries((prev) => prev.filter((item) => item.itinerary_id !== id));
    } catch (err) {
      alert(`Failed to delete itinerary: ${err.message || 'Error'}`);
    }
  };

  const handleDeleteConversation = async (id, title) => {
    if (!window.confirm(`Delete saved chat "${title}"?`)) return;
    try {
      await deleteSavedConversation(id);
      setConversations((prev) => prev.filter((item) => item.conversation_id !== id));
    } catch (err) {
      alert(`Failed to delete conversation: ${err.message || 'Error'}`);
    }
  };

  const handleTransferCurrentChat = async () => {
    if (!guestSessionId) return;
    setTransferMsg('Transferring current chat session to your account...');
    try {
      await transferConversation(guestSessionId);
      setTransferMsg('✅ Active chat successfully linked to your account!');
      await refreshAllData(true);
      setTimeout(() => setTransferMsg(''), 4000);
    } catch (err) {
      setTransferMsg(`⚠️ Transfer notice: ${err.message || 'No active guest chat found to transfer.'}`);
      setTimeout(() => setTransferMsg(''), 4000);
    }
  };

  const handleTransferCurrentTrip = async () => {
    if (!guestSessionId) return;
    setTransferMsg('Transferring current plan to your account...');
    try {
      await transferTrip(guestSessionId);
      setTransferMsg('✅ Current trip plan successfully saved to your account!');
      await refreshAllData(true);
      setTimeout(() => setTransferMsg(''), 4000);
    } catch (err) {
      setTransferMsg(`⚠️ Transfer notice: ${err.message || 'No active trip plan found in session to transfer.'}`);
      setTimeout(() => setTransferMsg(''), 4000);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(30, 8, 12, 0.65)',
        backdropFilter: 'blur(4px)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          background: '#FFFFFF',
          borderRadius: '20px',
          border: '2px solid var(--gold-border, #E5D2AD)',
          boxShadow: '0 16px 40px rgba(88, 17, 26, 0.25)',
          maxWidth: '740px',
          width: '100%',
          maxHeight: '88vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          animation: 'fadeIn 0.2s ease-out',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            background: 'linear-gradient(135deg, #58111A 0%, #3D0810 100%)',
            color: '#FFFFFF',
            padding: '1.15rem 1.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '2px solid var(--gold-primary, #B8860B)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '1.4rem' }}>👤</span>
            <div>
              <div style={{ fontFamily: 'var(--font-serif, serif)', fontWeight: 700, fontSize: '1.15rem' }}>
                My Account & Saved History
              </div>
              <div style={{ fontSize: '0.75rem', color: '#E5D2AD' }}>
                Signed in as: {user?.email}
              </div>
            </div>
          </div>
          <button
            type="button"
            data-testid="account-modal-close-btn"
            onClick={onClose}
            aria-label="Close"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#E5D2AD',
              fontSize: '1.4rem',
              cursor: 'pointer',
              lineHeight: 1,
              padding: '4px',
            }}
          >
            ✕
          </button>
        </div>

        {/* Tab Selector */}
        <div
          style={{
            display: 'flex',
            borderBottom: '1px solid #E5D2AD',
            background: '#FDFBF7',
            overflowX: 'auto',
          }}
        >
          {[
            { id: 'bookings', label: `🎫 My Bookings (${bookings.length})` },
            { id: 'itineraries', label: `🧳 My Trips (${itineraries.length})` },
            { id: 'conversations', label: `💬 My Conversations (${conversations.length})` },
            { id: 'profile', label: '👤 My Profile' },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              data-testid={`tab-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              style={{
                flex: 1,
                minWidth: '130px',
                padding: '0.75rem 0.5rem',
                background: activeTab === tab.id ? '#FFFFFF' : 'transparent',
                border: 'none',
                borderBottom: activeTab === tab.id ? '3px solid #58111A' : 'none',
                color: activeTab === tab.id ? '#58111A' : '#7D6A5D',
                fontWeight: activeTab === tab.id ? 700 : 600,
                fontSize: '0.84rem',
                cursor: 'pointer',
                textAlign: 'center',
                whiteSpace: 'nowrap',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content Area */}
        <div style={{ padding: '1.25rem', overflowY: 'auto', flex: 1 }}>
          {loading && (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#7D6A5D' }}>
              Loading your records...
            </div>
          )}

          {errorMsg && (
            <div style={{ background: '#FFF5F5', color: '#C53030', padding: '0.75rem', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '1rem' }}>
              ⚠️ {errorMsg}
            </div>
          )}

          {transferMsg && (
            <div style={{ background: '#F0FFF4', color: '#276749', padding: '0.75rem', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '1rem', border: '1px solid #C6F6D5' }}>
              {transferMsg}
            </div>
          )}

          {/* TAB 1: BOOKINGS */}
          {!loading && activeTab === 'bookings' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '8px' }}>
                <div>
                  <div style={{ fontWeight: 800, color: '#58111A', fontSize: '1rem' }}>
                    Simulated Yatra Bookings
                  </div>
                  <div style={{ fontSize: '0.76rem', color: '#7D6A5D' }}>
                    Local Mock Portal verification records associated with your account
                  </div>
                </div>
                <span style={{ fontSize: '0.72rem', background: '#FDF6EC', border: '1px solid #E5D2AD', color: '#B8860B', padding: '3px 8px', borderRadius: '6px', fontWeight: 600 }}>
                  LOCAL MOCK PORTAL / DEMO
                </span>
              </div>

              {bookings.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2.5rem 1rem', color: '#7D6A5D', background: '#FAF7F2', borderRadius: '12px' }}>
                  <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🎫</div>
                  <div style={{ fontWeight: 700, color: '#58111A' }}>No simulated bookings yet</div>
                  <div style={{ fontSize: '0.82rem', marginTop: '4px' }}>
                    Complete a realistic mock booking in Darshan Bookings while signed in, and your confirmed demo pass will appear here.
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {bookings.map((b) => {
                    const d = new Date(b.created_at);
                    const dateFormatted = isNaN(d) ? b.created_at : d.toLocaleString();
                    const originRoute = b.receipt?.origin || 'Delhi';
                    const routeText = `${originRoute} ➔ Katra (Shri Mata Vaishno Devi Shrine)`;
                    const emailAccount = user?.email || b.receipt?.email || b.user_id || 'Registered Pilgrim';
                    const transportDesc = b.transport_info || b.transport_mode || 'Train (Vande Bharat Express)';
                    const hotelDesc = b.hotel_name || 'Devi Darshan Hotel (Katra)';
                    const paymentLabel = `${b.payment_status || 'COMPLETED_SANDBOX'} (Sandbox Paid — ₹0 Live Charge)`;
                    const slotTimeDesc = b.slot_time || 'Morning Slot (06:00)';

                    const handleDownloadCardPDF = () => {
                      generatePilgrimPassPDF(b, {
                        option: {
                          transport: { name: transportDesc, mode: b.transport_mode || 'Train' },
                          slot: { category: b.category, slot_date: b.slot_date, slot_time: slotTimeDesc }
                        },
                        hotel: { name: hotelDesc },
                        pax: b.pax_count,
                        origin: originRoute,
                        total_price: b.total_price,
                      });
                    };

                    const handlePrintCardPass = () => {
                      setSelectedPass(b);
                      setTimeout(() => window.print(), 300);
                    };

                    return (
                      <div
                        key={b.booking_id}
                        data-testid={`booking-card-${b.booking_id}`}
                        style={{
                          border: '1.5px solid #E5D2AD',
                          borderRadius: '12px',
                          padding: '1.15rem',
                          background: '#FFFDF9',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '10px',
                          boxShadow: '0 2px 8px rgba(88, 17, 26, 0.04)',
                        }}
                      >
                        {/* Demo Disclaimers */}
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            flexWrap: 'wrap',
                            gap: '6px',
                            background: '#FEF3C7',
                            border: '1px solid #F59E0B',
                            borderRadius: '6px',
                            padding: '4px 10px',
                            fontSize: '0.68rem',
                            fontWeight: 800,
                            color: '#92400E',
                            letterSpacing: '0.03em',
                          }}
                        >
                          <span>⚠️ LOCAL MOCK PORTAL / DEMO</span>
                          <span>NOT AN OFFICIAL SHRINE BOARD BOOKING</span>
                        </div>

                        {/* Card Header */}
                        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                              <span style={{ fontWeight: 800, color: '#58111A', fontSize: '1.15rem', letterSpacing: '0.03em' }}>
                                {b.booking_id}
                              </span>
                              <span style={{ fontSize: '0.72rem', background: '#C6F6D5', color: '#22543D', padding: '2px 8px', borderRadius: '999px', fontWeight: 700 }}>
                                {b.status}
                              </span>
                            </div>
                            <div style={{ fontSize: '0.78rem', color: '#4A3B32', marginTop: '4px' }}>
                              Devotee: <strong>{b.user_name}</strong> • Account: <strong>{emailAccount}</strong> • Pilgrims: <strong>{b.pax_count}</strong>
                            </div>
                            <div style={{ fontSize: '0.72rem', color: '#7D6A5D', marginTop: '2px' }}>
                              Booked on: {dateFormatted}
                            </div>
                          </div>

                          <div style={{ textAlign: 'right' }}>
                            <div style={{ fontWeight: 800, color: '#58111A', fontSize: '1.2rem' }}>
                              ₹{Number(b.total_price || 0).toLocaleString('en-IN')}
                            </div>
                            <div style={{ fontSize: '0.72rem', color: '#2F855A', fontWeight: 700 }}>
                              {paymentLabel}
                            </div>
                          </div>
                        </div>

                        {/* Particulars Grid */}
                        <div style={{
                          background: '#FBF8F3',
                          border: '1px solid #EFE4D2',
                          borderRadius: '8px',
                          padding: '0.75rem 0.9rem',
                          display: 'grid',
                          gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
                          gap: '8px 16px',
                          fontSize: '0.8rem',
                          color: '#3D2F27',
                        }}>
                          <div>📅 <strong>Yatra Date:</strong> {b.slot_date}</div>
                          <div>🛕 <strong>Darshan Category:</strong> {b.category}</div>
                          <div>⏰ <strong>Darshan Slot:</strong> {slotTimeDesc}</div>
                          <div>🗺️ <strong>Route:</strong> {routeText}</div>
                          <div>🚆 <strong>Transport:</strong> {transportDesc}</div>
                          <div>🏨 <strong>Stay:</strong> {hotelDesc}</div>
                        </div>

                        {/* Actions Row */}
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', flexWrap: 'wrap', marginTop: '4px' }}>
                          <button
                            type="button"
                            data-testid={`view-details-btn-${b.booking_id}`}
                            onClick={() => setSelectedPass(b)}
                            style={{
                              background: '#FFFDF9',
                              color: '#58111A',
                              border: '1.5px solid #C5A059',
                              borderRadius: '8px',
                              padding: '0.45rem 0.9rem',
                              fontSize: '0.82rem',
                              fontWeight: 700,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '5px',
                            }}
                          >
                            <span>🔍</span>
                            <span>View Details</span>
                          </button>

                          <button
                            type="button"
                            data-testid={`download-pass-btn-${b.booking_id}`}
                            onClick={handleDownloadCardPDF}
                            style={{
                              background: 'linear-gradient(135deg, #155724 0%, #0d3817 100%)',
                              color: '#FFFFFF',
                              border: '1px solid #28a745',
                              borderRadius: '8px',
                              padding: '0.45rem 0.95rem',
                              fontSize: '0.82rem',
                              fontWeight: 700,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '5px',
                            }}
                          >
                            <span>📥</span>
                            <span>Download Pass (PDF)</span>
                          </button>

                          <button
                            type="button"
                            data-testid={`print-pass-btn-${b.booking_id}`}
                            onClick={handlePrintCardPass}
                            style={{
                              background: 'linear-gradient(135deg, #58111A 0%, #3D0810 100%)',
                              color: '#FFFFFF',
                              border: '1px solid #B8860B',
                              borderRadius: '8px',
                              padding: '0.45rem 0.95rem',
                              fontSize: '0.82rem',
                              fontWeight: 700,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '5px',
                            }}
                          >
                            <span>🖨️</span>
                            <span>Print Pass</span>
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: ITINERARIES */}
          {!loading && activeTab === 'itineraries' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '8px' }}>
                <div>
                  <div style={{ fontWeight: 800, color: '#58111A', fontSize: '1rem' }}>
                    My Saved Trips & Itineraries
                  </div>
                  <div style={{ fontSize: '0.76rem', color: '#7D6A5D' }}>
                    Personal pilgrimage plans saved to your account
                  </div>
                </div>

                {guestSessionId && (
                  <button
                    type="button"
                    onClick={handleTransferCurrentTrip}
                    style={{
                      background: '#FFFDF9',
                      border: '1.5px solid #E5D2AD',
                      borderRadius: '8px',
                      color: '#58111A',
                      padding: '0.4rem 0.75rem',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    📥 Save Current Session Plan
                  </button>
                )}
              </div>

              {itineraries.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2.5rem 1rem', color: '#7D6A5D', background: '#FAF7F2', borderRadius: '12px' }}>
                  <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🗺️</div>
                  <div style={{ fontWeight: 700, color: '#58111A' }}>No saved itineraries yet</div>
                  <div style={{ fontSize: '0.82rem', marginTop: '4px' }}>
                    Generate an itinerary in Darshan Bookings and click "Save Trip" to store it here.
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {itineraries.map((itin) => {
                    const d = new Date(itin.created_at);
                    const dateFormatted = isNaN(d) ? itin.created_at : d.toLocaleDateString();
                    return (
                      <div
                        key={itin.itinerary_id}
                        style={{
                          border: '1.5px solid #E5D2AD',
                          borderRadius: '12px',
                          padding: '0.85rem 1rem',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          background: '#FFFDF9',
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 700, color: '#58111A', fontSize: '0.95rem' }}>
                            {itin.title}
                          </div>
                          <div style={{ fontSize: '0.76rem', color: '#7D6A5D', marginTop: '2px' }}>
                            Saved on {dateFormatted} • ID: {itin.itinerary_id}
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          {onLoadItinerary && (
                            <button
                              type="button"
                              onClick={() => {
                                onLoadItinerary(itin.data);
                                onClose();
                              }}
                              style={{
                                background: '#58111A',
                                color: '#FFFFFF',
                                border: 'none',
                                borderRadius: '6px',
                                padding: '0.4rem 0.75rem',
                                fontSize: '0.78rem',
                                fontWeight: 600,
                                cursor: 'pointer',
                              }}
                            >
                              Load Plan
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => handleDeleteItinerary(itin.itinerary_id, itin.title)}
                            style={{
                              background: '#FFF5F5',
                              color: '#C53030',
                              border: '1px solid #FEB2B2',
                              borderRadius: '6px',
                              padding: '0.4rem 0.65rem',
                              fontSize: '0.78rem',
                              cursor: 'pointer',
                            }}
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: CONVERSATIONS */}
          {!loading && activeTab === 'conversations' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '8px' }}>
                <div>
                  <div style={{ fontWeight: 800, color: '#58111A', fontSize: '1rem' }}>
                    My Saved Conversations
                  </div>
                  <div style={{ fontSize: '0.76rem', color: '#7D6A5D' }}>
                    Archived AI Companion dialogues saved to your account
                  </div>
                </div>

                {guestSessionId && (
                  <button
                    type="button"
                    onClick={handleTransferCurrentChat}
                    style={{
                      background: '#FFFDF9',
                      border: '1.5px solid #E5D2AD',
                      borderRadius: '8px',
                      color: '#58111A',
                      padding: '0.4rem 0.75rem',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    📥 Save Current Session Chat
                  </button>
                )}
              </div>

              {conversations.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2.5rem 1rem', color: '#7D6A5D', background: '#FAF7F2', borderRadius: '12px' }}>
                  <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>💬</div>
                  <div style={{ fontWeight: 700, color: '#58111A' }}>No saved conversations yet</div>
                  <div style={{ fontSize: '0.82rem', marginTop: '4px' }}>
                    Conversations you save in AI Companion will be archived here for reference.
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {conversations.map((conv) => {
                    const d = new Date(conv.created_at);
                    const dateFormatted = isNaN(d) ? conv.created_at : d.toLocaleDateString();
                    return (
                      <div
                        key={conv.conversation_id}
                        style={{
                          border: '1.5px solid #E5D2AD',
                          borderRadius: '12px',
                          padding: '0.85rem 1rem',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          background: '#FFFDF9',
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 700, color: '#58111A', fontSize: '0.95rem' }}>
                            {conv.title}
                          </div>
                          <div style={{ fontSize: '0.76rem', color: '#7D6A5D', marginTop: '2px' }}>
                            {conv.messages?.length || 0} messages • Saved on {dateFormatted}
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          {onLoadConversation && (
                            <button
                              type="button"
                              onClick={() => {
                                onLoadConversation(conv.messages);
                                onClose();
                              }}
                              style={{
                                background: '#58111A',
                                color: '#FFFFFF',
                                border: 'none',
                                borderRadius: '6px',
                                padding: '0.4rem 0.75rem',
                                fontSize: '0.78rem',
                                fontWeight: 600,
                                cursor: 'pointer',
                              }}
                            >
                              Load Chat
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => handleDeleteConversation(conv.conversation_id, conv.title)}
                            style={{
                              background: '#FFF5F5',
                              color: '#C53030',
                              border: '1px solid #FEB2B2',
                              borderRadius: '6px',
                              padding: '0.4rem 0.65rem',
                              fontSize: '0.78rem',
                              cursor: 'pointer',
                            }}
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 4: PROFILE */}
          {!loading && activeTab === 'profile' && (
            <div>
              <div style={{ fontWeight: 800, color: '#58111A', fontSize: '1rem', marginBottom: '1rem' }}>
                Devotee Profile Details
              </div>

              <div style={{ background: '#FFFDF9', border: '1.5px solid #E5D2AD', borderRadius: '14px', padding: '1.25rem', marginBottom: '1rem' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#7D6A5D', textTransform: 'uppercase', fontWeight: 600 }}>Email Address</div>
                    <div style={{ fontWeight: 700, color: '#58111A', fontSize: '0.95rem', marginTop: '2px' }}>{user.email}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#7D6A5D', textTransform: 'uppercase', fontWeight: 600 }}>User Identifier</div>
                    <div style={{ fontFamily: 'monospace', fontWeight: 600, color: '#7D6A5D', fontSize: '0.88rem', marginTop: '2px' }}>{user.user_id}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#7D6A5D', textTransform: 'uppercase', fontWeight: 600 }}>Preferred Darshan</div>
                    <div style={{ fontWeight: 600, color: '#4A3B32', fontSize: '0.9rem', marginTop: '2px' }}>
                      {profile?.preferences?.preferred_darshan || user?.preferences?.preferred_darshan || 'Normal Darshan'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: '#7D6A5D', textTransform: 'uppercase', fontWeight: 600 }}>Travel Style</div>
                    <div style={{ fontWeight: 600, color: '#4A3B32', fontSize: '0.9rem', marginTop: '2px' }}>
                      {profile?.preferences?.travel_style || user?.preferences?.travel_style || 'Standard'}
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ fontWeight: 700, color: '#58111A', fontSize: '0.9rem', marginBottom: '0.75rem' }}>
                Account Activity Summary
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem' }}>
                <div style={{ background: '#FAF7F2', borderRadius: '10px', padding: '0.85rem', textAlign: 'center', border: '1px solid #E5D2AD' }}>
                  <div style={{ fontSize: '1.4rem' }}>🎫</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#58111A' }}>{bookings.length}</div>
                  <div style={{ fontSize: '0.74rem', color: '#7D6A5D' }}>Simulated Bookings</div>
                </div>
                <div style={{ background: '#FAF7F2', borderRadius: '10px', padding: '0.85rem', textAlign: 'center', border: '1px solid #E5D2AD' }}>
                  <div style={{ fontSize: '1.4rem' }}>🧳</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#58111A' }}>{itineraries.length}</div>
                  <div style={{ fontSize: '0.74rem', color: '#7D6A5D' }}>Saved Itineraries</div>
                </div>
                <div style={{ background: '#FAF7F2', borderRadius: '10px', padding: '0.85rem', textAlign: 'center', border: '1px solid #E5D2AD' }}>
                  <div style={{ fontSize: '1.4rem' }}>💬</div>
                  <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#58111A' }}>{conversations.length}</div>
                  <div style={{ fontSize: '0.74rem', color: '#7D6A5D' }}>Saved Conversations</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Demo Pass Viewer Modal */}
      {selectedPass && (
        <div
          role="dialog"
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            zIndex: 1100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem',
          }}
          onClick={() => setSelectedPass(null)}
        >
          <div
            style={{
              background: '#FFFFFF',
              borderRadius: '16px',
              border: '2px solid #B8860B',
              boxShadow: '0 20px 50px rgba(0,0,0,0.3)',
              maxWidth: '540px',
              width: '100%',
              overflow: 'hidden',
              animation: 'fadeIn 0.2s ease-out',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div style={{ background: 'linear-gradient(135deg, #58111A 0%, #3D0810 100%)', color: '#FFFFFF', padding: '1.15rem 1.25rem', textAlign: 'center', borderBottom: '2px solid #B8860B' }}>
              <div style={{ fontSize: '0.72rem', letterSpacing: '0.08em', color: '#E5D2AD', fontWeight: 800, textTransform: 'uppercase' }}>
                LOCAL MOCK PORTAL / DEMO • NOT AN OFFICIAL SHRINE BOARD BOOKING
              </div>
              <div style={{ fontFamily: 'var(--font-serif, serif)', fontSize: '1.25rem', fontWeight: 800, marginTop: '4px' }}>
                ✅ Simulated Yatra Booking Confirmation
              </div>
              <div style={{ fontSize: '0.76rem', color: '#D6C8B2', marginTop: '2px' }}>
                Demo Pilgrim Pass — Generated via Local Browser Automation
              </div>
            </div>

            {/* Pass Body */}
            <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ background: '#FDFBF7', border: '1.5px dashed #B8860B', borderRadius: '10px', padding: '0.85rem', textAlign: 'center' }}>
                <div style={{ fontSize: '0.72rem', color: '#7D6A5D', textTransform: 'uppercase', fontWeight: 700 }}>Mock Booking Reference</div>
                <div style={{ fontSize: '1.45rem', fontWeight: 800, color: '#58111A', letterSpacing: '0.04em', marginTop: '2px' }}>
                  {selectedPass.booking_id}
                </div>
                <div style={{ fontSize: '0.72rem', color: '#276749', fontWeight: 800, marginTop: '3px' }}>
                  STATUS: {selectedPass.status} ({selectedPass.payment_status || 'COMPLETED_SANDBOX'} - ₹0 LIVE BANK CHARGE)
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.82rem', background: '#FFFDF9', border: '1px solid #E5D2AD', borderRadius: '10px', padding: '0.85rem' }}>
                <div><strong>Pilgrim Devotee:</strong> {selectedPass.user_name}</div>
                <div><strong>Associated Account:</strong> {user?.email || selectedPass.receipt?.email || selectedPass.user_id}</div>
                <div><strong>Pilgrim Count:</strong> {selectedPass.pax_count} devotee(s)</div>
                <div><strong>Darshan Date:</strong> {selectedPass.slot_date}</div>
                <div><strong>Darshan Category:</strong> {selectedPass.category}</div>
                <div><strong>Slot Time:</strong> {selectedPass.slot_time || 'Morning Slot (06:00)'}</div>
                <div><strong>Route / Origin:</strong> {selectedPass.receipt?.origin || 'Delhi'} ➔ Katra</div>
                <div><strong>Transport:</strong> {selectedPass.transport_info || selectedPass.transport_mode || 'Train (Vande Bharat Express)'}</div>
                <div><strong>Accommodation:</strong> {selectedPass.hotel_name || 'Devi Darshan Hotel (Katra)'}</div>
                <div><strong>Simulated Total:</strong> ₹{Number(selectedPass.total_price || 0).toLocaleString('en-IN')}</div>
                <div style={{ gridColumn: 'span 2' }}><strong>Created Timestamp:</strong> {new Date(selectedPass.created_at).toLocaleString()}</div>
              </div>

              <div style={{ fontSize: '0.72rem', color: '#7D6A5D', textAlign: 'center', fontStyle: 'italic', background: '#FAF7F2', padding: '0.5rem 0.75rem', borderRadius: '6px', border: '1px solid #E5D2AD' }}>
                Note: This pass is a simulated demonstration record generated by the local mock booking portal for academic verification. No actual Shrine Board booking occurred.
              </div>

              <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', flexWrap: 'wrap', marginTop: '6px' }}>
                <button
                  type="button"
                  onClick={() => setSelectedPass(null)}
                  style={{
                    background: '#FFFDF9',
                    border: '1px solid #E5D2AD',
                    borderRadius: '8px',
                    padding: '0.45rem 0.95rem',
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                  }}
                >
                  Close
                </button>
                <button
                  type="button"
                  data-testid="modal-download-pass-btn"
                  onClick={() => generatePilgrimPassPDF(selectedPass, {
                    option: {
                      transport: { name: selectedPass.transport_info, mode: selectedPass.transport_mode },
                      slot: { category: selectedPass.category, slot_date: selectedPass.slot_date, slot_time: selectedPass.slot_time }
                    },
                    hotel: selectedPass.hotel_name ? { name: selectedPass.hotel_name } : null,
                    pax: selectedPass.pax_count,
                    origin: selectedPass.receipt?.origin || 'Delhi',
                    total_price: selectedPass.total_price,
                  })}
                  style={{
                    background: 'linear-gradient(135deg, #155724 0%, #0d3817 100%)',
                    color: '#FFFFFF',
                    border: '1px solid #28a745',
                    borderRadius: '8px',
                    padding: '0.45rem 1rem',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                  }}
                >
                  <span>📥</span>
                  <span>Download Pass (PDF)</span>
                </button>
                <button
                  type="button"
                  data-testid="modal-print-pass-btn"
                  onClick={() => window.print()}
                  style={{
                    background: 'linear-gradient(135deg, #58111A 0%, #3D0810 100%)',
                    color: '#FFFFFF',
                    border: '1px solid #B8860B',
                    borderRadius: '8px',
                    padding: '0.45rem 1rem',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                  }}
                >
                  <span>🖨️</span>
                  <span>Print Demo Pass</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
