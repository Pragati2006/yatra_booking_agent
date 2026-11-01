import React, { useState, useEffect, useMemo } from 'react';
import SightseeingCard from './SightseeingCard';
import { getSightseeing } from '../services/api';

const CATEGORY_TABS = [
  { id: 'All', label: 'All Destinations' },
  { id: 'On the trek route', label: 'On Trek Route' },
  { id: 'Nearby temple', label: 'Nearby Temples' },
  { id: 'Nature', label: 'Nature & Springs' },
  { id: 'Hill station', label: 'Hill Stations' },
  { id: 'Hill station / adventure', label: 'Adventure / Hill' },
  { id: 'Nature / heritage', label: 'Heritage Sites' },
  { id: 'Jammu city', label: 'Jammu City' },
  { id: 'Kashmir', label: 'Kashmir Valley' },
];

export default function SightseeingBrowser({
  places = [],
  selectedPlaces = [],
  onToggleSelect,
  onGenerateItinerary,
  onChooseLater,
  onSkipSightseeing = null,
  onReviewTripDirectly = null,
  returnedFromReview = false,
  onBack = null,
  loading = false,
  error = '',
  tripRequest = null,
  isStandalone = false,
  title = null,
  subtitle = null,
  onExplorePlace = null,
  onPlanYatra = null,
}) {
  const [internalPlaces, setInternalPlaces] = useState([]);
  const [internalLoading, setInternalLoading] = useState(() => !places || places.length === 0);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [localSelected, setLocalSelected] = useState([]);

  useEffect(() => {
    if (!places || places.length === 0) {
      getSightseeing()
        .then((data) => {
          if (data && data.places) setInternalPlaces(data.places);
        })
        .catch((err) => console.error('Failed to load sightseeing destinations:', err))
        .finally(() => setInternalLoading(false));
    }
  }, [places]);

  const allPlaces = places && places.length > 0 ? places : internalPlaces;
  const isLoading = loading || internalLoading;
  const effectiveSelected = onToggleSelect ? selectedPlaces : localSelected;

  const handleToggle = (place) => {
    if (onToggleSelect) {
      onToggleSelect(place);
    } else {
      setLocalSelected((prev) => {
        const pName = typeof place === 'object' ? place.name : place;
        const exists = prev.some((p) => (typeof p === 'object' ? p.name : p) === pName);
        if (exists) return prev.filter((p) => (typeof p === 'object' ? p.name : p) !== pName);
        return [...prev, place];
      });
    }
  };

  // Compute category place counts
  const categoryCounts = useMemo(() => {
    const counts = { All: allPlaces.length };
    allPlaces.forEach((p) => {
      const cat = p.category || 'Other';
      counts[cat] = (counts[cat] || 0) + 1;
    });
    return counts;
  }, [allPlaces]);

  // Filter places based on search query and selected category
  const filteredPlaces = useMemo(() => {
    return allPlaces.filter((p) => {
      const matchesCategory = selectedCategory === 'All' || p.category === selectedCategory;
      if (!matchesCategory) return false;

      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase().trim();
      const nameMatch = p.name && p.name.toLowerCase().includes(q);
      const descMatch = p.description && p.description.toLowerCase().includes(q);
      const regionMatch = p.region && p.region.toLowerCase().includes(q);
      return nameMatch || descMatch || regionMatch;
    });
  }, [allPlaces, selectedCategory, searchQuery]);

  // Check if a place object is selected
  const isPlaceSelected = (place) => {
    return effectiveSelected.some((p) => {
      const pName = typeof p === 'object' ? p.name : p;
      return String(pName).toLowerCase() === String(place.name).toLowerCase();
    });
  };

  return (
    <div data-testid="sightseeing-browser" style={{ width: '100%', marginBottom: '2.5rem' }}>
      {/* 1. Header Bar with Trip Context */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        flexWrap: 'wrap',
        gap: '14px',
        marginBottom: '1.25rem',
      }}>
        <div>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            background: '#FAF5EE',
            border: '1px solid var(--gold-border)',
            borderRadius: '16px',
            padding: '4px 12px',
            fontSize: '0.78rem',
            fontWeight: 700,
            color: 'var(--burgundy)',
            marginBottom: '6px',
          }}>
            <span>🏔️</span> Jammu &amp; Kashmir Destination Catalogue
          </div>
          <h2 style={{
            fontFamily: 'var(--font-serif)',
            fontWeight: 800,
            fontSize: '1.5rem',
            color: 'var(--burgundy)',
            margin: '0 0 4px 0',
          }}>
            {title || (isStandalone ? 'Featured Destinations across Jammu & Kashmir' : 'Select Sightseeing & Holy Shrines')}
          </h2>
          <p style={{ fontSize: '0.86rem', color: 'var(--text-muted)', margin: 0 }}>
            {subtitle || (isStandalone ? `Showing ${allPlaces.length} verified spiritual shrines, scenic valleys, and heritage sites across Katra and Jammu.` : `Showing ${allPlaces.length} verified destinations across Katra, Jammu, and surrounding valleys. Select destinations to customize your timeline.`)}
            {tripRequest?.origin && (
              <span style={{ marginLeft: '10px', fontSize: '0.8rem', background: '#FFFFFF', padding: '2px 8px', borderRadius: '8px', border: '1px solid var(--gold-border)' }}>
                📍 {tripRequest.origin} • {tripRequest.pax || 2} Pilgrims • {tripRequest.duration_days || 4} Days
              </span>
            )}
          </p>
        </div>

        {/* Top Action Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {effectiveSelected.length > 0 && (
            <span
              data-testid="selected-count-badge"
              className="pill pill-gold"
              style={{ fontSize: '0.84rem', padding: '6px 14px', fontWeight: 700 }}
            >
              ✓ {effectiveSelected.length} Places Selected
            </span>
          )}
          {isStandalone && onPlanYatra && (
            <button
              type="button"
              data-testid="standalone-start-yatra-btn"
              onClick={() => onPlanYatra(effectiveSelected)}
              className="btn btn-primary"
              style={{ padding: '0.65rem 1.6rem', fontSize: '0.86rem' }}
            >
              Plan Yatra with Destinations ➔
            </button>
          )}
          {!isStandalone && onGenerateItinerary && (
            <button
              type="button"
              data-testid="generate-itinerary-top-btn"
              onClick={onGenerateItinerary}
              disabled={loading}
              className="btn btn-primary"
              style={{ padding: '0.65rem 1.6rem', fontSize: '0.86rem' }}
            >
              {loading ? 'Building Timeline...' : `Build Itinerary (${effectiveSelected.length}) ➔`}
            </button>
          )}
        </div>
      </div>

      {/* 2. Selected Places Interactive Summary Bar */}
      <div
        data-testid="selected-places-summary"
        style={{
          background: effectiveSelected.length > 0 ? '#FFFDF7' : '#FAF6EE',
          border: '1.5px solid var(--gold-border)',
          borderRadius: '14px',
          padding: '12px 18px',
          marginBottom: '1.5rem',
          boxShadow: '0 2px 8px rgba(61, 8, 16, 0.04)',
        }}
      >
        {effectiveSelected.length > 0 ? (
          <div>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '8px',
              flexWrap: 'wrap',
              gap: '8px',
            }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--burgundy)' }}>
                📍 {isStandalone ? 'Selected Destinations' : 'Selected for Your Yatra'} ({effectiveSelected.length}):
              </span>
              <button
                type="button"
                data-testid="clear-all-sightseeing-btn"
                onClick={() => {
                  if (onToggleSelect) {
                    selectedPlaces.forEach((p) => {
                      const matched = allPlaces.find(
                        (pl) => pl.name.toLowerCase() === (p.name || p).toLowerCase()
                      );
                      if (matched) onToggleSelect(matched);
                    });
                  } else {
                    setLocalSelected([]);
                  }
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#721C24',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  textDecoration: 'underline',
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                Clear All Selections
              </button>
            </div>

            {/* List of Selected Place Tags with Remove Button */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {effectiveSelected.map((p, idx) => {
                const name = typeof p === 'object' ? p.name : p;
                const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
                return (
                  <span
                    key={idx}
                    data-testid={`selected-place-tag-${slug}`}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      background: '#FFFFFF',
                      border: '1px solid var(--gold-primary)',
                      borderRadius: '20px',
                      padding: '4px 10px',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      color: 'var(--burgundy)',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                    }}
                  >
                    <span>🔱 {name}</span>
                    <button
                      type="button"
                      data-testid={`remove-place-${slug}`}
                      onClick={() => {
                        const matched = allPlaces.find(
                          (pl) => pl.name.toLowerCase() === name.toLowerCase()
                        );
                        handleToggle(matched || { name });
                      }}
                      title={`Remove ${name}`}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#991B1B',
                        fontSize: '0.9rem',
                        lineHeight: 1,
                        cursor: 'pointer',
                        padding: '0 2px',
                        display: 'flex',
                        alignItems: 'center',
                      }}
                    >
                      ✕
                    </button>
                  </span>
                );
              })}
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ fontSize: '0.84rem', color: 'var(--text-muted)' }}>
              {isStandalone ? (
                <span><b>Explore &amp; Discover:</b> Inspect verified historical facts, route guidance, timings, and entry fees for 29 sacred destinations. Click any card to read heritage details, ask the AI companion, or start a customized pilgrimage plan.</span>
              ) : (
                <span><b>💡 Optional Sightseeing:</b> Choose spiritual shrines and scenic spots to include in your personalized itinerary, or click <b>Decide Later</b> to focus solely on the Maa Vaishno Devi pilgrimage.</span>
              )}
            </div>
            {!isStandalone && onChooseLater && (
              <button
                type="button"
                data-testid="decide-later-hint-btn"
                onClick={onChooseLater}
                className="btn btn-outline"
                style={{ fontSize: '0.78rem', padding: '4px 12px' }}
              >
                Decide Later in Katra
              </button>
            )}
          </div>
        )}
      </div>

      {/* 3. Search & Category Filters Toolbar */}
      <div
        className="card"
        style={{
          padding: '14px 16px',
          marginBottom: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          background: '#FFFFFF',
        }}
      >
        {/* Search Row */}
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: '1 1 260px' }}>
            <span style={{
              position: 'absolute',
              left: '12px',
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--text-muted)',
              fontSize: '0.9rem',
            }}>
              🔍
            </span>
            <input
              type="text"
              data-testid="sightseeing-search-input"
              placeholder="Search by destination name (e.g. 'Bhairavnath', 'Patnitop', 'Baba Dhansar')..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 36px 8px 34px',
                fontSize: '0.86rem',
                borderRadius: '8px',
                border: '1.5px solid var(--gold-border)',
              }}
            />
            {searchQuery && (
              <button
                type="button"
                data-testid="clear-search-btn"
                onClick={() => setSearchQuery('')}
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  fontSize: '0.9rem',
                }}
              >
                ✕
              </button>
            )}
          </div>

          <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
            Showing <b>{filteredPlaces.length}</b> of {allPlaces.length} destinations
          </div>
        </div>

        {/* Category Pills Row */}
        <div
          data-testid="category-filters"
          style={{
            display: 'flex',
            gap: '8px',
            overflowX: 'auto',
            paddingBottom: '4px',
            flexWrap: 'wrap',
          }}
        >
          {CATEGORY_TABS.map((cat) => {
            const count = categoryCounts[cat.id] || 0;
            const isActive = selectedCategory === cat.id;
            return (
              <button
                key={cat.id}
                type="button"
                data-testid={`category-filter-${cat.id.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
                onClick={() => setSelectedCategory(cat.id)}
                className={`btn ${isActive ? 'btn-primary' : 'btn-outline'}`}
                style={{
                  padding: '5px 12px',
                  fontSize: '0.76rem',
                  borderRadius: '20px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  whiteSpace: 'nowrap',
                }}
              >
                <span>{cat.label}</span>
                <span
                  style={{
                    background: isActive ? 'rgba(255,255,255,0.25)' : 'var(--gold-subtle)',
                    color: isActive ? '#FFFFFF' : 'var(--burgundy)',
                    padding: '1px 6px',
                    borderRadius: '10px',
                    fontSize: '0.7rem',
                    fontWeight: 700,
                  }}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 4. Error Display */}
      {error && (
        <div style={{
          background: '#FFF4F4',
          border: '1px solid #F5C6CB',
          color: '#721C24',
          padding: '10px 16px',
          borderRadius: '10px',
          marginBottom: '1.25rem',
          fontSize: '0.85rem',
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* 5. Destination Grid / Empty State */}
      {isLoading && allPlaces.length === 0 ? (
        <div
          data-testid="sightseeing-loading-state"
          style={{
            textAlign: 'center',
            padding: '3rem 1.5rem',
            background: '#FAF6EE',
            border: '1.5px solid var(--gold-border)',
            borderRadius: '16px',
            marginBottom: '2.5rem',
          }}
        >
          <div style={{ fontSize: '2rem', marginBottom: '8px' }}>⏳</div>
          <div style={{ fontFamily: 'var(--font-serif)', color: 'var(--burgundy)', fontWeight: 700 }}>
            Loading Sacred &amp; Scenic Destinations...
          </div>
        </div>
      ) : filteredPlaces.length > 0 ? (
        <div
          data-testid="sightseeing-grid"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '18px',
            marginBottom: '2.5rem',
          }}
        >
          {filteredPlaces.map((place, idx) => (
            <SightseeingCard
              key={idx}
              place={place}
              isSelected={isPlaceSelected(place)}
              onToggleSelect={() => handleToggle(place)}
              onExplorePlace={onExplorePlace}
            />
          ))}
        </div>
      ) : (
        <div
          data-testid="sightseeing-empty-state"
          style={{
            textAlign: 'center',
            padding: '3rem 1.5rem',
            background: '#FAF6EE',
            border: '1.5px dashed var(--gold-border)',
            borderRadius: '16px',
            marginBottom: '2.5rem',
          }}
        >
          <div style={{ fontSize: '2.5rem', marginBottom: '8px' }}>🔍</div>
          <h3 style={{ fontFamily: 'var(--font-serif)', color: 'var(--burgundy)', margin: '0 0 6px 0' }}>
            No Destinations Found
          </h3>
          <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', maxWidth: '440px', margin: '0 auto 1.25rem' }}>
            No shrines or scenic spots match "{searchQuery}" in category "{selectedCategory}". Try clearing your search query or selecting "All Destinations".
          </p>
          <button
            type="button"
            data-testid="reset-filters-btn"
            onClick={() => {
              setSearchQuery('');
              setSelectedCategory('All');
            }}
            className="btn btn-outline"
            style={{ fontSize: '0.82rem' }}
          >
            Reset Search & Category Filters
          </button>
        </div>
      )}

      {/* 6. Bottom Sticky Navigation & Actions */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '12px',
        padding: '14px 18px',
        background: '#FFFFFF',
        border: '1.5px solid var(--gold-border)',
        borderRadius: '16px',
        boxShadow: 'var(--shadow-md)',
      }}>
        {isStandalone ? (
          <>
            <div>
              {onBack && (
                <button
                  type="button"
                  data-testid="destinations-back-home-btn"
                  onClick={onBack}
                  className="btn btn-outline"
                  style={{ fontSize: '0.85rem' }}
                >
                  ← Back to Home
                </button>
              )}
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              {onPlanYatra && (
                <button
                  type="button"
                  data-testid="destinations-plan-trip-btn"
                  onClick={() => onPlanYatra(effectiveSelected)}
                  className="btn btn-primary"
                  style={{ padding: '0.65rem 2rem', fontSize: '0.88rem' }}
                >
                  Plan Your Yatra Now ➔
                </button>
              )}
            </div>
          </>
        ) : (
          <>
            <div>
              {onBack && (
                <button
                  type="button"
                  data-testid="sightseeing-back-btn"
                  onClick={onBack}
                  className="btn btn-outline"
                  style={{ fontSize: '0.85rem' }}
                >
                  ← Back to Accommodation
                </button>
              )}
            </div>

            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              {(onSkipSightseeing || onChooseLater) && (
                <button
                  type="button"
                  data-testid="skip-sightseeing-btn"
                  onClick={onSkipSightseeing || onChooseLater}
                  disabled={loading}
                  className="btn btn-outline"
                  style={{
                    borderColor: 'var(--gold-primary)',
                    color: 'var(--burgundy)',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                  }}
                >
                  ⏭️ Skip Sightseeing
                </button>
              )}

              {onChooseLater && (
                <button
                  type="button"
                  data-testid="choose-later-btn"
                  onClick={onChooseLater}
                  disabled={loading}
                  className="btn btn-outline"
                  style={{
                    borderColor: 'var(--gold-border)',
                    color: 'var(--text-muted)',
                    fontSize: '0.85rem',
                  }}
                >
                  Decide Later in Katra
                </button>
              )}

              {onReviewTripDirectly && (
                <button
                  type="button"
                  data-testid="review-trip-direct-btn"
                  onClick={onReviewTripDirectly}
                  disabled={loading}
                  className="btn btn-outline"
                  style={{
                    borderColor: 'var(--gold-primary)',
                    color: 'var(--burgundy)',
                    fontSize: '0.85rem',
                    fontWeight: 700,
                  }}
                >
                  📋 Review Trip &amp; Continue ➔
                </button>
              )}

              {returnedFromReview && (
                <button
                  type="button"
                  data-testid="back-to-review-btn"
                  onClick={onReviewTripDirectly}
                  className="btn btn-secondary"
                  style={{ fontSize: '0.85rem' }}
                >
                  ↩ Back to Trip Review
                </button>
              )}

              {onGenerateItinerary && (
                <button
                  type="button"
                  data-testid="generate-itinerary-btn"
                  onClick={onGenerateItinerary}
                  disabled={loading}
                  className="btn btn-primary"
                  style={{
                    padding: '0.75rem 2rem',
                    fontSize: '0.9rem',
                    fontWeight: 700,
                  }}
                >
                  {loading
                    ? 'Building Timeline...'
                    : `Generate Day-Wise Itinerary (${effectiveSelected.length} selected) ➔`}
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
