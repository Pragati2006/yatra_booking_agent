import React, { useState, useEffect, useRef } from 'react';

const POPULAR_HUBS = [
  'Delhi', 'Jammu', 'Mumbai', 'Ahmedabad', 'Amritsar', 
  'Srinagar', 'Surat', 'Bhopal', 'Haridwar', 'Kolkata'
];

export default function TravelSearch({ onSearch, loading = false, initialValues = {} }) {
  const [origin, setOrigin] = useState(initialValues.origin || 'Delhi');
  const [startDate, setStartDate] = useState(initialValues.startDate || initialValues.start_date || '2026-10-20');
  const [pax, setPax] = useState(initialValues.pax || 2);
  const [mode, setMode] = useState(initialValues.mode || 'any');
  const [category, setCategory] = useState(initialValues.category || 'Normal Darshan');
  const [duration, setDuration] = useState(initialValues.duration || initialValues.duration_days || 4);
  const [budgetType, setBudgetType] = useState(initialValues.budget_type || 'total');
  const [budgetAmount, setBudgetAmount] = useState(() => {
    if (initialValues.total_budget) return String(initialValues.total_budget);
    if (initialValues.budget_per_person) return String(initialValues.budget_per_person);
    return '';
  });
  const [travelStyle, setTravelStyle] = useState(initialValues.travel_style || 'balanced');
  const [accommodationPreference, setAccommodationPreference] = useState(initialValues.accommodation_preference || 'Standard');
  const [sightseeingChoice, setSightseeingChoice] = useState(initialValues.sightseeing_choice || 'recommend');

  const prevValuesRef = useRef(initialValues);

  useEffect(() => {
    const prev = prevValuesRef.current;
    if (initialValues.origin && initialValues.origin !== prev?.origin) {
      setOrigin(initialValues.origin);
    }
    const newStart = initialValues.startDate || initialValues.start_date;
    const prevStart = prev?.startDate || prev?.start_date;
    if (newStart && newStart !== prevStart) {
      setStartDate(newStart);
    }
    if (initialValues.pax && initialValues.pax !== prev?.pax) {
      setPax(initialValues.pax);
    }
    if (initialValues.mode && initialValues.mode !== prev?.mode) {
      setMode(initialValues.mode);
    }
    if (initialValues.category && initialValues.category !== prev?.category) {
      setCategory(initialValues.category);
    }
    const newDur = initialValues.duration || initialValues.duration_days;
    const prevDur = prev?.duration || prev?.duration_days;
    if (newDur && newDur !== prevDur) {
      setDuration(newDur);
    }
    if (initialValues.budget_type && initialValues.budget_type !== prev?.budget_type) {
      setBudgetType(initialValues.budget_type);
    }
    const newBudget = initialValues.total_budget || initialValues.budget_per_person;
    const prevBudget = prev?.total_budget || prev?.budget_per_person;
    if (newBudget && newBudget !== prevBudget) {
      setBudgetAmount(String(newBudget));
    }
    if (initialValues.travel_style && initialValues.travel_style !== prev?.travel_style) {
      setTravelStyle(initialValues.travel_style);
    }
    if (initialValues.accommodation_preference && initialValues.accommodation_preference !== prev?.accommodation_preference) {
      setAccommodationPreference(initialValues.accommodation_preference);
    }
    if (initialValues.sightseeing_choice && initialValues.sightseeing_choice !== prev?.sightseeing_choice) {
      setSightseeingChoice(initialValues.sightseeing_choice);
    }
    prevValuesRef.current = initialValues;
  }, [initialValues]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const bAmt = budgetAmount ? parseFloat(budgetAmount) : null;
    const bType = budgetType || 'total';
    const totalB = bAmt ? (bType === 'per_person' ? bAmt * parseInt(pax, 10) : bAmt) : null;
    const perPersonB = bAmt ? (bType === 'per_person' ? bAmt : bAmt / parseInt(pax, 10)) : null;

    let budgetStr = '';
    if (bAmt) {
      budgetStr = bType === 'per_person' ? ` with budget of ₹${bAmt} per person` : ` with total budget of ₹${bAmt}`;
    }

    const queryText = `${pax} people from ${origin} travelling to Katra on ${startDate} for ${duration} days with ${category}${mode !== 'any' ? ' by ' + mode : ''}${budgetStr}, ${travelStyle} pace, ${accommodationPreference} stay`;
    
    onSearch({
      queryText,
      origin,
      startDate,
      pax: parseInt(pax, 10),
      mode,
      category,
      duration: parseInt(duration, 10),
      total_budget: totalB,
      budget_type: bType,
      budget_per_person: perPersonB,
      travel_style: travelStyle,
      accommodation_preference: accommodationPreference,
      sightseeing_choice: sightseeingChoice,
    });
  };

  return (
    <div style={{
      background: '#FFFFFF',
      border: '1.5px solid var(--gold-border)',
      borderRadius: '20px',
      padding: '1.5rem',
      boxShadow: 'var(--shadow-md)',
      width: '100%',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
        <div>
          <div style={{ fontFamily: 'var(--font-serif)', fontWeight: 800, fontSize: '1.15rem', color: 'var(--burgundy)' }}>
            🔱 Plan Your Sacred Yatra
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Search verified trains, flights, buses, and shrine darshan slots to Katra
          </div>
        </div>
        <span className="pill pill-gold">
          Live Shrine Connectivity
        </span>
      </div>

      <form onSubmit={handleSubmit}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '12px',
          marginBottom: '1.25rem',
        }}>
          {/* Origin */}
          <div>
            <label htmlFor="travel-origin" style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--burgundy)', marginBottom: '4px' }}>
              📍 Departure City
            </label>
            <select
              id="travel-origin"
              value={origin}
              onChange={(e) => setOrigin(e.target.value)}
              style={{ padding: '0.55rem 0.75rem' }}
            >
              {POPULAR_HUBS.map((h) => (
                <option key={h} value={h}>{h}</option>
              ))}
            </select>
          </div>

          {/* Travel Date */}
          <div>
            <label htmlFor="travel-start-date" style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--burgundy)', marginBottom: '4px' }}>
              📅 Yatra Start Date
            </label>
            <input
              id="travel-start-date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              style={{ padding: '0.55rem 0.75rem' }}
            />
          </div>

          {/* Pilgrims */}
          <div>
            <label htmlFor="travel-pax" style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--burgundy)', marginBottom: '4px' }}>
              👤 Pilgrims (Pax)
            </label>
            <select
              id="travel-pax"
              value={pax}
              onChange={(e) => setPax(e.target.value)}
              style={{ padding: '0.55rem 0.75rem' }}
            >
              {[1, 2, 3, 4, 5, 6, 8, 10].map((num) => (
                <option key={num} value={num}>{num} {num === 1 ? 'Pilgrim' : 'Pilgrims'}</option>
              ))}
            </select>
          </div>

          {/* Transport Mode */}
          <div>
            <label htmlFor="travel-mode" style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--burgundy)', marginBottom: '4px' }}>
              🚆 Travel Mode
            </label>
            <select
              id="travel-mode"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              style={{ padding: '0.55rem 0.75rem' }}
            >
              <option value="any">Any Available Mode</option>
              <option value="train">Train</option>
              <option value="flight">Flight</option>
              <option value="bus">Bus</option>
            </select>
          </div>

          {/* Darshan Slot */}
          <div>
            <label htmlFor="travel-category" style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--burgundy)', marginBottom: '4px' }}>
              🙏 Darshan Category
            </label>
            <select
              id="travel-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              style={{ padding: '0.55rem 0.75rem' }}
            >
              <option value="Normal Darshan">Normal Darshan</option>
              <option value="VIP Darshan">VIP Darshan</option>
              <option value="Helicopter Darshan">Helicopter Darshan</option>
            </select>
          </div>

          {/* Duration */}
          <div>
            <label htmlFor="travel-duration" style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--burgundy)', marginBottom: '4px' }}>
              ⏱️ Trip Duration
            </label>
            <select
              id="travel-duration"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              style={{ padding: '0.55rem 0.75rem' }}
            >
              {[2, 3, 4, 5, 6, 7].map((days) => (
                <option key={days} value={days}>{days} Days ({days - 1} Nights)</option>
              ))}
            </select>
          </div>

          {/* Budget Scope */}
          <div>
            <label htmlFor="travel-budget-type" style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--burgundy)', marginBottom: '4px' }}>
              💰 Budget Scope
            </label>
            <select
              id="travel-budget-type"
              value={budgetType}
              onChange={(e) => setBudgetType(e.target.value)}
              style={{ padding: '0.55rem 0.75rem' }}
            >
              <option value="total">Total Group Budget</option>
              <option value="per_person">Per-Person Budget</option>
            </select>
          </div>

          {/* Budget Amount */}
          <div>
            <label htmlFor="travel-budget-amount" style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--burgundy)', marginBottom: '4px' }}>
              💵 Budget Amount (₹)
            </label>
            <input
              id="travel-budget-amount"
              type="number"
              placeholder={budgetType === 'total' ? 'e.g. 15000' : 'e.g. 7500'}
              value={budgetAmount}
              onChange={(e) => setBudgetAmount(e.target.value)}
              min="0"
              step="500"
              style={{ padding: '0.55rem 0.75rem' }}
            />
          </div>

          {/* Travel Pace */}
          <div>
            <label htmlFor="travel-pace" style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--burgundy)', marginBottom: '4px' }}>
              🚶 Travel Pace / Style
            </label>
            <select
              id="travel-pace"
              value={travelStyle}
              onChange={(e) => setTravelStyle(e.target.value)}
              style={{ padding: '0.55rem 0.75rem' }}
            >
              <option value="balanced">Balanced & Moderate</option>
              <option value="relaxed">Relaxed & Leisurely</option>
              <option value="packed">Packed & Full Exploration</option>
            </select>
          </div>

          {/* Accommodation Preference */}
          <div>
            <label htmlFor="travel-accommodation" style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--burgundy)', marginBottom: '4px' }}>
              🏨 Stay Preference
            </label>
            <select
              id="travel-accommodation"
              value={accommodationPreference}
              onChange={(e) => setAccommodationPreference(e.target.value)}
              style={{ padding: '0.55rem 0.75rem' }}
            >
              <option value="Standard">Standard (Comfort Guest House)</option>
              <option value="Deluxe">Deluxe (Premium Rooms)</option>
              <option value="Heritage">Heritage (Luxury Resort)</option>
            </select>
          </div>

          {/* Sightseeing Approach */}
          <div>
            <label htmlFor="travel-sightseeing" style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: 'var(--burgundy)', marginBottom: '4px' }}>
              🌄 Sightseeing Plan
            </label>
            <select
              id="travel-sightseeing"
              value={sightseeingChoice}
              onChange={(e) => setSightseeingChoice(e.target.value)}
              style={{ padding: '0.55rem 0.75rem' }}
            >
              <option value="recommend">AI Recommended Highlights</option>
              <option value="later">Decide Later in Katra</option>
            </select>
          </div>
        </div>

        {/* Action Button */}
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary"
            style={{ padding: '0.75rem 2rem', fontSize: '0.92rem' }}
          >
            {loading ? 'Searching Verified Options...' : 'Search Yatra Options ➔'}
          </button>
        </div>
      </form>
    </div>
  );
}
