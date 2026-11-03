import React, { useState } from 'react';
import { authorizePlan, startRPAWorkflow } from '../services/api';
import UserInterventionModal from './UserInterventionModal';

const WORKFLOW_STAGES = [
  { id: 1, name: 'Booking Details', key: 'DETAILS' },
  { id: 2, name: 'Booking Review', key: 'REVIEW' },
  { id: 3, name: 'OTP Verification', key: 'OTP' },
  { id: 4, name: 'CAPTCHA Verification', key: 'CAPTCHA' },
  { id: 5, name: 'Simulated Payment', key: 'PAYMENT' },
  { id: 6, name: 'Booking Confirmation', key: 'CONFIRMATION' },
  { id: 7, name: 'Demo Pilgrim Pass', key: 'PASS' },
];

const TONE_STYLES = {
  success: { bg: '#DCFCE7', color: '#166534', border: '#86EFAC', circleBg: '#059669' },
  info: { bg: '#EFF6FF', color: '#1E40AF', border: '#93C5FD', circleBg: '#2563EB' },
  warning: { bg: '#FEF3C7', color: '#92400E', border: '#FCD34D', circleBg: '#D97706' },
  danger: { bg: '#FEE2E2', color: '#991B1B', border: '#FCA5A5', circleBg: '#DC2626' },
  neutral: { bg: '#F8FAFC', color: '#64748B', border: '#CBD5E1', circleBg: '#94A3B8' },
};

function getStageStatus(stageId, workflowPhase, rpaRunning, rpaResult, rpaError) {
  const isCompleted = workflowPhase === 'COMPLETED' && !!rpaResult;
  const isExpired = workflowPhase === 'EXPIRED';
  const isFailed = workflowPhase === 'FAILED' || (!!rpaError && !isCompleted);

  switch (stageId) {
    case 1: // Booking Details
      return { status: 'Completed', tone: 'success', icon: '✓' };

    case 2: // Booking Review
      if (workflowPhase === 'IDLE' && !isCompleted) {
        return { status: 'In Progress', tone: 'info', icon: '⏳' };
      }
      return { status: 'Completed', tone: 'success', icon: '✓' };

    case 3: // OTP Verification
      if (isCompleted || ['CAPTCHA_REQUIRED', 'PAYMENT_SIMULATING'].includes(workflowPhase)) {
        return { status: 'Verified', tone: 'success', icon: '✓' };
      }
      if (isExpired && workflowPhase === 'OTP_REQUIRED') {
        return { status: 'Failed / Expired', tone: 'danger', icon: '✕' };
      }
      if (isFailed && workflowPhase === 'OTP_REQUIRED') {
        return { status: 'Failed / Expired', tone: 'danger', icon: '✕' };
      }
      if (workflowPhase === 'OTP_REQUIRED') {
        return { status: 'Waiting for User', tone: 'warning', icon: '⚠️' };
      }
      if (workflowPhase === 'INITIATING' || (workflowPhase === 'OTP_REQUIRED' && rpaRunning)) {
        return { status: 'In Progress', tone: 'info', icon: '⏳' };
      }
      return { status: 'Pending', tone: 'neutral', icon: '3' };

    case 4: // CAPTCHA Verification
      if (isCompleted || workflowPhase === 'PAYMENT_SIMULATING') {
        return { status: 'Verified', tone: 'success', icon: '✓' };
      }
      if (isExpired && workflowPhase === 'CAPTCHA_REQUIRED') {
        return { status: 'Failed / Expired', tone: 'danger', icon: '✕' };
      }
      if (isFailed && workflowPhase === 'CAPTCHA_REQUIRED') {
        return { status: 'Failed / Expired', tone: 'danger', icon: '✕' };
      }
      if (workflowPhase === 'CAPTCHA_REQUIRED') {
        return { status: 'Waiting for User', tone: 'warning', icon: '⚠️' };
      }
      return { status: 'Pending', tone: 'neutral', icon: '4' };

    case 5: // Simulated Payment
      if (isCompleted) {
        return { status: 'Completed', tone: 'success', icon: '✓' };
      }
      if (workflowPhase === 'PAYMENT_SIMULATING') {
        return { status: 'In Progress', tone: 'info', icon: '⏳' };
      }
      if (isFailed && workflowPhase === 'PAYMENT_SIMULATING') {
        return { status: 'Failed / Expired', tone: 'danger', icon: '✕' };
      }
      return { status: 'Pending', tone: 'neutral', icon: '5' };

    case 6: // Booking Confirmation
      if (isCompleted) {
        return { status: 'Completed', tone: 'success', icon: '✓' };
      }
      if (workflowPhase === 'PAYMENT_SIMULATING') {
        return { status: 'In Progress', tone: 'info', icon: '⏳' };
      }
      return { status: 'Pending', tone: 'neutral', icon: '6' };

    case 7: // Demo Pilgrim Pass
      if (isCompleted) {
        return { status: 'Completed', tone: 'success', icon: '✓' };
      }
      return { status: 'Pending', tone: 'neutral', icon: '7' };

    default:
      return { status: 'Pending', tone: 'neutral', icon: '•' };
  }
}

