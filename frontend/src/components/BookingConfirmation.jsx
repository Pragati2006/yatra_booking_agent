import React from 'react';
import { generatePilgrimPassPDF } from '../utils/pdfGenerator';

export default function BookingConfirmation({ confirmationData, bookingSummary, onReturnHome, onStartNewBooking }) {
  // Safety Invariant: Do not generate or display a successful pass for failed, incomplete or expired workflows
  if (!confirmationData || !confirmationData.booking_id) {
    return (
      <div
        data-testid="no-confirmed-booking-notice"
        className="card"
        style={{
          maxWidth: '680px',
          margin: '3rem auto',
          textAlign: 'center',
          padding: '2.5rem 2rem',
          border: '1.5px solid var(--gold-border, #E5D2AD)',
          borderRadius: '16px',
        }}
      >
        <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>⚠️</div>
        <h2 style={{ fontFamily: 'var(--font-serif)', color: 'var(--burgundy, #58111A)', marginBottom: '0.75rem' }}>
          No Active Confirmed Booking
        </h2>
        <p style={{ color: 'var(--text-muted, #6B7280)', fontSize: '0.92rem', lineHeight: 1.6, maxWidth: '520px', margin: '0 auto 1.5rem' }}>
          Pass generation and confirmation documents are strictly available only for completed, verified booking workflows. Please complete the booking review and RPA verification process first.
        </p>
        <button
          onClick={onReturnHome}
          className="btn btn-primary"
          style={{ padding: '0.75rem 2rem' }}
        >
          Return to Booking Portal ➔
        </button>
      </div>
    );
  }

  const { booking_id, message, receipt } = confirmationData;
  const { option, pax = 1, hotel, hotelNights = 2, origin = 'Delhi', tripRequest } = bookingSummary || {};

  const tr = option?.transport || option?.flight || {};
  const slot = option?.slot || {};
  const mode = (tr.mode || 'Train').toUpperCase();
  const operator = tr.operator || tr.name || 'Express Service';
  const depTime = tr.departure_time || '06:00';
  const travelDate = tr.travel_date || tripRequest?.start_date || '2026-10-20';
  const slotCategory = slot.category || confirmationData.category || 'Normal Darshan';
  const slotTime = slot.slot_time || confirmationData.slot_time || 'Morning Slot (06:00)';
  const hotelName = hotel ? hotel.name : 'Self-arranged Katra stay';
  const totalAmount = confirmationData.total_price || bookingSummary?.total_price || receipt?.total_price || 16092;

  const handleDownload = () => {
    generatePilgrimPassPDF(confirmationData, bookingSummary);
  };

  return (
    <div
      data-testid="step-4-confirmation-page"
      className="pilgrim-pass-container"
      style={{ maxWidth: '820px', margin: '0 auto', paddingTop: '1rem', paddingBottom: '3rem' }}
    >
      {/* Required Document Disclaimer Banner */}
      <div
        data-testid="mock-portal-disclaimer-banner"
        style={{
          background: '#FEF3C7',
          border: '1.5px solid #F59E0B',
          borderRadius: '12px',
          padding: '10px 16px',
          color: '#92400E',
          fontSize: '0.82rem',
          fontWeight: 700,
          textAlign: 'center',
          letterSpacing: '0.04em',
          marginBottom: '1.5rem',
          boxShadow: '0 2px 6px rgba(245, 158, 11, 0.1)',
        }}
      >
        ⚠️ DEMO — LOCAL MOCK PORTAL — NOT AN OFFICIAL SHRINE BOARD BOOKING
      </div>

      {/* Main Success Banner */}
      <div
        className="pilgrim-pass-banner"
        style={{
          background: 'linear-gradient(135deg, #58111A 0%, #3D0810 100%)',
          border: '2px solid var(--gold-primary, #C5A059)',
          borderRadius: '20px',
          padding: '2.5rem 2rem',
          color: '#FFFFFF',
          textAlign: 'center',
          boxShadow: '0 12px 32px rgba(88, 17, 26, 0.25)',
          marginBottom: '2rem',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div style={{ fontSize: '3rem', marginBottom: '8px' }}>🔱</div>
        <div
          className="pilgrim-pass-title"
          style={{
            fontFamily: 'var(--font-serif)',
            fontSize: '2rem',
            fontWeight: 800,
            color: '#FBF9F4',
            letterSpacing: '0.04em',
          }}
        >
          JAI MATA DI! BOOKING CONFIRMED
        </div>
        <div className="pilgrim-pass-subtitle" style={{ color: '#E5D2AD', fontSize: '0.92rem', marginTop: '6px' }}>
          Your pilgrimage registration has been officially confirmed via automated mock RPA execution
        </div>

        {/* Unique Booking Reference Box */}
        <div
          data-testid="booking-reference-box"
          className="pilgrim-pass-ref-box"
          style={{
            display: 'inline-block',
            background: 'rgba(255, 255, 255, 0.12)',
            border: '2px dashed var(--gold-primary, #C5A059)',
            borderRadius: '14px',
            padding: '12px 28px',
            marginTop: '1.5rem',
          }}
        >
          <div className="pilgrim-pass-ref-label" style={{ fontSize: '0.74rem', color: '#E5D2AD', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
            Official Booking Reference ID
          </div>
          <div
            data-testid="confirmed-booking-reference-id"
            className="pilgrim-pass-ref-id"
            style={{ fontSize: '1.9rem', fontWeight: 800, color: '#FFFFFF', letterSpacing: '0.08em', fontFamily: 'monospace', marginTop: '4px' }}
          >
            {booking_id}
          </div>
        </div>

        {/* Divine Blessing */}
        {message && (
          <div
            className="pilgrim-pass-blessing"
            style={{
              fontSize: '0.92rem',
              color: '#F5ECDA',
              fontStyle: 'italic',
              marginTop: '1.25rem',
              lineHeight: 1.5,
              maxWidth: '600px',
              marginInline: 'auto',
            }}
          >
            "{message}"
          </div>
        )}
      </div>

      {/* Summary Pass Card */}
      <div
        data-testid="demo-pilgrim-pass-full-card"
        className="card pilgrim-pass-card"
        style={{
          padding: '2rem',
          marginBottom: '2rem',
          border: '1.5px solid var(--gold-border, #E5D2AD)',
          borderRadius: '16px',
          background: '#FFFFFF',
          boxShadow: '0 6px 20px rgba(88, 17, 26, 0.05)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1.5px solid var(--border-subtle, #F0E6D8)',
            paddingBottom: '12px',
            marginBottom: '18px',
            flexWrap: 'wrap',
            gap: '8px',
          }}
        >
          <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '1.25rem', color: 'var(--burgundy, #58111A)' }}>
            🎫 Demo Pilgrim Yatra Pass Particulars
          </div>
          <span
            className="badge"
            style={{
              background: '#DCFCE7',
              color: '#166534',
              border: '1px solid #86EFAC',
              fontWeight: 800,
              fontSize: '0.74rem',
              padding: '4px 10px',
              borderRadius: '12px',
            }}
          >
            ✓ MOCK RPA VERIFIED
          </span>
        </div>

        <div
          className="pilgrim-pass-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '18px',
          }}
        >
          <div>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
              Travel Route & Operator
            </div>
            <div style={{ fontWeight: 800, fontSize: '1rem', color: 'var(--text-dark, #2D3748)', marginTop: '2px' }}>
              {origin} ➔ Katra
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              {operator} ({mode}) · Departs {depTime}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
              Shrine Darshan Slot & Date
            </div>
            <div style={{ fontWeight: 800, fontSize: '1rem', color: 'var(--text-dark, #2D3748)', marginTop: '2px' }}>
              {slotCategory}
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              Date: {travelDate} · {slotTime}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
              Pilgrims Count
            </div>
            <div style={{ fontWeight: 800, fontSize: '1rem', color: 'var(--text-dark, #2D3748)', marginTop: '2px' }}>
              {pax} {Number(pax) === 1 ? 'Pilgrim' : 'Pilgrims'}
            </div>
            <div style={{ fontSize: '0.82rem', color: '#166534', fontWeight: 600 }}>
              Identity & Devotee Record Verified
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
              Confirmed Katra Stay
            </div>
            <div style={{ fontWeight: 800, fontSize: '1rem', color: 'var(--text-dark, #2D3748)', marginTop: '2px' }}>
              {hotelName}
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              {hotel ? `${hotelNights} Nights Reserved` : 'Self-Arranged Lodging'}
            </div>
          </div>

          <div data-testid="simulated-payment-notice">
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
              Simulated Payment Status
            </div>
            <div style={{ fontWeight: 800, fontSize: '1.05rem', color: '#047857', marginTop: '2px' }}>
              ₹{Number(totalAmount).toLocaleString('en-IN')}
            </div>
            <div style={{ fontSize: '0.8rem', color: '#059669', fontWeight: 700 }}>
              Sandbox Mode (₹0 Live Charge)
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
              Security Checkpoints
            </div>
            <div style={{ fontWeight: 800, fontSize: '0.92rem', color: '#166534', marginTop: '2px' }}>
              OTP Verified ✓
            </div>
            <div style={{ fontSize: '0.82rem', color: '#166534', fontWeight: 700 }}>
              CAPTCHA Challenge Solved ✓
            </div>
          </div>
        </div>

        {/* RFID Access Card Notice */}
        <div
          className="pilgrim-pass-rfid-notice"
          style={{
            marginTop: '1.5rem',
            padding: '12px 16px',
            background: '#F0FDF4',
            border: '1.5px solid #BBF7D0',
            borderRadius: '12px',
            fontSize: '0.84rem',
            color: '#166534',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            lineHeight: 1.5,
          }}
        >
          <span style={{ fontSize: '1.25rem' }}>🎫</span>
          <div>
            <b>RFID Access Card Instruction:</b> Please present this official booking reference (<b>{booking_id}</b>) at the Katra Yatra Registration Counter / Banganga Checkpost to obtain physical Shrine Board RFID Yatra Access Cards before starting the Holy Bhawan trek.
          </div>
        </div>
      </div>

      {/* Action Buttons Row */}
      <div
        className="no-print"
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '12px',
          flexWrap: 'wrap',
        }}
      >
        <button
          type="button"
          data-testid="download-pass-btn"
          onClick={handleDownload}
          className="btn btn-primary"
          style={{
            padding: '0.75rem 1.8rem',
            fontSize: '0.92rem',
            fontWeight: 700,
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span>📄</span> Download Pass (PDF)
        </button>

        <button
          type="button"
          data-testid="print-pass-btn"
          onClick={() => window.print()}
          className="btn btn-outline"
          style={{
            padding: '0.75rem 1.8rem',
            fontSize: '0.92rem',
            fontWeight: 700,
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span>🖨️</span> Print Pass
        </button>

        {onStartNewBooking && (
          <button
            type="button"
            data-testid="book-another-yatra-btn"
            onClick={onStartNewBooking}
            className="btn btn-outline"
            style={{
              padding: '0.75rem 1.6rem',
              fontSize: '0.92rem',
              fontWeight: 700,
            }}
          >
            🔄 Plan Another Yatra
          </button>
        )}

        <button
          type="button"
          onClick={onReturnHome}
          className="btn btn-outline"
          style={{
            padding: '0.75rem 1.6rem',
            fontSize: '0.92rem',
          }}
        >
          Return to Home Page
        </button>
      </div>
    </div>
  );
}
