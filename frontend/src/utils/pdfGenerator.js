/**
 * frontend/src/utils/pdfGenerator.js
 * Generates an authentic, standards-compliant PDF 1.4 file for Demo Pilgrim Yatra Passes
 * without any external npm dependencies.
 */

export function generatePilgrimPassPDF(bookingData, bookingSummary = {}) {
  const tr = bookingSummary?.option?.transport || bookingSummary?.option?.flight || {};
  const slot = bookingSummary?.option?.slot || {};
  const hotel = bookingSummary?.hotel;

  const bid = String(bookingData?.booking_id || 'VD-RPA-DEMO').replace(/[^\w-]/g, '');
  const userName = String(bookingData?.user_name || bookingData?.email || 'Registered Pilgrim Devotee');
  const pax = String(bookingData?.pax_count || bookingSummary?.pax || 1);
  const slotDate = String(bookingData?.slot_date || slot.slot_date || '2026-10-20');
  const category = String(bookingData?.category || slot.category || 'Normal Darshan');
  const slotTime = String(bookingData?.slot_time || slot.slot_time || 'Morning Slot (06:00)');
  const origin = bookingSummary?.origin || 'Delhi';
  const transport = String(bookingData?.transport_info || `${tr.operator || tr.name || 'Express Service'} (${tr.mode || 'Train'}) from ${origin}`);
  const hotelName = String(bookingData?.hotel_name || (hotel ? hotel.name : 'Devi Darshan Hotel, Katra'));
  const priceVal = bookingData?.total_price || bookingSummary?.total_price || 16092;
  const totalPrice = `INR ${Number(priceVal).toLocaleString('en-IN')}`;

  const escapePdf = (str) => {
    return String(str || '')
      .replace(/₹/g, 'INR ')
      .replace(/➔/g, '->')
      .replace(/✓/g, '[X]')
      .replace(/🙏/g, '')
      .replace(/\\/g, '\\\\')
      .replace(/\(/g, '\\(')
      .replace(/\)/g, '\\)');
  };

  const streamLines = [
    'BT',
    '/F1 18 Tf 50 740 Td (SHRI MATA VAISHNO DEVI SHRINE - PILGRIM YATRA PASS) Tj',
    '/F2 9 Tf 0 -20 Td (DEMO -- LOCAL MOCK PORTAL -- NOT AN OFFICIAL SHRINE BOARD BOOKING) Tj',
    `/F1 13 Tf 0 -35 Td (OFFICIAL BOOKING REFERENCE: ${escapePdf(bid)}) Tj`,
    '/F2 10 Tf 0 -22 Td (Status: SIMULATED / CONFIRMED   |   Security: OTP Verified [X] & CAPTCHA Solved [X]) Tj',
    '/F1 11 Tf 0 -30 Td (PILGRIM & DARSHAN PARTICULARS:) Tj',
    `/F2 10 Tf 0 -18 Td (Primary Devotee: ${escapePdf(userName)}     Total Devotees: ${escapePdf(pax)} Pilgrim(s)) Tj`,
    `/F2 10 Tf 0 -18 Td (Darshan Date: ${escapePdf(slotDate)}     Category: ${escapePdf(category)}) Tj`,
    `/F2 10 Tf 0 -18 Td (Darshan Slot: ${escapePdf(slotTime)}     Reporting: Banganga / Katra Counter) Tj`,
    '/F1 11 Tf 0 -28 Td (CONFIRMED LOGISTICS & ACCOMMODATION:) Tj',
    `/F2 10 Tf 0 -18 Td (Travel Service: ${escapePdf(transport)}) Tj`,
    `/F2 10 Tf 0 -18 Td (Accommodation: ${escapePdf(hotelName)}) Tj`,
    `/F2 10 Tf 0 -18 Td (Simulated Amount: ${escapePdf(totalPrice)} [Sandbox Mode - INR 0 Live Bank Charge]) Tj`,
    '/F1 11 Tf 0 -30 Td (IMPORTANT PILGRIMAGE INSTRUCTIONS:) Tj',
    '/F2 9 Tf 0 -16 Td (1. Present this reference at Katra Main Registration Counter to collect RFID Access Cards.) Tj',
    '/F2 9 Tf 0 -14 Td (2. All devotees must carry valid government photo identification during Yatra.) Tj',
    '/F2 9 Tf 0 -14 Td (3. Track darshan timings closely. Helicopter and battery cars require queue clearance.) Tj',
    '/F2 9 Tf 0 -25 Td (DEMO SIMULATION NOTICE: Generated via Automated Playwright RPA Workflow sandbox.) Tj',
    '/F1 11 Tf 0 -25 Td (Jai Mata Di! May Maa Vaishno Devi bless you and your family with peace and happiness.) Tj',
    'ET',
  ];

  const streamContent = streamLines.join('\n') + '\n';
  const streamLen = streamContent.length;

  const lines = [
    '%PDF-1.4',
    '1 0 obj',
    '<< /Type /Catalog /Pages 2 0 R >>',
    'endobj',
    '2 0 obj',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    'endobj',
    '3 0 obj',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>',
    'endobj',
    '4 0 obj',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>',
    'endobj',
    '5 0 obj',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    'endobj',
    '6 0 obj',
    `<< /Length ${streamLen} >>`,
    'stream',
    `${streamContent}endstream`,
    'endobj',
  ];

  const body = lines.join('\n') + '\n';

  const offsets = [0];
  for (let i = 1; i <= 6; i++) {
    offsets.push(body.indexOf(`${i} 0 obj`));
  }

  let xref = 'xref\n0 7\n0000000000 65535 f \n';
  for (let i = 1; i <= 6; i++) {
    const offStr = String(offsets[i]).padStart(10, '0');
    xref += `${offStr} 00000 n \n`;
  }

  const xrefPos = body.length;
  const trailer = `trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n${xrefPos}\n%%EOF\n`;
  const pdfString = body + xref + trailer;

  const buffer = new Uint8Array(pdfString.length);
  for (let i = 0; i < pdfString.length; i++) {
    buffer[i] = pdfString.charCodeAt(i) & 0xff;
  }

  const blob = new Blob([buffer], { type: 'application/pdf' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `Pilgrim_Pass_${bid}.pdf`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
