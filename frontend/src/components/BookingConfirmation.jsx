import React from 'react';

export default function BookingConfirmation({ confirmationData, bookingSummary, onReturnHome }) {
  const { booking_id, message } = confirmationData || {};
  const { option, pax = 1, hotel, hotelNights = 2, origin = 'Delhi' } = bookingSummary || {};

  const tr = option?.transport || option?.flight || {};
  const slot = option?.slot || {};

  return (
    <div className="pilgrim-pass-container" style={{ maxWidth: '780px', margin: '0 auto', paddingTop: '1rem' }}>
      {/* Success Badge Banner */}
      <div className="pilgrim-pass-banner" style={{
        background: 'linear-gradient(135deg, #58111A 0%, #3D0810 100%)',
        border: '2px solid var(--gold-primary)',
        borderRadius: '20px',
        padding: '2.5rem 2rem',
        color: '#FFFFFF',
        textAlign: 'center',
        boxShadow: 'var(--shadow-lg)',
        marginBottom: '2rem',
        position: 'relative',
        overflow: 'hidden',
      }}>
        <div style={{ fontSize: '3rem', marginBottom: '8px' }}>🔱</div>
        <div className="pilgrim-pass-title" style={{ fontFamily: 'var(--font-serif)', fontSize: '1.9rem', fontWeight: 800, color: '#FBF9F4', letterSpacing: '0.04em' }}>
          JAI MATA DI! BOOKING CONFIRMED
        </div>
        <div className="pilgrim-pass-subtitle" style={{ color: '#E5D2AD', fontSize: '0.92rem', marginTop: '4px' }}>
          Your pilgrimage registration has been officially confirmed by Shri Mata Vaishno Devi Shrine Agent
        </div>

        {/* Ref Box */}
        <div className="pilgrim-pass-ref-box" style={{
          display: 'inline-block',
          background: 'rgba(255, 255, 255, 0.12)',
          border: '1.5px dashed var(--gold-primary)',
          borderRadius: '12px',
          padding: '10px 24px',
          marginTop: '1.25rem',
        }}>
          <div className="pilgrim-pass-ref-label" style={{ fontSize: '0.72rem', color: '#E5D2AD', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Official Booking Reference ID
          </div>
          <div className="pilgrim-pass-ref-id" style={{ fontSize: '1.75rem', fontWeight: 800, color: '#FFFFFF', letterSpacing: '0.08em' }}>
            {booking_id || 'Pending Confirmation'}
          </div>
        </div>

        {/* Divine Blessing */}
        {message && (
          <div className="pilgrim-pass-blessing" style={{
            fontSize: '0.9rem',
            color: '#F5ECDA',
            fontStyle: 'italic',
            marginTop: '1.25rem',
            lineHeight: 1.5,
            maxWidth: '580px',
            marginInline: 'auto',
          }}>
            "{message}"
          </div>
        )}

        {/* Demo Simulation Disclaimer */}
        <div className="pilgrim-pass-disclaimer" style={{
          marginTop: '1.25rem',
          padding: '8px 16px',
          background: 'rgba(255, 255, 255, 0.12)',
          border: '1px solid rgba(229, 210, 173, 0.4)',
          borderRadius: '10px',
          fontSize: '0.76rem',
          color: '#E5D2AD',
          maxWidth: '620px',
          marginInline: 'auto',
        }}>
          <b>DEMO AUTOMATION &amp; SIMULATION NOTICE:</b> This yatra registration pass was generated in simulated sandbox mode via mock RPA. No live tickets or real-world bank transactions were executed.
        </div>
      </div>

      {/* Summary Pass Card */}
      <div className="card pilgrim-pass-card" style={{ padding: '1.75rem', marginBottom: '2rem', border: '1.5px solid var(--gold-border)' }}>
        <div className="pilgrim-pass-section-title" style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '1.1rem', color: 'var(--burgundy)', marginBottom: '14px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '8px' }}>
          🎫 Pilgrim Yatra Pass Particulars
        </div>

        <div className="pilgrim-pass-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          <div>
            <div className="pilgrim-pass-label" style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Travel Route</div>
            <div className="pilgrim-pass-value" style={{ fontWeight: 800, fontSize: '0.95rem', color: 'var(--text-dark)' }}>{origin} ➔ Katra</div>
            <div className="pilgrim-pass-subtext" style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{tr.operator || 'Express'} · Departure {tr.departure_time || '06:00'}</div>
          </div>

          <div>
            <div className="pilgrim-pass-label" style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Shrine Darshan Slot</div>
            <div className="pilgrim-pass-value" style={{ fontWeight: 800, fontSize: '0.95rem', color: 'var(--text-dark)' }}>{slot.category || 'Normal Darshan'}</div>
            <div className="pilgrim-pass-subtext" style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{slot.slot_time || 'Morning Slot'}</div>
          </div>

          <div>
            <div className="pilgrim-pass-label" style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Pilgrims Count</div>
            <div className="pilgrim-pass-value" style={{ fontWeight: 800, fontSize: '0.95rem', color: 'var(--text-dark)' }}>{pax} {pax === 1 ? 'Pilgrim' : 'Pilgrims'}</div>
            <div className="pilgrim-pass-subtext" style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Guest Identity: Registered</div>
          </div>

          {hotel && (
            <div>
              <div className="pilgrim-pass-label" style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Confirmed Hotel</div>
              <div className="pilgrim-pass-value" style={{ fontWeight: 800, fontSize: '0.95rem', color: 'var(--text-dark)' }}>{hotel.name}</div>
              <div className="pilgrim-pass-subtext" style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{hotelNights} Nights Stay Reserved</div>
            </div>
          )}
        </div>

        <div className="pilgrim-pass-rfid-notice" style={{
          marginTop: '1.25rem',
          padding: '10px 14px',
          background: '#F9FBF9',
          border: '1px solid #C3E6CB',
          borderRadius: '10px',
          fontSize: '0.82rem',
          color: '#155724',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          <span>✓</span> Shrine Board RFID Yatra Access Card will be issued upon reporting at Katra Yatra Registration Counter with this reference ID.
        </div>
      </div>

      {/* Action Buttons */}
      <div className="no-print" style={{ display: 'flex', justifyContent: 'center', gap: '1rem' }}>
        <button
          onClick={() => window.print()}
          className="btn btn-outline"
          style={{ padding: '0.65rem 1.6rem' }}
          data-testid="print-pass-btn"
        >
          🖨️ Print Yatra Pass
        </button>

        <button
          onClick={onReturnHome}
          className="btn btn-primary"
          style={{ padding: '0.65rem 2rem' }}
        >
          Return to Home Page ➔
        </button>
      </div>
    </div>
  );
}
