"""
agents/budget_engine.py
Deterministic cost calculation and budget evaluation engine for Vaishno Devi Yatra planning.

Strictly adheres to verified prototype dataset pricing semantics:
1. Transport:
   - Price in dataset is per passenger, per one-way leg.
   - Outbound and return legs are evaluated independently when both are provided.
   - Return fares are never silently fabricated or doubled into verified costs.
     If a round trip is requested but no return transport is verified, the return leg is
     either represented as a clearly labeled estimate or flagged as an incomplete requirement.
2. Darshan slots:
   - Price is per passenger (Normal=₹0, VIP=₹500, Helicopter=₹4640).
   - Only canonically free Normal Darshan or explicit positive numeric prices are verified.
3. Accommodation:
   - Price in dataset is per room, per night (price_per_night).
   - Rooms required: configurable via pax_per_room (default 2 guests/room, unless specified).
   - Nights: calculated strictly from valid check_in_date and check_out_date.
   - Invalid dates (e.g. check_out <= check_in) or missing dates are never silently guessed.
   - Room shortages (rooms_available < rooms_needed) are explicitly flagged and prevent
     the hotel from being marked as a complete/confirmed selection.
4. Estimated costs:
   - Road transfers, local Katra taxis, meals, and estimated return fares are strictly
     segregated into estimated_costs and clearly disclosed as non-dataset estimates.
5. Excluded costs:
   - Pony/palki, offerings, and shopping are listed separately and never added to totals.
6. Budget evaluation:
   - When required costs are incomplete or invalid, within_budget is NOT reported as definitive.
   - Uses Decimal arithmetic throughout to eliminate floating point rounding inaccuracies.
"""

import math
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple, Union


# Standard list of excluded pilgrimage expenses
EXCLUDED_EXPENSES: List[str] = [
    "Pony / Palki / Electric vehicle charges on the 13 km trek",
    "Personal ritual offerings, prasad, and private pooja",
    "Personal shopping, dry fruits, and Katra market souvenirs",
    "Incidental state monument or museum entry fees outside Katra base",
]


def _to_decimal(val: Union[int, float, str, Decimal, None]) -> Optional[Decimal]:
    """Safely converts input number to Decimal with 2 decimal places."""
    if val is None:
        return None
    try:
        return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def calculate_rooms_required(pax: int, pax_per_room: int = 2) -> int:
    """
    Calculates the number of rooms required for a given passenger count.
    Default capacity assumption is 2 persons per room unless otherwise configured.
    """
    if pax <= 0:
        return 1
    pax_cap = max(1, pax_per_room)
    return math.ceil(pax / pax_cap)


def calculate_hotel_nights(
    check_in_date: Optional[str] = None,
    check_out_date: Optional[str] = None,
    duration_days: Optional[int] = None,
) -> Tuple[Optional[int], Optional[str]]:
    """
    Calculates stay nights from explicit check-in/out dates or trip duration.
    Returns (nights, error_message).
    Strictly validates dates; does not silently guess if dates are invalid.
    """
    if check_in_date or check_out_date:
        if not check_in_date or not check_out_date:
            return None, "Both check_in_date and check_out_date must be provided for date-based night calculation."
        try:
            d_in = datetime.strptime(check_in_date.strip()[:10], "%Y-%m-%d").date()
            d_out = datetime.strptime(check_out_date.strip()[:10], "%Y-%m-%d").date()
        except Exception:
            return None, f"Invalid date format for check-in ('{check_in_date}') or check-out ('{check_out_date}'). Expected YYYY-MM-DD."

        diff = (d_out - d_in).days
        if diff < 0:
            return None, f"Check-out date ({check_out_date}) cannot be earlier than check-in date ({check_in_date})."
        if diff == 0:
            return 0, "Check-in and check-out dates are on the same day (0 nights stay)."
        return diff, None

    if duration_days is not None:
        if duration_days <= 0:
            return None, f"Invalid trip duration ({duration_days} days). Duration must be at least 1 day."
        if duration_days == 1:
            return 0, "A 1-day trip represents a day excursion with 0 hotel nights."
        return duration_days - 1, None

    return None, "Neither check-in/out dates nor trip duration were provided to determine hotel nights."


