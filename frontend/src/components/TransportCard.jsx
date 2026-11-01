import React from 'react';

export default function TransportCard({ option, pax = 1, isSelected, onSelect }) {
  const tr = option.transport || option.flight || {};
  const slot = option.slot || {};
  const mode = (tr.mode || 'train').toUpperCase();
  const operator = tr.operator || tr.name || (mode === 'TRAIN' ? 'Indian Railways' : 'Express Service');
  const serviceNo = tr.transport_no || (tr.id ? `ID #${tr.id}` : null);
  const depTime = tr.departure_time || '06:00';
  const travelDate = tr.travel_date || null;
  const origin = tr.origin || 'Delhi';
  const dest = tr.destination || 'Katra';
  const isConnecting = option.is_connecting || tr.is_connecting;

  // Calculate arrival time and duration if not provided
  let calculatedArrTime = tr.arrival_time;
  if (!calculatedArrTime && tr.departure_time && tr.duration_mins) {
    try {
      const [dh, dm] = tr.departure_time.split(':').map(Number);
      const totalMinutes = dh * 60 + dm + Number(tr.duration_mins);
      const arrHour = Math.floor((totalMinutes / 60) % 24);
      const arrMin = totalMinutes % 60;
      const daysLater = Math.floor(totalMinutes / (24 * 60));
      calculatedArrTime = `${String(arrHour).padStart(2, '0')}:${String(arrMin).padStart(2, '0')}${daysLater > 0 ? ` (+${daysLater}d)` : ''}`;
    } catch {
      calculatedArrTime = tr.departure_time;
    }
  }
  const arrTime = calculatedArrTime || '14:00';

  const durationStr = tr.duration_str || (tr.duration_mins ? `${Math.floor(tr.duration_mins / 60)}h ${tr.duration_mins % 60}m` : null);

  // Fares segregation
  const farePerPerson = tr.fare_per_person || tr.price || 0;
  const transportFareTotal = tr.total_fare || (farePerPerson * pax);
  const slotPricePerPerson = slot.price || 0;
  const slotTotal = slotPricePerPerson * pax;
  const bundleTotal = option.total_price || (transportFareTotal + slotTotal);
  const bundleExplanation = option.bundle_explanation || `Includes ${mode.toLowerCase()} fare for ${pax} ${pax === 1 ? 'pilgrim' : 'pilgrims'} and confirmed darshan slot registration.`;

  return (
    <div
      className="card card-hover transport-card"
      data-testid="transport-card"
      style={{
        border: isSelected ? '2px solid var(--gold-primary)' : '1px solid var(--gold-border)',
        background: isSelected ? '#FFFCF7' : '#FFFFFF',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        gap: '12px',
        position: 'relative',
      }}
    >
      {/* Header Badge */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span className="pill pill-gold">
              {mode === 'FLIGHT' ? '✈️ FLIGHT' : (mode === 'BUS' ? '🚌 BUS' : '🚆 TRAIN')}
            </span>
            <span style={{ fontWeight: 800, fontSize: '0.92rem', color: 'var(--burgundy)' }}>
              {operator}
            </span>
            {serviceNo && (
              <span className="pill" style={{ background: '#F0EAE1', color: 'var(--burgundy)', fontSize: '0.74rem', fontWeight: 700 }}>
                {serviceNo}
              </span>
            )}
          </div>
          {travelDate && (
            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '3px' }}>
              📅 Travel Date: <b>{travelDate}</b>
            </div>
          )}
        </div>
        {isConnecting && (
          <span className="pill" style={{ background: '#FFF3CD', color: '#856404', fontSize: '0.72rem' }}>
            🔄 Via {tr.connecting_hub || 'Hub'}
          </span>
        )}
      </div>

      {/* Route & Times */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto 1fr',
        alignItems: 'center',
        padding: '0.5rem 0',
        borderBottom: '1px solid var(--border-subtle)',
      }}>
        <div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-dark)' }}>
            {depTime}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>
            {origin}
          </div>
        </div>

        <div style={{ textAlign: 'center', padding: '0 0.8rem' }}>
          {durationStr && (
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 700, marginBottom: '2px' }}>
              ⏱️ {durationStr}
            </div>
          )}
          <div style={{ color: 'var(--gold-primary)', fontSize: '0.85rem' }}>
            ──────── ➔
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-dark)' }}>
            {arrTime}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>
            {dest}
          </div>
        </div>
      </div>

      {/* Yatra Slot Bundle */}
      <div style={{
        background: 'var(--gold-subtle)',
        border: '1px solid var(--gold-border)',
        borderRadius: '10px',
        padding: '8px 12px',
        fontSize: '0.8rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <div>
          <span style={{ fontWeight: 700, color: 'var(--burgundy)' }}>
            🔱 Yatra Slot:
          </span>{' '}
          {slot.category || 'Normal Darshan'} ({slot.slot_time || 'Morning Slot'})
          {slot.slot_date && <span style={{ color: 'var(--text-muted)' }}> · {slot.slot_date}</span>}
        </div>
        <span style={{ fontWeight: 700, color: '#155724' }}>
          {slotPricePerPerson > 0 ? `+₹${slotTotal}` : '✓ Free'}
        </span>
      </div>

      {/* Transparent Price Breakdown */}
      <div style={{
        background: '#FAF8F5',
        borderRadius: '8px',
        padding: '8px 10px',
        fontSize: '0.76rem',
        color: 'var(--text-dark)',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: 'var(--text-muted)' }}>Transport Fare ({pax}x ₹{farePerPerson}):</span>
          <span style={{ fontWeight: 700 }}>₹{transportFareTotal.toLocaleString('en-IN')}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: 'var(--text-muted)' }}>Darshan Registration:</span>
          <span style={{ fontWeight: 700, color: slotTotal === 0 ? '#155724' : 'var(--text-dark)' }}>
            {slotTotal === 0 ? 'Included (₹0)' : `₹${slotTotal.toLocaleString('en-IN')}`}
          </span>
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontStyle: 'italic', borderTop: '1px dashed #DDD', paddingTop: '4px', marginTop: '2px' }}>
          ℹ️ {bundleExplanation}
        </div>
      </div>

      {/* Total & Action */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '4px' }}>
        <div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Total Bundle ({pax} {pax === 1 ? 'pilgrim' : 'pilgrims'})
          </div>
          <div style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--burgundy)' }}>
            ₹{bundleTotal.toLocaleString('en-IN')}
          </div>
        </div>

        <button
          onClick={onSelect}
          className={`btn ${isSelected ? 'btn-gold' : 'btn-primary'}`}
          style={{ padding: '0.5rem 1.4rem', fontSize: '0.82rem' }}
        >
          {isSelected ? '✓ Selected Option' : 'Select Option ➔'}
        </button>
      </div>
    </div>
  );
}