export default function Authorization({ 
  bookingSummary, 
  onConfirmBooking: _onConfirmBooking, 
  onBack, 
  onNavigateToStep,
  onNavigateToConfirmation,
  currentUser = null,
  onRequireAuth = null,
  confirming: _confirming = false 
}) {
  const [rpaRunning, setRpaRunning] = useState(false);
  const [rpaResult, setRpaResult] = useState(null);
  const [rpaError, setRpaError] = useState(null);
  const [activeWorkflow, setActiveWorkflow] = useState(null);
  const [workflowPhase, setWorkflowPhase] = useState('IDLE'); // 'IDLE' | 'INITIATING' | 'OTP_REQUIRED' | 'CAPTCHA_REQUIRED' | 'PAYMENT_SIMULATING' | 'COMPLETED' | 'FAILED' | 'EXPIRED'
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

  const handleStartUnifiedBooking = async () => {
    if (rpaRunning) return;
    
    // Compulsory Authentication Check (Part 2)
    if (!currentUser) {
      if (onRequireAuth) {
        onRequireAuth();
      }
      return;
    }

    // Clear previous receipt and error state to guarantee a fresh, isolated run
    setRpaResult(null);
    setRpaError(null);
    setWorkflowPhase('INITIATING');
    setRpaRunning(true);

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
        user_name: currentUser?.email || currentUser?.name || 'Pilgrim Devotee',
        pax_count: pax,
        transport_text: `${tr.mode || 'train'} from ${origin}`,
        slot_text: slot.category || 'Normal Darshan',
        total_price: grandTotal,
        checkpoint_mode: 'SEQUENTIAL',
        headless: true,
        plan_version: planVersion,
        human_authorized: true,
      });

      if (data.status === 'PAUSED') {
        const nextState = data.state || 'OTP_REQUIRED';
        setWorkflowPhase(nextState);
        setActiveWorkflow({
          ...data,
          checkpoint_mode: 'SEQUENTIAL',
        });
      } else if (data.status === 'SUCCESS' || data.status === 'success') {
        setWorkflowPhase('COMPLETED');
        setRpaResult(data);
      } else {
        setWorkflowPhase('FAILED');
        setRpaError(data.message || 'Workflow returned non-success status.');
      }
    } catch (err) {
      console.error('Unified RPA Initiation Error:', err);
      setWorkflowPhase('FAILED');
      setRpaError(err.response?.data?.detail || err.message || 'Failed to start unified RPA booking workflow.');
    } finally {
      setRpaRunning(false);
    }
  };

  const handleWorkflowProgress = (progress) => {
    if (!progress) return;
    if (progress.phase) {
      setWorkflowPhase(progress.phase);
    } else if (progress.state) {
      setWorkflowPhase(progress.state);
    }
    if (progress.result) {
      setRpaResult(progress.result);
      setRpaError(null);
    }
    if (progress.error) {
      setRpaError(progress.error);
    } else if (progress.phase === 'COMPLETED' || progress.state === 'USER_ACTION_COMPLETED' || progress.phase === 'CAPTCHA_REQUIRED' || progress.state === 'CAPTCHA_REQUIRED') {
      setRpaError(null);
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
      {/* Synchronized 7-Stage Booking Progress Stepper */}
      <div
        data-testid="rpa-7-stage-stepper"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: '8px',
          background: '#FFFDF9',
          padding: '12px 14px',
          borderRadius: '12px',
          border: '1.5px solid var(--gold-border, #E8C874)',
          marginBottom: '1.5rem',
        }}
      >
        {WORKFLOW_STAGES.map((step) => {
          const info = getStageStatus(step.id, workflowPhase, rpaRunning, rpaResult, rpaError);
          const toneStyle = TONE_STYLES[info.tone] || TONE_STYLES.neutral;
          return (
            <div
              key={step.id}
              data-testid={`stage-${step.id}-box`}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                padding: '8px 10px',
                borderRadius: '8px',
                background: toneStyle.bg,
                border: `1px solid ${toneStyle.border}`,
                transition: 'all 0.2s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span
                  style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '50%',
                    background: toneStyle.circleBg,
                    color: '#FFF',
                    fontSize: '0.72rem',
                    fontWeight: 800,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  {info.icon}
                </span>
                <span
                  style={{
                    fontSize: '0.78rem',
                    fontWeight: 800,
                    color: '#1E293B',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {step.name}
                </span>
              </div>
              <div
                data-testid={`stage-${step.id}-status`}
                style={{
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  color: toneStyle.color,
                  letterSpacing: '0.2px',
                  paddingLeft: '26px',
                }}
              >
                {info.status}
              </div>
            </div>
          );
        })}
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

          {/* UNIFIED RPA YATRA BOOKING CARD */}
          <div className="card" style={{ background: '#FFFFFF', border: '1.5px solid var(--gold-border, #E8C874)', borderRadius: '12px', padding: '18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '6px' }}>
              <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '1.05rem', color: 'var(--burgundy)' }}>
                🛕 Unified Yatra Booking with Playwright RPA
              </div>
              <span className="badge" style={{ background: '#FEF3C7', color: '#92400E', fontWeight: 800, fontSize: '0.72rem', border: '1px solid #FCD34D' }}>
                LOCAL MOCK PORTAL DEMO
              </span>
            </div>

            <div style={{ fontSize: '0.84rem', color: 'var(--text-dark)', lineHeight: 1.5, marginBottom: '14px' }}>
              Initiate a single, continuous, human-supervised Playwright RPA booking experience. The browser agent navigates the local mock booking portal, pre-fills your selected transport and Darshan slot, and pauses exclusively at required human checkpoints (OTP & CAPTCHA).
            </div>

            {/* Safety & Compliance Notice */}
            <div style={{ background: '#F8FAFC', border: '1px dashed #CBD5E1', borderRadius: '8px', padding: '10px 12px', fontSize: '0.78rem', color: '#475569', marginBottom: '14px', lineHeight: 1.45 }}>
              🛡️ <b>Dual-Track Safety Architecture:</b> Automation operates strictly within our local sandbox. Real pilgrimage registrations on official Shrine Board portals (<i>maavaishnodevi.org</i>) require manual booking. Simulated payment is processed in sandbox mode (₹0 live charge).
            </div>

            {/* Authentication Guard Status Badge */}
            {!currentUser && (
              <div
                data-testid="auth-required-banner"
                style={{
                  background: '#FEF3C7',
                  border: '1.5px solid #F59E0B',
                  borderRadius: '10px',
                  padding: '10px 14px',
                  marginBottom: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '0.82rem',
                  color: '#92400E',
                }}
              >
                <span style={{ fontSize: '1.1rem' }}>🔒</span>
                <div>
                  <b>Authentication Required to Book:</b> Guest exploration is enabled. Clicking will prompt a quick email OTP verification before initiating RPA.
                </div>
              </div>
            )}
            {currentUser && (
              <div
                data-testid="auth-active-banner"
                style={{
                  background: '#F0FDF4',
                  border: '1.5px solid #86EFAC',
                  borderRadius: '10px',
                  padding: '8px 12px',
                  marginBottom: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '0.82rem',
                  color: '#166534',
                }}
              >
                <span>✓</span>
                <div>
                  Signed in as <b>{currentUser.email}</b>. Ready to execute Playwright RPA.
                </div>
              </div>
            )}

            {/* PRIMARY SINGLE CTA BUTTON */}
            {(!rpaResult || workflowPhase !== 'COMPLETED') && (
              <button
                type="button"
                onClick={handleStartUnifiedBooking}
                disabled={rpaRunning}
                className="btn btn-primary"
                data-testid="start-yatra-rpa-btn"
                style={{
                  width: '100%',
                  padding: '0.9rem 1.4rem',
                  fontSize: '1rem',
                  fontWeight: 800,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '10px',
                  background: 'linear-gradient(135deg, var(--burgundy, #6E1423), #8B1E3F)',
                  boxShadow: '0 4px 14px rgba(110, 20, 35, 0.25)',
                  cursor: rpaRunning ? 'not-allowed' : 'pointer',
                  borderRadius: '10px',
                }}
              >
                {rpaRunning ? (
                  <>⏳ Executing Continuous Playwright RPA...</>
                ) : (
                  <>🛕 Start Yatra Booking with RPA ➔</>
                )}
              </button>
            )}

            {/* Paused Checkpoint Notice if modal is closed */}
            {activeWorkflow && workflowPhase !== 'COMPLETED' && !rpaResult && (
              <div style={{ marginTop: '12px', background: '#FFFBEB', border: '1.5px solid #FCD34D', borderRadius: '10px', padding: '12px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <div>
                  <div style={{ fontWeight: 800, color: '#92400E', fontSize: '0.86rem' }}>
                    ⚠️ Paused at Security Checkpoint: {workflowPhase === 'OTP_REQUIRED' ? 'OTP Verification Required' : 'CAPTCHA Challenge Required'}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: '#B45309', marginTop: '2px' }}>
                    Please enter your mock verification code to automatically resume the booking.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveWorkflow({ ...activeWorkflow })}
                  className="btn btn-gold"
                  style={{ fontSize: '0.8rem', padding: '6px 14px', fontWeight: 700 }}
                >
                  Enter Verification Code ➔
                </button>
              </div>
            )}

            {/* Error Display */}
            {rpaError && workflowPhase !== 'COMPLETED' && (
              <div style={{ marginTop: '12px', background: '#FDF2F2', border: '1.5px solid #FCA5A5', padding: '10px 14px', borderRadius: '10px', color: '#991B1B', fontSize: '0.82rem' }}>
                <strong>Booking Error:</strong> {rpaError}
                <div style={{ marginTop: '6px' }}>
                  <button
                    type="button"
                    onClick={handleStartUnifiedBooking}
                    className="btn btn-outline"
                    style={{ fontSize: '0.76rem', padding: '4px 10px', borderColor: '#FCA5A5', color: '#991B1B' }}
                  >
                    🔄 Retry Fresh Booking
                  </button>
                </div>
              </div>
            )}

            {/* Confirmed Demo Pilgrim Pass (Stage 7) */}
            {rpaResult && workflowPhase === 'COMPLETED' && (
              <div
                data-testid="demo-pilgrim-pass-card"
                style={{
                  marginTop: '14px',
                  background: '#F0FDF4',
                  border: '2px solid #86EFAC',
                  borderRadius: '12px',
                  padding: '16px',
                  boxShadow: '0 4px 16px rgba(5, 150, 105, 0.12)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px dashed #86EFAC', paddingBottom: '10px', marginBottom: '12px', flexWrap: 'wrap', gap: '6px' }}>
                  <div>
                    <span className="badge" style={{ background: '#DCFCE7', color: '#166534', fontWeight: 800, fontSize: '0.72rem', border: '1px solid #86EFAC' }}>
                      LOCAL MOCK PORTAL / DEMO
                    </span>
                    <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#166534', marginTop: '4px' }}>
                      Simulated Yatra Booking Confirmation
                    </div>
                    <div style={{ fontSize: '0.86rem', color: '#15803D', fontWeight: 700, marginTop: '2px' }}>
                      Demo Pilgrim Pass: <strong style={{ fontFamily: 'monospace', fontSize: '1.05rem', color: '#166534' }}>{rpaResult.booking_id}</strong>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      type="button"
                      onClick={() => window.print()}
                      className="btn btn-outline"
                      data-testid="print-demo-pass-btn"
                      style={{ fontSize: '0.78rem', padding: '6px 12px', borderColor: '#86EFAC', color: '#166534', fontWeight: 700 }}
                    >
                      🖨️ Print Demo Pass
                    </button>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px', fontSize: '0.82rem', color: '#374151' }}>
                  <div><strong>Pilgrim:</strong> {rpaResult.user_name || currentUser?.email || 'Guest Pilgrim'} ({rpaResult.pax_count || pax} pax)</div>
                  <div><strong>Darshan Slot:</strong> {slot.category || 'Normal Darshan'} ({slot.slot_time || 'Morning Slot'})</div>
                  <div><strong>Transport:</strong> {operator} ({mode}) from {origin}</div>
                  <div><strong>Accommodation:</strong> {hotel ? hotel.name : 'Self-arranged Katra stay'}</div>
                  <div><strong>Simulated Payment:</strong> ₹{(rpaResult.total_price || grandTotal).toLocaleString('en-IN')} <span style={{ color: '#059669', fontWeight: 700 }}>(Sandbox ₹0 Live Charge)</span></div>
                  <div><strong>Security Status:</strong> <span style={{ color: '#166534', fontWeight: 700 }}>OTP Verified ✓ & CAPTCHA Solved ✓</span></div>
                </div>

                <div style={{ fontSize: '0.82rem', color: '#047857', marginTop: '12px', fontStyle: 'italic', textAlign: 'center', background: '#DCFCE7', padding: '8px', borderRadius: '8px', border: '1px solid #BBF7D0' }}>
                  🙏 Jai Mata Di! May Maa Vaishno Devi bless you and your family with peace and happiness.
                </div>

                <div style={{ marginTop: '14px', display: 'flex', justifyContent: 'flex-end', gap: '8px', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    onClick={handleStartUnifiedBooking}
                    className="btn btn-outline"
                    data-testid="start-fresh-booking-btn"
                    style={{ fontSize: '0.82rem', padding: '6px 14px', fontWeight: 700 }}
                  >
                    🔄 Start Fresh Booking with RPA
                  </button>
                  <button
                    type="button"
                    onClick={() => onNavigateToConfirmation && onNavigateToConfirmation(rpaResult)}
                    className="btn btn-primary"
                    data-testid="continue-to-confirmation-card-btn"
                    style={{ fontSize: '0.85rem', padding: '6px 16px', fontWeight: 800 }}
                  >
                    Continue to Confirmation ➔
                  </button>
                </div>
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

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button
            onClick={() => handleNavigateStep(2)}
            className="btn btn-outline"
            style={{ fontSize: '0.82rem' }}
          >
            Change Transport / Hotel
          </button>

          {rpaResult && workflowPhase === 'COMPLETED' ? (
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <button
                type="button"
                onClick={() => window.print()}
                className="btn btn-outline"
                style={{ padding: '0.75rem 1.4rem', fontSize: '0.9rem' }}
              >
                🖨️ Print Demo Pass
              </button>
              <button
                type="button"
                data-testid="continue-to-confirmation-btn"
                onClick={() => onNavigateToConfirmation && onNavigateToConfirmation(rpaResult)}
                className="btn btn-primary"
                style={{
                  padding: '0.75rem 1.8rem',
                  fontSize: '0.92rem',
                  fontWeight: 800,
                  backgroundColor: 'var(--burgundy, #58111A)',
                  borderColor: 'var(--gold-primary, #C5A059)',
                }}
              >
                Continue to Confirmation ➔
              </button>
            </div>
          ) : (
            <button
              type="button"
              data-testid="bottom-start-yatra-rpa-btn"
              onClick={handleStartUnifiedBooking}
              disabled={rpaRunning}
              className="btn btn-primary"
              style={{ padding: '0.75rem 1.8rem', fontSize: '0.9rem' }}
            >
              {rpaRunning ? '⏳ Booking in Progress...' : '🛕 Start Yatra Booking with RPA ➔'}
            </button>
          )}
        </div>
      </div>

      {/* Week 8: User Intervention Modal */}
      {activeWorkflow && (
        <UserInterventionModal
          workflowData={activeWorkflow}
          sessionId={sessionId || activeWorkflow.session_id}
          isOpen={!!activeWorkflow}
          onClose={() => setActiveWorkflow(null)}
          onWorkflowProgress={handleWorkflowProgress}
          onWorkflowComplete={(result) => {
            setRpaResult(result);
            setWorkflowPhase('COMPLETED');
            setActiveWorkflow(null);
          }}
          onWorkflowCancelled={() => {
            setWorkflowPhase('IDLE');
            setActiveWorkflow(null);
          }}
        />
      )}
    </div>
  );
}

