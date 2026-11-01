import React, { useState } from 'react';
import ItineraryTimeline from './ItineraryTimeline';

/**
 * RecommendedYatra.jsx
 * Consolidated "Your Recommended Yatra" presentation page.
 * Displays automatically generated recommendations across:
 * - Trip Overview
 * - Selected Transport
 * - Selected Accommodation
 * - Selected Darshan Slot
 * - Sightseeing Feasibility & Day-Wise Itinerary (with travel & recovery considerations)
 * - Itemised Budget (distinguishing verified direct costs, discretionary estimates, and excluded expenses)
 * - Confirmation prompt: "Are you happy with these selections, or would you like to change anything before proceeding?"
 *   - Path A: "Confirm Selections & Continue"
 *   - Path B: "Change My Selections" (with direct jump to editable categories)
 */
export default function RecommendedYatra({
  planData,
  tripRequest,
  sessionId,
  planVersion = 1,
  onConfirmSelections,
  onEditCategory,
  planRevisionNotice = '',
}) {
  const [showCategorySelector, setShowCategorySelector] = useState(false);

  // Extract components from planData
  const option = planData?.selected_option || planData?.option || {};
  const tr = option.transport || option.flight || {};
  const slot = option.slot || {};
  const hotel = planData?.hotel || planData?.selected_hotel || null;
  const itinerary = planData?.itinerary || [];
  const feasiblePlaces = planData?.feasible_places || [];
  const infeasiblePlaces = planData?.infeasible_places || [];
  const budgetEval = planData?.budget_evaluation || {};

  const req = tripRequest || planData?.request || {};
  const origin = req.origin || tr.origin || 'Delhi';
  const pax = req.pax || req.pilgrims || 1;
  const durationDays = req.duration_days || req.duration || req.days || (itinerary.length > 0 ? itinerary.length : 4);
  const travelDate = req.start_date || tr.travel_date || '2026-10-20';
  const hotelNights = Math.max(1, durationDays - 1);
  const roomsCount = Math.ceil(pax / 2);

  // Transport details
  const mode = (tr.mode || 'train').toUpperCase();
  const operator = tr.operator || (mode === 'TRAIN' ? 'Indian Railways' : 'Express Service');
  const serviceNo = tr.transport_no || (tr.id ? `ID #${tr.id}` : 'Direct Service');
  const depTime = tr.departure_time || '06:00';
  const arrTime = tr.arrival_time || '14:00';
  const durationStr = tr.duration_str || (tr.duration_mins ? `${Math.floor(tr.duration_mins / 60)}h ${tr.duration_mins % 60}m` : null);
  const farePerPerson = tr.fare_per_person || tr.price || 0;
  const transportFareTotal = tr.total_fare || (farePerPerson * pax);

  // Darshan details
  const slotCategory = slot.category || req.category || 'Normal Darshan';
  const slotTime = slot.slot_time || '06:00';
  const slotPricePerPerson = slot.price || 0;
  const darshanTotal = slotPricePerPerson * pax;

  // Accommodation details
  const hotelPricePerNight = hotel?.price_per_night || 0;
  const hotelTotal = hotelPricePerNight * roomsCount * hotelNights;

  // Financial Summary from budgetEval or deterministic formula
  const verifiedDirectTotal = transportFareTotal + darshanTotal + hotelTotal;
  const roadTransferEst = budgetEval?.estimated_costs?.items?.local_road_transfer || (mode === 'FLIGHT' ? 1500 * pax : 350 * pax);
  const mealsEst = budgetEval?.estimated_costs?.items?.meals_and_refreshments || (350 * pax * durationDays);
  const totalEstimated = roadTransferEst + mealsEst;
  const grandTotal = planVersion > 1 ? (verifiedDirectTotal + totalEstimated) : (budgetEval.grand_total || (verifiedDirectTotal + totalEstimated));
  const costPerPerson = pax > 0 ? Math.round(grandTotal / pax) : grandTotal;
  const targetBudget = req.total_budget ? Number(req.total_budget) : (budgetEval.total_budget ? Number(budgetEval.total_budget) : null);
  const remainingBudget = targetBudget !== null ? targetBudget - grandTotal : null;
  const isWithinBudget = planVersion > 1 ? (targetBudget !== null ? grandTotal <= targetBudget : null) : (budgetEval.within_budget !== undefined ? budgetEval.within_budget : (targetBudget !== null ? grandTotal <= targetBudget : null));

  return (
    <div data-testid="recommended-yatra-page" style={{ width: '100%' }}>
      {/* Page Header */}
      <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <span className="pill pill-gold" style={{ fontSize: '0.8rem', fontWeight: 800 }}>
              AI Recommended Package
            </span>
            <span className="pill" style={{ background: '#F0EAE1', color: 'var(--burgundy)', fontSize: '0.78rem', fontWeight: 700 }}>
              Plan Revision #{planVersion} {sessionId ? `• Session ${sessionId.slice(0, 8)}` : ''}
            </span>
          </div>
          <h1 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.85rem', fontWeight: 800, color: 'var(--burgundy)', margin: '6px 0 2px 0' }}>
            Your Recommended Yatra Package
          </h1>
          <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', margin: 0 }}>
            Curated specifically for your travel dates, budget scope, and Maa Vaishno Devi darshan timing feasibility.
          </p>
        </div>

        <button
          type="button"
          data-testid="toggle-change-selections-btn"
          onClick={() => setShowCategorySelector(!showCategorySelector)}
          className="btn btn-outline"
          style={{ fontSize: '0.84rem', padding: '7px 16px', borderColor: 'var(--gold-primary)', color: 'var(--burgundy)' }}
        >
          ✏️ Change My Selections
        </button>
      </div>

      {/* Plan Revision Banner if updated */}
      {planRevisionNotice && (
        <div style={{
          background: '#FFFBEB',
          border: '1.5px solid #FCD34D',
          borderRadius: '12px',
          padding: '12px 16px',
          marginBottom: '1.5rem',
          fontSize: '0.85rem',
          color: '#92400E',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          <span>ℹ️</span> {planRevisionNotice}
        </div>
      )}

      {/* Editable Category Quick-Links Drawer */}
      {showCategorySelector && (
        <div className="card" style={{ background: '#FFFDF7', border: '1.5px solid var(--gold-border)', marginBottom: '1.75rem', padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <div style={{ fontWeight: 800, color: 'var(--burgundy)', fontSize: '0.92rem' }}>
              Select a category to customize:
            </div>
            <button
              onClick={() => setShowCategorySelector(false)}
              style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: '0.9rem' }}
            >
              ✕ Close
            </button>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              type="button"
              data-testid="edit-cat-transport"
              onClick={() => onEditCategory('transport')}
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem', padding: '6px 14px' }}
            >
              🚆 Transport
            </button>
            <button
              type="button"
              data-testid="edit-cat-darshan"
              onClick={() => onEditCategory('darshan')}
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem', padding: '6px 14px' }}
            >
              🙏 Darshan Slot
            </button>
            <button
              type="button"
              data-testid="edit-cat-accommodation"
              onClick={() => onEditCategory('accommodation')}
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem', padding: '6px 14px' }}
            >
              🏨 Accommodation
            </button>
            <button
              type="button"
              data-testid="edit-cat-sightseeing"
              onClick={() => onEditCategory('sightseeing')}
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem', padding: '6px 14px' }}
            >
              🌄 Sightseeing
            </button>
            <button
              type="button"
              data-testid="edit-cat-budget"
              onClick={() => onEditCategory('budget')}
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem', padding: '6px 14px' }}
            >
              💰 Budget
            </button>
            <button
              type="button"
              data-testid="edit-cat-dates"
              onClick={() => onEditCategory('dates')}
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem', padding: '6px 14px' }}
            >
              📅 Dates & Duration
            </button>
            <button
              type="button"
              data-testid="edit-cat-style"
              onClick={() => onEditCategory('style')}
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem', padding: '6px 14px' }}
            >
              🧭 Style & Pacing
            </button>
          </div>
        </div>
      )}

      {/* Main Consolidated Grids */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        
        {/* Left Column: Trip Overview, Transport, Hotel, Darshan */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          
          {/* 1. Trip Overview Card */}
          <div className="card" style={{ background: '#FFFFFF' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '1.05rem', color: 'var(--burgundy)' }}>
                📍 Pilgrimage Overview
              </div>
              <span className="pill pill-gold" style={{ fontSize: '0.72rem' }}>
                {durationDays} Days / {hotelNights} Nights
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '0.84rem' }}>
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.74rem' }}>Starting Location</span>
                <b>{origin}</b>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.74rem' }}>Sacred Destination</span>
                <b>Katra & Bhawan</b>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.74rem' }}>Pilgrims Count</span>
                <b>{pax} {pax === 1 ? 'Pilgrim' : 'Pilgrims'}</b>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.74rem' }}>Yatra Start Date</span>
                <b>{travelDate}</b>
              </div>
            </div>
          </div>

          {/* 2. Selected Transport Service Card */}
          <div className="card" style={{ background: '#FFFFFF', border: '1.5px solid var(--gold-border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="pill pill-gold" style={{ fontSize: '0.72rem' }}>
                    {mode === 'FLIGHT' ? '✈️ FLIGHT' : (mode === 'BUS' ? '🚌 BUS' : '🚆 TRAIN')}
                  </span>
                  <span style={{ fontWeight: 800, fontSize: '0.98rem', color: 'var(--burgundy)' }}>
                    {operator} {serviceNo && `· ${serviceNo}`}
                  </span>
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Departure: <b>{origin}</b> ➔ Arrival: <b>{tr.destination || 'Katra'}</b>
                </div>
              </div>
              <button
                type="button"
                onClick={() => onEditCategory('transport')}
                className="btn btn-outline"
                style={{ fontSize: '0.74rem', padding: '4px 10px' }}
              >
                Change
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', padding: '8px 0', borderTop: '1px solid var(--border-subtle)', borderBottom: '1px solid var(--border-subtle)', marginBottom: '8px' }}>
              <div>
                <div style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-dark)' }}>{depTime}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{origin}</div>
              </div>
              <div style={{ textAlign: 'center', padding: '0 8px' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 700 }}>
                  {durationStr ? `⏱️ ${durationStr}` : 'Scheduled'}
                </div>
                <div style={{ color: 'var(--gold-primary)', fontSize: '0.8rem' }}>────── ➔</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-dark)' }}>{arrTime}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{tr.destination || 'Katra'}</div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.82rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Transport Fare ({pax}x ₹{farePerPerson}):</span>
              <b style={{ color: 'var(--burgundy)', fontSize: '0.95rem' }}>₹{transportFareTotal.toLocaleString('en-IN')}</b>
            </div>
          </div>

          {/* 3. Selected Darshan Slot Card */}
          <div className="card" style={{ background: '#FFFFFF', border: '1.5px solid var(--gold-border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="pill pill-gold" style={{ fontSize: '0.72rem' }}>
                    🙏 DARSHAN
                  </span>
                  <span style={{ fontWeight: 800, fontSize: '0.98rem', color: 'var(--burgundy)' }}>
                    {slotCategory}
                  </span>
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Shri Mata Vaishno Devi Shrine Board, Bhawan
                </div>
              </div>
              <span className="pill pill-success" style={{ fontSize: '0.68rem' }}>
                ✓ Shrine Verified
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.84rem', marginTop: '6px' }}>
              <div>
                <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.74rem' }}>Scheduled Time & Date</span>
                <b>{slotTime} · {slot.slot_date || travelDate}</b>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.74rem' }}>Shrine Fee</span>
                <b style={{ color: darshanTotal === 0 ? '#155724' : 'var(--burgundy)' }}>
                  {darshanTotal === 0 ? 'Free / Included' : `₹${darshanTotal.toLocaleString('en-IN')}`}
                </b>
              </div>
            </div>
          </div>

          {/* 4. Selected Accommodation Card */}
          <div className="card" style={{ background: '#FFFFFF', border: '1.5px solid var(--gold-border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="pill pill-gold" style={{ fontSize: '0.72rem' }}>
                    🏨 HOTEL
                  </span>
                  <span style={{ fontWeight: 800, fontSize: '0.98rem', color: 'var(--burgundy)' }}>
                    {hotel?.name || 'Katra Stay Reserved'}
                  </span>
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  {hotel?.location || 'Central Katra Base'} · {hotel?.category || 'Standard'} Category
                </div>
              </div>
              <button
                type="button"
                onClick={() => onEditCategory('accommodation')}
                className="btn btn-outline"
                style={{ fontSize: '0.74rem', padding: '4px 10px' }}
              >
                Change
              </button>
            </div>

            {hotel ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.82rem', marginTop: '6px' }}>
                <div>
                  <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.72rem' }}>Room Configuration</span>
                  <b>{roomsCount} room(s) for {pax} guest(s)</b>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.72rem' }}>Stay Duration</span>
                  <b>{hotelNights} Night(s)</b>
                </div>
                <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'space-between', borderTop: '1px solid var(--border-subtle)', paddingTop: '6px', marginTop: '4px' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Hotel Total ({roomsCount} rm x {hotelNights} n):</span>
                  <b style={{ color: 'var(--burgundy)' }}>₹{hotelTotal.toLocaleString('en-IN')}</b>
                </div>
              </div>
            ) : (
              <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '4px' }}>
                No Katra hotel reserved (day-excursion or self-arranged stay).
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Sightseeing & Itinerary + Itemised Budget */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          
          {/* 5. Sightseeing & Day-Wise Itinerary */}
          <div className="card" style={{ background: '#FFFFFF', padding: '1.25rem' }}>
            <ItineraryTimeline
              itinerary={itinerary}
              daysCount={durationDays}
              feasiblePlaces={feasiblePlaces}
              infeasiblePlaces={infeasiblePlaces}
              onEditCategory={onEditCategory}
            />
          </div>

          {/* 6. Itemised Budget Summary */}
          <div className="card" style={{ background: 'var(--gold-subtle)', border: '1.5px solid var(--gold-border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '1.05rem', color: 'var(--burgundy)' }}>
                💰 Itemised Budget Breakdown
              </div>
              <button
                type="button"
                onClick={() => onEditCategory('budget')}
                className="btn btn-outline"
                style={{ fontSize: '0.74rem', padding: '4px 10px', background: '#FFFFFF' }}
              >
                Adjust Budget
              </button>
            </div>

            {/* Verified Direct Costs */}
            <div style={{ fontSize: '0.78rem', color: 'var(--text-dark)', display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>✓ Verified Transport ({pax}x fare):</span>
                <b>₹{transportFareTotal.toLocaleString('en-IN')}</b>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>✓ Verified Darshan Slot ({pax}x fee):</span>
                <b>₹{darshanTotal.toLocaleString('en-IN')}</b>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>✓ Verified Hotel ({roomsCount} rm, {hotelNights} n):</span>
                <b>₹{hotelTotal.toLocaleString('en-IN')}</b>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #E5D2AD', paddingTop: '4px', marginTop: '2px', fontWeight: 700 }}>
                <span>Total Verified Direct Charges:</span>
                <span style={{ color: '#155724' }}>₹{verifiedDirectTotal.toLocaleString('en-IN')}</span>
              </div>
            </div>

            {/* Discretionary Estimates */}
            <div style={{ background: '#FFFDF9', borderRadius: '8px', padding: '8px 10px', fontSize: '0.74rem', color: '#856404', border: '1px solid #FFEBAA', marginBottom: '8px' }}>
              <div style={{ fontWeight: 700, marginBottom: '2px' }}>Estimated Discretionary Expenses (Pay on-site):</div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>• Road Transfers (Katra taxi/shuttle):</span>
                <span>₹{roadTransferEst.toLocaleString('en-IN')}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>• Meals & Refreshments ({pax} pax, {durationDays} d):</span>
                <span>₹{mealsEst.toLocaleString('en-IN')}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700, marginTop: '2px', borderTop: '1px dashed #FFEBAA', paddingTop: '2px' }}>
                <span>Total Estimates:</span>
                <span>₹{totalEstimated.toLocaleString('en-IN')}</span>
              </div>
            </div>

            {/* Grand Total & Per Person */}
            <div style={{ background: '#FFFFFF', borderRadius: '10px', padding: '10px 14px', border: '1.5px solid var(--gold-border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Grand Group Total</div>
                  <div style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--burgundy)' }}>
                    ₹{grandTotal.toLocaleString('en-IN')}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Cost Per Pilgrim</div>
                  <div style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--burgundy-dark)' }}>
                    ₹{costPerPerson.toLocaleString('en-IN')}
                  </div>
                </div>
              </div>

              {/* Target Budget Comparison if provided */}
              {targetBudget !== null && (
                <div style={{ marginTop: '8px', paddingTop: '6px', borderTop: '1px solid var(--border-subtle)', fontSize: '0.78rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Target Budget: <b>₹{targetBudget.toLocaleString('en-IN')}</b></span>
                  {isWithinBudget ? (
                    <span className="pill pill-success" style={{ fontSize: '0.7rem' }}>
                      ✓ Within Budget (Surplus ₹{remainingBudget?.toLocaleString('en-IN')})
                    </span>
                  ) : (
                    <span className="pill" style={{ background: '#FEE2E2', color: '#991B1B', fontSize: '0.7rem' }}>
                      ⚠️ Exceeded by ₹{Math.abs(remainingBudget || 0).toLocaleString('en-IN')}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Excluded Expenses Notice */}
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '6px' }}>
              ℹ️ Excludes voluntary trek pony/palki charges, personal pooja offerings, and Katra market shopping.
            </div>
          </div>
        </div>
      </div>

      {/* ========================================================= */}
      {/* REQUIREMENT 3: ASK FOR CONFIRMATION BEFORE PROCEEDING     */}
      {/* ========================================================= */}
      <div
        className="card"
        style={{
          background: 'linear-gradient(135deg, #FFFCF7 0%, #FFF9F0 100%)',
          border: '2px solid var(--gold-primary)',
          borderRadius: '16px',
          padding: '1.5rem',
          boxShadow: 'var(--shadow-md)',
          marginBottom: '2rem',
        }}
      >
        <div style={{ textAlign: 'center', maxWidth: '680px', margin: '0 auto' }}>
          <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.25rem', fontWeight: 800, color: 'var(--burgundy)', marginBottom: '8px' }}>
            Are you happy with these selections, or would you like to change anything before proceeding?
          </div>
          <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
            You can confirm this recommended plan to proceed directly to the final booking review and human authorization gate, or customize individual transport, hotel, darshan, or sightseeing choices.
          </p>

          <div style={{ display: 'flex', gap: '14px', justifyContent: 'center', flexWrap: 'wrap' }}>
            {/* Path A */}
            <button
              type="button"
              data-testid="confirm-selections-continue-btn"
              onClick={onConfirmSelections}
              className="btn btn-primary"
              style={{
                padding: '0.8rem 2.2rem',
                fontSize: '0.96rem',
                fontWeight: 800,
                boxShadow: '0 4px 14px rgba(88, 17, 26, 0.25)',
              }}
            >
              ✓ Confirm Selections & Continue ➔
            </button>

            {/* Path B */}
            <button
              type="button"
              data-testid="change-my-selections-btn"
              onClick={() => setShowCategorySelector(!showCategorySelector)}
              className="btn btn-outline"
              style={{
                padding: '0.8rem 1.8rem',
                fontSize: '0.94rem',
                fontWeight: 700,
                borderColor: 'var(--gold-primary)',
                color: 'var(--burgundy)',
              }}
            >
              ✏️ Change My Selections
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
