import React, { useState } from 'react';

/**
 * Parses raw activity strings or objects into structured timeline items:
 * - time: e.g. "10:00 AM – 01:30 PM", "05:30 AM", or "—"
 * - title: concise, scannable activity label (e.g. "Train journey to Katra")
 * - details: important specific facts, service IDs, or route guidance
 */
function parseItineraryActivity(activity) {
  if (!activity) return { time: '', title: '', details: '' };

  if (typeof activity === 'object') {
    return {
      time: activity.time || '',
      title: activity.title || activity.name || 'Scheduled Activity',
      details: activity.details || activity.description || '',
    };
  }

  const rawStr = String(activity).trim();
  let time = '';
  let content = rawStr;

  // Extract leading time / time-range if present (e.g. "10:00 AM – 01:30 PM: ...", "08:00 PM – Onward: ...")
  const timeMatch = rawStr.match(
    /^(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)(?:\s*[–\-—]\s*(?:\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)|[Oo]nward))?)\s*:\s*(.*)$/i
  );

  if (timeMatch) {
    time = timeMatch[1].trim();
    content = timeMatch[2].trim();
  } else {
    const singleTimeMatch = rawStr.match(/^(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))\s*[-–—:]\s*(.*)$/i);
    if (singleTimeMatch) {
      time = singleTimeMatch[1].trim();
      content = singleTimeMatch[2].trim();
    }
  }

  // 1. Inbound Train Travel
  if (/Travel by Train via|Train journey via/i.test(content)) {
    const match = content.match(
      /(?:Travel by Train via|Train journey via)\s+([\s\S]+?)\s+departing at\s+([\s\S]+?)\s+from\s+([\s\S]+?)\s+to\s+([\s\S]+)$/i
    );
    if (match) {
      const rawOpAndService = match[1].trim();
      const depTime = match[2].trim();
      const origin = match[3].trim();
      const dest = match[4].trim();

      let operator = rawOpAndService;
      let serviceNo = '';
      const parenMatch = rawOpAndService.match(/^(.+?)\s*\((.+)\)$/);
      if (parenMatch) {
        operator = parenMatch[1].trim();
        serviceNo = parenMatch[2].trim();
      }

      return {
        time,
        title: `Train journey to ${dest.includes('Katra') ? 'Katra' : dest}`,
        details: [operator, serviceNo, `Departs ${origin} at ${depTime}`].filter(Boolean).join(' · '),
      };
    }
  }

  // 2. Inbound Flight Travel
  if (/Fly with/i.test(content)) {
    const match = content.match(
      /Fly with\s+([\s\S]+?)\s+departing at\s+([\s\S]+?)\s+from\s+([\s\S]+?)\s+to\s+([\s\S]+)$/i
    );
    if (match) {
      const rawCarrierAndFlight = match[1].trim();
      const depTime = match[2].trim();
      const origin = match[3].trim();
      const dest = match[4].trim();

      let carrier = rawCarrierAndFlight;
      let flightNo = '';
      const parenMatch = rawCarrierAndFlight.match(/^(.+?)\s*\((.+)\)$/);
      if (parenMatch) {
        carrier = parenMatch[1].trim();
        flightNo = parenMatch[2].trim();
      }

      return {
        time,
        title: `Flight journey to ${dest.includes('Jammu') ? 'Jammu Airport' : dest}`,
        details: [carrier, flightNo, `Departs ${origin} at ${depTime}`].filter(Boolean).join(' · '),
      };
    }
  }

  // 3. Hotel Check-in & Station Transfer
  if (/transfer to hotel and check-in at|check-in at/i.test(content)) {
    const hotelMatch = content.match(/check-in at\s*([^()]+)\s*(?:\(([^)]+)\))?/i);
    const hotelName = hotelMatch ? hotelMatch[1].trim() : 'hotel';
    const hotelCat = hotelMatch && hotelMatch[2] ? `(${hotelMatch[2].trim()})` : '';
    return {
      time,
      title: 'Arrival & Hotel Check-in',
      details: [hotelName, hotelCat, 'Station/airport transfer to Katra base'].filter(Boolean).join(' · '),
    };
  }

  // 4. Hotel Check-out
  if (/hotel check-out/i.test(content)) {
    const outMatch = content.match(/hotel check-out at\s*(.*)/i);
    const hotelName = outMatch ? outMatch[1].trim() : '';
    return {
      time,
      title: 'Hotel Check-out',
      details: [hotelName ? `Check out at ${hotelName}` : 'Room check-out', 'Leisure morning breakfast'].join(' · '),
    };
  }

  // 5. Mandatory RFID Registration
  if (/RFID Registration/i.test(content)) {
    return {
      time,
      title: 'Mandatory Yatra RFID Registration',
      details: 'Obtain RFID tracking card at Katra counter · Required for trek barcode checkpoints',
    };
  }

  // 6. Return Journey (Train or Flight)
  if (/return journey to.*by Train/i.test(content) || /Transfer to Katra Railway Station/i.test(content)) {
    const destMatch = content.match(/return journey to\s*([^ by]+)/i);
    const dest = destMatch ? destMatch[1].trim() : 'origin';
    return {
      time,
      title: `Return Train Journey to ${dest}`,
      details: 'Transfer to Katra railway station · Scheduled return departure',
    };
  }

  if (/return flight to/i.test(content) || /Taxi transfer to Jammu Airport/i.test(content)) {
    const destMatch = content.match(/return flight to\s*([^.]+)/i);
    const dest = destMatch ? destMatch[1].trim() : 'origin';
    return {
      time,
      title: `Return Flight to ${dest}`,
      details: 'Road transfer via NH-44 to Jammu Airport · Scheduled return flight',
    };
  }

  // 7. Holy Darshan of Maa Vaishno Devi Ji
  if (/Sacred Darshan of Maa Vaishno Devi Ji/i.test(content)) {
    const slotMatch = content.match(/\(([^)]+)\)/);
    const slotInfo = slotMatch ? slotMatch[1].trim() : '';
    return {
      time,
      title: 'Sacred Darshan at Holy Bhawan',
      details: ['Maa Vaishno Devi Ji Holy Cave Darshan', slotInfo].filter(Boolean).join(' · '),
    };
  }

  // 8. Bhairavnath Temple
  if (/Bhairavnath Temple/i.test(content)) {
    return {
      time,
      title: 'Bhairavnath Temple Darshan',
      details: 'Ropeway or ~3 km mountain trek from Bhawan · Completes the holy pilgrimage',
    };
  }

  // 9. En Route Shrines: Charan Paduka & Ardhkuwari
  if (/Charan Paduka/i.test(content) || /Ardhkuwari/i.test(content) || /Garbh Joon/i.test(content)) {
    return {
      time,
      title: 'En Route Shrines: Charan Paduka & Ardhkuwari',
      details: 'Midway darshan & Garbh Joon cave pause along the trek route',
    };
  }

  // 10. Holy Trek Departure (Helicopter or on Foot)
  if (/Helicopter flight from Katra helipad/i.test(content)) {
    return {
      time,
      title: 'Helicopter Flight to Sanjichhat',
      details: 'Katra Helipad ➔ Sanjichhat (~8 mins) · 2.5 km gentle walk to Bhawan',
    };
  }

  if (/trek departure from Katra/i.test(content)) {
    return {
      time,
      title: 'Holy Trek Departure from Katra',
      details: 'Via Ban Ganga / Tarakote Marg · 13 km mountain ascent to Bhawan',
    };
  }

  // 11. Descent to Katra Base
  if (/descent back to Katra/i.test(content) || /Return flight via Sanjichhat helipad/i.test(content)) {
    return {
      time,
      title: content.includes('flight') ? 'Return Flight to Katra Base' : 'Descent to Katra Base',
      details: 'Scenic return journey to Katra hotel · Overnight muscle recovery & rest',
    };
  }

  // 12. Post-Trek Recovery & Breakfast
  if (/foot muscle recovery|Leisure breakfast, sleep-in/i.test(content)) {
    return {
      time,
      title: 'Leisure Breakfast & Muscle Recovery',
      details: 'Morning sleep-in and gentle foot relaxation at hotel after the trek',
    };
  }

  // 13. Souvenir & Prasad Shopping
  if (/Last-minute Katra bazaar shopping/i.test(content)) {
    return {
      time,
      title: 'Souvenir & Prasad Shopping',
      details: 'Katra bazaar visit for walnuts, dry fruits & Mata prasad',
    };
  }

  if (/market stroll/i.test(content) || /bazaar/i.test(content)) {
    return {
      time,
      title: 'Katra Market Stroll & Orientation',
      details: 'Explore local bazaars for dry fruits, prasad & devotional souvenirs',
    };
  }

  // 14. Dining & Rest
  if (/dinner/i.test(content)) {
    return {
      time,
      title: /Dogra/i.test(content) ? 'Traditional Dogra Dinner' : 'Evening Dinner & Rest',
      details: 'Relaxed dining in Katra town',
    };
  }

  // 15. Sightseeing Excursions (Baba Dhansar, Patnitop, Shiv Khori, Nau Devi, etc.)
  const excursionMatch = content.match(
    /(?:Afternoon gentle excursion to|Guided exploration of|Scenic mountain drive to|Transit to|Explore|Short visit to)\s*([^,()]+)(?:\(([^)]+)\))?/i
  );
  if (excursionMatch) {
    const place = excursionMatch[1].trim();
    const note = excursionMatch[2] ? excursionMatch[2].trim() : '';
    const isExcursion = !place.toLowerCase().startsWith('visit') && !place.toLowerCase().startsWith('explore');
    return {
      time,
      title: isExcursion ? `Excursion to ${place}` : place,
      details: note || `Scenic sightseeing and spiritual exploration of ${place}`,
    };
  }

  // General fallback: if content has punctuation, split first clause as title
  const parts = content.split(/[:;·—–-]\s+/);
  if (parts.length > 1 && parts[0].length <= 50) {
    return {
      time,
      title: parts[0].trim(),
      details: parts.slice(1).join(' · ').trim(),
    };
  }

  return {
    time,
    title: content,
    details: '',
  };
}

