import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import YatraBooking from './pages/YatraBooking';
import SightseeingBrowser from './components/SightseeingBrowser';
import AIChat from './components/AIChat';
import AuthModal from './components/AuthModal';
import SavedTripsModal from './components/SavedTripsModal';
import { getAuthMe, logout, setAuthToken } from './services/api';
import './App.css';

export default function App() {
  const [activeTab, setActiveTab] = useState('home'); // 'home' | 'booking' | 'sightseeing' | 'assistant'
  const [bookingParams, setBookingParams] = useState(null);
  const [assistantInitialQuery, setAssistantInitialQuery] = useState(null);
  const [hasMountedBooking, setHasMountedBooking] = useState(false);

  // Week 9: Optional Passwordless Authentication & User State (Default Guest Mode)
  const [currentUser, setCurrentUser] = useState(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showSavedTripsModal, setShowSavedTripsModal] = useState(false);

  // Check existing session silently on load without blocking guest access
  useEffect(() => {
    let isMounted = true;
    getAuthMe()
      .then((res) => {
        if (isMounted && res.authenticated && res.user) {
          setCurrentUser(res.user);
        } else if (isMounted && !res.authenticated) {
          setAuthToken(null);
        }
      })
      .catch(() => {
        // Unauthenticated guest is normal; do not show error
      });
    return () => { isMounted = false; };
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // Ignore
    } finally {
      setAuthToken(null);
    }
    setCurrentUser(null);
    setShowSavedTripsModal(false);
  };

  const handleStartBooking = (params = null) => {
    if (params) {
      setBookingParams(params);
    }
    setHasMountedBooking(true);
    setActiveTab('booking');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleExplorePlaceQuery = (query) => {
    setAssistantInitialQuery(query);
    setActiveTab('assistant');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Top Navbar */}
      <div className="container">
        <Navbar
          activeTab={activeTab}
          setActiveTab={(tab) => {
            if (tab === 'booking') {
              setHasMountedBooking(true);
              setActiveTab('booking');
            } else {
              setActiveTab(tab);
            }
            window.scrollTo({ top: 0, behavior: 'smooth' });
          }}
          user={currentUser}
          onOpenAuthModal={() => setShowAuthModal(true)}
          onOpenSavedTrips={() => setShowSavedTripsModal(true)}
          onLogout={handleLogout}
        />
      </div>

      {/* Main View Container */}
      <main className="container" style={{ flex: 1 }}>
        {activeTab === 'home' && (
          <Home
            onStartBooking={handleStartBooking}
            onExplorePlaceQuery={handleExplorePlaceQuery}
            onViewAllDestinations={() => {
              setActiveTab('sightseeing');
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }}
          />
        )}

        {(hasMountedBooking || activeTab === 'booking') && (
          <div style={{ display: activeTab === 'booking' ? 'block' : 'none' }}>
            <YatraBooking
              initialSearchParams={bookingParams}
              currentUser={currentUser}
              onRequireAuth={() => setShowAuthModal(true)}
              onReturnHome={() => {
                setActiveTab('home');
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
            />
          </div>
        )}

        {activeTab === 'sightseeing' && (
          <div style={{ paddingTop: '1rem', paddingBottom: '3rem' }}>
            <SightseeingBrowser
              isStandalone={true}
              onExplorePlace={handleExplorePlaceQuery}
              onPlanYatra={(selectedPlaces) => {
                handleStartBooking({
                  sightseeing_choice: 'custom',
                  sightseeing_places: selectedPlaces,
                });
              }}
              onBack={() => {
                setActiveTab('home');
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
            />
          </div>
        )}

        {activeTab === 'assistant' && (
          <div style={{ maxWidth: '980px', margin: '0 auto', paddingTop: '1rem', paddingBottom: '3rem' }}>
            <div style={{ marginBottom: '1.25rem', textAlign: 'center' }}>
              <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.85rem', fontWeight: 800, color: 'var(--burgundy)' }}>
                🔱 Vaishno Devi AI Assistant
              </div>
              <div style={{ fontSize: '0.88rem', color: 'var(--text-muted)' }}>
                Ask any question about yatra planning, live transport availability, Katra weather, or itinerary updates.
              </div>
            </div>

            <AIChat
              initialMessage={assistantInitialQuery}
              onNavigateToBooking={(payload) => handleStartBooking(payload)}
              onExplorePlace={(placeName) => handleExplorePlaceQuery(`Tell me about ${placeName}`)}
            />
          </div>
        )}
      </main>

      {/* Luxury Footer */}
      <footer style={{
        background: 'linear-gradient(135deg, #3D0810 0%, #2D050B 100%)',
        borderTop: '2px solid var(--gold-primary)',
        color: '#F5ECDA',
        padding: '2.5rem 1rem 1.5rem',
        marginTop: 'auto',
      }}>
        <div className="container">
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '2rem',
            marginBottom: '2rem',
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                <span style={{ fontSize: '1.4rem' }}>🔱</span>
                <span style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '1.1rem', color: '#FFFFFF' }}>
                  VAISHNO DEVI YATRA
                </span>
              </div>
              <p style={{ fontSize: '0.82rem', color: '#D6C8B2', lineHeight: 1.5 }}>
                An intelligent multi-agent pilgrimage & tourism platform powered by LangChain, MongoDB, and Playwright browser RPA.
              </p>
            </div>

            <div>
              <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '0.95rem', color: '#FFFFFF', marginBottom: '10px' }}>
                Quick Navigation
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.82rem' }}>
                <a href="#" onClick={(e) => { e.preventDefault(); setActiveTab('home'); }} style={{ color: '#E5D2AD', textDecoration: 'none' }}>Home</a>
                <a href="#" onClick={(e) => { e.preventDefault(); handleStartBooking(); }} style={{ color: '#E5D2AD', textDecoration: 'none' }}>Plan Darshan</a>
                <a href="#" onClick={(e) => { e.preventDefault(); setActiveTab('sightseeing'); window.scrollTo({ top: 0, behavior: 'smooth' }); }} style={{ color: '#E5D2AD', textDecoration: 'none' }}>29 Sightseeing Destinations</a>
                <a href="#" onClick={(e) => { e.preventDefault(); setActiveTab('assistant'); }} style={{ color: '#E5D2AD', textDecoration: 'none' }}>AI Companion</a>
              </div>
            </div>

            <div>
              <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '0.95rem', color: '#FFFFFF', marginBottom: '10px' }}>
                Emergency & Helpline
              </div>
              <div style={{ fontSize: '0.82rem', color: '#D6C8B2', lineHeight: 1.6 }}>
                📞 Shrine Board Call Centre: 01991-232075<br />
                🚨 Yatra Medical Aid: 01991-232115<br />
                📍 Katra Main Counter: Central Bus Stand, Katra
              </div>
            </div>
          </div>

          <div style={{
            borderTop: '1px solid rgba(229, 210, 173, 0.2)',
            paddingTop: '1.25rem',
            textAlign: 'center',
            fontSize: '0.78rem',
            color: '#A89984',
          }}>
            © {CURRENT_YEAR} Maa Vaishno Devi Yatra AI Platform. All rights reserved. Jai Mata Di.
          </div>
        </div>
      </footer>

      {/* Week 9: Optional Passwordless Auth Modal */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onAuthSuccess={(user, token) => {
          setCurrentUser(user);
          if (token) setAuthToken(token);
        }}
      />

      {/* Week 9: Authenticated User Saved Trips Modal */}
      <SavedTripsModal
        isOpen={showSavedTripsModal}
        onClose={() => setShowSavedTripsModal(false)}
        user={currentUser}
        onLoadItinerary={(itineraryData) => {
          setBookingParams(itineraryData);
          setHasMountedBooking(true);
          setActiveTab('booking');
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
      />
    </div>
  );
}

const CURRENT_YEAR = new Date().getFullYear();
