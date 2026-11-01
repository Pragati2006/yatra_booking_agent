import React, { useState } from 'react';

const TRAVEL_NOTES = {
  'On the trek route': 'Trek on foot; battery car, pony & ropeway available along the route.',
  'Nearby temple': 'Short local taxi or auto-rickshaw ride from Katra town (10–30 mins).',
  'Nature': 'Half/full-day taxi excursion from Katra with scenic valley views.',
  'Hill station': 'Scenic mountain excursion by taxi from Katra/Jammu (~2.5–3 hrs).',
  'Hill station / adventure': 'Full-day mountain excursion from Katra/Jammu (~2.5–3 hrs).',
  'Nature / heritage': 'Half-day taxi excursion from Jammu or Katra.',
  'Jammu city': 'Direct road route from Katra to Jammu city (~1–1.5 hrs).',
  'Kashmir': 'Northern valley excursion accessible via NH-44 or flight from Jammu.',
  'Pilgrimage Base': 'Centrally located base town with registration counters and bazaars.',
};

export default function SightseeingCard({ place, isSelected, onToggleSelect, onExplorePlace = null }) {
  const [showDetails, setShowDetails] = useState(false);

  if (!place) return null;

  const cardId = place.name ? place.name.toLowerCase().replace(/[^a-z0-9]+/g, '-') : 'destination';
  const travelRequirement = TRAVEL_NOTES[place.category] || null;

  return (
    <div
      data-testid={`place-card-${cardId}`}
      className="card card-hover"
      style={{
        border: isSelected ? '2px solid var(--gold-primary)' : '1px solid var(--gold-border)',
        background: isSelected ? '#FFFDF7' : '#FFFFFF',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '14px',
        position: 'relative',
        borderRadius: '16px',
        boxShadow: isSelected
          ? '0 6px 20px rgba(184, 134, 11, 0.16)'
          : '0 4px 12px rgba(61, 8, 16, 0.04)',
        transition: 'all 0.2s ease',
      }}
    >
      {/* Top Image & Selection Indicator */}
      <div style={{ position: 'relative', height: '150px', borderRadius: '12px', overflow: 'hidden', marginBottom: '12px' }}>
        {place.image ? (
          <img
            src={'/' + place.image}
            alt={place.name}
            onError={(e) => {
              e.currentTarget.style.display = 'none';
              if (e.currentTarget.nextSibling) {
                e.currentTarget.nextSibling.style.display = 'flex';
              }
            }}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : null}
        <div
          style={{
            display: place.image ? 'none' : 'flex',
            width: '100%',
            height: '100%',
            background: 'linear-gradient(135deg, #58111A, #3D0810)',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#E5D2AD',
            fontSize: '2.4rem',
          }}
        >
          🔱
        </div>

        {/* Selection Toggle Button */}
        <button
          type="button"
          data-testid={`toggle-place-${cardId}`}
          onClick={onToggleSelect}
          style={{
            position: 'absolute',
            top: '8px',
            right: '8px',
            background: isSelected ? 'var(--burgundy)' : 'rgba(255, 255, 255, 0.94)',
            color: isSelected ? '#FFFFFF' : 'var(--burgundy)',
            border: isSelected ? '1.5px solid var(--gold-primary)' : '1.5px solid var(--gold-border)',
            borderRadius: '999px',
            padding: '5px 12px',
            fontSize: '0.76rem',
            fontWeight: 800,
            cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.25)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            transition: 'all 0.15s ease',
          }}
        >
          {isSelected ? '✓ Selected' : '+ Add Place'}
        </button>

        {/* Category Pill */}
        <span
          className="pill"
          style={{
            position: 'absolute',
            bottom: '8px',
            left: '8px',
            background: 'rgba(45, 5, 11, 0.88)',
            color: '#F5ECDA',
            border: '1px solid var(--gold-border)',
            fontSize: '0.7rem',
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: '8px',
          }}
        >
          {place.category}
        </span>

        {/* Region Tag if available */}
        {place.region && (
          <span
            style={{
              position: 'absolute',
              bottom: '8px',
              right: '8px',
              background: 'rgba(255, 255, 255, 0.9)',
              color: 'var(--burgundy)',
              border: '1px solid var(--gold-border)',
              fontSize: '0.68rem',
              fontWeight: 700,
              padding: '2px 6px',
              borderRadius: '6px',
            }}
          >
            📍 {place.region}
          </span>
        )}
      </div>

      {/* Place Information Content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: '8px',
          marginBottom: '4px',
        }}>
          <h3 style={{
            fontFamily: 'var(--font-serif)',
            fontWeight: 800,
            fontSize: '1.05rem',
            color: 'var(--burgundy)',
            lineHeight: 1.25,
            margin: 0,
          }}>
            {place.name}
          </h3>
          {isSelected && (
            <span style={{
              background: '#F0FDF4',
              color: '#166534',
              border: '1px solid #BBF7D0',
              fontSize: '0.68rem',
              fontWeight: 700,
              padding: '2px 6px',
              borderRadius: '6px',
              whiteSpace: 'nowrap',
            }}>
              In Plan
            </span>
          )}
        </div>

        {/* Distance & Timings */}
        <div style={{ fontSize: '0.78rem', color: 'var(--gold-primary)', fontWeight: 600, margin: '2px 0 6px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          <span>⏱️ {place.distance || 'Katra Region'}</span>
          {place.timings && <span>• 🕐 {place.timings}</span>}
        </div>

        {/* Entry Fee (if available & not strictly free) */}
        {place.entry_fee && place.entry_fee !== 'Free' && (
          <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
            🎟️ <b>Fee:</b> {place.entry_fee}
          </div>
        )}

        {/* Description */}
        <div style={{ fontSize: '0.82rem', color: 'var(--text-dark)', lineHeight: 1.45, flex: 1 }}>
          {showDetails ? place.description : (
            place.description && place.description.length > 110
              ? place.description.slice(0, 105) + '...'
              : place.description
          )}
        </div>

        {/* Extended Historical Background & Route Details */}
        {showDetails && (
          <div
            data-testid={`place-details-${cardId}`}
            style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}
          >
            {place.historical_background && (
              <div style={{
                background: '#FAF6EE',
                border: '1px dashed var(--gold-border)',
                borderRadius: '8px',
                padding: '8px 10px',
                fontSize: '0.76rem',
                color: 'var(--text-dark)',
                lineHeight: 1.45,
              }}>
                <b style={{ color: 'var(--burgundy)' }}>📜 Heritage Context:</b> {place.historical_background}
              </div>
            )}

            {travelRequirement && (
              <div style={{
                background: '#F4F7FB',
                border: '1px solid #D6E4F0',
                borderRadius: '8px',
                padding: '6px 10px',
                fontSize: '0.74rem',
                color: '#1E3A8A',
                lineHeight: 1.4,
              }}>
                <b>🚗 Travel & Access:</b> {travelRequirement}
              </div>
            )}

            {place.location_route && (
              <div style={{
                background: '#FDFBF7',
                border: '1px solid var(--gold-border)',
                borderRadius: '8px',
                padding: '6px 10px',
                fontSize: '0.74rem',
                color: 'var(--text-muted)',
                lineHeight: 1.4,
              }}>
                <b>📍 Route Guide:</b> {place.location_route}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Card Action Footer */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderTop: '1px solid var(--border-subtle, #E4D5B7)',
        marginTop: '10px',
        paddingTop: '8px',
      }}>
        <button
          type="button"
          data-testid={`toggle-details-${cardId}`}
          onClick={() => setShowDetails(!showDetails)}
          style={{
            background: 'none',
            border: 'none',
            fontSize: '0.76rem',
            color: 'var(--burgundy)',
            fontWeight: 700,
            cursor: 'pointer',
            padding: 0,
          }}
        >
          {showDetails ? 'Hide Details ▲' : 'Read Heritage & Route ▼'}
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {onExplorePlace && (
            <button
              type="button"
              onClick={() => onExplorePlace(place.name)}
              style={{
                background: 'none',
                border: 'none',
                fontSize: '0.74rem',
                color: 'var(--burgundy)',
                fontWeight: 600,
                cursor: 'pointer',
                padding: '2px 4px',
              }}
            >
              💬 Ask AI
            </button>
          )}
          {place.video_search && (
            <a
              href={place.video_search}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                fontSize: '0.75rem',
                color: 'var(--gold-primary)',
                textDecoration: 'none',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <span>▶ Watch Guide</span>
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