/**
 * Generates a concise one-line summary for a day card (visible whether collapsed or expanded)
 */
function generateDaySummary(day) {
  if (!day) return '';
  const dayNum = Number(day.day_number) || 1;
  const title = (day.title || '').toLowerCase();

  // Use existing concise summary if clean and short
  if (day.summary && typeof day.summary === 'string' && day.summary.length < 130 && !day.summary.includes(' · ')) {
    return day.summary;
  }

  if (dayNum === 1 || title.includes('arrival')) {
    return 'Arrival in Katra, hotel check-in, mandatory RFID registration, and overnight rest.';
  }
  if (title.includes('recovery') || title.includes('dhansar') || title.includes('local sightseeing')) {
    return 'Post-trek physical recovery, relaxed morning breakfast, and gentle afternoon excursion.';
  }
  if (dayNum === 2 || title.includes('holy yatra') || title.includes('darshan trek') || title.includes('bhawan')) {
    return 'Holy trek to Bhawan, sacred darshan of Maa Vaishno Devi Ji, Bhairavnath shrine, and descent.';
  }
  if (title.includes('patnitop') || title.includes('sanasar') || title.includes('excursion')) {
    return 'Scenic mountain drive, guided meadow exploration, and viewpoints.';
  }
  if (title.includes('return') || title.includes('check-out') || title.includes('departure')) {
    return 'Hotel check-out, souvenir shopping in Katra bazaar, and return journey home.';
  }

  // Derive from activities
  if (Array.isArray(day.activities) && day.activities.length > 0) {
    const titles = day.activities
      .slice(0, 3)
      .map((a) => parseItineraryActivity(a).title)
      .filter(Boolean);
    if (titles.length > 0) {
      return titles.join(', ') + '.';
    }
  }

  return day.practicality_note || day.title || 'Day activities and scheduled halts.';
}

