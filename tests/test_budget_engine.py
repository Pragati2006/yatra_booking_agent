"""
tests/test_budget_engine.py
Comprehensive automated test suite for agents.budget_engine.
Verifies:
- Different outbound and return fares calculated independently
- Missing return fare handling without silent fabrication
- Explicitly labelled estimates versus verified prices
- Invalid dates and zero-night stays
- Configurable room capacity (pax_per_room) and room shortage detection
- Missing mandatory costs and incomplete budget evaluations
- No double-counting across transport, darshan, hotel, and estimates
- Exact-budget, under-budget, and over-budget cases
- Negative input handling and robust Decimal arithmetic
"""

import unittest
from decimal import Decimal

from agents import budget_engine


class TestBudgetEngine(unittest.TestCase):

    # =========================================================================
    # 1. Transport Tests (One-Way, Independent Return, Missing Return)
    # =========================================================================

    def test_transport_one_way(self):
        """Test standard one-way transport calculation: price * pax."""
        # 4 passengers * ₹450 = ₹1,800
        res = budget_engine.calculate_budget(
            pax=4,
            transport={"mode": "train", "price": 450, "operator": "Indian Railways"},
            is_round_trip=False,
        )

        self.assertTrue(res["is_complete"])
        self.assertEqual(res["verified_costs"]["transport"], 1800.0)
        self.assertEqual(res["verified_costs"]["details"]["transport"]["outbound"]["total"], 1800.0)
        self.assertIsNone(res["verified_costs"]["details"]["transport"]["return"])
        self.assertEqual(res["grand_total"], 1800.0)

    def test_different_outbound_and_return_fares(self):
        """Test round trip with different outbound and return fares calculated independently."""
        # Outbound: Flight ₹5,000 * 2 = ₹10,000
        # Return: Train 3AC ₹1,800 * 2 = ₹3,600
        # Total verified transport: ₹13,600
        res = budget_engine.calculate_budget(
            pax=2,
            transport={"mode": "flight", "price": 5000, "airline": "Vistara"},
            return_transport={"mode": "train", "price": 1800, "operator": "Northern Railway"},
            is_round_trip=True,
        )

        self.assertTrue(res["is_complete"])
        t_details = res["verified_costs"]["details"]["transport"]
        self.assertEqual(t_details["outbound"]["total"], 10000.0)
        self.assertEqual(t_details["return"]["total"], 3600.0)
        self.assertEqual(res["verified_costs"]["transport"], 13600.0)
        self.assertEqual(res["grand_total"], 13600.0)

    def test_missing_return_fare_unverified(self):
        """Test round-trip requested but return leg missing marks plan incomplete and not verified."""
        res = budget_engine.calculate_budget(
            pax=2,
            transport={"mode": "flight", "price": 5000},
            return_transport=None,
            is_round_trip=True,
            estimate_return_if_missing=False,  # strictly require verified return
        )

        self.assertFalse(res["is_complete"])
        self.assertIsNone(res["grand_total"])
        self.assertIsNone(res["within_budget"])
        self.assertTrue(any("return transport is missing or unverified" in i for i in res["issues"]))

    def test_missing_return_fare_as_labelled_estimate(self):
        """Test return fare can be accepted as an explicitly labeled estimate without fabricating verified cost."""
        res = budget_engine.calculate_budget(
            pax=2,
            transport={"mode": "flight", "price": 5000},
            return_transport=None,
            is_round_trip=True,
            estimate_return_if_missing=True,  # explicitly request illustrative estimate
        )

        self.assertTrue(res["is_complete"])
        # Outbound verified: ₹10,000
        self.assertEqual(res["verified_costs"]["transport"], 10000.0)
        # Return in estimated_costs: ₹10,000
        self.assertEqual(res["estimated_costs"]["items"]["estimated_return_transport"], 10000.0)
        self.assertTrue(res["is_partially_estimated"])
        self.assertEqual(res["grand_total"], 20000.0)

    # =========================================================================
    # 2. Accommodation & Room Shortage Tests
    # =========================================================================

    def test_configurable_room_capacity(self):
        """Test rooms required using standard 2 guests/room vs custom 3 guests/room vs 1 guest/room."""
        # 5 guests, default 2/room -> 3 rooms
        self.assertEqual(budget_engine.calculate_rooms_required(5, pax_per_room=2), 3)
        # 5 guests, 3/room -> 2 rooms
        self.assertEqual(budget_engine.calculate_rooms_required(5, pax_per_room=3), 2)
        # 4 guests, 1/room (single occupancy) -> 4 rooms
        self.assertEqual(budget_engine.calculate_rooms_required(4, pax_per_room=1), 4)

    def test_hotel_cost_from_valid_dates(self):
        """Test stay nights and cost calculation strictly from valid ISO dates."""
        # 4 guests -> 2 rooms. Check-in 2026-10-20, Check-out 2026-10-24 -> 4 nights.
        # Price: ₹1,500/room/night -> 2 * 4 * 1500 = ₹12,000
        res = budget_engine.calculate_budget(
            pax=4,
            accommodation={
                "name": "Trikuta Residency",
                "price_per_night": 1500,
            },
            check_in_date="2026-10-20",
            check_out_date="2026-10-24",
        )

        self.assertTrue(res["is_complete"])
        h_details = res["verified_costs"]["details"]["accommodation"]
        self.assertEqual(h_details["rooms"], 2)
        self.assertEqual(h_details["nights"], 4)
        self.assertEqual(h_details["total"], 12000.0)
        self.assertEqual(res["verified_costs"]["accommodation"], 12000.0)

    def test_invalid_checkout_date_fails_strictly(self):
        """Test check-out earlier than check-in fails without silent guessing."""
        res = budget_engine.calculate_budget(
            pax=2,
            accommodation={"name": "Hotel Katra", "price_per_night": 1000},
            check_in_date="2026-10-25",
            check_out_date="2026-10-20",  # earlier than check-in
        )

        self.assertFalse(res["is_complete"])
        self.assertIsNone(res["grand_total"])
        self.assertTrue(any("Check-out date" in i and "cannot be earlier" in i for i in res["issues"]))

    def test_zero_night_stay(self):
        """Test check-in and check-out on the same day represents 0 nights and flags appropriately."""
        nights, err = budget_engine.calculate_hotel_nights("2026-10-20", "2026-10-20")
        self.assertEqual(nights, 0)
        self.assertIn("0 nights", err)

    def test_room_shortage_detection(self):
        """Test that room shortage flags room_shortage=True and marks plan incomplete."""
        # 6 guests -> 3 rooms required, but only 1 room available
        res = budget_engine.calculate_budget(
            pax=6,
            accommodation={
                "name": "Small Inn",
                "price_per_night": 800,
                "rooms_available": 1,
                "hotel_nights": 2,
            },
        )

        self.assertFalse(res["is_complete"])
        h_details = res["verified_costs"]["details"]["accommodation"]
        self.assertTrue(h_details["room_shortage"])
        self.assertTrue(any("Hotel room shortage" in i for i in res["issues"]))

    # =========================================================================
    # 3. Darshan Slot Tests
    # =========================================================================

    def test_darshan_slots(self):
        """Test Normal Darshan (free), VIP Darshan (₹500), and Helicopter (₹4640)."""
        # Normal
        res_normal = budget_engine.calculate_budget(pax=4, darshan_slot={"category": "Normal Darshan", "price": 0})
        self.assertEqual(res_normal["verified_costs"]["darshan"], 0.0)

        # VIP
        res_vip = budget_engine.calculate_budget(pax=3, darshan_slot={"category": "VIP Darshan", "price": 500})
        self.assertEqual(res_vip["verified_costs"]["darshan"], 1500.0)

        # Heli
        res_heli = budget_engine.calculate_budget(pax=2, darshan_slot={"category": "Helicopter Darshan", "price": 4640})
        self.assertEqual(res_heli["verified_costs"]["darshan"], 9280.0)

    # =========================================================================
    # 4. Estimated vs Verified Costs & No Double-Counting
    # =========================================================================

    def test_distinct_verified_and_estimated_costs(self):
        """Verify estimates are never placed in total_verified and excluded items are not in grand_total."""
        res = budget_engine.calculate_budget(
            pax=2,
            transport={"mode": "train", "price": 600},  # 1,200
            darshan_slot={"category": "Normal Darshan", "price": 0},
            accommodation={"price_per_night": 1000, "hotel_nights": 2},  # 1 room * 2 nights * 1000 = 2,000
            estimated_costs={
                "local_taxi": 1200,
                "meals": 2000,
            },
        )

        self.assertTrue(res["is_complete"])
        # Verified: 1,200 + 2,000 = 3,200
        self.assertEqual(res["verified_costs"]["total_verified"], 3200.0)
        # Estimated: 1,200 + 2,000 = 3,200
        self.assertEqual(res["estimated_costs"]["total_estimated"], 3200.0)
        # Grand total = 3,200 + 3,200 = 6,400
        self.assertEqual(res["grand_total"], 6400.0)
        # Excluded costs exist but do not add to grand_total
        self.assertTrue(len(res["excluded_costs"]) >= 3)
        self.assertEqual(
            res["grand_total"],
            res["verified_costs"]["total_verified"] + res["estimated_costs"]["total_estimated"],
        )

    # =========================================================================
    # 5. Budget Threshold Evaluation (Under, Exact, Over, Incomplete)
    # =========================================================================

    def test_budget_under(self):
        """Test under-budget evaluation provides positive remaining budget and within_budget=True."""
        res = budget_engine.calculate_budget(
            pax=2,
            transport={"mode": "train", "price": 500},  # 1000
            accommodation={"price_per_night": 1500, "hotel_nights": 2},  # 3000
            total_budget=5000,
        )
        # Total: 4000. Budget: 5000 -> Remaining: 1000
        self.assertTrue(res["within_budget"])
        self.assertEqual(res["remaining_budget"], 1000.0)
        self.assertEqual(res["over_budget_amount"], 0.0)

    def test_budget_exactly_met(self):
        """Test exact budget match."""
        res = budget_engine.calculate_budget(
            pax=1,
            transport={"mode": "bus", "price": 1000},
            total_budget=1000,
        )
        self.assertTrue(res["within_budget"])
        self.assertEqual(res["remaining_budget"], 0.0)
        self.assertEqual(res["over_budget_amount"], 0.0)

    def test_budget_exceeded(self):
        """Test over-budget evaluation provides negative remaining budget and over_budget_amount."""
        res = budget_engine.calculate_budget(
            pax=2,
            transport={"mode": "flight", "price": 6000},  # 12,000
            accommodation={"price_per_night": 2000, "hotel_nights": 2},  # 4,000
            total_budget=14000,
        )
        # Total: 16,000. Budget: 14,000 -> Deficit: 2,000
        self.assertFalse(res["within_budget"])
        self.assertEqual(res["remaining_budget"], -2000.0)
        self.assertEqual(res["over_budget_amount"], 2000.0)
        self.assertTrue(any("exceeds target budget" in i for i in res["issues"]))

    def test_incomplete_costs_cannot_report_within_budget(self):
        """Test that missing mandatory prices prevent reporting a definitive within_budget."""
        res = budget_engine.calculate_budget(
            pax=2,
            transport={"mode": "flight", "price": None},  # Missing price!
            accommodation={"price_per_night": 2000, "hotel_nights": 2},
            total_budget=15000,
        )

        self.assertFalse(res["is_complete"])
        self.assertIsNone(res["within_budget"])
        self.assertIsNone(res["grand_total"])
        self.assertIsNone(res["remaining_budget"])

    # =========================================================================
    # 6. Edge Cases & Invalid Inputs
    # =========================================================================

    def test_invalid_negative_pax_or_budget(self):
        """Test that negative passenger count or budget flags invalid inputs."""
        res = budget_engine.calculate_budget(
            pax=-2,
            total_budget=-5000,
        )

        self.assertFalse(res["is_complete"])
        self.assertTrue(any("Passenger count" in i for i in res["issues"]))
        self.assertTrue(any("Total budget" in i for i in res["issues"]))


if __name__ == "__main__":
    unittest.main()
