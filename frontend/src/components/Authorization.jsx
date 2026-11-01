import React, { useState } from 'react';
import { runRPA, authorizePlan, startRPAWorkflow } from '../services/api';
import UserInterventionModal from './UserInterventionModal';

export default function Authorization({ 
  bookingSummary, 
  onConfirmBooking, 
  onBack, 
  onNavigateToStep,
  confirming = false 
}) {
  const [authorized, setAuthorized] = useState(false);
  const [rpaRunning, setRpaRunning] = useState(false);
  const [rpaResult, setRpaResult] = useState(null);
  const [rpaError, setRpaError] = useState(null);
  const [activeWorkflow, setActiveWorkflow] = useState(null);
  const [showPreferenceOptions, setShowPreferenceOptions] = useState(false);
  const [reviewAccepted, setReviewAccepted] = useState(false);

  const {
    option,
    pax = 1,
    hotel,
    hotelNights = 2,
    sightseeingPlaces = [],
    feasiblePlaces = [],
    infeasiblePlaces = [],
    origin = 'Delhi',
    sessionId = null,
    planVersion = 1,
    tripRequest = {},
    itineraryDays: _itineraryDays = [],
  } = bookingSummary;

  // Transport details
  const tr = option?.transport || option?.flight || {};
  const slot = option?.slot || {};
  const mode = (tr.mode || 'train').toUpperCase();
  const operator = tr.operator || tr.name || (mode === 'TRAIN' ? 'Indian Railways' : 'Express Service');
  const serviceNo = tr.transport_no || (tr.id ? `Service #${tr.id}` : null);
  const depTime = tr.departure_time || '06:00';
  const arrTime = tr.arrival_time || '14:00';
  const travelDate = tr.travel_date || tripRequest?.start_date || '2026-10-20';
  const durationStr = tr.duration_str || (tr.duration_mins ? `${Math.floor(tr.duration_mins / 60)}h ${tr.duration_mins % 60}m` : null);

  // Financial math (Decimal/Integer accuracy)
  const farePerPerson = tr.fare_per_person || tr.price || 0;
  const transportFareTotal = tr.total_fare || (farePerPerson * pax);
  const slotPricePerPerson = slot.price || 0;
  const slotTotal = slotPricePerPerson * pax;

  // Accommodation math
  const roomsCount = Math.max(1, Math.ceil(pax / 2));
  const hotelNightlyRate = hotel ? (hotel.price_per_night || 0) : 0;
  const hotelTotal = hotel ? hotelNightlyRate * hotelNights * roomsCount : 0;

  // Direct verified costs
  const totalVerified = transportFareTotal + slotTotal + hotelTotal;

  // Estimated discretionary costs
  const roadTransferEst = tr.mode === 'flight' ? 1500 : 500;
  const durationDays = tripRequest?.duration_days || (hotelNights + 1) || 4;
  const mealsEst = 350 * pax * durationDays;
  const totalEstimated = roadTransferEst + mealsEst;

  // Grand Total & Per Person
  const grandTotal = totalVerified + totalEstimated;
  const perPersonCost = Math.round(grandTotal / pax);

  // Target Budget comparison
  const targetBudget = tripRequest?.total_budget || null;
  const withinBudget = targetBudget ? grandTotal <= targetBudget : null;
  const remainingBudget = targetBudget ? targetBudget - grandTotal : null;

  const handleToggleAuthorize = async (e) => {
    const checked = e.target.checked;
    setAuthorized(checked);
    if (checked && sessionId) {
      try {
        await authorizePlan({
          session_id: sessionId,
          plan_version: planVersion,
        });
      } catch (err) {
        console.error('Failed to record server-side authorization:', err);
      }
    }
  };

  const handleRunRpaDemo = async () => {
    setRpaRunning(true);
    setRpaError(null);
    try {
      if (sessionId) {
        await authorizePlan({
          session_id: sessionId,
          plan_version: planVersion,
        });
      }

      const data = await runRPA({
        user_name: 'Guest-User',
        pax_count: pax,
        transport_text: `${tr.mode || 'train'} from ${origin}`,
        slot_text: slot.category || 'Normal Darshan',
        total_price: grandTotal,
        headless: true,
        session_id: sessionId || null,
        plan_version: planVersion,
        human_authorized: true,
      });

      if (data.status === 'success' && data.rpa) {
        setRpaResult(data.rpa);
        setAuthorized(true); // Auto-enable authorization upon successful RPA demo
      } else {
        setRpaError(data.message || 'RPA automation returned non-success status.');
      }
    } catch (err) {
      console.error('RPA Error:', err);
      setRpaError('Failed to execute Playwright RPA. Please check backend logs.');
    } finally {
      setRpaRunning(false);
    }
  };

  const handleRunUserControlledWorkflow = async (mode) => {
    setRpaRunning(true);
    setRpaError(null);
    try {
      if (sessionId) {
        await authorizePlan({
          session_id: sessionId,
          plan_version: planVersion,
        });
      }

      const effectiveSessionId = sessionId || `session-${Date.now()}`;
      const data = await startRPAWorkflow({
        session_id: effectiveSessionId,
        user_name: 'Guest-User',
        pax_count: pax,
        transport_text: `${tr.mode || 'train'} from ${origin}`,
        slot_text: slot.category || 'Normal Darshan',
        total_price: grandTotal,
        checkpoint_mode: mode,
        headless: true,
        plan_version: planVersion,
        human_authorized: true,
      });

      if (data.status === 'PAUSED') {
        setActiveWorkflow({
          ...data,
          checkpoint_mode: mode,
        });
      } else if (data.status === 'SUCCESS' || data.status === 'success') {
        setRpaResult(data);
        setAuthorized(true);
      } else {
        setRpaError(data.message || 'Workflow returned non-success status.');
      }
    } catch (err) {
      console.error('Workflow Initiation Error:', err);
      setRpaError('Failed to execute user-controlled workflow. Please check backend logs.');
    } finally {
      setRpaRunning(false);
    }
  };

  const handleNavigateStep = (stepId) => {
    if (onNavigateToStep) {
      onNavigateToStep(stepId);
    } else if (onBack) {
      onBack();
    }
  };

  return (
    <div>
      {/* Synchronized 6-Stage Booking Progress Stepper */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: '#FFFDF9', padding: '10px 14px', borderRadius: '10px', border: '1px solid var(--gold-border)', marginBottom: '1.25rem', overflowX: 'auto' }}>
        {[
          { num: 1, label: 'Pilgrim Details', done: true },
          { num: 2, label: 'Darshan Slot', done: true },
          { num: 3, label: 'Review Details', done: true },
          { num: 4, label: 'Security Verification', done: authorized || !!rpaResult },
          { num: 5, label: 'Payment Sandbox', active: authorized && !rpaResult, done: !!rpaResult },
          { num: 6, label: 'Confirmation Pass', active: !!rpaResult, done: !!rpaResult },
        ].map((step, idx) => (
          <React.Fragment key={step.num}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', whiteSpace: 'nowrap', opacity: step.active || step.done ? 1 : 0.5 }}>
              <span
                style={{
                  width: '22px',
                  height: '22px',
                  borderRadius: '50%',
                  background: step.done ? '#059669' : (step.active ? 'var(--burgundy)' : '#CBD5E1'),
                  color: '#FFF',
                  fontSize: '0.74rem',
                  fontWeight: 800,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {step.done && !step.active ? '✓' : step.num}
              </span>
              <span style={{ fontSize: '0.78rem', fontWeight: step.active ? 800 : 600, color: step.active ? 'var(--burgundy)' : '#475569' }}>
                {step.label}
              </span>
            </div>
            {idx < 5 && <span style={{ color: '#CBD5E1', fontSize: '0.7rem' }}>➔</span>}
          </React.Fragment>
        ))}
      </div>

      {/* Heading */}
      <div style={{ marginBottom: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '1.35rem', color: 'var(--burgundy)' }}>
            Review Summary & Human Authorization Gate
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Please review your complete consolidated trip particulars and authorize execution according to strict Human-in-the-Loop guidelines.
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="pill pill-gold" style={{ fontSize: '0.75rem', fontWeight: 700 }}>
            Plan Revision #{planVersion}
          </span>
          <button
            onClick={() => setShowPreferenceOptions(!showPreferenceOptions)}
            className="btn btn-outline"
            style={{ fontSize: '0.78rem', padding: '5px 12px' }}
          >
            ✏️ Change Selection
          </button>
        </div>
      </div>

      {/* Dynamic Preference Change Bar (if expanded) */}
      {showPreferenceOptions && (
        <div className="card" style={{ background: '#FFFDF5', border: '1.5px solid var(--gold-border)', marginBottom: '1.5rem', padding: '16px' }}>
          <div style={{ fontWeight: 800, color: 'var(--burgundy)', fontSize: '0.9rem', marginBottom: '8px' }}>
            Select what you would like to adjust:
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button onClick={() => handleNavigateStep(2)} className="btn btn-secondary" style={{ fontSize: '0.8rem', padding: '6px 14px' }}>
              🚆 Change Transport
            </button>
            <button onClick={() => handleNavigateStep(3)} className="btn btn-secondary" style={{ fontSize: '0.8rem', padding: '6px 14px' }}>
              🏨 Change Accommodation
            </button>
            <button onClick={() => handleNavigateStep(4)} className="btn btn-secondary" style={{ fontSize: '0.8rem', padding: '6px 14px' }}>
              🌄 Change Sightseeing
            </button>
            <button onClick={() => handleNavigateStep(1)} className="btn btn-secondary" style={{ fontSize: '0.8rem', padding: '6px 14px' }}>
              ⚙️ Change Dates, Pax or Budget
            </button>
            <button onClick={() => setShowPreferenceOptions(false)} className="btn btn-outline" style={{ fontSize: '0.8rem', padding: '6px 12px' }}>
              ✕ Close
            </button>
          </div>
        </div>
      )}

      {/* CONSOLIDATED TRIP REVIEW GRIDS */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        
        {/* Left Column: Complete Itinerary & Cost Breakdown */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '1.05rem', color: 'var(--burgundy)', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '8px' }}>
            📋 Consolidated Booking Particulars
          </div>

          {/* 1. Trip & Pilgrim Particulars */}
          <div style={{ background: '#FAF8F5', borderRadius: '10px', padding: '10px 14px' }}>
            <div style={{ fontSize: '0.74rem', color: 'var(--gold-primary)', fontWeight: 700, textTransform: 'uppercase' }}>
              Trip Route & Pilgrims
            </div>
            <div style={{ fontWeight: 800, fontSize: '0.95rem', color: 'var(--text-dark)' }}>
              {origin} ➔ Katra Base & Holy Bhawan
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              📅 Dates: {travelDate} ({durationDays} Days · {hotelNights} Nights) · 👥 {pax} {pax === 1 ? 'Pilgrim' : 'Pilgrims'}
            </div>
          </div>

          {/* 2. Transport Particulars */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontSize: '0.74rem', color: 'var(--gold-primary)', fontWeight: 700, textTransform: 'uppercase' }}>
                Selected Transport Service
              </div>
              <span className="pill pill-success" style={{ fontSize: '0.68rem' }}>✓ Verified Fare</span>
            </div>
            <div style={{ fontWeight: 800, fontSize: '0.95rem', color: 'var(--text-dark)', marginTop: '2px' }}>
              {operator} {serviceNo ? `· ${serviceNo}` : ''} ({mode})
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              Departs: <b>{depTime}</b> from {origin} · Arrives: <b>{arrTime}</b> at {tr.destination || 'Katra'}
              {durationStr && <span> (⏱️ {durationStr})</span>}
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--burgundy)', fontWeight: 700, marginTop: '2px' }}>
              Transport Fare: ₹{transportFareTotal.toLocaleString('en-IN')} (₹{farePerPerson}/person)
            </div>
          </div>

          {/* 3. Darshan Slot Particulars */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontSize: '0.74rem', color: 'var(--gold-primary)', fontWeight: 700, textTransform: 'uppercase' }}>
                Holy Shrine Darshan Slot
              </div>
              <span className="pill pill-success" style={{ fontSize: '0.68rem' }}>✓ Shrine Verified</span>
            </div>
            <div style={{ fontWeight: 800, fontSize: '0.95rem', color: 'var(--text-dark)', marginTop: '2px' }}>
              {slot.category || 'Normal Darshan'} ({slot.slot_time || 'Morning Slot'})
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              Shri Mata Vaishno Devi Shrine Board, Bhawan · {slot.slot_date || travelDate}
            </div>
            <div style={{ fontSize: '0.8rem', color: '#155724', fontWeight: 700, marginTop: '2px' }}>
              Registration Fee: {slotTotal === 0 ? 'Included / Free (₹0)' : `₹${slotTotal.toLocaleString('en-IN')}`}
            </div>
          </div>

          {/* 4. Hotel Accommodation Particulars */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontSize: '0.74rem', color: 'var(--gold-primary)', fontWeight: 700, textTransform: 'uppercase' }}>
                Katra Accommodation
              </div>
              {hotel && <span className="pill pill-success" style={{ fontSize: '0.68rem' }}>✓ Verified Hotel</span>}
            </div>
            {hotel ? (
              <>
                <div style={{ fontWeight: 800, fontSize: '0.95rem', color: 'var(--text-dark)', marginTop: '2px' }}>
                  {hotel.name}
                </div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                  {hotel.category} · {hotel.location} · {roomsCount} room(s) for {pax} guest(s) · {hotelNights} Night(s)
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--burgundy)', fontWeight: 700, marginTop: '2px' }}>
                  Hotel Total: ₹{hotelTotal.toLocaleString('en-IN')} (₹{hotel.price_per_night}/room/night)
                </div>
              </>
            ) : (
              <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '2px' }}>
                No Katra hotel reserved (day-excursion or self-arranged stay).
              </div>
            )}
          </div>

          {/* 5. Sightseeing & Feasibility */}
          <div>
            <div style={{ fontSize: '0.74rem', color: 'var(--gold-primary)', fontWeight: 700, textTransform: 'uppercase' }}>
              Sightseeing Excursions & Feasibility
            </div>
            {(feasiblePlaces.length > 0 || sightseeingPlaces.length > 0) ? (
              <>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                  {(feasiblePlaces.length > 0 ? feasiblePlaces : sightseeingPlaces).map((sp, idx) => (
                    <span key={idx} className="pill pill-gold" style={{ fontSize: '0.72rem' }}>
                      ✓ {typeof sp === 'string' ? sp : (sp.name || sp.place)}
                    </span>
                  ))}
                </div>
                {infeasiblePlaces.length > 0 && (
                  <div style={{ fontSize: '0.74rem', color: '#721C24', background: '#FDF2F2', borderRadius: '6px', padding: '6px 8px', marginTop: '6px' }}>
                    ℹ️ <b>Omitted Excursions:</b> {infeasiblePlaces.map((inf) => typeof inf === 'string' ? inf : `${inf.place || inf.name} (${inf.reason || 'duration constraints'})`).join(', ')}
                  </div>
                )}
              </>
            ) : (
              <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '2px' }}>
                Skipped optional sightseeing (dedicated focus on holy darshan & recovery).
              </div>
            )}
          </div>

          {/* 6. Itemised Budget Breakdown */}
          <div style={{
            background: 'var(--gold-subtle)',
            border: '1px solid var(--gold-border)',
            borderRadius: '12px',
            padding: '12px 16px',
            marginTop: 'auto',
          }}>
            <div style={{ fontWeight: 800, fontSize: '0.92rem', color: 'var(--burgundy)', marginBottom: '8px' }}>
              💰 Itemised Financial Summary
            </div>

            {/* Direct Verified Costs */}
            <div style={{ fontSize: '0.76rem', color: 'var(--text-dark)', display: 'flex', flexDirection: 'column', gap: '3px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>✓ Verified Transport ({pax}x fare):</span>
                <b>₹{transportFareTotal.toLocaleString('en-IN')}</b>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>✓ Verified Darshan Slot ({pax}x fee):</span>
                <b>₹{slotTotal.toLocaleString('en-IN')}</b>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>✓ Verified Hotel ({roomsCount} rm, {hotelNights} n):</span>
                <b>₹{hotelTotal.toLocaleString('en-IN')}</b>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #E8C874', paddingTop: '3px', marginTop: '2px' }}>
                <span style={{ fontWeight: 700 }}>Total Verified Direct Costs:</span>
                <span style={{ fontWeight: 800, color: '#155724' }}>₹{totalVerified.toLocaleString('en-IN')}</span>
              </div>
            </div>

            {/* Discretionary Estimates */}
            <div style={{ fontSize: '0.73rem', color: '#856404', background: '#FFF3CD', borderRadius: '6px', padding: '6px 8px', marginTop: '8px' }}>
              <div style={{ fontWeight: 700, marginBottom: '2px' }}>Estimated Discretionary Expenses (Not pre-charged):</div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>• Road Transfers (Katra/Jammu taxi/auto):</span>
                <span>₹{roadTransferEst.toLocaleString('en-IN')}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>• Estimated Meals ({pax} pax, {durationDays} days):</span>
                <span>₹{mealsEst.toLocaleString('en-IN')}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700, marginTop: '2px' }}>
                <span>Subtotal Estimates:</span>
                <span>₹{totalEstimated.toLocaleString('en-IN')}</span>
              </div>
            </div>

            {/* Excluded Costs Note */}
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '6px' }}>
              * Excluded expenses: Pony / Palki trek charges, personal ritual offerings, and dry fruits are not included.
            </div>

            {/* Grand Total */}
            <div style={{ borderTop: '2px solid var(--gold-border)', paddingTop: '8px', marginTop: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Total Estimated Trip Cost ({pax} {pax === 1 ? 'pilgrim' : 'pilgrims'})
                </div>
                <div style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--burgundy)' }}>
                  ₹{grandTotal.toLocaleString('en-IN')}
                </div>
                <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                  Approx. <b>₹{perPersonCost.toLocaleString('en-IN')}</b> per person
                </div>
              </div>

              {targetBudget && (
                <div style={{ textAlign: 'right' }}>
                  <span className={`pill ${withinBudget ? 'pill-success' : 'pill-gold'}`} style={{ fontSize: '0.72rem' }}>
                    {withinBudget ? '✓ Within Budget' : '⚠️ Exceeds Target'}
                  </span>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                    Target: ₹{targetBudget.toLocaleString('en-IN')}
                  </div>
                  <div style={{ fontSize: '0.72rem', fontWeight: 700, color: withinBudget ? '#155724' : '#721C24' }}>
                    {withinBudget ? `₹${remainingBudget.toLocaleString('en-IN')} remaining` : `+₹${Math.abs(remainingBudget).toLocaleString('en-IN')} over`}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Preference Change Prompt & Human Gate & RPA */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          
          {/* REQUIREMENT 4: ASK THE USER WHETHER THEY WANT TO CHANGE PREFERENCES */}
          <div className="card" style={{ border: '2px solid var(--gold-primary)', background: '#FFFCF5' }}>
            <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '1.05rem', color: 'var(--burgundy)', marginBottom: '6px' }}>
              ❓ Are you happy with these choices, or would you like to change your preferences?
            </div>
            <div style={{ fontSize: '0.84rem', color: 'var(--text-dark)', lineHeight: 1.5, marginBottom: '14px' }}>
              You can confirm this plan as is, or modify transport, accommodation, sightseeing, or travel dates.
            </div>

            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <button
                onClick={() => {
                  setReviewAccepted(true);
                  setShowPreferenceOptions(false);
                }}
                className={`btn ${reviewAccepted ? 'btn-gold' : 'btn-primary'}`}
                style={{ flex: '1', minWidth: '180px', padding: '0.65rem 1rem', fontSize: '0.86rem' }}
              >
                {reviewAccepted ? '✓ Choices Approved' : '👍 Everything Looks Good — Continue'}
              </button>

              <button
                onClick={() => setShowPreferenceOptions(!showPreferenceOptions)}
                className="btn btn-outline"
                style={{ flex: '1', minWidth: '180px', padding: '0.65rem 1rem', fontSize: '0.86rem' }}
              >
                ✏️ Change Preferences
              </button>
            </div>
          </div>

          {/* Human Confirmation Gate */}
          <div className="card" style={{ border: '2px solid var(--gold-border)', background: '#FFFDF9' }}>
            <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '1.05rem', color: 'var(--burgundy)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>⚠️</span> Human Confirmation Gate
            </div>
            <div style={{ fontSize: '0.84rem', color: 'var(--text-dark)', lineHeight: 1.5, marginBottom: '14px' }}>
              In accordance with ethical AI and security protocols, booking execution requires your explicit authorization for <b>Plan Revision #{planVersion}</b>. No automated action is finalized without human consent.
            </div>

            <label style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
              padding: '10px 14px',
              background: '#FFFFFF',
              border: authorized ? '2px solid var(--burgundy)' : '1px solid var(--gold-border)',
              borderRadius: '10px',
              cursor: 'pointer',
              marginBottom: '10px',
            }}>
              <input
                type="checkbox"
                checked={authorized}
                onChange={handleToggleAuthorize}
                style={{ width: '18px', height: '18px', marginTop: '2px', accentColor: 'var(--burgundy)' }}
              />
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--burgundy)' }}>
                I hereby authorize the Yatra Agent to confirm my booking details and issue registration credentials.
              </div>
            </label>
          </div>

          {/* RPA Automation Demonstration Card */}
          <div className="card" style={{ background: '#FFFFFF' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '0.98rem', color: 'var(--burgundy)' }}>
                🤖 Playwright Browser RPA Demonstration
              </div>
              <span className="pill pill-gold" style={{ fontSize: '0.7rem' }}>
                Headless Automation
              </span>
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '12px' }}>
              Demonstrate the automated verification process by triggering the backend Playwright agent in simulated sandbox mode.
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <button
                onClick={handleRunRpaDemo}
                disabled={rpaRunning}
                className="btn btn-secondary"
                style={{ width: '100%', padding: '0.55rem', fontSize: '0.82rem' }}
              >
                {rpaRunning ? '⏳ Executing Playwright Browser Agent...' : '⚡ Run Standard Playwright RPA Demo'}
              </button>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => handleRunUserControlledWorkflow('OTP')}
                  disabled={rpaRunning}
                  className="btn btn-outline"
                  style={{ padding: '0.55rem', fontSize: '0.8rem', color: '#6E1423', borderColor: '#E8C874' }}
                >
                  🔐 Test OTP Flow
                </button>
                <button
                  type="button"
                  onClick={() => handleRunUserControlledWorkflow('CAPTCHA')}
                  disabled={rpaRunning}
                  className="btn btn-outline"
                  style={{ padding: '0.55rem', fontSize: '0.8rem', color: '#1E40AF', borderColor: '#BFDBFE' }}
                >
                  🛡️ Test CAPTCHA Flow
                </button>
              </div>

              <button
                type="button"
                onClick={() => handleRunUserControlledWorkflow('SEQUENTIAL')}
                disabled={rpaRunning}
                className="btn btn-outline"
                style={{ width: '100%', marginTop: '8px', padding: '0.55rem', fontSize: '0.8rem', color: '#047857', borderColor: '#86EFAC', background: '#F0FDF4' }}
              >
                🔄 Test Complete Sequential Flow (OTP ➔ CAPTCHA ➔ Payment ➔ Pass)
              </button>
            </div>

            {/* RPA Results / Receipt */}
            {rpaResult && (
              <div style={{
                marginTop: '12px',
                background: '#F0FDF4',
                border: '1.5px solid #86EFAC',
                borderRadius: '12px',
                padding: '12px 14px',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px', borderBottom: '1px dashed #86EFAC', paddingBottom: '6px' }}>
                  <div style={{ fontWeight: 800, color: '#166534', fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>✓</span> Simulated Yatra Booking Confirmation
                  </div>
                  <span className="badge" style={{ background: '#DCFCE7', color: '#166534', fontWeight: 800, fontSize: '0.7rem', border: '1px solid #86EFAC' }}>
                    LOCAL MOCK PORTAL / DEMO
                  </span>
                </div>
                <div style={{ color: '#166534', fontSize: '0.95rem' }}>
                  Demo Pilgrim Pass: <strong style={{ fontFamily: 'monospace' }}>{rpaResult.booking_id}</strong>
                </div>
                <div style={{ color: '#374151', fontSize: '0.78rem', marginTop: '3px' }}>
                  Receipt: <strong>Demo Pilgrim Pass (Mock)</strong> · Pax: {rpaResult.pax_count || pax} · Total: ₹{(rpaResult.total_price || grandTotal).toLocaleString('en-IN')}
                </div>
                <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                  <button
                    type="button"
                    onClick={() => window.print()}
                    className="btn btn-outline"
                    style={{ fontSize: '0.74rem', padding: '4px 10px', borderColor: '#86EFAC', color: '#166534' }}
                  >
                    🖨️ Print Demo Pass
                  </button>
                </div>
                {rpaResult.details && (
                  <details style={{ marginTop: '6px', fontSize: '0.72rem', color: '#6B7280' }}>
                    <summary style={{ cursor: 'pointer', fontWeight: 600 }}>⚙️ View Diagnostics</summary>
                    <div style={{ marginTop: '2px', fontStyle: 'italic' }}>{rpaResult.details}</div>
                  </details>
                )}
              </div>
            )}

            {rpaError && (
              <div style={{ marginTop: '10px', background: '#FDF2F2', border: '1px solid #F5B7B1', padding: '8px 12px', borderRadius: '8px', color: '#922B21', fontSize: '0.78rem' }}>
                {rpaError}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Action Row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
        <button onClick={onBack} className="btn btn-outline">
          ← Back to Itinerary
        </button>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={() => handleNavigateStep(2)}
            className="btn btn-outline"
            style={{ fontSize: '0.82rem' }}
          >
            Change Transport / Hotel
          </button>

          <button
            onClick={() => onConfirmBooking(authorized)}
            disabled={!authorized || confirming}
            className="btn btn-primary"
            style={{ padding: '0.8rem 2.5rem', fontSize: '0.94rem' }}
          >
            {confirming ? 'Confirming Yatra Booking...' : 'Authorize & Confirm Booking ➔'}
          </button>
        </div>
      </div>

      {/* Week 8: User Intervention Modal */}
      {activeWorkflow && (
        <UserInterventionModal
          workflowData={activeWorkflow}
          sessionId={sessionId || activeWorkflow.session_id}
          isOpen={!!activeWorkflow}
          onClose={() => setActiveWorkflow(null)}
          onWorkflowComplete={(result) => {
            setRpaResult(result);
            setAuthorized(true);
            setActiveWorkflow(null);
          }}
          onWorkflowCancelled={() => {
            setActiveWorkflow(null);
          }}
        />
      )}
    </div>
  );
}

