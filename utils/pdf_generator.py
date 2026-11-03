"""
utils/pdf_generator.py
Lightweight, zero-dependency PDF 1.4 document generator for Demo Pilgrim Yatra Passes.

Generates valid, well-formed PDF binary payloads containing:
- Prominent Shrine Board Demo Header
- Required Disclaimer: DEMO — LOCAL MOCK PORTAL — NOT AN OFFICIAL SHRINE BOARD BOOKING
- Unique Booking Reference ID
- Pilgrim particulars, darshan slot, transport, accommodation, and simulated payment notice
- RFID check-in instructions and traditional blessing
"""

from typing import Dict, Any


def escape_pdf_text(text: Any) -> str:
    """Escapes special characters in PDF literal text strings."""
    if text is None:
        return ""
    s = str(text)
    # Replace non-ascii chars with clean ascii representation for standard Type1 Helvetica
    s = s.replace("₹", "INR ").replace("➔", "->").replace("✓", "[X]").replace("🙏", "")
    s = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return s.encode("ascii", "replace").decode("ascii")


def generate_pdf_pass_bytes(booking: Dict[str, Any]) -> bytes:
    """
    Builds a clean, single-page PDF 1.4 document matching the exact pilgrim pass details.
    Returns raw bytes suitable for HTTP response or file writing.
    """
    bid = escape_pdf_text(booking.get("booking_id") or "VD-DEMO-000000")
    user_name = escape_pdf_text(booking.get("user_name") or "Guest Pilgrim")
    pax = escape_pdf_text(booking.get("pax_count") or 1)
    slot_date = escape_pdf_text(booking.get("slot_date") or "2026-10-20")
    category = escape_pdf_text(booking.get("category") or "Normal Darshan")
    slot_time = escape_pdf_text(booking.get("slot_time") or "Morning Slot (06:00)")
    transport = escape_pdf_text(booking.get("transport_info") or booking.get("transport_mode") or "Train (Delhi -> Katra)")
    hotel = escape_pdf_text(booking.get("hotel_name") or "Devi Darshan Hotel (Katra)")
    total_price = escape_pdf_text(f"INR {booking.get('total_price', 0):,}")

    stream_lines = [
        "BT",
        "/F1 18 Tf 50 740 Td (SHRI MATA VAISHNO DEVI SHRINE - PILGRIM YATRA PASS) Tj",
        "/F2 9 Tf 0 -20 Td (DEMO -- LOCAL MOCK PORTAL -- NOT AN OFFICIAL SHRINE BOARD BOOKING) Tj",
        "/F1 13 Tf 0 -35 Td (OFFICIAL BOOKING REFERENCE: " + bid + ") Tj",
        "/F2 10 Tf 0 -22 Td (Status: SIMULATED / CONFIRMED   |   Security: OTP Verified [X] & CAPTCHA Solved [X]) Tj",
        "/F1 11 Tf 0 -30 Td (PILGRIM & DARSHAN PARTICULARS:) Tj",
        "/F2 10 Tf 0 -18 Td (Primary Devotee: " + user_name + "     Total Devotees: " + pax + " Pilgrim(s)) Tj",
        "/F2 10 Tf 0 -18 Td (Darshan Date: " + slot_date + "     Category: " + category + ") Tj",
        "/F2 10 Tf 0 -18 Td (Darshan Slot: " + slot_time + "     Reporting: Banganga / Katra Counter) Tj",
        "/F1 11 Tf 0 -28 Td (CONFIRMED LOGISTICS & ACCOMMODATION:) Tj",
        "/F2 10 Tf 0 -18 Td (Travel Service: " + transport + ") Tj",
        "/F2 10 Tf 0 -18 Td (Accommodation: " + hotel + ") Tj",
        "/F2 10 Tf 0 -18 Td (Simulated Amount: " + total_price + " [Sandbox Mode - INR 0 Live Bank Charge]) Tj",
        "/F1 11 Tf 0 -30 Td (IMPORTANT PILGRIMAGE INSTRUCTIONS:) Tj",
        "/F2 9 Tf 0 -16 Td (1. Present this reference at Katra Main Registration Counter to collect RFID Access Cards.) Tj",
        "/F2 9 Tf 0 -14 Td (2. All devotees must carry valid government photo identification during Yatra.) Tj",
        "/F2 9 Tf 0 -14 Td (3. Track darshan timings closely. Helicopter and battery cars require queue clearance.) Tj",
        "/F2 9 Tf 0 -25 Td (DEMO SIMULATION NOTICE: Generated via Automated Playwright RPA Workflow sandbox.) Tj",
        "/F1 11 Tf 0 -25 Td (Jai Mata Di! May Maa Vaishno Devi bless you and your family with peace and happiness.) Tj",
        "ET",
    ]
    stream_content = "\n".join(stream_lines) + "\n"
    stream_len = len(stream_content.encode("latin1"))

    lines = [
        "%PDF-1.4",
        "1 0 obj",
        "<< /Type /Catalog /Pages 2 0 R >>",
        "endobj",
        "2 0 obj",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "endobj",
        "3 0 obj",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
        "endobj",
        "4 0 obj",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        "endobj",
        "5 0 obj",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        "endobj",
        "6 0 obj",
        f"<< /Length {stream_len} >>",
        "stream",
        stream_content + "endstream",
        "endobj",
    ]

    body = "\n".join(lines) + "\n"
    body_bytes = body.encode("latin1")

    offsets = [0]
    for obj_idx in range(1, 7):
        target = f"{obj_idx} 0 obj".encode("latin1")
        offsets.append(body_bytes.find(target))

    xref_lines = [f"xref\n0 7\n0000000000 65535 f "]
    for off in offsets[1:]:
        xref_lines.append(f"{off:010d} 00000 n ")

    xref_str = "\n".join(xref_lines) + "\n"
    xref_pos = len(body_bytes)
    trailer = f"trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"

    return body_bytes + xref_str.encode("latin1") + trailer.encode("latin1")
