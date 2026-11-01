import React from 'react';

export default function HotelCard({ hotel, isSelected, onSelect }) {
  const name = hotel.name || 'Shrine Board Pilgrim Guest House';
  const category = hotel.category || 'Standard';
  const price = hotel.price_per_night || 1200;
  const rooms = hotel.rooms_available || 5;
  const location = hotel.location || 'Katra Town Centre';
  const amenities = Array.isArray(hotel.amenities)
    ? hotel.amenities
    : (typeof hotel.amenities === 'string' ? hotel.amenities.split(',') : ['Hot Water', 'Wi-Fi', 'Room Service']);

  return (
    <div
      className="card card-hover"
      style={{
        border: isSelected ? '2px solid var(--gold-primary)' : '1px solid var(--gold-border)',
        background: isSelected ? '#FFFCF7' : '#FFFFFF',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        padding: '1.15rem',
        gap: '10px',
      }}
    >
      <div>
        {/* Category Pill & Rooms Left */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <span className="pill pill-gold" style={{ fontSize: '0.72rem' }}>
            🏨 {category}
          </span>
          <span style={{ fontSize: '0.74rem', color: rooms <= 3 ? '#C0392B' : '#27AE60', fontWeight: 700 }}>
            {rooms} {rooms === 1 ? 'room' : 'rooms'} left
          </span>
        </div>

        {/* Hotel Name */}
        <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '1.05rem', color: 'var(--burgundy)', lineHeight: 1.25 }}>
          {name}
        </div>

        {/* Location */}
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '3px' }}>
          📍 {location}
        </div>

        {/* Amenities */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '8px' }}>
          {amenities.slice(0, 3).map((am, i) => (
            <span
              key={i}
              style={{
                background: 'var(--bg-subtle)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '6px',
                padding: '2px 8px',
                fontSize: '0.72rem',
                color: 'var(--text-dark)',
              }}
            >
              {am.trim()}
            </span>
          ))}
        </div>
      </div>

      {/* Pricing & Selection */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderTop: '1px solid var(--border-subtle)',
        paddingTop: '10px',
        marginTop: '6px',
      }}>
        <div>
          <span style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--burgundy)' }}>
            ₹{price.toLocaleString('en-IN')}
          </span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {' '}/ night
          </span>
        </div>

        <button
          onClick={onSelect}
          className={`btn ${isSelected ? 'btn-gold' : 'btn-outline'}`}
          style={{ padding: '0.45rem 1.15rem', fontSize: '0.8rem' }}
        >
          {isSelected ? '✓ Selected Stay' : 'Select Stay'}
        </button>
      </div>
    </div>
  );
}
