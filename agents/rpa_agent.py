"""
agents/rpa_agent.py
Playwright-based Robotic Process Automation (RPA) Agent for Maa Vaishno Devi Yatra.

Capabilities:
1. Automated booking form execution and verification in a safe mock sandbox (Week 4).
2. Automated availability calendar navigation and structured slot data extraction (Week 5).
3. RPA Error Handling, State Validation, Retry-and-Escalate, and Pause-and-Handover (Week 6).

Safety and Security:
- Does NOT interact with real payment portals, OTP, CAPTCHA, or live Shrine Board databases.
- Operates entirely within local, sandboxed mock portals.
- Availability checking is read-only and does NOT mutate bookings or bypass human authorization.
- Retry-and-escalate is strictly bounded and never repeats side-effect actions (like booking submissions).
- Reliable browser resource cleanup via try...finally guarantees.
"""

import os
import json
import time
import tempfile
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from agents import session_store
from utils.logger import log_event
from utils.masking import mask_name, mask_otp, mask_sensitive_data, sanitize_log_message

logger = logging.getLogger(__name__)

# ==============================================================================
# DEFAULT EMBEDDED REALISTIC YATRA SLOTS DATASET (FOR LOCAL MOCK PORTAL)
# ==============================================================================
DEFAULT_MOCK_SLOTS: List[Dict[str, Any]] = [
    # 2026-10-20: Mixed statuses across categories (Normal, VIP, Helicopter)
    {"id": 101, "slot_date": "2026-10-20", "slot_time": "06:00", "session": "Morning Aarti & Darshan", "category": "Normal Darshan", "price": 0, "seats_available": 220, "status": "available"},
    {"id": 102, "slot_date": "2026-10-20", "slot_time": "09:00", "session": "Morning Session", "category": "Normal Darshan", "price": 0, "seats_available": 134, "status": "available"},
    {"id": 103, "slot_date": "2026-10-20", "slot_time": "12:00", "session": "Afternoon Session", "category": "Normal Darshan", "price": 0, "seats_available": 0, "status": "full"},
    {"id": 104, "slot_date": "2026-10-20", "slot_time": "15:00", "session": "Evening Session", "category": "Normal Darshan", "price": 0, "seats_available": 180, "status": "available"},
    {"id": 105, "slot_date": "2026-10-20", "slot_time": "06:00", "session": "Morning VIP Aarti", "category": "VIP Darshan", "price": 500, "seats_available": 37, "status": "available"},
    {"id": 106, "slot_date": "2026-10-20", "slot_time": "18:00", "session": "Evening VIP Aarti", "category": "VIP Darshan", "price": 500, "seats_available": 0, "status": "full"},
    {"id": 107, "slot_date": "2026-10-20", "slot_time": "09:00", "session": "Morning Helicopter Flight 1", "category": "Helicopter Darshan", "price": 4640, "seats_available": 12, "status": "available"},
    {"id": 108, "slot_date": "2026-10-20", "slot_time": "15:00", "session": "Afternoon Helicopter Flight 2", "category": "Helicopter Darshan", "price": 4640, "seats_available": 0, "status": "unavailable"},

    # 2026-10-21: High availability day
    {"id": 201, "slot_date": "2026-10-21", "slot_time": "06:00", "session": "Morning Aarti & Darshan", "category": "Normal Darshan", "price": 0, "seats_available": 310, "status": "available"},
    {"id": 202, "slot_date": "2026-10-21", "slot_time": "09:00", "session": "Morning Session", "category": "Normal Darshan", "price": 0, "seats_available": 250, "status": "available"},
    {"id": 203, "slot_date": "2026-10-21", "slot_time": "06:00", "session": "Morning VIP Aarti", "category": "VIP Darshan", "price": 500, "seats_available": 60, "status": "available"},
    {"id": 204, "slot_date": "2026-10-21", "slot_time": "12:00", "session": "Midday Helicopter Flight", "category": "Helicopter Darshan", "price": 4640, "seats_available": 24, "status": "available"},

    # 2026-10-22: Peak day (mostly full)
    {"id": 301, "slot_date": "2026-10-22", "slot_time": "06:00", "session": "Morning Aarti & Darshan", "category": "Normal Darshan", "price": 0, "seats_available": 0, "status": "full"},
    {"id": 302, "slot_date": "2026-10-22", "slot_time": "09:00", "session": "Morning Session", "category": "Normal Darshan", "price": 0, "seats_available": 0, "status": "full"},
    {"id": 303, "slot_date": "2026-10-22", "slot_time": "06:00", "session": "Morning VIP Aarti", "category": "VIP Darshan", "price": 500, "seats_available": 0, "status": "full"},
    {"id": 304, "slot_date": "2026-10-22", "slot_time": "12:00", "session": "Helicopter Service", "category": "Helicopter Darshan", "price": 4640, "seats_available": 0, "status": "unavailable"},

    # 2026-11-20: Autumn pilgrimage test & demonstration date (VIP Darshan, Normal Darshan, Helicopter Darshan)
    {"id": 501, "slot_date": "2026-11-20", "slot_time": "06:00", "session": "Morning VIP Aarti", "category": "VIP Darshan", "price": 500, "seats_available": 45, "status": "available"},
    {"id": 502, "slot_date": "2026-11-20", "slot_time": "18:00", "session": "Evening VIP Aarti", "category": "VIP Darshan", "price": 500, "seats_available": 18, "status": "available"},
    {"id": 503, "slot_date": "2026-11-20", "slot_time": "09:00", "session": "Morning Session", "category": "Normal Darshan", "price": 0, "seats_available": 120, "status": "available"},
    {"id": 504, "slot_date": "2026-11-20", "slot_time": "12:00", "session": "Helicopter Service", "category": "Helicopter Darshan", "price": 4640, "seats_available": 8, "status": "available"},
]


