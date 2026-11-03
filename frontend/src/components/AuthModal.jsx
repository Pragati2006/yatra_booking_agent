import React, { useState, useEffect } from 'react';
import { requestOtp, verifyOtp } from '../services/api';

export default function AuthModal({
  isOpen,
  onClose,
  onAuthSuccess,
  currentItinerary,
  currentChatMessages,
  onSaveGuestWork,
}) {
  const [step, setStep] = useState('email'); // 'email' | 'otp' | 'success'
  const [email, setEmail] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [cooldown, setCooldown] = useState(0);
  const [authenticatedUser, setAuthenticatedUser] = useState(null);
  const [saveActiveWork, setSaveActiveWork] = useState(true);

  useEffect(() => {
    let timer;
    if (cooldown > 0) {
      timer = setInterval(() => {
        setCooldown((prev) => (prev > 0 ? prev - 1 : 0));
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [cooldown]);

  const handleClose = () => {
    setStep('email');
    setOtpCode('');
    setErrorMsg('');
    setSuccessMsg('');
    onClose();
  };

  if (!isOpen) return null;

  const handleRequestOtp = async (e) => {
    if (e) e.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail || !cleanEmail.includes('@')) {
      setErrorMsg('Please enter a valid email address.');
      return;
    }

    setLoading(true);
    setErrorMsg('');
    try {
      const res = await requestOtp(cleanEmail);
      if (res.status === 'success') {
        setStep('otp');
        setCooldown(res.cooldown_seconds || 60);
        setSuccessMsg(`We sent a 6-digit verification code to ${cleanEmail}`);
      } else {
        setErrorMsg(res.message || 'Failed to send verification code.');
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (detail && typeof detail === 'object' && detail.message) {
        setErrorMsg(detail.message);
        if (detail.retry_after_seconds) {
          setCooldown(detail.retry_after_seconds);
        }
      } else if (typeof detail === 'string') {
        setErrorMsg(detail);
      } else {
        setErrorMsg('Unable to send verification code. Please check your connection and try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e) => {
    if (e) e.preventDefault();
    const cleanCode = otpCode.trim();
    if (cleanCode.length !== 6 || !/^\d+$/.test(cleanCode)) {
      setErrorMsg('Please enter the 6-digit numeric verification code.');
      return;
    }

    setLoading(true);
    setErrorMsg('');
    try {
      const res = await verifyOtp(email.trim(), cleanCode);
      if (res.status === 'success') {
        setAuthenticatedUser(res.user);
        if (onAuthSuccess) {
          onAuthSuccess(res.user, res.session_token);
        }

        // If user has active guest work and wants to save it
        const hasGuestWork = (currentItinerary && currentItinerary.length > 0) ||
                             (currentChatMessages && currentChatMessages.length > 1);

        if (hasGuestWork && onSaveGuestWork && saveActiveWork) {
          onSaveGuestWork(res.user);
        }

        setStep('success');
      } else {
        setErrorMsg(res.message || 'Invalid or expired verification code.');
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (detail && typeof detail === 'object' && detail.message) {
        setErrorMsg(detail.message);
      } else if (typeof detail === 'string') {
        setErrorMsg(detail);
      } else {
        setErrorMsg('Invalid or expired verification code. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const hasGuestWork = (currentItinerary && currentItinerary.length > 0) ||
                       (currentChatMessages && currentChatMessages.length > 1);

  return (
    <div
      role="dialog"
      aria-modal="true"
      data-testid="auth-modal"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(30, 8, 12, 0.65)',
        backdropFilter: 'blur(4px)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !loading) {
          handleClose();
        }
      }}
    >
      <div
        style={{
          background: '#FFFFFF',
          borderRadius: '20px',
          border: '2px solid var(--gold-border, #E5D2AD)',
          boxShadow: '0 16px 40px rgba(88, 17, 26, 0.25)',
          maxWidth: '480px',
          width: '100%',
          overflow: 'hidden',
          animation: 'fadeIn 0.2s ease-out',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            background: 'linear-gradient(135deg, #58111A 0%, #3D0810 100%)',
            color: '#FFFFFF',
            padding: '1.25rem 1.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '2px solid var(--gold-primary, #B8860B)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '1.4rem' }}>🪔</span>
            <div>
              <div style={{ fontFamily: 'var(--font-serif, serif)', fontWeight: 700, fontSize: '1.15rem' }}>
                {step === 'success' ? 'Welcome, Pilgrim!' : 'Sign In / Save Your Trips'}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#E5D2AD' }}>
                Passwordless Email Authentication
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            aria-label="Close"
            style={{
              background: 'transparent',
              border: 'none',
              color: '#E5D2AD',
              fontSize: '1.4rem',
              cursor: 'pointer',
              lineHeight: 1,
              padding: '4px',
            }}
          >
            ✕
          </button>
        </div>

        {/* Body Content */}
        <div style={{ padding: '1.5rem' }}>
          {/* STEP 1: Email Form */}
          {step === 'email' && (
            <form onSubmit={handleRequestOtp}>
              <p style={{ fontSize: '0.88rem', color: '#4A3B32', lineHeight: 1.5, marginTop: 0 }}>
                Enter your email address to sign in or create an account. We will send a secure one-time verification code. <strong>No password is required.</strong>
              </p>

              <div style={{ marginBottom: '1.2rem' }}>
                <label
                  htmlFor="authEmailInput"
                  style={{ display: 'block', fontWeight: 600, fontSize: '0.84rem', color: '#58111A', marginBottom: '6px' }}
                >
                  Email Address
                </label>
                <input
                  id="authEmailInput"
                  data-testid="auth-email-input"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="pilgrim@example.com"
                  required
                  autoFocus
                  style={{
                    width: '100%',
                    padding: '0.75rem 1rem',
                    borderRadius: '10px',
                    border: '1.5px solid #D5C2AD',
                    fontSize: '0.95rem',
                    boxSizing: 'border-box',
                    outline: 'none',
                    transition: 'border 0.2s',
                  }}
                  onFocus={(e) => { e.target.style.borderColor = '#B8860B'; }}
                  onBlur={(e) => { e.target.style.borderColor = '#D5C2AD'; }}
                />
              </div>

              {errorMsg && (
                <div style={{ background: '#FFF5F5', border: '1px solid #FEB2B2', color: '#C53030', padding: '0.65rem', borderRadius: '8px', fontSize: '0.84rem', marginBottom: '1rem' }}>
                  ⚠️ {errorMsg}
                </div>
              )}

              <button
                type="submit"
                data-testid="auth-send-otp-btn"
                disabled={loading}
                className="btn btn-primary"
                style={{
                  width: '100%',
                  padding: '0.8rem',
                  fontSize: '0.95rem',
                  fontWeight: 700,
                  cursor: loading ? 'wait' : 'pointer',
                  opacity: loading ? 0.7 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                }}
              >
                {loading ? 'Sending Code...' : 'Send Verification Code ➔'}
              </button>

              <div style={{ marginTop: '1.25rem', padding: '0.75rem', background: '#FFFDF9', borderRadius: '10px', border: '1px dashed #E5D2AD', fontSize: '0.78rem', color: '#7D6A5D', lineHeight: 1.4 }}>
                <strong>🌟 Default Guest Mode:</strong> Sign-in is 100% optional. You can explore yatra information, generate itineraries, and check availability as a guest at any time without creating an account.
              </div>
            </form>
          )}

          {/* STEP 2: OTP Verification Form */}
          {step === 'otp' && (
            <form onSubmit={handleVerifyOtp}>
              {successMsg && (
                <div style={{ background: '#F0FDF4', border: '1px solid #86EFAC', color: '#166534', padding: '0.65rem', borderRadius: '8px', fontSize: '0.84rem', marginBottom: '1rem' }}>
                  ✉️ {successMsg}
                </div>
              )}

              <p style={{ fontSize: '0.86rem', color: '#4A3B32', lineHeight: 1.5, marginTop: 0 }}>
                Please enter the 6-digit one-time verification code sent to <strong>{email}</strong>.
              </p>

              <div style={{ marginBottom: '1.2rem' }}>
                <label
                  htmlFor="authOtpInput"
                  style={{ display: 'block', fontWeight: 600, fontSize: '0.84rem', color: '#58111A', marginBottom: '6px' }}
                >
                  6-Digit Verification Code
                </label>
                <input
                  id="authOtpInput"
                  data-testid="auth-otp-input"
                  type="text"
                  maxLength={6}
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ''))}
                  placeholder="123456"
                  required
                  autoFocus
                  style={{
                    width: '100%',
                    padding: '0.75rem 1rem',
                    borderRadius: '10px',
                    border: '1.5px solid #D5C2AD',
                    fontSize: '1.4rem',
                    fontWeight: 700,
                    letterSpacing: '8px',
                    textAlign: 'center',
                    boxSizing: 'border-box',
                    outline: 'none',
                    fontFamily: 'monospace',
                  }}
                  onFocus={(e) => { e.target.style.borderColor = '#B8860B'; }}
                  onBlur={(e) => { e.target.style.borderColor = '#D5C2AD'; }}
                />
              </div>

              {hasGuestWork && (
                <div style={{ marginBottom: '1.2rem', padding: '0.65rem', background: '#FDF8F0', borderRadius: '8px', border: '1px solid #E5D2AD', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <input
                    type="checkbox"
                    id="saveActiveWorkCheck"
                    checked={saveActiveWork}
                    onChange={(e) => setSaveActiveWork(e.target.checked)}
                    style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                  />
                  <label htmlFor="saveActiveWorkCheck" style={{ fontSize: '0.82rem', color: '#58111A', fontWeight: 600, cursor: 'pointer' }}>
                    Save my current trip & consultation chat to my account
                  </label>
                </div>
              )}

              {errorMsg && (
                <div style={{ background: '#FFF5F5', border: '1px solid #FEB2B2', color: '#C53030', padding: '0.65rem', borderRadius: '8px', fontSize: '0.84rem', marginBottom: '1rem' }}>
                  ⚠️ {errorMsg}
                </div>
              )}

              <button
                type="submit"
                disabled={loading || otpCode.length !== 6}
                className="btn btn-primary"
                style={{
                  width: '100%',
                  padding: '0.8rem',
                  fontSize: '0.95rem',
                  fontWeight: 700,
                  cursor: (loading || otpCode.length !== 6) ? 'not-allowed' : 'pointer',
                  opacity: (loading || otpCode.length !== 6) ? 0.7 : 1,
                  marginBottom: '0.75rem',
                }}
              >
                {loading ? 'Verifying...' : 'Verify Code & Sign In'}
              </button>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.82rem' }}>
                <button
                  type="button"
                  onClick={() => { setStep('email'); setErrorMsg(''); }}
                  style={{ background: 'transparent', border: 'none', color: '#58111A', cursor: 'pointer', textDecoration: 'underline' }}
                >
                  Change email
                </button>
                <button
                  type="button"
                  disabled={cooldown > 0 || loading}
                  onClick={handleRequestOtp}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: cooldown > 0 ? '#9CA3AF' : '#B8860B',
                    cursor: cooldown > 0 ? 'default' : 'pointer',
                    fontWeight: 600,
                  }}
                >
                  {cooldown > 0 ? `Resend code in ${cooldown}s` : 'Resend Code'}
                </button>
              </div>
            </form>
          )}

          {/* STEP 3: Success Screen */}
          {step === 'success' && (
            <div style={{ textAlign: 'center', padding: '1rem 0' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>🙏</div>
              <h3 style={{ fontFamily: 'var(--font-serif, serif)', color: 'var(--burgundy, #58111A)', marginTop: 0 }}>
                Jai Mata Di!
              </h3>
              <p style={{ fontSize: '0.9rem', color: '#4A3B32', marginBottom: '1.5rem' }}>
                You are signed in as <strong>{authenticatedUser?.email}</strong>.
                {saveActiveWork && hasGuestWork && ' Your active trip has been preserved and saved to your account.'}
              </p>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleClose}
                style={{ padding: '0.65rem 2rem', fontSize: '0.92rem', fontWeight: 700 }}
              >
                Continue to Application ➔
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