def calculate_budget(
    pax: int = 1,
    transport: Optional[Dict[str, Any]] = None,
    return_transport: Optional[Dict[str, Any]] = None,
    darshan_slot: Optional[Dict[str, Any]] = None,
    accommodation: Optional[Dict[str, Any]] = None,
    estimated_costs: Optional[Dict[str, Union[int, float, Decimal]]] = None,
    total_budget: Optional[Union[int, float, Decimal]] = None,
    is_round_trip: bool = False,
    estimate_return_if_missing: bool = False,
    pax_per_room: int = 2,
    check_in_date: Optional[str] = None,
    check_out_date: Optional[str] = None,
    duration_days: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Deterministic budget and cost evaluation.

    Pricing Rules:
    - Transport prices are per passenger and per one-way leg.
    - Outbound and return legs are priced independently if both are supplied.
    - Return fares are never silently doubled into verified costs.
    - Darshan slot prices are per passenger.
    - Accommodation is per room per night; rooms = ceil(pax / pax_per_room).
    - If required costs are incomplete, within_budget is NOT reported as definitive.
    """
    issues: List[str] = []
    is_complete = True

    # Validate passenger count
    if pax is None or pax <= 0:
        issues.append(f"Passenger count (pax={pax}) must be an integer greater than or equal to 1.")
        is_complete = False
        pax = 1
    else:
        pax = int(pax)

    # Validate budget amount if supplied
    target_budget_dec: Optional[Decimal] = None
    if total_budget is not None:
        target_budget_dec = _to_decimal(total_budget)
        if target_budget_dec is None or target_budget_dec < Decimal("0.00"):
            issues.append(f"Total budget ({total_budget}) must be a non-negative number.")
            is_complete = False
            target_budget_dec = None

    # -------------------------------------------------------------------------
    # 1. Transport Calculation (Outbound & Return)
    # -------------------------------------------------------------------------
    transport_verified = Decimal("0.00")
    transport_details: Dict[str, Any] = {
        "selected": False,
        "is_round_trip": is_round_trip,
        "outbound": None,
        "return": None,
        "total": Decimal("0.00"),
    }

    # Outbound leg
    if transport:
        transport_details["selected"] = True
        out_mode = transport.get("mode", "transport")
        out_price_raw = transport.get("price") if transport.get("price") is not None else transport.get("price_per_person")
        out_dec = _to_decimal(out_price_raw)

        if out_dec is None or out_dec < Decimal("0.00"):
            issues.append(f"Selected outbound {out_mode} transport has no valid verified price.")
            is_complete = False
            transport_details["outbound"] = {
                "mode": out_mode,
                "operator": transport.get("operator") or transport.get("airline"),
                "price_per_person": None,
                "pax": pax,
                "total": None,
                "verified": False,
            }
        else:
            out_total = out_dec * Decimal(str(pax))
            transport_verified += out_total
            transport_details["outbound"] = {
                "mode": out_mode,
                "operator": transport.get("operator") or transport.get("airline"),
                "price_per_person": float(out_dec),
                "pax": pax,
                "total": float(out_total),
                "verified": True,
            }

    # Return leg handling
    if return_transport:
        transport_details["selected"] = True
        ret_mode = return_transport.get("mode", "transport")
        ret_price_raw = return_transport.get("price") if return_transport.get("price") is not None else return_transport.get("price_per_person")
        ret_dec = _to_decimal(ret_price_raw)

        if ret_dec is None or ret_dec < Decimal("0.00"):
            issues.append(f"Selected return {ret_mode} transport has no valid verified price.")
            is_complete = False
            transport_details["return"] = {
                "mode": ret_mode,
                "operator": return_transport.get("operator") or return_transport.get("airline"),
                "price_per_person": None,
                "pax": pax,
                "total": None,
                "verified": False,
            }
        else:
            ret_total = ret_dec * Decimal(str(pax))
            transport_verified += ret_total
            transport_details["return"] = {
                "mode": ret_mode,
                "operator": return_transport.get("operator") or return_transport.get("airline"),
                "price_per_person": float(ret_dec),
                "pax": pax,
                "total": float(ret_total),
                "verified": True,
            }
    elif is_round_trip and transport:
        # User requested round-trip, but no return leg was explicitly selected
        if estimate_return_if_missing:
            # Create a clearly labeled return estimate (NOT verified)
            out_unit = transport_details["outbound"]["price_per_person"] if transport_details.get("outbound") else None
            if out_unit is not None:
                ret_est_amount = Decimal(str(out_unit)) * Decimal(str(pax))
                if estimated_costs is None:
                    estimated_costs = {}
                else:
                    estimated_costs = dict(estimated_costs)
                estimated_costs["estimated_return_transport"] = float(ret_est_amount)
                transport_details["return"] = {
                    "mode": transport.get("mode", "transport"),
                    "price_per_person": float(out_unit),
                    "pax": pax,
                    "total": float(ret_est_amount),
                    "verified": False,
                    "is_estimate": True,
                    "note": "Return fare is an illustrative estimate based on outbound fare. Not a verified reservation.",
                }
        else:
            issues.append("Round-trip travel was requested, but return transport is missing or unverified.")
            is_complete = False
            transport_details["return"] = {
                "status": "MISSING_RETURN_LEG",
                "verified": False,
            }

    transport_details["total"] = float(transport_verified)

    # -------------------------------------------------------------------------
    # 2. Darshan Slot Calculation
    # -------------------------------------------------------------------------
    darshan_verified = Decimal("0.00")
    darshan_details: Dict[str, Any] = {
        "selected": False,
        "category": None,
        "price_per_person": None,
        "pax": pax,
        "total": Decimal("0.00"),
    }

    if darshan_slot:
        darshan_details["selected"] = True
        category = darshan_slot.get("category", "Normal Darshan")
        darshan_details["category"] = category

        unit_price = darshan_slot.get("price")
        if unit_price is None:
            unit_price = darshan_slot.get("price_per_person")

        # Canonical free shrine board category
        if unit_price is None and category == "Normal Darshan":
            unit_price = 0

        dec_price = _to_decimal(unit_price)
        if dec_price is None or dec_price < Decimal("0.00"):
            issues.append(f"Selected darshan slot '{category}' has no verified non-negative price.")
            is_complete = False
        else:
            darshan_details["price_per_person"] = float(dec_price)
            d_total = dec_price * Decimal(str(pax))
            darshan_verified = d_total
            darshan_details["total"] = float(d_total)

    # -------------------------------------------------------------------------
    # 3. Accommodation Calculation
    # -------------------------------------------------------------------------
    hotel_verified = Decimal("0.00")
    rooms_needed = calculate_rooms_required(pax, pax_per_room=pax_per_room)
    hotel_details: Dict[str, Any] = {
        "selected": False,
        "name": None,
        "category": None,
        "price_per_room_per_night": None,
        "rooms": 0,
        "nights": 0,
        "room_shortage": False,
        "total": Decimal("0.00"),
    }

    if accommodation:
        hotel_details["selected"] = True
        hotel_details["name"] = accommodation.get("name")
        hotel_details["category"] = accommodation.get("category")

        # Rooms calculation (respects explicit rooms or configurable capacity)
        explicit_rooms = accommodation.get("rooms") or accommodation.get("rooms_count")
        if explicit_rooms is not None and int(explicit_rooms) > 0:
            rooms_needed = int(explicit_rooms)
            hotel_details["room_allocation_basis"] = f"explicit ({rooms_needed} room(s))"
        else:
            rooms_needed = calculate_rooms_required(pax, pax_per_room=pax_per_room)
            hotel_details["room_allocation_basis"] = f"assumed {pax_per_room} guests/room"
        hotel_details["rooms"] = rooms_needed

        # Room availability verification
        rooms_avail = accommodation.get("rooms_available")
        if rooms_avail is not None:
            rooms_avail_int = int(rooms_avail)
            hotel_details["rooms_available"] = rooms_avail_int
            if rooms_avail_int < rooms_needed:
                hotel_details["room_shortage"] = True
                issues.append(
                    f"Hotel room shortage: '{accommodation.get('name', 'Hotel')}' requires {rooms_needed} room(s) "
                    f"for {pax} guest(s), but only {rooms_avail_int} room(s) are available."
                )
                is_complete = False

        # Night calculation (strict verification, no silent guessing)
        c_in = check_in_date or accommodation.get("stay_date") or accommodation.get("check_in_date")
        c_out = check_out_date or accommodation.get("check_out_date")
        explicit_nights = accommodation.get("hotel_nights") or accommodation.get("nights")

        if explicit_nights is not None and int(explicit_nights) >= 0:
            nights = int(explicit_nights)
            night_err = None
        else:
            nights, night_err = calculate_hotel_nights(c_in, c_out, duration_days=duration_days)

        if night_err:
            issues.append(f"Accommodation night calculation failed: {night_err}")
            is_complete = False
            hotel_details["nights"] = 0
        else:
            hotel_details["nights"] = nights or 0

        # Nightly rate lookup
        unit_price = accommodation.get("price_per_night")
        if unit_price is None:
            unit_price = accommodation.get("price_per_room_per_night") or accommodation.get("price")

        dec_price = _to_decimal(unit_price)
        if dec_price is None or dec_price < Decimal("0.00"):
            issues.append(f"Selected accommodation '{accommodation.get('name', 'Hotel')}' has no verified nightly price.")
            is_complete = False
        else:
            hotel_details["price_per_room_per_night"] = float(dec_price)
            if hotel_details["nights"] > 0 and rooms_needed > 0:
                h_total = dec_price * Decimal(str(rooms_needed)) * Decimal(str(hotel_details["nights"]))
                hotel_verified = h_total
                hotel_details["total"] = float(h_total)
            else:
                hotel_details["total"] = 0.0

    # -------------------------------------------------------------------------
    # 4. Verified Direct Total
    # -------------------------------------------------------------------------
    total_verified = transport_verified + darshan_verified + hotel_verified

    # -------------------------------------------------------------------------
    # 5. Estimated Discretionary Costs
    # -------------------------------------------------------------------------
    total_estimated = Decimal("0.00")
    est_breakdown: Dict[str, float] = {}

    if estimated_costs and isinstance(estimated_costs, dict):
        for item_name, amount in estimated_costs.items():
            amt_dec = _to_decimal(amount)
            if amt_dec is not None and amt_dec > Decimal("0.00"):
                est_breakdown[item_name] = float(amt_dec)
                total_estimated += amt_dec

    # -------------------------------------------------------------------------
    # 6. Grand Total
    # -------------------------------------------------------------------------
    grand_total: Optional[float] = None
    if is_complete:
        grand_total = float(total_verified + total_estimated)

    # -------------------------------------------------------------------------
    # 7. Budget Evaluation (Only definitive if is_complete is True)
    # -------------------------------------------------------------------------
    within_budget: Optional[bool] = None
    remaining_budget: Optional[float] = None
    over_budget_amount: Optional[float] = None

    if is_complete and target_budget_dec is not None and grand_total is not None:
        dec_grand = Decimal(str(grand_total))
        if dec_grand <= target_budget_dec:
            within_budget = True
            diff = target_budget_dec - dec_grand
            remaining_budget = float(diff)
            over_budget_amount = 0.0
        else:
            within_budget = False
            deficit = dec_grand - target_budget_dec
            remaining_budget = -float(deficit)
            over_budget_amount = float(deficit)
            issues.append(
                f"Total plan cost (₹{grand_total:,.2f}) exceeds target budget "
                f"(₹{float(target_budget_dec):,.2f}) by ₹{over_budget_amount:,.2f}."
            )
    elif not is_complete and target_budget_dec is not None:
        issues.append("Budget evaluation cannot be deterministically finalized because one or more required costs are incomplete or unverified.")

    return {
        "verified_costs": {
            "transport": float(transport_verified),
            "darshan": float(darshan_verified),
            "accommodation": float(hotel_verified),
            "total_verified": float(total_verified),
            "details": {
                "transport": transport_details,
                "darshan": darshan_details,
                "accommodation": hotel_details,
            },
        },
        "estimated_costs": {
            "items": est_breakdown,
            "breakdown": est_breakdown,
            "total_estimated": float(total_estimated),
        },
        "excluded_costs": list(EXCLUDED_EXPENSES),
        "excluded_expenses": list(EXCLUDED_EXPENSES),
        "rooms_needed": rooms_needed,
        "grand_total": grand_total,
        "total_budget": float(target_budget_dec) if target_budget_dec is not None else None,
        "remaining_budget": remaining_budget,
        "over_budget_amount": over_budget_amount,
        "within_budget": within_budget,
        "is_complete": is_complete,
        "is_partially_estimated": bool(est_breakdown),
        "issues": issues,
    }
