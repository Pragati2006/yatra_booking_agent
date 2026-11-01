import React from 'react';

export default function Navbar({
  activeTab,
  setActiveTab,
  user = null,
  onOpenAuthModal,
  onOpenSavedTrips,
  onLogout,
}) {
  return (
    <header style={{
      background: '#FFFFFF',
      border: '1.5px solid var(--gold-border)',
      borderRadius: '22px',
      padding: '0.65rem 1.6rem',
      marginTop: '0.75rem',
      marginBottom: '1rem',
      boxShadow: '0 4px 16px rgba(88, 17, 26, 0.05)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      position: 'sticky',
      top: '0.75rem',
      zIndex: 100,
      flexWrap: 'wrap',
      gap: '0.75rem',
    }}>
      {/* Brand */}
      <div 
        data-testid="nav-brand-logo"
        role="button"
        tabIndex={0}
        onClick={() => setActiveTab('home')}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveTab('home'); } }}
        style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}
      >
        <div style={{
          width: '38px',
          height: '38px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #58111A 0%, #3D0810 100%)',
          border: '1.5px solid #B8860B',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#E5D2AD',
          fontSize: '1.15rem',
          boxShadow: '0 2px 6px rgba(88,17,26,0.2)',
        }}>
          🔱
        </div>
        <div>
          <div style={{
            fontFamily: 'var(--font-serif)',
            fontWeight: 800,
            fontSize: '1.05rem',
            color: 'var(--burgundy)',
            letterSpacing: '0.04em',
            lineHeight: 1.1,
          }}>
            VAISHNO DEVI YATRA
          </div>
          <div style={{
            fontSize: '0.7rem',
            fontWeight: 600,
            color: 'var(--gold-primary)',
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
          }}>
            Pilgrimage & Tourism AI
          </div>
        </div>
      </div>

      {/* Nav Links */}
      <nav style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
        {[
          { id: 'home', label: 'Home' },
          { id: 'booking', label: 'Darshan Bookings' },
          { id: 'sightseeing', label: 'Featured Destinations' },
          { id: 'assistant', label: 'AI Companion' },
        ].map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              data-testid={`nav-${item.id}`}
              aria-current={isActive ? 'page' : undefined}
              onClick={() => setActiveTab(item.id)}
              style={{
                background: isActive ? 'var(--gold-subtle)' : 'transparent',
                border: isActive ? '1px solid var(--gold-border)' : '1px solid transparent',
                color: isActive ? 'var(--burgundy)' : 'var(--text-dark)',
                fontFamily: 'var(--font-sans)',
                fontWeight: isActive ? 700 : 600,
                fontSize: '0.86rem',
                padding: '0.45rem 1rem',
                borderRadius: '999px',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!isActive) e.currentTarget.style.color = 'var(--burgundy)';
              }}
              onMouseLeave={(e) => {
                if (!isActive) e.currentTarget.style.color = 'var(--text-dark)';
              }}
            >
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Right Action: Plan Yatra + Optional Account Entry Point */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <button
          type="button"
          data-testid="nav-plan-yatra-btn"
          onClick={() => setActiveTab('booking')}
          className="btn btn-primary"
          style={{ padding: '0.45rem 1.1rem', fontSize: '0.82rem' }}
        >
          <span>Plan Yatra</span>
          <span>➔</span>
        </button>

        {/* Optional Account Entry Point */}
        {!user ? (
          <button
            type="button"
            data-testid="nav-signin-btn"
            onClick={onOpenAuthModal}
            style={{
              background: '#FFFDF9',
              border: '1.5px solid var(--gold-border, #E5D2AD)',
              color: 'var(--burgundy, #58111A)',
              padding: '0.45rem 0.95rem',
              borderRadius: '999px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = '#B8860B';
              e.currentTarget.style.background = '#FDF6EC';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = '#E5D2AD';
              e.currentTarget.style.background = '#FFFDF9';
            }}
          >
            <span>👤</span>
            <span>Sign In</span>
          </button>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <button
              type="button"
              data-testid="nav-saved-trips-btn"
              onClick={onOpenSavedTrips}
              style={{
                background: '#FDF6EC',
                border: '1px solid #B8860B',
                color: '#58111A',
                padding: '0.45rem 0.85rem',
                borderRadius: '999px',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
              }}
            >
              <span>👤</span>
              <span>My Account</span>
            </button>
            <button
              type="button"
              data-testid="nav-logout-btn"
              onClick={onLogout}
              title={`Signed in as ${user.email}. Click to sign out.`}
              style={{
                background: 'transparent',
                border: '1px solid #E5D2AD',
                color: '#7D6A5D',
                padding: '0.45rem 0.75rem',
                borderRadius: '999px',
                fontSize: '0.78rem',
                cursor: 'pointer',
              }}
            >
              Sign Out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