def generate_mock_portal_html(slots_data: Optional[List[Dict[str, Any]]] = None, render_delay_ms: int = 200, security_mode: str = "") -> str:
    """
    Generates the unified mock portal HTML supporting realistic 6-step pilgrimage booking checkout,
    availability calendar, simulated OTP/CAPTCHA checkpoints, sandbox payment, and formatted receipt.
    """
    slots_json = json.dumps(slots_data if slots_data is not None else DEFAULT_MOCK_SLOTS)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Shri Mata Vaishno Devi Shrine Board — Mock Yatra Booking Portal</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #FDF6EC; margin: 0; padding: 24px; color: #3B1F1F; }}
        .card {{ background: white; border-radius: 16px; padding: 24px; max-width: 680px; margin: 0 auto; box-shadow: 0 8px 24px rgba(110,20,35,0.15); border: 2px solid #E8C874; }}
        h2, h3, h4 {{ color: #6E1423; margin-top: 0; }}
        .portal-header {{ text-align: center; margin-bottom: 16px; border-bottom: 2px solid #E8C874; padding-bottom: 12px; }}
        .portal-header h1 {{ font-size: 1.35rem; color: #6E1423; margin: 0; letter-spacing: 0.5px; }}
        .portal-header p {{ font-size: 0.8rem; color: #8A6857; margin: 4px 0 0 0; }}
        .portal-nav {{ display: flex; gap: 8px; margin-bottom: 16px; border-bottom: 1px solid #E8C874; padding-bottom: 8px; }}
        .tab-btn {{ background: #FDF6EC; border: 1px solid #E8C874; border-radius: 6px; padding: 8px 16px; font-weight: bold; cursor: pointer; color: #6E1423; transition: all 0.2s; }}
        .tab-btn:hover {{ background: #FAEDCD; }}
        .tab-btn.active {{ background: #6E1423; color: white; border-color: #6E1423; }}
        
        /* Stepper */
        .stepper {{ display: flex; justify-content: space-between; align-items: center; background: #FFFDF9; border: 1px solid #E8C874; border-radius: 10px; padding: 10px 14px; margin-bottom: 18px; font-size: 0.76rem; overflow-x: auto; }}
        .step-item {{ display: flex; align-items: center; gap: 4px; color: #8A6857; font-weight: 600; white-space: nowrap; }}
        .step-item.active {{ color: #6E1423; font-weight: 800; }}
        .step-item.completed {{ color: #047857; font-weight: 700; }}
        .step-circle {{ width: 20px; height: 20px; border-radius: 50%; background: #E2E8F0; color: #475569; display: flex; align-items: center; justify-content: center; font-size: 0.72rem; }}
        .step-item.active .step-circle {{ background: #6E1423; color: white; }}
        .step-item.completed .step-circle {{ background: #047857; color: white; }}

        .field {{ margin-bottom: 12px; }}
        .form-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
        label {{ display: block; font-weight: bold; margin-bottom: 4px; font-size: 0.84rem; color: #6E1423; }}
        input, select {{ width: 100%; padding: 9px 12px; border-radius: 8px; border: 1px solid #CCC; box-sizing: border-box; font-size: 0.92rem; }}
        input:focus, select:focus {{ border-color: #6E1423; outline: none; box-shadow: 0 0 0 2px rgba(110,20,35,0.1); }}
        
        .btn {{ background: linear-gradient(135deg, #C2374A, #6E1423); color: white; border: none; padding: 10px 18px; font-size: 0.92rem; font-weight: bold; border-radius: 8px; width: 100%; cursor: pointer; margin-top: 8px; transition: opacity 0.2s; }}
        .btn:hover {{ opacity: 0.95; }}
        .btn-secondary {{ background: #FDF6EC; color: #6E1423; border: 1px solid #E8C874; }}
        .btn-secondary:hover {{ background: #FAEDCD; }}
        .btn-row {{ display: flex; gap: 10px; margin-top: 14px; }}
        
        .sandbox-notice {{ background: #FFFBEB; border: 1px dashed #D97706; color: #92400E; padding: 8px 12px; border-radius: 8px; font-size: 0.78rem; margin-bottom: 14px; display: flex; align-items: center; gap: 6px; }}
        .review-box {{ background: #FFFDF9; border: 1px solid #E8C874; border-radius: 10px; padding: 14px; margin-bottom: 14px; font-size: 0.85rem; }}
        .review-row {{ display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px dashed #E2E8F0; }}
        .review-row:last-child {{ border-bottom: none; }}

        .success {{ background: #F0FDF4; border: 2px solid #22C55E; color: #14532D; padding: 20px; border-radius: 12px; display: none; margin-top: 16px; }}
        .badge {{ background: #E8C874; color: #3B1F1F; font-size: 0.76rem; font-weight: bold; padding: 4px 8px; border-radius: 6px; display: inline-block; }}
        .badge-available {{ background: #DEF7EC; color: #03543F; }}
        .badge-full {{ background: #FDE8E8; color: #9B1C1C; }}
        .badge-unavailable {{ background: #E5E7EB; color: #374151; }}
        
        .loading-state {{ background: #FFF8E7; border: 1px dashed #E8C874; color: #B7791F; padding: 14px; border-radius: 8px; text-align: center; font-weight: bold; margin: 16px 0; }}
        .empty-state {{ background: #F7FAFC; border: 1px dashed #CBD5E0; color: #718096; padding: 20px; border-radius: 8px; text-align: center; margin: 16px 0; font-size: 0.92rem; }}
        .error-state {{ background: #FFF5F5; border: 1px solid #FEB2B2; color: #C53030; padding: 14px; border-radius: 8px; text-align: center; margin: 16px 0; font-size: 0.9rem; }}
        .slots-grid {{ display: flex; flex-direction: column; gap: 8px; margin-top: 12px; max-height: 280px; overflow-y: auto; }}
        .slot-card {{ border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 12px; background: #FAFAFA; display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: all 0.2s; }}
        .slot-card:hover, .slot-card.selected {{ border-color: #6E1423; background: #FFFDF9; }}
        .slot-header {{ font-weight: bold; font-size: 0.88rem; color: #6E1423; }}
        .slot-sub {{ font-size: 0.8rem; color: #718096; margin-top: 2px; }}
        .slot-status {{ font-size: 0.72rem; font-weight: bold; text-transform: uppercase; padding: 2px 6px; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="portal-header">
            <span class="badge" style="margin-bottom: 6px;">🤖 SMVDSB PILGRIMAGE PORTAL — LOCAL MOCK SANDBOX</span>
            <h1>Shri Mata Vaishno Devi Shrine Board</h1>
            <p>Official Simulated Yatra Darshan & Helicopter Booking Service</p>
        </div>

        <!-- Portal Navigation Tabs (Preserves Week 5 Tab Switching) -->
        <div class="portal-nav" id="portalNav">
            <button type="button" id="tabBooking" class="tab-btn active" onclick="showTab('booking')">📝 Pilgrimage Booking</button>
            <button type="button" id="tabCalendar" class="tab-btn" onclick="showTab('calendar')">📅 Availability Calendar</button>
        </div>

        <!-- Booking Section with 6-Step Multi-Stage Journey -->
        <div id="bookingSection">
            <!-- 6-Step Stepper -->
            <div class="stepper" id="portalStepper">
                <div class="step-item active" id="stStep1"><span class="step-circle">1</span> Details</div>
                <div class="step-item" id="stStep2"><span class="step-circle">2</span> Slot</div>
                <div class="step-item" id="stStep3"><span class="step-circle">3</span> Review</div>
                <div class="step-item" id="stStep4"><span class="step-circle">4</span> Verify</div>
                <div class="step-item" id="stStep5"><span class="step-circle">5</span> Payment</div>
                <div class="step-item" id="stStep6"><span class="step-circle">6</span> Receipt</div>
            </div>

            <div class="sandbox-notice">
                <span>🔒</span> <strong>Demo Sandbox Environment:</strong> Simulated local mock portal. Real Shrine Board bookings remain manual on maavaishnodevi.org.
            </div>

            <!-- Form Container (Preserves #bookingForm for Week 4 & Week 6 DOM Validation) -->
            <form id="bookingForm" onsubmit="event.preventDefault(); submitBooking();">
                <input type="hidden" id="securityMode" name="securityMode" value="{security_mode}">

                <!-- STEP 1: PILGRIM DETAILS -->
                <div id="step1Section">
                    <h3>Step 1: Pilgrim Registration & Travel Details</h3>
                    <div class="form-row">
                        <div class="field">
                            <label for="userName">Pilgrim Full Name *</label>
                            <input type="text" id="userName" name="userName" required placeholder="Full Name as on Govt ID" value="Guest Pilgrim">
                        </div>
                        <div class="field">
                            <label for="userAge">Age *</label>
                            <input type="number" id="userAge" name="userAge" min="1" max="120" value="35">
                        </div>
                    </div>

                    <div class="form-row">
                        <div class="field">
                            <label for="userGender">Gender</label>
                            <select id="userGender" name="userGender">
                                <option value="Male">Male</option>
                                <option value="Female">Female</option>
                                <option value="Other">Other</option>
                            </select>
                        </div>
                        <div class="field">
                            <label for="paxCount">Number of Pilgrims *</label>
                            <input type="number" id="paxCount" name="paxCount" required min="1" value="1">
                        </div>
                    </div>

                    <div class="form-row">
                        <div class="field">
                            <label for="userMobile">Mobile Number (Demo Verification)</label>
                            <input type="text" id="userMobile" name="userMobile" value="+91 98765 43210">
                        </div>
                        <div class="field">
                            <label for="userEmail">Email Address (Confirmation Receipt)</label>
                            <input type="email" id="userEmail" name="userEmail" value="pilgrim.demo@example.com">
                        </div>
                    </div>

                    <div class="form-row">
                        <div class="field">
                            <label for="transportInfo">Arrival Transport Mode</label>
                            <input type="text" id="transportInfo" name="transportInfo" value="Train (Vande Bharat Express)">
                        </div>
                        <div class="field">
                            <label for="yatraSlot">Requested Darshan Category / Slot</label>
                            <input type="text" id="yatraSlot" name="yatraSlot" value="Morning Aarti & Darshan (06:00)">
                        </div>
                    </div>

                    <div class="form-row">
                        <div class="field">
                            <label for="totalAmount">Estimated Total Fees (₹)</label>
                            <input type="text" id="totalAmount" name="totalAmount" value="₹0">
                        </div>
                        <div class="field">
                            <label for="paymentMethod">Simulated Gateway Token</label>
                            <input type="text" id="paymentMethod" name="paymentMethod" value="MOCK_SANDBOX_AUTH">
                        </div>
                    </div>

                    <div id="step1Error" style="display: none; color: #C53030; font-size: 0.82rem; margin-bottom: 8px;">
                        Please provide valid pilgrim name and number of pilgrims.
                    </div>

                    <div class="btn-row">
                        <button type="button" id="btnStep1Next" onclick="goToStep(2)" class="btn">Proceed to Slot Selection ➔</button>
                    </div>

                    <!-- Primary submitBtn preserved for automated tests that invoke submit directly -->
                    <button type="button" id="submitBtn" onclick="submitBooking()" class="btn btn-secondary" style="margin-top: 6px; font-size: 0.8rem;">
                        ⚡ Quick Confirm Booking (Automated RPA Trigger)
                    </button>
                </div>

                <!-- STEP 2: DATE AND SLOT SELECTION -->
                <div id="step2Section" style="display: none;">
                    <h3>Step 2: Yatra Darshan Date & Slot Selection</h3>
                    <div class="form-row">
                        <div class="field">
                            <label for="stepDate">Darshan Date</label>
                            <input type="date" id="stepDate" value="2026-10-20" onchange="renderStepSlots()">
                        </div>
                        <div class="field">
                            <label for="stepCategory">Category Filter</label>
                            <select id="stepCategory" onchange="renderStepSlots()">
                                <option value="">All Categories</option>
                                <option value="Normal Darshan">Normal Darshan</option>
                                <option value="VIP Darshan">VIP Darshan</option>
                                <option value="Helicopter Darshan">Helicopter Darshan</option>
                            </select>
                        </div>
                    </div>

                    <label>Available Slots for Selected Date:</label>
                    <div id="stepSlotsList" class="slots-grid"></div>

                    <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px; margin-top: 10px; font-size: 0.82rem;">
                        Selected Slot: <strong id="stepSelectedSlotDisplay" style="color: #6E1423;">Morning Aarti & Darshan (06:00)</strong>
                    </div>

                    <div class="btn-row">
                        <button type="button" id="btnStep2Back" onclick="goToStep(1)" class="btn btn-secondary" style="width: 40%;">← Back</button>
                        <button type="button" id="btnStep2Next" onclick="goToStep(3)" class="btn" style="width: 60%;">Proceed to Review ➔</button>
                    </div>
                </div>

                <!-- STEP 3: BOOKING REVIEW -->
                <div id="step3Section" style="display: none;">
                    <h3>Step 3: Review Booking Particulars</h3>
                    <div class="review-box">
                        <div class="review-row"><span>Primary Pilgrim:</span> <strong id="revName">Guest Pilgrim</strong></div>
                        <div class="review-row"><span>Age & Gender:</span> <span id="revAgeGender">35 yrs, Male</span></div>
                        <div class="review-row"><span>Pilgrims Count:</span> <strong id="revPax">1</strong></div>
                        <div class="review-row"><span>Contact Mobile:</span> <span id="revMobile">+91 98765 43210</span></div>
                        <div class="review-row"><span>Darshan Date:</span> <strong id="revDate">2026-10-20</strong></div>
                        <div class="review-row"><span>Darshan Slot:</span> <strong id="revSlot">Morning Aarti & Darshan (06:00)</strong></div>
                        <div class="review-row"><span>Registration Fee:</span> <span>₹0 (Free Pilgrimage Pass)</span></div>
                        <div class="review-row" style="border-top: 2px solid #E8C874; margin-top: 6px; padding-top: 6px;">
                            <span>Total Payable:</span> <strong id="revTotal" style="color: #6E1423; font-size: 1.1rem;">₹0</strong>
                        </div>
                    </div>

                    <div class="btn-row">
                        <button type="button" id="btnStep3Back" onclick="goToStep(2)" class="btn btn-secondary" style="width: 40%;">← Edit Details</button>
                        <button type="button" id="btnStep3Next" onclick="proceedFromReview()" class="btn" style="width: 60%;">Proceed to Verification / Payment ➔</button>
                    </div>
                </div>
            </form>

            <!-- STEP 4: SIMULATED SECURITY CHECKPOINTS (Week 8) -->
            <div id="otpChallengeSection" style="display: none; background: #FFF9E6; border: 2px solid #E8C874; border-radius: 12px; padding: 18px; margin-top: 14px;">
                <h3 style="color: #6E1423; margin-top: 0;">🔐 Step 4: Security Verification (OTP Required)</h3>
                <div style="background: #FFFDF0; border: 1px solid #F6D860; border-radius: 8px; padding: 10px; margin-bottom: 12px; font-size: 0.85rem; color: #744210;">
                    <div>📱 <strong>Simulated SMS Delivery:</strong> A one-time verification code has been dispatched to pilgrim mobile.</div>
                    <div style="margin-top: 4px;"><strong>Demo Verification Code:</strong> <code style="background: #FEF08A; padding: 2px 6px; border-radius: 4px; font-weight: 800;">123456</code></div>
                </div>
                <div class="field">
                    <label for="userOtpInput">Enter 6-Digit OTP:</label>
                    <input type="text" id="userOtpInput" placeholder="Enter 6-digit OTP (e.g. 123456)" maxlength="6" style="letter-spacing: 2px; font-weight: bold; text-align: center;">
                </div>
                <div style="display: flex; gap: 10px; align-items: center; margin-top: 8px;">
                    <button type="button" id="btnVerifyOtp" class="btn" style="margin-top: 0; width: auto;" onclick="verifyOtp()">Verify OTP</button>
                    <button type="button" id="btnResendOtp" class="btn btn-secondary" style="margin-top: 0; width: auto; font-size: 0.8rem;" onclick="resendOtp()">🔄 Resend Code (<span id="resendTimer">30</span>s)</button>
                    <span id="otpStatusBadge" class="badge" style="margin-bottom: 0;">WAITING_FOR_USER</span>
                </div>
                <div id="otpErrorMsg" style="display: none; color: #C53030; font-size: 0.85rem; margin-top: 8px;">Invalid OTP code. Please enter the correct 6-digit code (Demo: 123456).</div>
                <button type="button" id="btnCompleteOtpVerification" class="btn" style="display: none; margin-top: 12px; background: #27AE60;" onclick="completeSecurityAndConfirm()">Proceed to Payment Sandbox ➔</button>
            </div>

            <div id="captchaChallengeSection" style="display: none; background: #F0F4F8; border: 2px solid #6E1423; border-radius: 12px; padding: 18px; margin-top: 14px;">
                <h3 style="color: #6E1423; margin-top: 0;">🛡️ Step 4: Human Verification (CAPTCHA Challenge)</h3>
                <p style="font-size: 0.85rem; color: #4A3B32; margin-top: 4px;">
                    Please solve the visual security puzzle manually. Robotic process automation is strictly prohibited from bypassing CAPTCHAs.
                </p>
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                    <div id="captchaBox" style="background: #2D3748; color: #E8C874; font-family: monospace; font-size: 1.4rem; font-weight: bold; padding: 8px 16px; border-radius: 6px; letter-spacing: 4px; user-select: none;">
                        M7K9P
                    </div>
                    <span style="font-size: 0.8rem; color: #718096;">(Case-sensitive security token)</span>
                </div>
                <div class="field">
                    <label for="userCaptchaInput">Enter Characters Shown Above:</label>
                    <input type="text" id="userCaptchaInput" placeholder="Enter CAPTCHA text (e.g. M7K9P)" maxlength="10">
                </div>
                <div style="display: flex; gap: 10px; align-items: center; margin-top: 8px;">
                    <button type="button" id="btnVerifyCaptcha" class="btn" style="margin-top: 0; width: auto;" onclick="verifyCaptcha()">Solve CAPTCHA</button>
                    <span id="captchaStatusBadge" class="badge" style="margin-bottom: 0;">WAITING_FOR_USER</span>
                </div>
                <div id="captchaErrorMsg" style="display: none; color: #C53030; font-size: 0.85rem; margin-top: 8px;">Incorrect CAPTCHA answer. Please try again.</div>
                <button type="button" id="btnCompleteCaptchaVerification" class="btn" style="display: none; margin-top: 12px; background: #27AE60;" onclick="completeSecurityAndConfirm()">Proceed to Payment Sandbox ➔</button>
            </div>

            <!-- STEP 5: SIMULATED PAYMENT / FINAL REVIEW -->
            <div id="step5PaymentSection" style="display: none; background: #FFFDF9; border: 2px solid #E8C874; border-radius: 12px; padding: 18px; margin-top: 14px;">
                <h3>Step 5: Simulated Payment Sandbox</h3>
                <div class="sandbox-notice">
                    <span>💳</span> <strong>Safe Sandbox Transaction:</strong> No real money or card data is collected. This is a local simulation.
                </div>
                <div class="review-box">
                    <div class="review-row"><span>Payable Amount:</span> <strong id="payTotal" style="color: #6E1423; font-size: 1.1rem;">₹0</strong></div>
                    <div class="review-row"><span>Transaction Mode:</span> <span>Demo Sandbox Gateway (Free Registration)</span></div>
                    <div class="review-row"><span>Gateway Status:</span> <span style="color: #047857; font-weight: 700;">Ready for Authorization</span></div>
                </div>

                <div class="field">
                    <label>Choose Demo Payment Method:</label>
                    <select id="dummyPaymentSelect">
                        <option value="FREE_REGISTRATION">Free Pilgrimage Registration (₹0)</option>
                        <option value="MOCK_UPI">Mock UPI Sandbox (@yatra)</option>
                        <option value="MOCK_NETBANKING">Mock NetBanking Demo</option>
                    </select>
                </div>

                <button type="button" id="btnConfirmFinalBooking" onclick="finalizeBooking()" class="btn" style="background: #27AE60; font-size: 1rem;">
                    Confirm Booking & Issue Pilgrim Pass ➔
                </button>
            </div>

            <!-- STEP 6: CONFIRMATION RECEIPT (Preserves #confirmation and #outBookingId) -->
            <div id="confirmation" class="success">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #86EFAC; padding-bottom: 10px; margin-bottom: 12px;">
                    <div>
                        <span class="badge" style="background: #E8F5E9; color: #1B5E20; border: 1px solid #A5D6A7; font-weight: 800; font-size: 0.72rem;">
                            LOCAL MOCK PORTAL / DEMO
                        </span>
                        <h3 style="margin: 6px 0 0 0; color: #14532D; font-size: 1.25rem;">
                            ✅ Simulated Yatra Booking Confirmation
                        </h3>
                        <p style="font-size: 0.82rem; color: #4B5563; margin: 4px 0 0 0;">
                            Demo Pilgrim Pass — Generated via Local Browser Automation
                        </p>
                    </div>
                    <button type="button" id="btnPrintReceipt" onclick="window.print()" class="btn btn-secondary" style="width: auto; margin-top: 0; padding: 6px 12px; font-size: 0.78rem;">
                        🖨️ Print Demo Pass
                    </button>
                </div>

                <div class="review-box" style="background: white; border-color: #86EFAC;">
                    <div class="review-row">
                        <span>Confirmation Booking ID:</span>
                        <strong id="outBookingId" style="font-family: monospace; font-size: 1.15rem; color: #6E1423;"></strong>
                    </div>
                    <div class="review-row"><span>Receipt Classification:</span> <strong style="color: #047857;">Demo Pilgrim Pass (Local Simulation)</strong></div>
                    <div class="review-row"><span>Primary Pilgrim:</span> <span id="confUserName">Guest Pilgrim</span></div>
                    <div class="review-row"><span>Devotees:</span> <span id="confPax">1</span></div>
                    <div class="review-row"><span>Darshan Slot:</span> <span id="confSlot">Morning Aarti & Darshan (06:00)</span></div>
                    <div class="review-row"><span>Amount:</span> <span id="confAmount">₹0</span></div>
                    <div class="review-row"><span>Timestamp:</span> <span id="confTimestamp">Just now</span></div>
                </div>

                <p style="font-size: 0.9rem; color: #15803D; text-align: center; font-weight: 700; margin: 10px 0 0 0;">
                    🙏 Jai Mata Di! Wishing you a blessed, serene and spiritually fulfilling yatra!
                </p>
            </div>
        </div>

        <!-- Section 2: Availability Calendar (Week 5 RPA Scope - 100% Preserved) -->
        <div id="calendarSection" style="display: none;">
            <h2>🗓️ Darshan Slot Availability Calendar</h2>
            <p style="font-size: 0.85rem; color: #718096; margin-top: -6px;">
                Check real-time slot statuses and capacity for Shri Mata Vaishno Devi Ji.
            </p>

            <form id="availabilityForm" onsubmit="event.preventDefault(); fetchSlots();">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                    <div class="field">
                        <label for="calendarDate">Yatra Darshan Date</label>
                        <input type="date" id="calendarDate" name="calendarDate" value="2026-10-20">
                    </div>
                    <div class="field">
                        <label for="slotCategoryFilter">Darshan Category</label>
                        <select id="slotCategoryFilter" name="slotCategoryFilter">
                            <option value="">All Categories</option>
                            <option value="Normal Darshan">Normal Darshan</option>
                            <option value="VIP Darshan">VIP Darshan</option>
                            <option value="Helicopter Darshan">Helicopter Darshan</option>
                        </select>
                    </div>
                </div>

                <button type="button" id="btnCheckAvailability" onclick="fetchSlots()" class="btn">
                    🔍 Check Slot Availability
                </button>
            </form>

            <div id="calendarLoading" style="display: none;" class="loading-state">
                ⏳ Consulting Shri Mata Vaishno Devi Shrine Board Slot Inventory...
            </div>

            <div id="slotsContainer" style="display: none;">
                <h4 style="margin: 14px 0 6px 0; color: #6E1423;">
                    Slot Availability for <span id="displayDate"></span>
                </h4>
                <div id="slotsList" class="slots-grid"></div>
                <div id="emptyCalendarNotice" style="display: none;" class="empty-state">
                    No yatra slots available for this date. Please select another date.
                </div>
            </div>

            <div id="calendarErrorNotice" style="display: none;" class="error-state"></div>
        </div>
    </div>

    <script>
        const ALL_SLOTS = {slots_json};
        const RENDER_DELAY_MS = {render_delay_ms};
        const urlParams = new URLSearchParams(window.location.search);
        let activeCheckpoint = urlParams.get('checkpoint') || '';
        let currentStep = 1;
        let selectedSlotObject = ALL_SLOTS[0] || null;

        function showTab(tabName) {{
            document.getElementById('tabBooking').classList.toggle('active', tabName === 'booking');
            document.getElementById('tabCalendar').classList.toggle('active', tabName === 'calendar');
            document.getElementById('bookingSection').style.display = tabName === 'booking' ? 'block' : 'none';
            document.getElementById('calendarSection').style.display = tabName === 'calendar' ? 'block' : 'none';
        }}

        function updateStepper(step) {{
            currentStep = step;
            for (let i = 1; i <= 6; i++) {{
                const el = document.getElementById('stStep' + i);
                if (!el) continue;
                el.classList.remove('active', 'completed');
                if (i < step) el.classList.add('completed');
                else if (i === step) el.classList.add('active');
            }}
        }}

        function goToStep(step) {{
            const name = (document.getElementById('userName').value || '').trim();
            const pax = parseInt(document.getElementById('paxCount').value || '1', 10);

            if (step > 1 && (!name || isNaN(pax) || pax < 1)) {{
                document.getElementById('step1Error').style.display = 'block';
                return;
            }}
            document.getElementById('step1Error').style.display = 'none';

            // Sync review fields
            document.getElementById('revName').textContent = name || 'Guest Pilgrim';
            document.getElementById('revPax').textContent = pax;
            document.getElementById('revAgeGender').textContent = (document.getElementById('userAge').value || '35') + ' yrs, ' + document.getElementById('userGender').value;
            document.getElementById('revMobile').textContent = document.getElementById('userMobile').value || '+91 98765 43210';
            document.getElementById('revDate').textContent = document.getElementById('stepDate').value || '2026-10-20';
            document.getElementById('revSlot').textContent = document.getElementById('yatraSlot').value || 'Morning Aarti & Darshan (06:00)';
            document.getElementById('revTotal').textContent = document.getElementById('totalAmount').value || '₹0';
            document.getElementById('payTotal').textContent = document.getElementById('totalAmount').value || '₹0';

            document.getElementById('step1Section').style.display = step === 1 ? 'block' : 'none';
            document.getElementById('step2Section').style.display = step === 2 ? 'block' : 'none';
            document.getElementById('step3Section').style.display = step === 3 ? 'block' : 'none';
            if (step === 2) renderStepSlots();

            updateStepper(step);
        }}

        function renderStepSlots() {{
            const dateVal = document.getElementById('stepDate').value;
            const catVal = document.getElementById('stepCategory').value;
            const list = document.getElementById('stepSlotsList');
            if (!list) return;
            list.innerHTML = '';

            const matched = ALL_SLOTS.filter(s => {{
                if (dateVal && s.slot_date !== dateVal) return false;
                if (catVal && s.category !== catVal) return false;
                return true;
            }});

            if (matched.length === 0) {{
                list.innerHTML = '<div class="empty-state">No slots matching criteria.</div>';
                return;
            }}

            matched.forEach(s => {{
                const card = document.createElement('div');
                card.className = 'slot-card' + (selectedSlotObject && selectedSlotObject.id === s.id ? ' selected' : '');
                const badgeClass = s.status === 'available' ? 'badge-available' : (s.status === 'full' ? 'badge-full' : 'badge-unavailable');
                card.innerHTML = `
                    <div>
                        <div class="slot-header">${{s.category}} • ${{s.session}}</div>
                        <div class="slot-sub">Time: ${{s.slot_time}} | Fee: ₹${{s.price}}</div>
                    </div>
                    <div><span class="slot-status ${{badgeClass}}">${{s.status}}</span></div>
                `;
                card.onclick = () => {{
                    selectedSlotObject = s;
                    document.getElementById('yatraSlot').value = s.category + ' (' + s.slot_time + ')';
                    document.getElementById('stepSelectedSlotDisplay').textContent = s.category + ' - ' + s.session + ' (' + s.slot_time + ')';
                    document.getElementById('totalAmount').value = '₹' + (s.price * parseInt(document.getElementById('paxCount').value || '1', 10));
                    renderStepSlots();
                }};
                list.appendChild(card);
            }});
        }}

        function proceedFromReview() {{
            const secMode = (document.getElementById('securityMode') ? document.getElementById('securityMode').value : '') || activeCheckpoint;
            document.getElementById('bookingForm').style.display = 'none';
            document.getElementById('step3Section').style.display = 'none';
            if (activeCheckpoint === 'CAPTCHA' || secMode === 'CAPTCHA') {{
                document.getElementById('captchaChallengeSection').style.display = 'block';
                document.getElementById('otpChallengeSection').style.display = 'none';
                document.getElementById('step5PaymentSection').style.display = 'none';
                updateStepper(4);
                return;
            }}
            if (activeCheckpoint === 'OTP' || secMode === 'OTP' || secMode === 'SEQUENTIAL' || secMode === 'BOTH') {{
                document.getElementById('otpChallengeSection').style.display = 'block';
                document.getElementById('captchaChallengeSection').style.display = 'none';
                document.getElementById('step5PaymentSection').style.display = 'none';
                updateStepper(4);
                return;
            }}
            document.getElementById('step5PaymentSection').style.display = 'block';
            updateStepper(5);
        }}

        function submitBooking() {{
            const secMode = (document.getElementById('securityMode') ? document.getElementById('securityMode').value : '') || activeCheckpoint;
            if (activeCheckpoint === 'CAPTCHA' || secMode === 'CAPTCHA') {{
                document.getElementById('bookingForm').style.display = 'none';
                document.getElementById('captchaChallengeSection').style.display = 'block';
                document.getElementById('otpChallengeSection').style.display = 'none';
                document.getElementById('step5PaymentSection').style.display = 'none';
                updateStepper(4);
                return;
            }}
            if (activeCheckpoint === 'OTP' || secMode === 'OTP' || secMode === 'SEQUENTIAL' || secMode === 'BOTH') {{
                document.getElementById('bookingForm').style.display = 'none';
                document.getElementById('otpChallengeSection').style.display = 'block';
                document.getElementById('captchaChallengeSection').style.display = 'none';
                document.getElementById('step5PaymentSection').style.display = 'none';
                updateStepper(4);
                return;
            }}

            finalizeBooking();
        }}

        function verifyOtp() {{
            const val = (document.getElementById('userOtpInput').value || '').trim();
            if (val.length >= 4) {{
                const badge = document.getElementById('otpStatusBadge');
                badge.textContent = 'VERIFIED';
                badge.className = 'badge badge-available';
                document.getElementById('otpErrorMsg').style.display = 'none';
                document.getElementById('btnCompleteOtpVerification').style.display = 'block';
            }} else {{
                document.getElementById('otpErrorMsg').style.display = 'block';
            }}
        }}

        let resendSeconds = 30;
        function resendOtp() {{
            const timerEl = document.getElementById('resendTimer');
            resendSeconds = 30;
            const it = setInterval(() => {{
                resendSeconds--;
                if (timerEl) timerEl.textContent = resendSeconds;
                if (resendSeconds <= 0) clearInterval(it);
            }}, 1000);
            alert("Simulated OTP resent! Demo code remains: 123456");
        }}

        function verifyCaptcha() {{
            const val = (document.getElementById('userCaptchaInput').value || '').trim();
            const target = (document.getElementById('captchaBox').textContent || '').trim();
            if (val.toUpperCase() === target.toUpperCase()) {{
                const badge = document.getElementById('captchaStatusBadge');
                badge.textContent = 'SOLVED';
                badge.className = 'badge badge-available';
                document.getElementById('captchaErrorMsg').style.display = 'none';
                document.getElementById('btnCompleteCaptchaVerification').style.display = 'block';
            }} else {{
                document.getElementById('captchaErrorMsg').style.display = 'block';
            }}
        }}

        function completeOtpVerification() {{
            const secMode = (document.getElementById('securityMode') ? document.getElementById('securityMode').value : '') || activeCheckpoint;
            document.getElementById('otpChallengeSection').style.display = 'none';
            if (secMode === 'SEQUENTIAL' || secMode === 'BOTH') {{
                document.getElementById('captchaChallengeSection').style.display = 'block';
                updateStepper(4);
                return;
            }}
            document.getElementById('step5PaymentSection').style.display = 'block';
            updateStepper(5);
        }}

        function completeCaptchaVerification() {{
            document.getElementById('captchaChallengeSection').style.display = 'none';
            document.getElementById('step5PaymentSection').style.display = 'block';
            updateStepper(5);
        }}

        function completeSecurityAndConfirm() {{
            if (document.getElementById('otpChallengeSection').style.display !== 'none') {{
                completeOtpVerification();
                return;
            }}
            if (document.getElementById('captchaChallengeSection').style.display !== 'none') {{
                completeCaptchaVerification();
                return;
            }}
            finalizeBooking();
        }}

        function finalizeBooking() {{
            document.getElementById('bookingForm').style.display = 'none';
            document.getElementById('step1Section').style.display = 'none';
            document.getElementById('step2Section').style.display = 'none';
            document.getElementById('step3Section').style.display = 'none';
            document.getElementById('otpChallengeSection').style.display = 'none';
            document.getElementById('captchaChallengeSection').style.display = 'none';
            document.getElementById('step5PaymentSection').style.display = 'none';

            const bookingId = "VD-RPA-" + Math.floor(100000 + Math.random() * 900000);
            document.getElementById('outBookingId').textContent = bookingId;
            document.getElementById('confUserName').textContent = document.getElementById('userName').value || 'Guest Pilgrim';
            document.getElementById('confPax').textContent = document.getElementById('paxCount').value || '1';
            document.getElementById('confSlot').textContent = document.getElementById('yatraSlot').value || 'Morning Aarti & Darshan (06:00)';
            document.getElementById('confAmount').textContent = document.getElementById('totalAmount').value || '₹0';
            document.getElementById('confTimestamp').textContent = new Date().toLocaleTimeString();

            document.getElementById('confirmation').style.display = 'block';
            updateStepper(6);
        }}

        function fetchSlots() {{
            const dateVal = document.getElementById('calendarDate').value;
            const catVal = document.getElementById('slotCategoryFilter').value;
            const loading = document.getElementById('calendarLoading');
            const container = document.getElementById('slotsContainer');
            const list = document.getElementById('slotsList');
            const emptyNotice = document.getElementById('emptyCalendarNotice');
            const displayDate = document.getElementById('displayDate');

            displayDate.textContent = dateVal || 'Selected Date';
            loading.style.display = 'block';
            container.style.display = 'none';
            list.innerHTML = '';
            emptyNotice.style.display = 'none';

            setTimeout(() => {{
                loading.style.display = 'none';
                container.style.display = 'block';

                const matched = ALL_SLOTS.filter(s => {{
                    if (s.slot_date !== dateVal) return false;
                    if (catVal && s.category !== catVal) return false;
                    return true;
                }});

                if (matched.length === 0) {{
                    emptyNotice.style.display = 'block';
                    return;
                }}

                matched.forEach(s => {{
                    const card = document.createElement('div');
                    card.className = 'slot-card';
                    card.setAttribute('data-slot-id', s.id);
                    card.setAttribute('data-date', s.slot_date);
                    card.setAttribute('data-category', s.category);
                    card.setAttribute('data-status', s.status);
                    card.setAttribute('data-capacity', s.seats_available);
                    card.setAttribute('data-price', s.price);

                    const badgeClass = s.status === 'available' ? 'badge-available' : (s.status === 'full' ? 'badge-full' : 'badge-unavailable');
                    const capText = s.status === 'available' ? (s.seats_available + ' seats left') : (s.status === 'full' ? '0 seats left (Full)' : 'Unavailable');

                    card.innerHTML = `
                        <div>
                            <div class="slot-header">
                                <span class="slot-id">SLOT-${{s.id}}</span> •
                                <span class="slot-category">${{s.category}}</span>
                            </div>
                            <div class="slot-sub">
                                <span class="slot-time">${{s.slot_time}}</span> •
                                <span class="slot-session">${{s.session}}</span>
                            </div>
                            <div class="slot-sub">
                                <span class="slot-price">₹${{s.price}}</span> •
                                <span class="slot-capacity" data-capacity="${{s.seats_available}}">${{capText}}</span>
                            </div>
                        </div>
                        <div>
                            <span class="slot-status ${{badgeClass}}">${{s.status}}</span>
                        </div>
                    `;
                    list.appendChild(card);
                }});
            }}, RENDER_DELAY_MS);
        }}
    </script>
</body>
</html>
"""

MOCK_PORTAL_HTML = generate_mock_portal_html()


# ==============================================================================
# WEEK 6: RPA ERROR HANDLING & EXCEPTION HIERARCHY
# ==============================================================================

class RPAError(Exception):
    """Base exception for all RPA automation tasks."""
    def __init__(self, message: str, operation: str = "", diagnostics: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.diagnostics = diagnostics or {}


class RecoverableRPAError(RPAError):
    """Transient errors that can be safely retried (e.g. transient timeout, slow rendering)."""
    pass


class NonRecoverableRPAError(RPAError):
    """Permanent errors that must NOT be retried (e.g. structural DOM degradation, invalid input)."""
    pass


class StructuralPageChangeError(NonRecoverableRPAError):
    """Triggered when required page DOM elements or selectors are missing or modified."""
    def __init__(self, message: str, operation: str = "", selector: str = "", diagnostics: Optional[Dict[str, Any]] = None):
        super().__init__(message, operation=operation, diagnostics=diagnostics)
        self.selector = selector
        self.is_structural = True


class DataIntegrityError(NonRecoverableRPAError):
    """Triggered when extracted slot data violates structural or business integrity rules."""
    def __init__(self, message: str, operation: str = "", diagnostics: Optional[Dict[str, Any]] = None):
        super().__init__(message, operation=operation, diagnostics=diagnostics)


class StateValidationError(RPAError):
    """Triggered when post-action state verification fails."""
    def __init__(
        self,
        message: str,
        operation: str = "",
        expected_state: str = "",
        actual_state: str = "",
        is_structural: bool = False,
        diagnostics: Optional[Dict[str, Any]] = None
    ):
        diag = diagnostics or {}
        diag.update({"expected_state": expected_state, "actual_state": actual_state})
        super().__init__(message, operation=operation, diagnostics=diag)
        self.expected_state = expected_state
        self.actual_state = actual_state
        self.is_structural = is_structural


# ==============================================================================
# WEEK 6: STATE VALIDATION HELPERS
# ==============================================================================

def validate_portal_loaded(page, timeout_ms: int = 3000, logs: Optional[List[str]] = None) -> bool:
    """Verifies that the mock portal container and navigation tabs are present in the DOM."""
    def log(msg: str):
        if logs is not None:
            logs.append(msg)

    if page.locator(".card").count() == 0:
        raise StructuralPageChangeError(
            "Portal container (.card) is missing from DOM. Possible structural page change.",
            operation="validate_portal_loaded",
            selector=".card"
        )

    if page.locator("#portalNav").count() == 0:
        raise StructuralPageChangeError(
            "Navigation container (#portalNav) is missing from DOM.",
            operation="validate_portal_loaded",
            selector="#portalNav"
        )

    if page.locator("#tabBooking").count() == 0 or page.locator("#tabCalendar").count() == 0:
        raise StructuralPageChangeError(
            "Navigation tab elements (#tabBooking / #tabCalendar) are missing from DOM.",
            operation="validate_portal_loaded",
            selector="#tabBooking / #tabCalendar"
        )

    log("Portal root structure and navigation tabs successfully validated.")
    return True


def validate_calendar_tab_active(page, timeout_ms: int = 3000, logs: Optional[List[str]] = None) -> bool:
    """Verifies that the calendar section is present and visible, and the calendar tab is active."""
    def log(msg: str):
        if logs is not None:
            logs.append(msg)

    cal_sec = page.locator("#calendarSection")
    if cal_sec.count() == 0:
        raise StructuralPageChangeError(
            "Calendar section element (#calendarSection) is missing from DOM.",
            operation="validate_calendar_tab_active",
            selector="#calendarSection"
        )

    try:
        cal_sec.wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        raise StateValidationError(
            "Calendar section (#calendarSection) failed to become visible after tab switch.",
            operation="validate_calendar_tab_active",
            expected_state="visible",
            actual_state="hidden",
            is_structural=False
        )

    tab_cal = page.locator("#tabCalendar")
    class_attr = tab_cal.get_attribute("class") or ""
    if "active" not in class_attr:
        log("Warning: #tabCalendar does not show active class after tab switch.")

    log("Availability calendar tab and section display successfully validated.")
    return True


def validate_date_input_state(page, expected_date: str, logs: Optional[List[str]] = None) -> bool:
    """Verifies that the date input field contains the expected requested date."""
    date_input = page.locator("#calendarDate")
    if date_input.count() == 0:
        raise StructuralPageChangeError(
            "Date input field (#calendarDate) is missing from DOM.",
            operation="validate_date_input_state",
            selector="#calendarDate"
        )

    actual_val = date_input.input_value()
    if actual_val != expected_date:
        raise StateValidationError(
            f"Calendar date field value mismatch: expected '{expected_date}', got '{actual_val}'.",
            operation="validate_date_input_state",
            expected_state=expected_date,
            actual_state=actual_val
        )
    return True


def validate_category_filter_state(page, expected_category: Optional[str], logs: Optional[List[str]] = None) -> bool:
    """Verifies that the category dropdown matches the selected category filter."""
    if not expected_category:
        return True

    cat_select = page.locator("#slotCategoryFilter")
    if cat_select.count() == 0:
        raise StructuralPageChangeError(
            "Category select (#slotCategoryFilter) is missing from DOM.",
            operation="validate_category_filter_state",
            selector="#slotCategoryFilter"
        )

    actual_val = cat_select.input_value()
    if actual_val != expected_category:
        raise StateValidationError(
            f"Category filter value mismatch: expected '{expected_category}', got '{actual_val}'.",
            operation="validate_category_filter_state",
            expected_state=expected_category,
            actual_state=actual_val
        )
    return True


def validate_calendar_readiness(page, timeout_ms: int = 5000, logs: Optional[List[str]] = None) -> str:
    """
    Validates calendar lookup readiness:
    1. Dynamic loading spinner (#calendarLoading) must be hidden.
    2. Results container (#slotsContainer) must be present in DOM and visible.
    3. Distinguishes:
       - 'SLOTS_FOUND': .slot-card elements are rendered.
       - 'EMPTY_CALENDAR': legitimate empty calendar notice is visible.
       - 'PORTAL_ERROR': portal error notice is displayed.
    Raises StructuralPageChangeError if #slotsContainer is missing from DOM.
    Raises StateValidationError if neither cards nor empty notice are present.
    """
    def log(msg: str):
        if logs is not None:
            logs.append(msg)

    # 1. Loading indicator check
    loading_loc = page.locator("#calendarLoading")
    if loading_loc.count() > 0:
        try:
            loading_loc.wait_for(state="hidden", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            raise RecoverableRPAError(
                "Dynamic loading indicator (#calendarLoading) timed out waiting to complete.",
                operation="validate_calendar_readiness"
            )

    # 2. Check for explicit error notice
    error_notice = page.locator("#calendarErrorNotice")
    if error_notice.count() > 0 and error_notice.is_visible():
        err_msg = error_notice.inner_text().strip()
        log(f"Portal error state detected: {err_msg}")
        return "PORTAL_ERROR"

    # 3. Structural check: #slotsContainer must exist in DOM
    slots_container = page.locator("#slotsContainer")
    if slots_container.count() == 0:
        raise StructuralPageChangeError(
            "Results container element (#slotsContainer) missing from DOM.",
            operation="validate_calendar_readiness",
            selector="#slotsContainer"
        )

    if not slots_container.is_visible():
        raise StateValidationError(
            "Results container (#slotsContainer) is not visible after search completion.",
            operation="validate_calendar_readiness",
            expected_state="visible",
            actual_state="hidden"
        )

    # 4. Check for legitimate empty calendar notice
    empty_notice = page.locator("#emptyCalendarNotice")
    if empty_notice.count() > 0 and empty_notice.is_visible():
        log("Validated legitimate empty calendar state.")
        return "EMPTY_CALENDAR"

    # 5. Check for slot cards
    card_count = page.locator(".slot-card").count()
    if card_count > 0:
        log(f"Validated calendar readiness: {card_count} slot cards displayed.")
        return "SLOTS_FOUND"

    # 6. Neither empty notice nor cards visible despite container visible: degradation
    raise StateValidationError(
        "Results container is visible but contains neither slot cards nor empty notice.",
        operation="validate_calendar_readiness",
        expected_state="slot-cards or empty-notice",
        actual_state="empty container without notice"
    )


def validate_slot_record_integrity(slot: Dict[str, Any]) -> None:
    """
    Validates structural and business integrity constraints for an extracted slot record.
    Raises DataIntegrityError if constraints are violated.
    """
    slot_id = slot.get("slot_id")
    if not slot_id or str(slot_id).strip() == "" or str(slot_id).strip() == "UNKNOWN":
        raise DataIntegrityError(f"Slot record missing mandatory slot ID: {slot}", operation="validate_slot_record_integrity")

    status = slot.get("availability_status")
    if status not in ("available", "full", "unavailable"):
        raise DataIntegrityError(f"Invalid availability status '{status}' for slot {slot_id}", operation="validate_slot_record_integrity")

    capacity = slot.get("remaining_capacity")
    if capacity is not None and capacity < 0:
        raise DataIntegrityError(f"Negative remaining capacity ({capacity}) for slot {slot_id}", operation="validate_slot_record_integrity")

    price = slot.get("price")
    if price is not None and price < 0.0:
        raise DataIntegrityError(f"Negative price ({price}) for slot {slot_id}", operation="validate_slot_record_integrity")


def validate_booking_form_state(page, logs: Optional[List[str]] = None) -> bool:
    """Verifies that the booking form and required inputs are present and visible."""
    def log(msg: str):
        if logs is not None:
            logs.append(msg)

    form = page.locator("#bookingForm")
    if form.count() == 0:
        raise StructuralPageChangeError("Booking form (#bookingForm) missing from DOM.", operation="validate_booking_form_state", selector="#bookingForm")
    if not form.is_visible():
        raise StateValidationError("Booking form is not visible.", operation="validate_booking_form_state", expected_state="visible", actual_state="hidden")

    for field_id in ("#userName", "#paxCount", "#submitBtn"):
        if page.locator(field_id).count() == 0:
            raise StructuralPageChangeError(f"Required booking field '{field_id}' missing from DOM.", operation="validate_booking_form_state", selector=field_id)

    log("Validated booking form readiness.")
    return True


def validate_booking_confirmation_state(page, logs: Optional[List[str]] = None) -> bool:
    """Verifies that the booking confirmation container is visible and has a non-empty booking ID."""
    def log(msg: str):
        if logs is not None:
            logs.append(msg)

    conf = page.locator("#confirmation")
    if conf.count() == 0:
        raise StructuralPageChangeError("Confirmation container (#confirmation) missing from DOM.", operation="validate_booking_confirmation_state", selector="#confirmation")
    if not conf.is_visible():
        raise StateValidationError("Confirmation element is not visible.", operation="validate_booking_confirmation_state", expected_state="visible", actual_state="hidden")

    bid_elem = page.locator("#outBookingId")
    if bid_elem.count() == 0:
        raise StructuralPageChangeError("Booking ID element (#outBookingId) missing from DOM.", operation="validate_booking_confirmation_state", selector="#outBookingId")

    bid_text = bid_elem.inner_text().strip()
    if not bid_text:
        raise StateValidationError("Booking ID element is empty.", operation="validate_booking_confirmation_state", expected_state="non-empty string", actual_state="empty")

    log(f"Validated booking confirmation state with ID: {bid_text}")
    return True


# ==============================================================================
# WEEK 6: BOUNDED RETRY-AND-ESCALATE ENGINE
# ==============================================================================

def retry_with_backoff(
    action_callable: Callable[[int], Any],
    operation_name: str,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.5,
    backoff_multiplier: float = 2.0,
    max_delay_seconds: float = 2.0,
    recoverable_exceptions: tuple = (PlaywrightTimeoutError, RecoverableRPAError),
    logs: Optional[List[str]] = None,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> Any:
    """
    Executes an action callable with bounded exponential backoff retries for recoverable errors.
    Non-recoverable errors (e.g. StructuralPageChangeError, DataIntegrityError, NonRecoverableRPAError)
    fail-fast immediately and are never retried.
    """
    def log(msg: str):
        if logs is not None:
            logs.append(msg)

    last_exception = None
    for attempt in range(1, max_attempts + 1):
        try:
            return action_callable(attempt)
        except Exception as exc:
            last_exception = exc

            # 1. Non-recoverable errors: NEVER retry
            if isinstance(exc, NonRecoverableRPAError):
                log(f"[NON_RECOVERABLE] Non-recoverable failure in '{operation_name}' on attempt {attempt}: {exc.__class__.__name__}: {str(exc)}")
                raise exc

            # 2. Check if recoverable
            is_recoverable = isinstance(exc, recoverable_exceptions) or isinstance(exc, PlaywrightTimeoutError)
            if not is_recoverable:
                log(f"[UNRECOVERABLE] Unexpected error in '{operation_name}' on attempt {attempt}: {exc.__class__.__name__}: {str(exc)}")
                raise exc

            # 3. Recoverable error handling
            if attempt < max_attempts:
                delay = min(base_delay_seconds * (backoff_multiplier ** (attempt - 1)), max_delay_seconds)
                log(f"[RETRY] Recoverable error in '{operation_name}' (attempt {attempt}/{max_attempts}): {exc.__class__.__name__}: {str(exc)}. Retrying in {delay:.2f}s...")
                log_event(
                    logging.WARNING,
                    "rpa_agent",
                    "RPA_RETRY_INITIATED",
                    f"Recoverable error in '{operation_name}' (attempt {attempt}/{max_attempts}): {exc.__class__.__name__}. Retrying in {delay:.2f}s...",
                    error_category="RECOVERABLE_RPA_ERROR",
                    retry_attempt=attempt,
                    details={"operation": operation_name, "error_type": exc.__class__.__name__, "delay_seconds": delay}
                )
                if on_retry:
                    try:
                        on_retry(attempt, exc)
                    except Exception:
                        pass
                time.sleep(delay)
            else:
                log(f"[ESCALATE] Maximum retry attempts ({max_attempts}) exhausted for '{operation_name}'. Escalating.")
                log_event(
                    logging.ERROR,
                    "rpa_agent",
                    "RPA_RETRY_LIMIT_REACHED",
                    f"Maximum retry attempts ({max_attempts}) exhausted for '{operation_name}'. Escalating.",
                    error_category="RETRY_EXHAUSTED",
                    retry_attempt=attempt,
                    human_intervention_required=True,
                    details={"operation": operation_name, "max_attempts": max_attempts, "last_error": sanitize_log_message(str(exc))}
                )
                raise RecoverableRPAError(
                    f"Exhausted {max_attempts} attempts for '{operation_name}': {str(exc)}",
                    operation=operation_name,
                    diagnostics={"max_attempts": max_attempts, "last_error": str(exc)}
                ) from exc

    if last_exception:
        raise last_exception


# ==============================================================================
# WEEK 6: PAUSE-AND-HANDOVER TRIGGER & FORMATTER
# ==============================================================================

def create_handover_result(
    error: Exception,
    failed_operation: str,
    attempt_count: int,
    page=None,
    screenshot_path: Optional[str] = None,
    logs: Optional[List[str]] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Creates a structured human handover result for non-recoverable or retry-exhausted RPA failures.
    Ensures safe screenshot capture without masking the original exception.
    """
    if isinstance(error, StructuralPageChangeError) or getattr(error, "is_structural", False):
        error_category = "STRUCTURAL_CHANGE"
    elif isinstance(error, DataIntegrityError):
        error_category = "DATA_INTEGRITY_VIOLATION"
    elif isinstance(error, (PlaywrightTimeoutError, RecoverableRPAError)):
        error_category = "RETRY_EXHAUSTED"
    elif isinstance(error, NonRecoverableRPAError):
        error_category = "NON_RECOVERABLE_FAILURE"
    else:
        error_category = "SYSTEM_ERROR"

    diag_dict = dict(diagnostics) if diagnostics else {}
    if hasattr(error, "diagnostics") and isinstance(error.diagnostics, dict):
        diag_dict.update(error.diagnostics)

    actual_screenshot_path = None
    if page is not None and screenshot_path:
        try:
            page.screenshot(path=screenshot_path)
            actual_screenshot_path = screenshot_path
            if logs is not None:
                logs.append(f"Audit handover screenshot captured: {screenshot_path}")
        except Exception as ss_err:
            # Screenshot failure must NEVER mask or replace the original exception
            if logs is not None:
                logs.append(f"Warning: Screenshot capture failed during handover: {str(ss_err)}")
            diag_dict["screenshot_capture_error"] = str(ss_err)

    log_event(
        logging.ERROR,
        "rpa_agent",
        "RPA_HUMAN_HANDOVER",
        f"Human intervention required for failed operation: {failed_operation}",
        error_category=error_category,
        retry_attempt=attempt_count,
        human_intervention_required=True,
        workflow_state="HANDOVER_REQUIRED",
        final_outcome="FAILED",
        details={"failed_operation": failed_operation, "attempt_count": attempt_count, "error_type": error.__class__.__name__}
    )

    return {
        "status": "HANDOVER_REQUIRED",
        "handover_required": True,
        "retryable": False,
        "error_category": error_category,
        "failed_operation": failed_operation,
        "attempt_count": attempt_count,
        "message": f"Human intervention required: {str(error)}",
        "error": str(error),
        "screenshot_path": actual_screenshot_path,
        "diagnostics": diag_dict,
        "logs": logs or [],
    }


# ==============================================================================
# PHASE 2: IMPLEMENT AVAILABILITY NAVIGATION (WITH STATE VALIDATION)
# ==============================================================================

def navigate_to_availability_calendar(
    page,
    html_url: str,
    requested_date: Optional[str] = "2026-10-20",
    category: Optional[str] = None,
    timeout_ms: int = 10000,
    logs: Optional[List[str]] = None,
    validate_state: bool = True
) -> None:
    """
    Navigates to the local mock portal and opens the availability calendar.
    Uses Playwright locators and explicit waits:
    - Waits for tab button (#tabCalendar) to be visible.
    - Clicks tab to switch to calendar section.
    - Explicitly validates calendar section state.
    - Inputs requested date and optional category filter with validation.
    - Clicks check availability button.
    - Explicitly validates calendar readiness and results container.
    """
    def log(msg: str):
        if logs is not None:
            logs.append(msg)

    log(f"Navigating to mock portal URL: {html_url}")
    log_event(
        logging.INFO,
        "rpa_agent",
        "RPA_PORTAL_OPEN",
        f"Opening mock availability portal URL: {html_url}",
        details={"portal_url": html_url, "requested_date": requested_date, "category": category}
    )
    page.goto(html_url, timeout=timeout_ms)

    # State validation 1: Root portal loaded
    if validate_state:
        validate_portal_loaded(page, timeout_ms=timeout_ms, logs=logs)

    # 1. Wait for calendar navigation tab
    log("Waiting for availability calendar tab locator (#tabCalendar)...")
    tab_calendar = page.locator("#tabCalendar")
    tab_calendar.wait_for(state="visible", timeout=timeout_ms)
    tab_calendar.click()

    # State validation 2: Calendar tab active and section visible
    log("Waiting for calendar section to become visible (#calendarSection)...")
    if validate_state:
        validate_calendar_tab_active(page, timeout_ms=timeout_ms, logs=logs)
    else:
        calendar_sec = page.locator("#calendarSection")
        calendar_sec.wait_for(state="visible", timeout=timeout_ms)

    # 3. Enter requested date if supplied
    if requested_date:
        log(f"Setting requested yatra date: {requested_date}")
        date_input = page.locator("#calendarDate")
        date_input.wait_for(state="visible", timeout=timeout_ms)
        date_input.fill(requested_date)
        if validate_state:
            validate_date_input_state(page, expected_date=requested_date, logs=logs)

    # 4. Select category filter if supplied
    if category:
        log(f"Setting category filter: {category}")
        cat_select = page.locator("#slotCategoryFilter")
        cat_select.select_option(value=category)
        if validate_state:
            validate_category_filter_state(page, expected_category=category, logs=logs)

    # 5. Trigger availability lookup
    log("Clicking Check Availability button (#btnCheckAvailability)...")
    check_btn = page.locator("#btnCheckAvailability")
    check_btn.click(timeout=timeout_ms)

    # 6 & 7. Dynamic element handling and readiness validation
    log("Waiting for dynamic loading indicator (#calendarLoading) to complete...")
    log("Waiting for slots container (#slotsContainer) to become visible...")
    if validate_state:
        readiness_status = validate_calendar_readiness(page, timeout_ms=timeout_ms, logs=logs)
        log(f"Calendar readiness state: {readiness_status}")
    else:
        page.wait_for_selector("#calendarLoading", state="hidden", timeout=timeout_ms)
        page.wait_for_selector("#slotsContainer", state="visible", timeout=timeout_ms)

    log("Availability calendar navigation completed successfully.")
    log_event(
        logging.INFO,
        "rpa_agent",
        "RPA_VALIDATION_COMPLETED",
        f"Calendar readiness and date/category validation completed successfully for date={requested_date}",
        details={"date": requested_date, "category": category}
    )


# ==============================================================================
# PHASE 3: EXTRACT SLOT AVAILABILITY DATA (WITH INTEGRITY VALIDATION)
# ==============================================================================

def extract_slot_availability(
    page,
    requested_date: Optional[str] = None,
    timeout_ms: int = 5000,
    logs: Optional[List[str]] = None,
    validate_integrity: bool = True
) -> Dict[str, Any]:
    """
    Extracts structured slot availability data from the rendered mock portal.
    Uses Playwright locators on .slot-card elements.
    Validates structural and business integrity constraints for each extracted slot.
    Distinguishes:
    - Empty calendar (#emptyCalendarNotice visible): returns is_empty=True, slots=[]
    - Error state (#calendarErrorNotice visible): returns status=ERROR
    - Successful extraction of available, full, and unavailable slots
    """
    def log(msg: str):
        if logs is not None:
            logs.append(msg)

    # Check for error notice
    error_notice = page.locator("#calendarErrorNotice")
    if error_notice.count() > 0 and error_notice.is_visible():
        err_msg = error_notice.inner_text().strip()
        log(f"Portal error state detected: {err_msg}")
        return {
            "status": "ERROR",
            "error": err_msg or "Unknown portal error",
            "date": requested_date,
            "total_slots": 0,
            "slots": [],
            "is_empty": False,
            "extracted_at": datetime.now().isoformat()
        }

    # Check for empty calendar notice
    empty_notice = page.locator("#emptyCalendarNotice")
    if empty_notice.count() > 0 and empty_notice.is_visible():
        log(f"Empty calendar notice visible for date {requested_date}.")
        return {
            "status": "SUCCESS",
            "date": requested_date,
            "total_slots": 0,
            "available_count": 0,
            "full_count": 0,
            "unavailable_count": 0,
            "slots": [],
            "is_empty": True,
            "extracted_at": datetime.now().isoformat()
        }

    # Extract slot cards via Playwright locators
    cards = page.locator(".slot-card").all()
    log(f"Locating rendered slot cards: found {len(cards)} elements.")

    extracted_slots: List[Dict[str, Any]] = []
    avail_count = 0
    full_count = 0
    unavail_count = 0

    for card in cards:
        slot_id_raw = card.get_attribute("data-slot-id")
        slot_id_text = card.locator(".slot-id").inner_text().strip() if card.locator(".slot-id").count() > 0 else (slot_id_raw or "UNKNOWN")

        yatra_date = card.get_attribute("data-date") or requested_date or ""
        slot_category = card.locator(".slot-category").inner_text().strip() if card.locator(".slot-category").count() > 0 else (card.get_attribute("data-category") or "General Darshan")
        slot_time = card.locator(".slot-time").inner_text().strip() if card.locator(".slot-time").count() > 0 else ""
        slot_session = card.locator(".slot-session").inner_text().strip() if card.locator(".slot-session").count() > 0 else ""

        # Status normalization: map to 'available', 'full', or 'unavailable'
        status_raw = (card.get_attribute("data-status") or "").lower()
        if not status_raw and card.locator(".slot-status").count() > 0:
            status_raw = card.locator(".slot-status").inner_text().strip().lower()

        if "avail" in status_raw and "unavail" not in status_raw:
            norm_status = "available"
            avail_count += 1
        elif "full" in status_raw or "booked" in status_raw or "sold" in status_raw:
            norm_status = "full"
            full_count += 1
        else:
            norm_status = "unavailable"
            unavail_count += 1

        # Capacity extraction
        capacity_val = card.get_attribute("data-capacity")
        if capacity_val is not None:
            try:
                capacity_int = int(capacity_val)
            except ValueError:
                capacity_int = None
        else:
            capacity_int = None

        # Price extraction
        price_val = card.get_attribute("data-price")
        if price_val is not None:
            try:
                price_float = float(price_val)
            except ValueError:
                price_float = 0.0
        else:
            price_float = 0.0

        slot_record = {
            "slot_id": slot_id_text,
            "yatra_date": yatra_date,
            "slot_name": slot_category,
            "time": slot_time,
            "session": slot_session,
            "availability_status": norm_status,
            "remaining_capacity": capacity_int,
            "price": price_float,
            "retrieved_at": datetime.now().isoformat()
        }

        # Week 6: State and data integrity validation
        if validate_integrity:
            validate_slot_record_integrity(slot_record)

        extracted_slots.append(slot_record)

    log_event(
        logging.INFO,
        "rpa_agent",
        "RPA_SLOT_EXTRACTION_COMPLETED",
        f"Extracted {len(extracted_slots)} slot records from mock portal",
        details={"total_slots": len(extracted_slots), "available": avail_count, "full": full_count, "unavailable": unavail_count}
    )

    return {
        "status": "SUCCESS",
        "date": requested_date or (extracted_slots[0]["yatra_date"] if extracted_slots else None),
        "total_slots": len(extracted_slots),
        "available_count": avail_count,
        "full_count": full_count,
        "unavailable_count": unavail_count,
        "slots": extracted_slots,
        "is_empty": len(extracted_slots) == 0,
        "extracted_at": datetime.now().isoformat()
    }


# ==============================================================================
# PHASE 4 & 5: END-TO-END AVAILABILITY RPA WORKFLOW (WITH ERROR RECOVERY)
# ==============================================================================

def check_yatra_slot_availability(
    requested_date: Optional[str] = "2026-10-20",
    category: Optional[str] = None,
    headless: bool = True,
    portal_html: Optional[str] = None,
    render_delay_ms: int = 200,
    timeout_ms: int = 10000,
    take_screenshot: bool = True,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.5,
    enable_retry: bool = True,
) -> Dict[str, Any]:
    """
    Automated Playwright RPA task with Week 6 error handling, retry-and-escalate,
    state validation, and pause-and-handover:
    1. Launches Chromium browser using project configuration.
    2. Opens local mock portal with availability calendar.
    3. Navigates to calendar, selects date, and triggers dynamic lookup with state validation.
    4. Executes bounded retries with backoff for recoverable errors.
    5. Detects structural DOM changes and data integrity violations, triggering safe human handover.
    6. Reliably closes browser resources via try...finally block.
    """
    temp_dir = tempfile.gettempdir()
    html_path = os.path.join(temp_dir, "yatra_mock_portal.html")
    screenshot_path = os.path.join(temp_dir, f"rpa_availability_{requested_date or 'default'}.png")

    html_content = portal_html if portal_html is not None else generate_mock_portal_html(render_delay_ms=render_delay_ms)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    html_url = f"file:///{html_path.replace(os.sep, '/')}"

    workflow_result: Dict[str, Any] = {
        "status": "FAILED",
        "date": requested_date,
        "category_filter": category,
        "total_slots": 0,
        "slots": [],
        "screenshot_path": None,
        "logs": [],
        "extracted_at": None,
        "handover_required": False,
        "retry_attempts_used": 1,
    }

    log_event(
        logging.INFO,
        "rpa_agent",
        "RPA_AVAILABILITY_CHECK_STARTED",
        f"RPA availability check started for date={requested_date}, category={category}",
        details={"requested_date": requested_date, "category": category, "headless": headless, "max_attempts": max_attempts}
    )

    try:
        with sync_playwright() as p:
            workflow_result["logs"].append("Launching Playwright Chromium browser instance...")
            log_event(
                logging.INFO,
                "rpa_agent",
                "RPA_BROWSER_INIT",
                "Playwright Chromium browser instance initialized",
                details={"headless": headless}
            )
            browser = p.chromium.launch(headless=headless)
            current_page = None
            attempts_made = 0
            try:
                page = browser.new_page()
                current_page = page

                def execute_flow(attempt_number: int):
                    nonlocal attempts_made
                    attempts_made = attempt_number
                    workflow_result["retry_attempts_used"] = attempt_number

                    # Phase 2: Navigation with explicit waits and state validation
                    navigate_to_availability_calendar(
                        page=page,
                        html_url=html_url,
                        requested_date=requested_date,
                        category=category,
                        timeout_ms=timeout_ms,
                        logs=workflow_result["logs"],
                        validate_state=True
                    )

                    # Phase 3: Structured slot extraction with integrity checks
                    workflow_result["logs"].append("Extracting structured slot records from page elements...")
                    return extract_slot_availability(
                        page=page,
                        requested_date=requested_date,
                        timeout_ms=timeout_ms,
                        logs=workflow_result["logs"],
                        validate_integrity=True
                    )

                if enable_retry:
                    extracted = retry_with_backoff(
                        action_callable=execute_flow,
                        operation_name="check_yatra_slot_availability",
                        max_attempts=max_attempts,
                        base_delay_seconds=base_delay_seconds,
                        logs=workflow_result["logs"]
                    )
                else:
                    extracted = execute_flow(1)

                workflow_result["status"] = extracted["status"]
                workflow_result["total_slots"] = extracted["total_slots"]
                workflow_result["available_count"] = extracted.get("available_count", 0)
                workflow_result["full_count"] = extracted.get("full_count", 0)
                workflow_result["unavailable_count"] = extracted.get("unavailable_count", 0)
                workflow_result["slots"] = extracted["slots"]
                workflow_result["is_empty"] = extracted.get("is_empty", False)
                workflow_result["extracted_at"] = extracted["extracted_at"]
                workflow_result["handover_required"] = False
                workflow_result["recovered"] = (attempts_made > 1)

                log_event(
                    logging.INFO,
                    "rpa_agent",
                    "RPA_WORKFLOW_COMPLETED",
                    f"RPA availability check completed successfully with {workflow_result['total_slots']} slots",
                    final_outcome="SUCCESS",
                    details={"date": requested_date, "total_slots": workflow_result["total_slots"], "attempts_used": attempts_made}
                )

                # Audit screenshot capture
                if take_screenshot:
                    try:
                        page.screenshot(path=screenshot_path)
                        workflow_result["screenshot_path"] = screenshot_path
                        workflow_result["logs"].append(f"Audit screenshot captured: {screenshot_path}")
                    except Exception as ss_err:
                        workflow_result["logs"].append(f"Warning: Audit screenshot failed: {str(ss_err)}")

            except Exception as exc:
                handover = create_handover_result(
                    error=exc,
                    failed_operation="check_yatra_slot_availability",
                    attempt_count=max(1, attempts_made),
                    page=current_page,
                    screenshot_path=screenshot_path if take_screenshot else None,
                    logs=workflow_result["logs"],
                    diagnostics={"requested_date": requested_date, "category": category}
                )
                workflow_result.update(handover)

            finally:
                # Guaranteed resource closure
                browser.close()
                workflow_result["logs"].append("Playwright browser instance closed cleanly.")

    except Exception as outer_exc:
        return create_handover_result(
            error=outer_exc,
            failed_operation="launch_browser",
            attempt_count=1,
            page=None,
            screenshot_path=None,
            logs=workflow_result.get("logs", []),
            diagnostics={"outer_error": str(outer_exc)}
        )

    return workflow_result


# ==============================================================================
# EXISTING WEEK 4 BOOKING EXECUTION (ENHANCED WITH SIDE-EFFECT SAFETY & STATE VALIDATION)
# ==============================================================================

def execute_playwright_mock_booking(
    user_name: str,
    pax_count: int,
    transport_text: str,
    slot_text: str,
    total_price: float,
    headless: bool = True
) -> dict:
    """
    Runs a Playwright RPA automation step against a temporary mock booking form page.
    Includes state validation before submitting and after confirmation.
    Side-effect safety: will NEVER re-submit a form automatically if confirmation times out,
    triggering human handover instead to prevent duplicate bookings.
    """
    temp_dir = tempfile.gettempdir()
    html_path = os.path.join(temp_dir, "yatra_mock_portal.html")
    screenshot_path = os.path.join(temp_dir, "rpa_booking_confirmation.png")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(MOCK_PORTAL_HTML)

    html_url = f"file:///{html_path.replace(os.sep, '/')}"

    rpa_result = {
        "status": "FAILED",
        "booking_id": None,
        "screenshot_path": None,
        "logs": [],
        "handover_required": False,
    }

    if not user_name or not str(user_name).strip():
        rpa_result["status"] = "VALIDATION_FAILED"
        rpa_result["error"] = "Pilgrim name is required and cannot be empty."
        rpa_result["error_category"] = "INVALID_PILGRIM_DETAILS"
        rpa_result["logs"].append("Validation error: Pilgrim name cannot be empty.")
        return rpa_result

    if pax_count is None or int(pax_count) <= 0:
        rpa_result["status"] = "VALIDATION_FAILED"
        rpa_result["error"] = f"Invalid passenger count ({pax_count}). Must be at least 1."
        rpa_result["error_category"] = "INVALID_PILGRIM_DETAILS"
        rpa_result["logs"].append("Validation error: Passenger count must be positive.")
        return rpa_result

    try:
        with sync_playwright() as p:
            rpa_result["logs"].append("Launching Playwright Chromium browser...")
            browser = p.chromium.launch(headless=headless)
            current_page = None
            try:
                page = browser.new_page()
                current_page = page

                rpa_result["logs"].append(f"Navigating to safe mock portal: {html_url}")
                page.goto(html_url)

                # State validation: verify booking form is loaded and ready
                validate_portal_loaded(page, logs=rpa_result["logs"])
                validate_booking_form_state(page, logs=rpa_result["logs"])

                # Fill passenger details via RPA selectors
                rpa_result["logs"].append("Filling pilgrim name and passenger count via RPA...")
                page.fill("#userName", user_name)
                page.fill("#paxCount", str(pax_count))
                page.fill("#transportInfo", transport_text)
                page.fill("#yatraSlot", slot_text)
                page.fill("#totalAmount", f"₹{total_price}")

                time.sleep(0.5)

                rpa_result["logs"].append("Submitting form via RPA trigger...")
                # Note: Booking submission causes a side-effect. We do NOT repeat this action on timeout.
                page.click("#submitBtn")

                if page.locator("#btnConfirmFinalBooking").count() > 0 and page.locator("#btnConfirmFinalBooking").is_visible():
                    rpa_result["logs"].append("Submitting simulated payment in sandbox...")
                    page.click("#btnConfirmFinalBooking")

                page.wait_for_selector("#confirmation", state="visible", timeout=5000)

                # State validation: confirm booking confirmation display and booking ID
                validate_booking_confirmation_state(page, logs=rpa_result["logs"])

                booking_id = page.text_content("#outBookingId")
                rpa_result["logs"].append(f"RPA Mock Booking completed successfully. Booking ID: {booking_id}")

                try:
                    page.screenshot(path=screenshot_path)
                    rpa_result["screenshot_path"] = screenshot_path
                except Exception as ss_err:
                    rpa_result["logs"].append(f"Warning: Screenshot failed: {str(ss_err)}")

                rpa_result["status"] = "SUCCESS"
                rpa_result["booking_id"] = booking_id

            except Exception as e:
                rpa_result["logs"].append(f"RPA execution error: {str(e)}")
                if rpa_result.get("booking_id"):
                    # Scenario 16: Cleanup/post-confirmation warning does not overwrite confirmed booking ID
                    rpa_result["logs"].append("Booking was confirmed; preserving booking ID despite cleanup/post-confirmation warning.")
                else:
                    # Handover result to prevent ambiguous re-submission of booking!
                    handover = create_handover_result(
                        error=e,
                        failed_operation="execute_playwright_mock_booking",
                        attempt_count=1,
                        page=current_page,
                        screenshot_path=screenshot_path,
                        logs=rpa_result["logs"],
                        diagnostics={"user_name": user_name, "pax_count": pax_count, "side_effect_prevented": True}
                    )
                    rpa_result.update(handover)
            finally:
                try:
                    browser.close()
                    rpa_result["logs"].append("Playwright browser instance closed cleanly.")
                except Exception as close_err:
                    rpa_result["logs"].append(f"Warning: Browser close cleanup: {close_err}")

    except Exception as e:
        rpa_result["logs"].append(f"RPA execution error: {str(e)}")
        rpa_result["error"] = str(e)
        rpa_result["handover_required"] = True
        rpa_result["error_category"] = "SYSTEM_ERROR"

    return rpa_result


# ==============================================================================
# WEEK 8: USER-CONTROLLED WORKFLOW & HUMAN-IN-THE-LOOP CHECKPOINT AUTOMATION
# ==============================================================================

def detect_security_checkpoint(
    page,
    timeout_ms: int = 1500,
    logs: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Week 8: Checks whether browser execution has reached a security-sensitive checkpoint.
    Detects OTP verification gates or CAPTCHA challenge prompts on the page.
    Returns checkpoint descriptor dictionary or None if page is in normal workflow.
    """
    def log(msg: str):
        if logs is not None:
            logs.append(msg)

    try:
        # Check OTP checkpoint
        otp_loc = page.locator("#otpChallengeSection")
        if otp_loc.count() > 0 and otp_loc.is_visible():
            badge_text = ""
            if page.locator("#otpStatusBadge").count() > 0:
                badge_text = page.locator("#otpStatusBadge").inner_text().strip()
            if badge_text != "VERIFIED":
                log("Security checkpoint detected: One-Time Password (OTP) verification required.")
                return {
                    "checkpoint_type": session_store.WORKFLOW_STATE_OTP_REQUIRED,
                    "selector": "#otpChallengeSection",
                    "status": session_store.WORKFLOW_STATE_WAITING_FOR_USER,
                    "message": "One-Time Password (OTP) verification required on authorized booking portal. Pilgrim must input OTP directly.",
                    "pending_action": "ENTER_OTP_IN_PORTAL",
                }

        # Check CAPTCHA checkpoint
        captcha_loc = page.locator("#captchaChallengeSection")
        if captcha_loc.count() > 0 and captcha_loc.is_visible():
            badge_text = ""
            if page.locator("#captchaStatusBadge").count() > 0:
                badge_text = page.locator("#captchaStatusBadge").inner_text().strip()
            if badge_text != "SOLVED":
                log("Security checkpoint detected: CAPTCHA challenge required.")
                return {
                    "checkpoint_type": session_store.WORKFLOW_STATE_CAPTCHA_REQUIRED,
                    "selector": "#captchaChallengeSection",
                    "status": session_store.WORKFLOW_STATE_WAITING_FOR_USER,
                    "message": "Manual CAPTCHA challenge required on booking portal. Automation is strictly prohibited from solving CAPTCHA.",
                    "pending_action": "SOLVE_CAPTCHA_IN_PORTAL",
                }
    except Exception as exc:
        log(f"Warning during checkpoint detection: {str(exc)}")

    return None


def validate_checkpoint_cleared(
    page,
    checkpoint_type: str,
    logs: Optional[List[str]] = None,
) -> bool:
    """
    Week 8: Validates that the manual intervention checkpoint was genuinely completed by the user.
    """
    def log(msg: str):
        if logs is not None:
            logs.append(msg)

    try:
        # If already confirmed, it is cleared
        if page.locator("#confirmation").count() > 0 and page.locator("#confirmation").is_visible():
            log("Checkpoint cleared: confirmation display is visible.")
            return True

        if checkpoint_type == session_store.WORKFLOW_STATE_OTP_REQUIRED:
            if page.locator("#otpStatusBadge").count() > 0:
                badge = page.locator("#otpStatusBadge").inner_text().strip()
                if badge == "VERIFIED":
                    log("Validated OTP checkpoint cleared.")
                    return True
            return False

        if checkpoint_type == session_store.WORKFLOW_STATE_CAPTCHA_REQUIRED:
            if page.locator("#captchaStatusBadge").count() > 0:
                badge = page.locator("#captchaStatusBadge").inner_text().strip()
                if badge == "SOLVED":
                    log("Validated CAPTCHA checkpoint cleared.")
                    return True
            return False
    except Exception as exc:
        log(f"Warning during checkpoint clearance validation: {str(exc)}")

    return False


def execute_user_controlled_booking_workflow(
    session_id: str,
    workflow_id: Optional[str] = None,
    user_name: str = "Pilgrim",
    pax_count: int = 1,
    transport_text: str = "Train (Vande Bharat Express)",
    slot_text: str = "Morning Aarti & Darshan (06:00)",
    total_price: float = 0.0,
    checkpoint_mode: Optional[str] = None,
    user_confirmed_action: bool = False,
    headless: bool = True,
    manual_input_value: Optional[str] = None,
    simulate_manual_clearance: bool = False,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Week 8: Orchestrates human-in-the-loop, user-controlled RPA booking workflow.

    Phases:
    1. INITIATION (workflow_id is None):
       - Automates initial navigation and input form filling.
       - Stops immediately upon reaching an OTP or CAPTCHA checkpoint.
       - Records paused workflow in SQLite session store with bounded expiration.
       - Returns PAUSED envelope without blocking the FastAPI process thread.

    2. RESUMPTION (workflow_id provided):
       - Strictly requires user_confirmed_action == True.
       - Retrieves persisted workflow from SQLite with cross-session isolation.
       - Enforces non-expiration and non-cancellation invariants.
       - Validates browser/DOM state to confirm manual action completed.
       - Resumes to final confirmation and records USER_ACTION_COMPLETED.
       - Guarantees: never automatically retries payment/booking or CAPTCHA solving.
    """
    logs: List[str] = []
    temp_dir = tempfile.gettempdir()
    html_path = os.path.join(temp_dir, "yatra_mock_portal.html")
    screenshot_dir = os.path.join(temp_dir, "rpa_screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)

    # -------------------------------------------------------------------------
    # PHASE 1: INITIATION & CHECKPOINT DETECTION
    # -------------------------------------------------------------------------
    if not workflow_id:
        if not user_name or not str(user_name).strip():
            return {
                "status": "VALIDATION_FAILED",
                "error_category": "INVALID_PILGRIM_DETAILS",
                "message": "Pilgrim name is required and cannot be empty.",
                "logs": ["Validation error: Pilgrim name cannot be empty."]
            }
        if pax_count is None or int(pax_count) <= 0:
            return {
                "status": "VALIDATION_FAILED",
                "error_category": "INVALID_PILGRIM_DETAILS",
                "message": f"Invalid passenger count ({pax_count}). Must be at least 1.",
                "logs": ["Validation error: Passenger count must be positive."]
            }

        logs.append(f"Starting user-controlled RPA workflow for session: {session_id}")
        sec_mode = (checkpoint_mode or "").upper().strip()
        html_content = generate_mock_portal_html(security_mode=sec_mode)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        html_url = f"file:///{html_path.replace(os.sep, '/')}"

        # If a checkpoint is configured (OTP, CAPTCHA, or SEQUENTIAL), automate to the checkpoint and PAUSE
        if sec_mode in ("OTP", "CAPTCHA", "SEQUENTIAL", "BOTH"):
            expected_state = (
                session_store.WORKFLOW_STATE_OTP_REQUIRED
                if sec_mode in ("OTP", "SEQUENTIAL", "BOTH")
                else session_store.WORKFLOW_STATE_CAPTCHA_REQUIRED
            )
            pending_act = (
                "ENTER_OTP_IN_PORTAL"
                if sec_mode in ("OTP", "SEQUENTIAL", "BOTH")
                else "SOLVE_CAPTCHA_IN_PORTAL"
            )
            checkpoint_ss_path = os.path.join(screenshot_dir, f"checkpoint_{sec_mode.lower()}.png")

            try:
                with sync_playwright() as p:
                    logs.append("Launching Playwright Chromium browser for initiation...")
                    browser = p.chromium.launch(headless=headless)
                    try:
                        page = browser.new_page()
                        logs.append(f"Navigating to mock portal: {html_url}")
                        page.goto(html_url)

                        validate_portal_loaded(page, logs=logs)
                        validate_booking_form_state(page, logs=logs)

                        logs.append("Filling booking details prior to security checkpoint...")
                        page.fill("#userName", user_name)
                        page.fill("#paxCount", str(pax_count))
                        page.fill("#transportInfo", transport_text)
                        page.fill("#yatraSlot", slot_text)
                        page.fill("#totalAmount", f"₹{total_price}")

                        time.sleep(0.3)
                        logs.append("Submitting form to reach security verification gate...")
                        page.click("#submitBtn")

                        time.sleep(0.3)
                        # Detect checkpoint
                        cp = detect_security_checkpoint(page, logs=logs)
                        if not cp:
                            raise StateValidationError(
                                "Expected security checkpoint was not displayed.",
                                operation="detect_security_checkpoint",
                                expected_state=expected_state,
                                actual_state="normal_flow",
                            )

                        try:
                            page.screenshot(path=checkpoint_ss_path)
                            logs.append(f"Checkpoint screenshot captured: {checkpoint_ss_path}")
                        except Exception:
                            pass

                        # Persist workflow in SQLite session store (STRIPS sensitive data)
                        safe_cp_data = {
                            "user_name": user_name,
                            "pax_count": pax_count,
                            "transport_text": transport_text,
                            "slot_text": slot_text,
                            "total_price": total_price,
                            "checkpoint_mode": sec_mode,
                            "portal_url": html_url,
                            "screenshot_path": checkpoint_ss_path,
                        }

                        wf = session_store.create_user_workflow(
                            session_id=session_id,
                            state=expected_state,
                            step="security_checkpoint",
                            operation="yatra_mock_booking",
                            pending_action=pending_act,
                            expires_in_seconds=300,
                            checkpoint_data=safe_cp_data,
                            db_path=db_path,
                        )

                        logs.append(f"Automation paused safely at checkpoint. Workflow ID: {wf['workflow_id']}")
                        log_event(
                            logging.INFO,
                            "rpa_agent",
                            "RPA_WORKFLOW_PAUSED",
                            f"Workflow paused at security checkpoint ({sec_mode}). Human intervention required.",
                            workflow_state=expected_state,
                            human_intervention_required=True,
                            details={"workflow_id": wf["workflow_id"], "session_id": session_id, "checkpoint_mode": sec_mode}
                        )

                        msg = (
                            "One-Time Password (OTP) verification required on authorized booking portal. "
                            "Please enter the OTP sent to your mobile directly into the portal. "
                            "Notice: Never provide OTPs to the AI chat."
                            if sec_mode == "OTP"
                            else "CAPTCHA challenge required on booking portal. "
                            "Please solve the visual CAPTCHA puzzle manually. "
                            "Notice: Automation is strictly prohibited from bypassing this challenge."
                        )

                        return {
                            "status": "PAUSED",
                            "workflow_id": wf["workflow_id"],
                            "session_id": session_id,
                            "state": wf["state"],
                            "step": wf["step"],
                            "pending_action": wf["pending_action"],
                            "expires_at": wf["expires_at"],
                            "screenshot_path": checkpoint_ss_path,
                            "message": msg,
                            "instructions": (
                                "1. Open the authorized booking portal window.\n"
                                "2. Enter the OTP code directly on the portal.\n"
                                "3. Confirm the action in the application to resume automation."
                                if sec_mode == "OTP"
                                else "1. Open the authorized booking portal window.\n"
                                "2. Solve the visual CAPTCHA challenge manually.\n"
                                "3. Confirm the action in the application to resume automation."
                            ),
                            "handover_required": False,
                            "logs": logs,
                        }
                    finally:
                        browser.close()
                        logs.append("Playwright browser instance closed cleanly during pause.")
            except Exception as e:
                logs.append(f"Error reaching security checkpoint: {str(e)}")
                handover = create_handover_result(
                    error=e,
                    failed_operation="execute_user_controlled_booking_initiation",
                    attempt_count=1,
                    page=None,
                    logs=logs,
                    diagnostics={"session_id": session_id, "checkpoint_mode": sec_mode},
                )
                return handover

        # Unchecked direct mock booking
        return execute_playwright_mock_booking(
            user_name=user_name,
            pax_count=pax_count,
            transport_text=transport_text,
            slot_text=slot_text,
            total_price=total_price,
            headless=headless,
        )

    # -------------------------------------------------------------------------
    # PHASE 2: RESUMPTION & STATE VALIDATION
    # -------------------------------------------------------------------------
    logs.append(f"Resuming user-controlled workflow: {workflow_id} for session: {session_id}")
    log_event(
        logging.INFO,
        "rpa_agent",
        "RPA_WORKFLOW_RESUMED",
        f"Workflow resumption triggered for {workflow_id} (session {session_id})",
        workflow_state="RESUMING",
        details={"workflow_id": workflow_id, "session_id": session_id}
    )

    # Invariant 1: Require explicit user confirmation
    if not user_confirmed_action:
        logs.append("Resumption blocked: user_confirmed_action is False.")
        return {
            "status": "REJECTED",
            "workflow_id": workflow_id,
            "session_id": session_id,
            "message": "Explicit user confirmation is strictly required to resume a paused workflow.",
            "error_category": "CONFIRMATION_REQUIRED",
            "logs": logs,
        }

    # Invariant 2: Retrieve workflow with cross-session isolation
    wf = session_store.get_user_workflow(workflow_id, session_id=session_id, db_path=db_path)
    if not wf:
        logs.append(f"Resumption blocked: workflow {workflow_id} not found or session mismatch.")
        return {
            "status": "ERROR",
            "workflow_id": workflow_id,
            "session_id": session_id,
            "message": "Workflow not found or session access denied (cross-session rejection).",
            "error_category": "CROSS_SESSION_ACCESS_DENIED",
            "logs": logs,
        }

    # Invariant 3: Check terminal states (EXPIRED or CANCELLED)
    if wf["state"] == session_store.WORKFLOW_STATE_EXPIRED:
        logs.append("Resumption blocked: workflow has expired.")
        return {
            "status": "EXPIRED",
            "workflow_id": workflow_id,
            "session_id": session_id,
            "state": session_store.WORKFLOW_STATE_EXPIRED,
            "message": "Workflow has expired due to inactivity. Cannot resume.",
            "error_category": "WORKFLOW_EXPIRED",
            "logs": logs,
        }

    if wf["state"] == session_store.WORKFLOW_STATE_CANCELLED:
        logs.append("Resumption blocked: workflow has been cancelled.")
        return {
            "status": "CANCELLED",
            "workflow_id": workflow_id,
            "session_id": session_id,
            "state": session_store.WORKFLOW_STATE_CANCELLED,
            "message": "Workflow has been cancelled. Cannot resume.",
            "error_category": "WORKFLOW_CANCELLED",
            "logs": logs,
        }

    if wf["state"] == session_store.WORKFLOW_STATE_USER_ACTION_COMPLETED:
        logs.append("Workflow has already completed. Returning existing booking confirmation (idempotent resume).")
        cp_data = wf.get("checkpoint_data", {})
        return {
            "status": "SUCCESS",
            "workflow_id": workflow_id,
            "session_id": session_id,
            "state": session_store.WORKFLOW_STATE_USER_ACTION_COMPLETED,
            "booking_id": cp_data.get("booking_id", "VD-CONFIRMED"),
            "screenshot_path": cp_data.get("confirmation_screenshot"),
            "message": f"User-controlled workflow completed successfully. Booking ID: {cp_data.get('booking_id', 'VD-CONFIRMED')}",
            "logs": logs,
            "is_idempotent_replay": True,
        }

    if wf["state"] not in session_store.RESUMABLE_STATES:
        logs.append(f"Resumption blocked: invalid state {wf['state']}.")
        return {
            "status": "INVALID_STATE",
            "workflow_id": workflow_id,
            "session_id": session_id,
            "state": wf["state"],
            "message": f"Workflow cannot be resumed from state: {wf['state']}",
            "logs": logs,
        }

    # Browser continuation and page state validation
    cp_data = wf.get("checkpoint_data", {})
    sec_mode = cp_data.get("checkpoint_mode", "OTP")
    html_url = cp_data.get("portal_url") or f"file:///{html_path.replace(os.sep, '/')}"
    conf_ss_path = os.path.join(screenshot_dir, f"confirmed_{workflow_id}.png")

    try:
        with sync_playwright() as p:
            logs.append("Launching Playwright Chromium browser for resumption validation...")
            browser = p.chromium.launch(headless=headless)
            current_page = None
            try:
                page = browser.new_page()
                current_page = page
                if wf["state"] == session_store.WORKFLOW_STATE_CAPTCHA_REQUIRED:
                    target_url = f"{html_url}{'&' if '?' in html_url else '?'}checkpoint=CAPTCHA"
                elif wf["state"] == session_store.WORKFLOW_STATE_OTP_REQUIRED:
                    target_url = f"{html_url}{'&' if '?' in html_url else '?'}checkpoint=OTP"
                else:
                    target_url = html_url
                logs.append(f"Navigating to mock portal to validate checkpoint clearance: {target_url}")
                page.goto(target_url)

                validate_portal_loaded(page, logs=logs)

                # Recreate checkpoint state if new page loaded
                if page.locator("#bookingForm").is_visible():
                    page.fill("#userName", str(cp_data.get("user_name", user_name)))
                    page.fill("#paxCount", str(cp_data.get("pax_count", pax_count)))
                    page.fill("#transportInfo", str(cp_data.get("transport_text", transport_text)))
                    page.fill("#yatraSlot", str(cp_data.get("slot_text", slot_text)))
                    page.fill("#totalAmount", str(cp_data.get("total_price", total_price)))
                    page.click("#submitBtn")
                    time.sleep(0.3)

                # Check if manual input was provided or simulated
                if manual_input_value:
                    if page.locator("#userOtpInput").count() > 0 and page.locator("#userOtpInput").is_visible():
                        logs.append("Simulating manual pilgrim OTP entry in authorized portal...")
                        page.fill("#userOtpInput", manual_input_value)
                        page.click("#btnVerifyOtp")
                    elif page.locator("#userCaptchaInput").count() > 0 and page.locator("#userCaptchaInput").is_visible():
                        logs.append("Simulating manual pilgrim CAPTCHA resolution in authorized portal...")
                        page.fill("#userCaptchaInput", manual_input_value)
                        page.click("#btnVerifyCaptcha")
                    time.sleep(0.3)
                elif simulate_manual_clearance:
                    if page.locator("#userOtpInput").count() > 0 and page.locator("#userOtpInput").is_visible():
                        page.fill("#userOtpInput", "123456")
                        page.click("#btnVerifyOtp")
                    elif page.locator("#userCaptchaInput").count() > 0 and page.locator("#userCaptchaInput").is_visible():
                        page.fill("#userCaptchaInput", "M7K9P")
                        page.click("#btnVerifyCaptcha")
                    time.sleep(0.3)

                # State validation: verify checkpoint has been cleared
                cleared = validate_checkpoint_cleared(page, wf["state"], logs=logs)
                if not cleared:
                    logs.append("State validation failed: Checkpoint has NOT been cleared on the portal.")
                    log_event(
                        logging.WARNING,
                        "rpa_agent",
                        "RPA_VALIDATION_FAILED",
                        f"State validation failed during workflow resumption: checkpoint not cleared",
                        workflow_state=wf["state"],
                        error_category="VALIDATION_FAILED",
                        human_intervention_required=True,
                        details={"workflow_id": workflow_id}
                    )
                    return {
                        "status": "VALIDATION_FAILED",
                        "workflow_id": workflow_id,
                        "session_id": session_id,
                        "state": wf["state"],
                        "message": "Manual action verification failed: Checkpoint has not been cleared in the portal. Please perform the manual action first.",
                        "logs": logs,
                    }

                # Complete current checkpoint verification
                if sec_mode in ("OTP", "SEQUENTIAL", "BOTH") and page.locator("#btnCompleteOtpVerification").is_visible():
                    page.click("#btnCompleteOtpVerification")
                    time.sleep(0.3)
                elif sec_mode == "CAPTCHA" and page.locator("#btnCompleteCaptchaVerification").is_visible():
                    page.click("#btnCompleteCaptchaVerification")
                    time.sleep(0.3)

                # Check if page transitioned to a secondary checkpoint (e.g. CAPTCHA in SEQUENTIAL mode)
                seq_cp = detect_security_checkpoint(page, logs=logs)
                if seq_cp:
                    logs.append(f"Sequential security checkpoint reached: {seq_cp['checkpoint_type']}. Pausing for human intervention.")
                    seq_state = seq_cp["checkpoint_type"]
                    seq_pending = seq_cp.get("pending_action", "SOLVE_CAPTCHA_IN_PORTAL")
                    seq_ss_path = os.path.join(screenshot_dir, f"checkpoint_{seq_state.lower()}_{workflow_id}.png")
                    try:
                        page.screenshot(path=seq_ss_path)
                    except Exception:
                        pass

                    session_store.update_user_workflow(
                        workflow_id=workflow_id,
                        session_id=session_id,
                        state=seq_state,
                        step="captcha_checkpoint",
                        pending_action=seq_pending,
                        checkpoint_data=dict(cp_data, checkpoint_mode="CAPTCHA", portal_url=f"{html_url}{'&' if '?' in html_url else '?'}checkpoint=CAPTCHA", screenshot_path=seq_ss_path),
                        db_path=db_path,
                    )

                    return {
                        "status": "PAUSED",
                        "workflow_id": workflow_id,
                        "session_id": session_id,
                        "state": seq_state,
                        "step": "captcha_checkpoint",
                        "pending_action": seq_pending,
                        "screenshot_path": seq_ss_path,
                        "message": "OTP verification completed. Manual CAPTCHA challenge is now required on the booking portal.",
                        "instructions": (
                            "1. Enter the visual CAPTCHA code shown in the portal.\n"
                            "2. Confirm the action to proceed to the payment sandbox."
                        ),
                        "handover_required": False,
                        "logs": logs,
                    }

                if page.locator("#btnConfirmFinalBooking").count() > 0 and page.locator("#btnConfirmFinalBooking").is_visible():
                    logs.append("Submitting simulated payment in sandbox...")
                    page.click("#btnConfirmFinalBooking")

                page.wait_for_selector("#confirmation", state="visible", timeout=5000)
                validate_booking_confirmation_state(page, logs=logs)

                booking_id = page.text_content("#outBookingId")
                logs.append(f"User-controlled booking confirmed successfully! Booking ID: {booking_id}")
                log_event(
                    logging.INFO,
                    "rpa_agent",
                    "RPA_WORKFLOW_COMPLETED",
                    f"User-controlled booking confirmed successfully. Booking ID: {booking_id}",
                    workflow_state=session_store.WORKFLOW_STATE_USER_ACTION_COMPLETED,
                    final_outcome="SUCCESS",
                    details={"workflow_id": workflow_id, "booking_id": booking_id}
                )

                try:
                    page.screenshot(path=conf_ss_path)
                except Exception:
                    pass

                # Update workflow state in SQLite
                session_store.update_user_workflow(
                    workflow_id=workflow_id,
                    session_id=session_id,
                    state=session_store.WORKFLOW_STATE_USER_ACTION_COMPLETED,
                    step="booking_confirmed",
                    pending_action="NONE",
                    checkpoint_data={"booking_id": booking_id, "confirmation_screenshot": conf_ss_path},
                    db_path=db_path,
                )

                return {
                    "status": "SUCCESS",
                    "workflow_id": workflow_id,
                    "session_id": session_id,
                    "state": session_store.WORKFLOW_STATE_USER_ACTION_COMPLETED,
                    "booking_id": booking_id,
                    "screenshot_path": conf_ss_path,
                    "message": f"User-controlled workflow completed successfully. Booking ID: {booking_id}",
                    "logs": logs,
                }
            except Exception as exc:
                logs.append(f"Browser continuation error: {str(exc)}")
                if 'booking_id' in locals() and booking_id:
                    logs.append("Booking was confirmed; preserving booking ID despite cleanup/post-confirmation warning.")
                    return {
                        "status": "SUCCESS",
                        "workflow_id": workflow_id,
                        "session_id": session_id,
                        "state": session_store.WORKFLOW_STATE_USER_ACTION_COMPLETED,
                        "booking_id": booking_id,
                        "screenshot_path": conf_ss_path,
                        "message": f"User-controlled workflow completed successfully. Booking ID: {booking_id}",
                        "logs": logs,
                    }
                handover = create_handover_result(
                    error=exc,
                    failed_operation="execute_user_controlled_booking_resumption",
                    attempt_count=1,
                    page=current_page,
                    screenshot_path=conf_ss_path,
                    logs=logs,
                    diagnostics={"workflow_id": workflow_id, "session_id": session_id},
                )
                return handover
            finally:
                try:
                    browser.close()
                    logs.append("Playwright browser instance closed cleanly.")
                except Exception as close_err:
                    logs.append(f"Warning: Browser close cleanup: {close_err}")
    except Exception as exc:
        logs.append(f"Resumption system error: {str(exc)}")
        return {
            "status": "HANDOVER_REQUIRED",
            "workflow_id": workflow_id,
            "session_id": session_id,
            "error": str(exc),
            "handover_required": True,
            "message": f"Browser process encountered an error: {str(exc)}. Please restart the booking manually.",
            "logs": logs,
        }

