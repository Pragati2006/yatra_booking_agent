import React, { useState, useEffect } from 'react';
import { resumeRPAWorkflow, cancelRPAWorkflow, getRPAWorkflowStatus } from '../services/api';

export default function UserInterventionModal({
  workflowData,
  sessionId,
  isOpen = true,
  onClose,
  onWorkflowComplete,
  onWorkflowCancelled,
}) {
  const safeData = workflowData || {};
  const {
    workflow_id: workflowId,
    state: initialWorkflowState = 'WAITING_FOR_USER',
    expires_at: initialExpiresAt,
    checkpoint_mode: checkpointMode = (initialWorkflowState === 'OTP_REQUIRED' ? 'OTP' : 'CAPTCHA'),
  } = safeData;

  const [workflowState, setWorkflowState] = useState(initialWorkflowState);
  const [resuming, setResuming] = useState(false);
  const [resumingPhase, setResumingPhase] = useState('');
  const [cancelling, setCancelling] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [successResult, setSuccessResult] = useState(null);
  const [simulatedInput, setSimulatedInput] = useState('');
  const [completionTime, setCompletionTime] = useState('');
  const [resendCooldown, setResendCooldown] = useState(0);
  const [resendNotice, setResendNotice] = useState('');
  const [secondsRemaining, setSecondsRemaining] = useState(() => {
    if (!initialExpiresAt) return 300;
    const diff = Math.max(0, Math.floor((new Date(initialExpiresAt).getTime() - Date.now()) / 1000));
    return diff > 0 ? diff : 0;
  });

  const isOtp = workflowState === 'OTP_REQUIRED' || checkpointMode === 'OTP';
  const isCaptcha = workflowState === 'CAPTCHA_REQUIRED' || checkpointMode === 'CAPTCHA';
  const isExpired = workflowState === 'EXPIRED' || secondsRemaining <= 0;
  const isCancelled = workflowState === 'CANCELLED';
  const isCompleted = workflowState === 'USER_ACTION_COMPLETED' || workflowState === 'COMPLETED';

  // Resend cooldown timer
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => {
      setResendCooldown((prev) => (prev <= 1 ? 0 : prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  // Countdown timer for expiration
  useEffect(() => {
    if (isExpired || isCancelled || isCompleted) return;
    const timer = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          setWorkflowState('EXPIRED');
          setStatusMessage('Security workflow expired due to inactivity. Please restart the booking process.');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [isExpired, isCancelled, isCompleted]);

  // Periodic status poll (optional check if user verified in another tab)
  useEffect(() => {
    if (!workflowId || !sessionId || isExpired || isCancelled || isCompleted) return;
    const pollInterval = setInterval(async () => {
      try {
        const res = await getRPAWorkflowStatus(workflowId, sessionId);
        if (res && res.workflow) {
          const freshState = res.workflow.state;
          if (freshState !== workflowState) {
            setWorkflowState(freshState);
            if (freshState === 'USER_ACTION_COMPLETED') {
              setSuccessResult(res.workflow);
              setErrorMessage('');
              if (onWorkflowComplete) onWorkflowComplete(res.workflow);
            }
          }
        }
      } catch {
        // quiet ignore for polling
      }
    }, 4000);
    return () => clearInterval(pollInterval);
  }, [workflowId, sessionId, workflowState, isExpired, isCancelled, isCompleted, onWorkflowComplete]);

  const formatCountdown = (secs) => {
    const mins = Math.floor(secs / 60);
    const remainder = secs % 60;
    return `${mins}:${remainder < 10 ? '0' : ''}${remainder}`;
  };

  const handleSimulatedResendOtp = () => {
    if (resendCooldown > 0) return;
    setResendCooldown(30);
    setResendNotice('A new simulated verification code (Demo OTP: 123456) has been dispatched.');
    setTimeout(() => setResendNotice(''), 6000);
  };

  const handleResume = async (simulate = false) => {
    if (resuming || cancelling) return;
    setResuming(true);
    setResumingPhase('RESUMING_AUTOMATION');
    setErrorMessage('');

    try {
      const payload = {
        session_id: sessionId,
        workflow_id: workflowId,
        user_confirmed_action: true,
        manual_input_value: simulatedInput.trim() || (simulate ? (isOtp ? '123456' : 'M7K9P') : null),
        simulate_manual_clearance: simulate,
        headless: true,
      };

      setResumingPhase('VERIFICATION_SUCCESSFUL');
      const result = await resumeRPAWorkflow(payload);

      if (result.status === 'SUCCESS') {
        setResumingPhase('BOOKING_CONFIRMED');
        setWorkflowState('USER_ACTION_COMPLETED');
        setSuccessResult(result);
        setCompletionTime(new Date().toLocaleTimeString());
        setErrorMessage('');
        setStatusMessage(result.message || 'Verification successful! Your booking is confirmed.');
        if (onWorkflowComplete) {
          onWorkflowComplete(result);
        }
      } else if (result.status === 'PAUSED') {
        // Sequential checkpoint reached: e.g. transitioned from OTP to CAPTCHA!
        setResumingPhase('');
        setWorkflowState(result.state || 'CAPTCHA_REQUIRED');
        setSimulatedInput('');
        setErrorMessage('');
        setStatusMessage(result.message || 'OTP verified successfully. Manual CAPTCHA challenge is now required.');
      } else if (result.status === 'VALIDATION_FAILED') {
        setResumingPhase('');
        setErrorMessage(result.message || 'Validation failed: Security checkpoint has not been cleared in the portal.');
      } else if (result.status === 'EXPIRED') {
        setResumingPhase('');
        setWorkflowState('EXPIRED');
        setErrorMessage('Workflow has expired. Please restart the booking process.');
      } else if (result.status === 'CANCELLED') {
        setResumingPhase('');
        setWorkflowState('CANCELLED');
        setErrorMessage('Workflow has been cancelled.');
      } else if (result.status === 'HANDOVER_REQUIRED') {
        setResumingPhase('');
        setWorkflowState('HANDOVER_REQUIRED');
        setErrorMessage(result.message || 'Browser automation encountered an issue. Manual completion required.');
      } else {
        setResumingPhase('');
        setErrorMessage(result.message || 'Failed to resume workflow.');
      }
    } catch (err) {
      console.error('Error resuming workflow:', err?.message || 'Network error');
      setResumingPhase('');
      setErrorMessage(err.response?.data?.detail || 'An unexpected error occurred while resuming the workflow.');
    } finally {
      setResuming(false);
    }
  };

  const handleCancel = async () => {
    if (cancelling || resuming) return;
    if (!window.confirm('Are you sure you want to cancel this booking workflow?')) return;
    setCancelling(true);
    setErrorMessage('');
    try {
      const res = await cancelRPAWorkflow({
        session_id: sessionId,
        workflow_id: workflowId,
        reason: 'Cancelled by user via intervention modal',
      });
      setWorkflowState('CANCELLED');
      setStatusMessage('Workflow cancelled successfully.');
      if (onWorkflowCancelled) onWorkflowCancelled(res);
    } catch (err) {
      console.error('Error cancelling workflow:', err?.message || 'Network error');
      setErrorMessage('Failed to cancel workflow.');
    } finally {
      setCancelling(false);
    }
  };

  if (!isOpen || !workflowData) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(26, 15, 15, 0.75)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '16px',
      }}
    >
      <div
        className="card"
        style={{
          width: '100%',
          maxWidth: '620px',
          background: '#FFFFFF',
          borderRadius: '16px',
          boxShadow: '0 20px 40px rgba(110, 20, 35, 0.25)',
          border: '2px solid var(--gold-border, #E8C874)',
          padding: '24px',
          maxHeight: '90vh',
          overflowY: 'auto',
          animation: 'fadeIn 0.2s ease-out',
        }}
      >
        {/* Phase 5: Clean Pilgrimage Booking Progress Indicator */}
        <div style={{ marginBottom: '18px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 800, color: 'var(--burgundy, #6E1423)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              🛕 Vaishno Devi Yatra Booking
            </span>
            {!isExpired && !isCancelled && !isCompleted && (
              <span style={{ fontSize: '0.78rem', color: '#B45309', fontWeight: 700, background: '#FEF3C7', padding: '3px 8px', borderRadius: '6px' }}>
                ⏳ Expires in: {formatCountdown(secondsRemaining)}
              </span>
            )}
          </div>

          {/* Synchronized 6-Stage Visual Stepper */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', background: '#F8FAFC', padding: '8px 10px', borderRadius: '8px', border: '1px solid #E2E8F0', overflowX: 'auto' }}>
            {[
              { num: 1, label: 'Pilgrim Details', done: true },
              { num: 2, label: 'Darshan Slot', done: true },
              { num: 3, label: 'Review Details', done: true },
              { num: 4, label: 'Security Verification', active: !isCompleted && resumingPhase !== 'PAYMENT_SANDBOX', done: isCompleted || resumingPhase === 'PAYMENT_SANDBOX' },
              { num: 5, label: 'Payment Sandbox', active: resumingPhase === 'PAYMENT_SANDBOX', done: isCompleted },
              { num: 6, label: 'Confirmation Pass', active: isCompleted, done: isCompleted },
            ].map((step, idx) => (
              <React.Fragment key={step.num}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', whiteSpace: 'nowrap', opacity: step.active || step.done ? 1 : 0.5 }}>
                  <span
                    style={{
                      width: '20px',
                      height: '20px',
                      borderRadius: '50%',
                      background: step.done ? '#059669' : (step.active ? '#6E1423' : '#CBD5E1'),
                      color: '#FFF',
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {step.done && !step.active ? '✓' : step.num}
                  </span>
                  <span style={{ fontSize: '0.74rem', fontWeight: step.active ? 800 : 600, color: step.active ? '#6E1423' : '#475569' }}>
                    {step.label}
                  </span>
                </div>
                {idx < 5 && <span style={{ color: '#CBD5E1', fontSize: '0.7rem' }}>➔</span>}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Dynamic State Title */}
        <div style={{ marginBottom: '14px', borderBottom: '1px solid #F0E6D2', paddingBottom: '10px' }}>
          <h3 style={{ margin: 0, fontFamily: 'var(--font-serif)', color: 'var(--burgundy, #6E1423)', fontSize: '1.2rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>{isCompleted ? '🎉' : (isOtp ? '🔐' : (isCaptcha ? '🛡️' : '⚠️'))}</span>
            {isCompleted
              ? 'Jai Mata Di! Your Simulated Booking Is Confirmed'
              : (isOtp ? 'Additional Verification Required' : 'CAPTCHA Security Challenge')}
          </h3>
          <p style={{ margin: '4px 0 0 0', fontSize: '0.84rem', color: '#64748B' }}>
            {isCompleted
              ? 'Your pilgrimage reservation has been verified and confirmed in the local mock portal.'
              : 'Please complete the simulated verification in the local booking portal. Once completed, return here and continue.'}
          </p>
        </div>

        {/* Dual-Track Safety Architecture Badge */}
        <div
          style={{
            background: '#FDF8F0',
            border: '1px dashed #D4AF37',
            borderRadius: '8px',
            padding: '8px 12px',
            marginBottom: '14px',
            fontSize: '0.8rem',
            color: '#5C381E',
          }}
        >
          <strong>Notice:</strong> This is a <strong>LOCAL DEMO MOCK BOOKING</strong> portal test. Automation is strictly restricted to our sandbox. Official Shrine Board bookings remain manual on <strong>maavaishnodevi.org</strong>.
        </div>

        {/* Resuming in progress notice */}
        {resuming && (
          <div style={{ background: '#EFF6FF', border: '1px solid #93C5FD', borderRadius: '10px', padding: '14px', marginBottom: '14px', textAlign: 'center' }}>
            <div style={{ fontSize: '1.3rem', marginBottom: '4px' }}>⏳</div>
            <div style={{ fontWeight: 800, color: '#1E40AF', fontSize: '0.95rem' }}>
              Verification successful! Your booking is being processed.
            </div>
            <div style={{ color: '#3B82F6', fontSize: '0.8rem', marginTop: '4px' }}>
              Playwright RPA agent is continuing to final confirmation ({resumingPhase || 'BOOKING_PROCESSING'})...
            </div>
          </div>
        )}

        {/* Checkpoint Instructions (Only if not completed & not expired & not cancelled) */}
        {!isCompleted && !isExpired && !isCancelled && !resuming && (
          <>
            {isOtp && (
              <div style={{ background: '#FFFDF0', border: '1px solid #F6D860', borderRadius: '10px', padding: '12px 14px', marginBottom: '14px' }}>
                <div style={{ fontWeight: 800, color: '#744210', fontSize: '0.9rem', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>📱</span> Simulated OTP Delivery
                </div>
                <p style={{ margin: '0 0 8px 0', fontSize: '0.82rem', color: '#4A3B32', lineHeight: 1.4 }}>
                  A mock verification code has been dispatched to pilgrim's mobile number:
                  <strong style={{ marginLeft: '4px' }}>+91 98765-XXXXX</strong>
                  <span style={{ marginLeft: '6px', background: '#FEF08A', color: '#854D0E', padding: '2px 6px', borderRadius: '4px', fontWeight: 800, fontSize: '0.78rem' }}>
                    Demo OTP: 123456
                  </span>
                </p>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '6px' }}>
                  <button
                    type="button"
                    onClick={handleSimulatedResendOtp}
                    disabled={resendCooldown > 0}
                    style={{
                      background: 'transparent',
                      border: '1px solid #D97706',
                      color: '#B45309',
                      fontSize: '0.75rem',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      cursor: resendCooldown > 0 ? 'not-allowed' : 'pointer',
                      fontWeight: 600,
                    }}
                  >
                    {resendCooldown > 0 ? `Resend Code in ${resendCooldown}s` : '🔄 Resend Verification Code'}
                  </button>
                  {resendNotice && <span style={{ fontSize: '0.75rem', color: '#059669', fontWeight: 600 }}>{resendNotice}</span>}
                </div>
              </div>
            )}

            {isCaptcha && (
              <div style={{ background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: '10px', padding: '12px 14px', marginBottom: '14px' }}>
                <div style={{ fontWeight: 800, color: '#1E40AF', fontSize: '0.9rem', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>🧩</span> Simulated CAPTCHA Puzzle
                </div>
                <p style={{ margin: '0 0 8px 0', fontSize: '0.82rem', color: '#1E3A8A', lineHeight: 1.4 }}>
                  Solve the visual puzzle shown on the authorized booking window:
                  <span style={{ marginLeft: '6px', background: '#2D3748', color: '#E8C874', padding: '2px 8px', borderRadius: '4px', fontWeight: 800, letterSpacing: '2px', fontFamily: 'monospace' }}>
                    M7K9P
                  </span>
                </p>
              </div>
            )}

            {/* Quick Interactive Direct Entry Box */}
            <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '10px', padding: '12px 14px', marginBottom: '14px' }}>
              <label style={{ display: 'block', fontWeight: 700, fontSize: '0.82rem', color: '#475569', marginBottom: '6px' }}>
                {isOtp ? 'Enter Verification Code (Demo: 123456):' : 'Enter CAPTCHA Solution (Demo: M7K9P):'}
              </label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  value={simulatedInput}
                  onChange={(e) => setSimulatedInput(e.target.value)}
                  placeholder={isOtp ? 'Enter 6-digit code (e.g. 123456)' : 'Enter CAPTCHA (e.g. M7K9P)'}
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    borderRadius: '8px',
                    border: '1px solid #CBD5E1',
                    fontSize: '0.9rem',
                    fontFamily: 'monospace',
                  }}
                />
                <button
                  type="button"
                  onClick={() => handleResume(false)}
                  disabled={resuming || !simulatedInput.trim()}
                  className="btn btn-primary"
                  style={{ fontSize: '0.82rem', padding: '8px 14px', whiteSpace: 'nowrap' }}
                >
                  {resuming ? 'Validating...' : 'Verify & Continue ➔'}
                </button>
              </div>
              <div style={{ fontSize: '0.74rem', color: '#64748B', marginTop: '4px' }}>
                Directly validates checkpoint in the local mock portal and resumes Playwright.
              </div>
            </div>
          </>
        )}

        {/* Confirmed Booking Receipt */}
        {isCompleted && successResult && (
          <div style={{ background: '#F0FDF4', border: '2px solid #86EFAC', borderRadius: '12px', padding: '16px', marginBottom: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px dashed #86EFAC', paddingBottom: '10px', marginBottom: '10px' }}>
              <div>
                <span className="badge" style={{ background: '#DCFCE7', color: '#166534', fontWeight: 800, fontSize: '0.72rem', padding: '3px 8px', borderRadius: '4px', border: '1px solid #86EFAC' }}>
                  LOCAL MOCK PORTAL / DEMO
                </span>
                <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#166534', marginTop: '4px' }}>
                  Simulated Yatra Booking Confirmation
                </div>
                <div style={{ fontSize: '0.85rem', color: '#15803D', fontWeight: 600, marginTop: '2px' }}>
                  Demo Pilgrim Pass: <span style={{ fontFamily: 'monospace', fontWeight: 800 }}>{successResult.booking_id}</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => window.print()}
                className="btn btn-outline"
                style={{ fontSize: '0.75rem', padding: '4px 10px', borderColor: '#86EFAC', color: '#166534' }}
              >
                🖨️ Print Demo Pass
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.82rem', color: '#374151' }}>
              <div><strong>Receipt:</strong> <span style={{ color: '#059669', fontWeight: 700 }}>Demo Pilgrim Pass (Mock)</span></div>
              <div><strong>Gateway:</strong> Sandbox Mode (₹0 live charge)</div>
              <div><strong>Pilgrim:</strong> Guest Pilgrim</div>
              <div><strong>Timestamp:</strong> {completionTime || 'Just now'}</div>
            </div>

            <div style={{ fontSize: '0.82rem', color: '#047857', marginTop: '10px', fontStyle: 'italic', textAlign: 'center', background: '#DCFCE7', padding: '6px', borderRadius: '6px' }}>
              🙏 Jai Mata Di! May Maa Vaishno Devi bless you and your family with peace and happiness.
            </div>
          </div>
        )}

        {/* Error Notification (Only rendered when there is an actual error and NOT completed) */}
        {errorMessage && !isCompleted && (
          <div style={{ background: '#FDE8E8', border: '1px solid #F98080', color: '#9B1C1C', borderRadius: '8px', padding: '10px 14px', fontSize: '0.84rem', marginBottom: '14px' }}>
            <strong>Action Required:</strong> {errorMessage}
          </div>
        )}

        {/* Expired Notice */}
        {isExpired && !isCompleted && (
          <div style={{ background: '#FDF2E9', border: '1px solid #F5C6CB', color: '#78281F', borderRadius: '8px', padding: '12px 14px', fontSize: '0.85rem', marginBottom: '14px' }}>
            <strong>Workflow Expired:</strong> This security intervention timed out after 5 minutes of inactivity to protect your session. Please initiate a new booking.
          </div>
        )}

        {/* Cancelled Notice */}
        {isCancelled && !isCompleted && (
          <div style={{ background: '#F7FAFC', border: '1px solid #E2E8F0', color: '#4A5568', borderRadius: '8px', padding: '12px 14px', fontSize: '0.85rem', marginBottom: '14px' }}>
            <strong>Workflow Cancelled:</strong> This workflow was successfully cancelled by the user. No actions were performed.
          </div>
        )}

        {/* Phase 5: Technical Details Section (Hidden behind collapsible summary) */}
        <details style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '8px', padding: '8px 12px', fontSize: '0.78rem', color: '#64748B', marginTop: '12px' }}>
          <summary style={{ cursor: 'pointer', fontWeight: 700, color: '#475569' }}>
            ⚙️ Technical Details & Diagnostics
          </summary>
          <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px', fontFamily: 'monospace' }}>
            <div>Workflow ID: {workflowId}</div>
            <div>Internal State: {workflowState}</div>
            <div>Session ID: {sessionId}</div>
            <div>Mode: {checkpointMode}</div>
            {statusMessage && <div>Status Msg: {statusMessage}</div>}
          </div>
        </details>

        {/* Modal Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px', borderTop: '1px solid #F0E6D2', paddingTop: '14px' }}>
          {!isCompleted && !isExpired && !isCancelled && (
            <>
              <button
                type="button"
                onClick={handleCancel}
                disabled={cancelling || resuming}
                className="btn btn-outline"
                style={{ fontSize: '0.82rem', padding: '8px 14px', color: '#C53030', borderColor: '#FEB2B2' }}
              >
                {cancelling ? 'Cancelling...' : '✕ Cancel Workflow'}
              </button>

              <button
                type="button"
                onClick={() => handleResume(true)}
                disabled={resuming || cancelling}
                className="btn btn-gold"
                style={{ fontSize: '0.84rem', padding: '8px 16px', fontWeight: 700 }}
              >
                {resuming ? '⏳ Continuing...' : 'Continue Booking ➔'}
              </button>
            </>
          )}

          {(isCompleted || isExpired || isCancelled) && (
            <div style={{ width: '100%', display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={onClose}
                className="btn btn-primary"
                style={{ fontSize: '0.88rem', padding: '8px 22px' }}
              >
                Close & Return
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