export default function ItineraryTimeline({
  itinerary = [],
  daysCount = null,
  feasiblePlaces = [],
  infeasiblePlaces = [],
  _sightseeingChoice = null,
  _selectedPlacesCount = 0,
  onEditCategory = null,
  onModifySights = null,
  onProceed = null,
  onBack = null,
}) {
  // Collapsible Days State: Day 1 (index 0) expanded by default; other days collapsed
  const [expandedDays, setExpandedDays] = useState({ 0: true });

  if (!itinerary || itinerary.length === 0) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '2.5rem 1.5rem', background: '#FFFFFF' }}>
        <div style={{ fontSize: '2rem', marginBottom: '8px' }}>🗓️</div>
        <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.15rem', color: 'var(--burgundy)', fontWeight: 700 }}>
          Generating Customized Day-by-Day Sacred Itinerary...
        </div>
        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>
          Organizing transport timings, darshan slots, and pacing buffers.
        </div>
      </div>
    );
  }

  const safeFeasible = Array.isArray(feasiblePlaces) ? feasiblePlaces : [];
  const safeInfeasible = Array.isArray(infeasiblePlaces) ? infeasiblePlaces : [];
  const effectiveDaysCount = daysCount || itinerary.length;

  const toggleDay = (idx) => {
    setExpandedDays((prev) => ({
      ...prev,
      [idx]: !prev[idx],
    }));
  };

  const allExpanded = itinerary.every((_, idx) => expandedDays[idx]);

  const handleToggleAll = () => {
    if (allExpanded) {
      setExpandedDays({});
    } else {
      const all = {};
      itinerary.forEach((_, idx) => {
        all[idx] = true;
      });
      setExpandedDays(all);
    }
  };

  const handleModifySights = () => {
    if (onModifySights) {
      onModifySights();
    } else if (onEditCategory) {
      onEditCategory('sightseeing');
    }
  };

  return (
    <div style={{ width: '100%' }}>
      {/* 1. Header Bar: Main Heading, Actions & Compact Feasibility */}
      <div style={{ marginBottom: '1.25rem' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: '12px',
          marginBottom: '10px',
        }}>
          <div>
            <h3
              style={{
                fontFamily: 'var(--font-serif)',
                fontWeight: 800,
                fontSize: '1.2rem',
                color: 'var(--burgundy)',
                margin: '0 0 4px 0',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <span>🗓️</span> Day-by-Day Sacred Itinerary
            </h3>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              Tailored around your darshan slots, transport timings, and recovery buffers ({effectiveDaysCount} Days)
            </div>
          </div>

          {/* Header Action Controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <button
              type="button"
              data-testid="itinerary-toggle-all-btn"
              onClick={handleToggleAll}
              className="btn btn-outline"
              style={{
                fontSize: '0.76rem',
                padding: '5px 12px',
                borderColor: 'var(--gold-border)',
                background: '#FFFFFF',
                color: 'var(--text-dark)',
              }}
            >
              {allExpanded ? 'Collapse All' : 'Expand All'}
            </button>

            {(onModifySights || onEditCategory) && (
              <button
                type="button"
                data-testid="itinerary-modify-sights-btn"
                onClick={handleModifySights}
                className="btn btn-outline"
                style={{
                  fontSize: '0.76rem',
                  padding: '5px 14px',
                  borderColor: 'var(--gold-primary)',
                  color: 'var(--burgundy)',
                  fontWeight: 700,
                  background: '#FFFFFF',
                }}
              >
                🌄 Modify Sights
              </button>
            )}
          </div>
        </div>

        {/* Compact Feasible Sightseeing Summary Bar */}
        {safeFeasible.length > 0 && (
          <div
            data-testid="feasible-advisory"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              flexWrap: 'wrap',
              background: '#F6FAF7',
              border: '1px solid #C3E6CB',
              borderRadius: '10px',
              padding: '7px 12px',
              marginBottom: '8px',
            }}
          >
            <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#155724' }}>
              ✓ Feasible Sights Included:
            </span>
            {safeFeasible.map((place, idx) => {
              const name = typeof place === 'string' ? place : (place?.name || place?.place || String(place));
              return (
                <span
                  key={idx}
                  data-testid="feasible-place-badge"
                  className="pill pill-gold"
                  style={{ fontSize: '0.72rem', padding: '2px 8px' }}
                >
                  ✓ {name}
                </span>
              );
            })}
          </div>
        )}

        {/* Compact Infeasible / Omitted Destinations Advisory */}
        {safeInfeasible.length > 0 && (
          <div
            data-testid="infeasible-advisory"
            style={{
              background: '#FFF9F6',
              border: '1px solid #F5C6CB',
              borderLeft: '4px solid #C0392B',
              borderRadius: '10px',
              padding: '9px 12px',
              marginBottom: '8px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 800, color: '#721C24', fontSize: '0.78rem', marginBottom: '4px' }}>
              <span>⚠️</span>
              <span>Omitted Destinations ({safeInfeasible.length}):</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {safeInfeasible.map((item, idx) => {
                const placeName = typeof item === 'string' ? item : (item.place || item.name || 'Destination');
                const reason = typeof item === 'object' ? item.reason : null;
                const suggestion = typeof item === 'object' ? item.suggestion : null;
                return (
                  <div key={idx} data-testid="infeasible-place-card" style={{ fontSize: '0.75rem', color: '#721C24', lineHeight: 1.4 }}>
                    <b>{placeName}:</b> {reason || 'Omitted due to trip duration and pacing constraints.'}
                    {suggestion && <span style={{ color: '#155724', marginLeft: '6px' }}>💡 {suggestion}</span>}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* 2. List of Distinct Day Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '1.25rem' }}>
        {itinerary.map((day, idx) => {
          const dayNum = day.day_number || idx + 1;
          const isExpanded = !!expandedDays[idx];
          const rawActivities = Array.isArray(day.activities) ? day.activities : [];
          const parsedActivities = rawActivities.map(parseItineraryActivity);
          const daySummary = generateDaySummary(day);

          return (
            <div
              key={idx}
              data-testid={`itinerary-day-card-${dayNum}`}
              className="itinerary-day-card"
            >
              {/* Day Header Trigger Button (Accessible, Keyboard Friendly) */}
              <button
                type="button"
                data-testid={`day-header-${dayNum}`}
                aria-expanded={isExpanded}
                aria-controls={`day-timeline-${dayNum}`}
                onClick={() => toggleDay(idx)}
                style={{
                  width: '100%',
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  textAlign: 'left',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                }}
              >
                {/* Header Row: DAY Pill, Day Title, Date, Chevron */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <span
                      data-testid={`day-label-${dayNum}`}
                      className="pill pill-burgundy"
                      style={{ fontSize: '0.72rem', padding: '2px 8px', fontWeight: 700, letterSpacing: '0.04em' }}
                    >
                      DAY {dayNum}
                    </span>
                    <span
                      data-testid={`day-title-${dayNum}`}
                      style={{
                        fontFamily: 'var(--font-serif)',
                        fontWeight: 800,
                        fontSize: '0.96rem',
                        color: 'var(--burgundy)',
                        lineHeight: 1.3,
                      }}
                    >
                      {day.title || `Day ${dayNum}`}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                    <span
                      data-testid={`day-date-${dayNum}`}
                      style={{ fontSize: '0.78rem', color: 'var(--gold-primary)', fontWeight: 600 }}
                    >
                      {day.date || `Day ${dayNum}`}
                    </span>
                    <span
                      data-testid={`day-chevron-${dayNum}`}
                      style={{
                        fontSize: '0.82rem',
                        color: 'var(--burgundy)',
                        display: 'inline-block',
                        transition: 'transform 0.2s ease',
                        transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                        userSelect: 'none',
                      }}
                      aria-hidden="true"
                    >
                      ▶
                    </span>
                  </div>
                </div>

                {/* Day Brief Summary (Remains visible whether collapsed or expanded) */}
                <div
                  data-testid={`day-summary-${dayNum}`}
                  style={{
                    fontSize: '0.79rem',
                    color: 'var(--text-muted)',
                    lineHeight: 1.45,
                    paddingLeft: '2px',
                  }}
                >
                  {daySummary}
                </div>
              </button>

              {/* Collapsible Timeline Content */}
              {isExpanded && (
                <div
                  id={`day-timeline-${dayNum}`}
                  data-testid={`day-timeline-${dayNum}`}
                  style={{
                    marginTop: '12px',
                    paddingTop: '12px',
                    borderTop: '1px solid var(--border-subtle, #E4D5B7)',
                  }}
                >
                  {parsedActivities.length > 0 ? (
                    parsedActivities.map((act, actIdx) => {
                      const isLast = actIdx === parsedActivities.length - 1;
                      return (
                        <div
                          key={actIdx}
                          data-testid={`timeline-item-${dayNum}-${actIdx}`}
                          className="timeline-item-container"
                        >
                          {/* Left Column: Prominent Start Time / Range */}
                          <div
                            data-testid={`timeline-time-${dayNum}-${actIdx}`}
                            className="timeline-time-col"
                          >
                            {act.time || '—'}
                          </div>

                          {/* Center Column: Marker & Vertical Connecting Line */}
                          <div className="timeline-marker-col">
                            <div
                              data-testid={`timeline-marker-${dayNum}-${actIdx}`}
                              className="timeline-dot"
                            />
                            {!isLast && <div className="timeline-connector" />}
                          </div>

                          {/* Right Column: Title & Concise Details */}
                          <div
                            data-testid={`timeline-content-${dayNum}-${actIdx}`}
                            className="timeline-content-col"
                          >
                            <div
                              data-testid={`timeline-title-${dayNum}-${actIdx}`}
                              style={{
                                fontSize: '0.86rem',
                                fontWeight: 700,
                                color: 'var(--burgundy)',
                                lineHeight: 1.3,
                              }}
                            >
                              {act.title}
                            </div>
                            {act.details ? (
                              <div
                                data-testid={`timeline-desc-${dayNum}-${actIdx}`}
                                style={{
                                  fontSize: '0.78rem',
                                  color: 'var(--text-muted)',
                                  marginTop: '2px',
                                  lineHeight: 1.4,
                                }}
                              >
                                {act.details}
                              </div>
                            ) : null}
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontStyle: 'italic', padding: '6px 0' }}>
                      No scheduled activities recorded for this day.
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 3. Pacing & Recovery Informational Note (Subtle, separate section beneath the timeline) */}
      <div
        data-testid="itinerary-pacing-note"
        style={{
          background: '#FAF6EE',
          border: '1px solid var(--gold-border)',
          borderRadius: '12px',
          padding: '10px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
        }}
      >
        <span style={{ fontSize: '1.1rem' }}>⚡</span>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
          <b style={{ color: 'var(--burgundy)' }}>Pacing Note:</b> Dedicated rest buffers are allocated post-Bhawan descent before any local Jammu sightseeing to protect against pilgrim fatigue.
        </div>
      </div>

      {/* 4. Sequential Step Navigation Buttons (if rendered in step-by-step flow) */}
      {(onBack || onProceed) && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1.5rem' }}>
          {onBack ? (
            <button type="button" onClick={onBack} className="btn btn-outline" style={{ fontSize: '0.85rem' }}>
              ← Back to Sightseeing
            </button>
          ) : <div />}

          {onProceed ? (
            <button type="button" onClick={onProceed} className="btn btn-primary" style={{ padding: '0.75rem 2rem', fontSize: '0.9rem' }}>
              Proceed to Review &amp; Authorization ➔
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}
