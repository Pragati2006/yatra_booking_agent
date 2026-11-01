import React, { useState, useEffect } from 'react';
import TravelSearch from '../components/TravelSearch';
import AIChat from '../components/AIChat';
import { getSightseeing } from '../services/api';

export default function Home({ onStartBooking, onExplorePlaceQuery, onViewAllDestinations = null }) {
  const [featuredPlaces, setFeaturedPlaces] = useState([]);
  const [selectedPlaceModal, setSelectedPlaceModal] = useState(null);

  useEffect(() => {
    // Load top destinations for featured section
    getSightseeing()
      .then((data) => {
        if (data && data.places) {
          // Curate top 6 iconic pilgrimage & scenic spots
          const priorityNames = [
            'Bhairavnath Temple',
            'Ardhkuwari Cave',
            'Charan Paduka',
            'Baba Dhansar',
            'Patnitop',
            'Shiv Khori',
          ];
          const sorted = [...data.places].sort((a, b) => {
            const aIdx = priorityNames.indexOf(a.name);
            const bIdx = priorityNames.indexOf(b.name);
            if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx;
            if (aIdx !== -1) return -1;
            if (bIdx !== -1) return 1;
            return 0;
          });
          setFeaturedPlaces(sorted.slice(0, 6));
        }
      })
      .catch((err) => console.error('Failed to load featured destinations:', err));
  }, []);

  return (
    <div className="page-container">
      {/* 1. HERO BANNER SECTION */}
      <section
        className="hero-banner"
        style={{
          backgroundImage: `url('/assets/images/places/vaishno devi.jpg')`,
        }}
      >
        <div className="hero-overlay" />
        <div className="hero-content">
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            background: 'rgba(255, 255, 255, 0.16)',
            border: '1px solid rgba(229, 210, 173, 0.4)',
            color: '#F5ECDA',
            borderRadius: '999px',
            padding: '5px 14px',
            fontSize: '0.8rem',
            fontWeight: 700,
            letterSpacing: '0.06em',
            marginBottom: '1rem',
          }}>
            <span>🔱</span> JAI MATA DI · SACRED PILGRIMAGE PORTAL
          </div>

          <h1 className="hero-title">
            Shri Mata Vaishno Devi Yatra
          </h1>

          <p className="hero-subtitle">
            Experience a divine journey to the holy shrine of Mata Vaishno Devi Ji nestled in the Trikuta Mountains of Katra, Jammu & Kashmir. Plan your darshan, verified transport, accommodations, and local sightseeing seamlessly.
          </p>

          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <button
              onClick={() => onStartBooking()}
              className="btn btn-gold"
              style={{ padding: '0.8rem 2rem', fontSize: '0.95rem' }}
            >
              Plan Your Yatra Now ➔
            </button>
            <a
              href="#ai-assistant-section"
              className="btn btn-outline"
              style={{ padding: '0.8rem 1.8rem', fontSize: '0.95rem' }}
            >
              💬 Ask AI Companion
            </a>
          </div>
        </div>
      </section>

      {/* Quick Search Widget */}
      <div style={{ marginTop: '-2.5rem', position: 'relative', zIndex: 10, marginBottom: '2.5rem' }}>
        <TravelSearch
          onSearch={(searchParams) => {
            onStartBooking(searchParams);
          }}
        />
      </div>

      {/* 2. AI ASSISTANT SECTION (Prominently placed beneath hero as required) */}
      <section id="ai-assistant-section" style={{ marginBottom: '3.5rem' }}>
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            color: 'var(--gold-primary)',
            fontSize: '0.78rem',
            fontWeight: 800,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            marginBottom: '4px',
          }}>
            <span>🔱</span> INTELLIGENT COMPANION
          </div>
          <h2 style={{ fontSize: '2rem', color: 'var(--burgundy-dark)', marginBottom: '6px' }}>
            AI Companion & Yatra Assistant
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem', maxWidth: '640px', margin: '0 auto' }}>
            Ask anything about Katra, trek routes, darshan registration, packing advice, weather, or personalized multi-day trip recommendations.
          </p>
        </div>

        <AIChat
          onNavigateToBooking={onStartBooking}
          onExplorePlace={onExplorePlaceQuery}
        />
      </section>

      {/* 3. FEATURED DESTINATIONS */}
      <section id="featured-destinations" data-testid="home-featured-destinations" style={{ marginBottom: '3.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <div style={{
              color: 'var(--gold-primary)',
              fontSize: '0.78rem',
              fontWeight: 800,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              marginBottom: '4px',
            }}>
              EXPLORE JAMMU & KASHMIR
            </div>
            <h2 style={{ fontSize: '1.85rem', color: 'var(--burgundy-dark)' }}>
              Featured Destinations
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
              Revered temples, holy caves, and scenic Himalayan retreats across Katra and Jammu
            </p>
          </div>
          <button
            type="button"
            data-testid="view-all-destinations-btn"
            onClick={() => onViewAllDestinations ? onViewAllDestinations() : onStartBooking()}
            className="btn btn-outline"
            style={{ fontSize: '0.82rem' }}
          >
            View All 29 Destinations ➔
          </button>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '1.25rem',
        }}>
          {featuredPlaces.map((place, idx) => (
            <div
              key={idx}
              className="card card-hover"
              style={{ display: 'flex', flexDirection: 'column', padding: '12px' }}
            >
              <div style={{ height: '160px', borderRadius: '12px', overflow: 'hidden', position: 'relative', marginBottom: '10px' }}>
                {place.image ? (
                  <img
                    src={'/' + place.image}
                    alt={place.name}
                    onError={(e) => { e.currentTarget.style.display = 'none'; }}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                ) : null}
                <div style={{
                  position: 'absolute',
                  top: '8px',
                  left: '8px',
                  background: 'rgba(45, 5, 11, 0.85)',
                  color: '#F5ECDA',
                  border: '1px solid var(--gold-border)',
                  borderRadius: '999px',
                  padding: '2px 10px',
                  fontSize: '0.7rem',
                  fontWeight: 700,
                }}>
                  {place.category}
                </div>
              </div>

              <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '1.05rem', color: 'var(--burgundy)' }}>
                {place.name}
              </div>
              <div style={{ fontSize: '0.76rem', color: 'var(--gold-primary)', fontWeight: 600, margin: '2px 0 6px' }}>
                ⏱️ {place.distance || 'Katra Region'} · {place.timings || 'Open daily'}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.4, flex: 1, marginBottom: '12px' }}>
                {place.description ? place.description.slice(0, 95) + '...' : ''}
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => setSelectedPlaceModal(place)}
                  className="btn btn-outline"
                  style={{ flex: 1, padding: '0.45rem', fontSize: '0.78rem' }}
                >
                  View Details
                </button>
                <button
                  onClick={() => onExplorePlaceQuery ? onExplorePlaceQuery(`Tell me about ${place.name}`) : null}
                  className="btn btn-secondary"
                  style={{ flex: 1, padding: '0.45rem', fontSize: '0.78rem' }}
                >
                  Ask AI 💬
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 4. PILGRIMAGE ESSENTIALS / ADVISORY STRIPS */}
      <section style={{
        background: '#FFFFFF',
        border: '1.5px solid var(--gold-border)',
        borderRadius: '20px',
        padding: '2rem',
        boxShadow: 'var(--shadow-sm)',
        marginBottom: '2rem',
      }}>
        <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '1.25rem', color: 'var(--burgundy)', marginBottom: '1rem' }}>
          📜 Pilgrimage Essentials & Yatra Guidelines
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
          <div>
            <div style={{ fontWeight: 800, fontSize: '0.88rem', color: 'var(--burgundy)', marginBottom: '4px' }}>
              🆔 RFID Yatra Card
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
              Mandatory RFID-based Yatra Access Cards must be acquired at Katra railway station or bus stand counters before commencing the trek.
            </div>
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '0.88rem', color: 'var(--burgundy)', marginBottom: '4px' }}>
              🛕 Holy Aarti Timings
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
              Sacred Aarti takes place at Bhawan twice daily: Morning 06:00 AM to 08:00 AM and Evening 07:00 PM to 08:30 PM.
            </div>
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '0.88rem', color: 'var(--burgundy)', marginBottom: '4px' }}>
              🧳 Weather & Packing
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
              The Bhawan shrine (~5,200 ft) is noticeably cooler than Katra town. Always carry comfortable trekking footwear and light woollens.
            </div>
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '0.88rem', color: 'var(--burgundy)', marginBottom: '4px' }}>
              🚁 Helicopter & Battery Cars
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
              Helicopter operates between Katra and Sanjichhat. Eco-friendly battery cars operate between Ardhkuwari and Bhawan for elderly pilgrims.
            </div>
          </div>
        </div>
      </section>

      {/* Place Detail Modal */}
      {selectedPlaceModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.65)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '1rem',
        }}>
          <div style={{
            background: '#FFFFFF',
            border: '2px solid var(--gold-primary)',
            borderRadius: '20px',
            maxWidth: '620px',
            width: '100%',
            maxHeight: '90vh',
            overflowY: 'auto',
            padding: '1.75rem',
            boxShadow: 'var(--shadow-lg)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.4rem', fontWeight: 800, color: 'var(--burgundy)' }}>
                {selectedPlaceModal.name}
              </div>
              <button
                onClick={() => setSelectedPlaceModal(null)}
                style={{ background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                ✕
              </button>
            </div>

            {selectedPlaceModal.image && (
              <img
                src={'/' + selectedPlaceModal.image}
                alt={selectedPlaceModal.name}
                style={{ width: '100%', height: '220px', objectFit: 'cover', borderRadius: '12px', marginBottom: '14px' }}
              />
            )}

            <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
              <span className="pill pill-gold">{selectedPlaceModal.category}</span>
              <span className="pill pill-gold">📍 {selectedPlaceModal.distance}</span>
              <span className="pill pill-gold">⏱️ {selectedPlaceModal.timings}</span>
            </div>

            <div style={{ fontSize: '0.88rem', color: 'var(--text-dark)', lineHeight: 1.5, marginBottom: '12px' }}>
              {selectedPlaceModal.description}
            </div>

            {selectedPlaceModal.historical_background && (
              <div style={{ background: '#FFF9F0', border: '1px solid #E5D2AD', borderRadius: '10px', padding: '12px', marginBottom: '14px' }}>
                <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '0.85rem', color: 'var(--burgundy)', marginBottom: '4px' }}>
                  📜 Historical Significance
                </div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-dark)', lineHeight: 1.45 }}>
                  {selectedPlaceModal.historical_background}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              {selectedPlaceModal.video_search && (
                <a
                  href={selectedPlaceModal.video_search}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-outline"
                  style={{ fontSize: '0.82rem' }}
                >
                  ▶ Watch Video Guide
                </a>
              )}
              <button
                onClick={() => {
                  setSelectedPlaceModal(null);
                  if (onExplorePlaceQuery) onExplorePlaceQuery(`Tell me about ${selectedPlaceModal.name}`);
                }}
                className="btn btn-primary"
                style={{ fontSize: '0.82rem' }}
              >
                Ask Companion About This ➔
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
