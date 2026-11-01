import unittest
from unittest.mock import patch, MagicMock
import time

import mongo_db
import mongodb_tools
import langchain_tools
from agents import coordinator


class TestMongoDBToolsRetrieval(unittest.TestCase):
    """
    Phase 5: Verify retrieval functions across both collections / fallback datasets:
    1. Exact attraction name
    2. Partial attraction name
    3. Nearby Katra search
    4. Region/category search
    5. Aarti timings
    6. Registration information
    7. Yatra routes
    8. Facilities and helpline topics
    """

    def test_01_exact_attraction_name(self):
        results = mongodb_tools.search_tourist_attraction("Bhairavnath Temple")
        self.assertTrue(len(results) >= 1)
        names = [p["name"] for p in results]
        self.assertIn("Bhairavnath Temple", names)

    def test_02_partial_attraction_name(self):
        results = mongodb_tools.search_tourist_attraction("Bhairav")
        self.assertTrue(len(results) >= 1)
        self.assertTrue(any("Bhairav" in p["name"] for p in results))

    def test_03_nearby_katra_search(self):
        results = mongodb_tools.search_tourist_attraction("places around katra")
        self.assertTrue(len(results) >= 1)
        names = [p["name"] for p in results]
        # Katra base town itself must be excluded from nearby places
        self.assertNotIn("Katra", [n.strip() for n in names])
        # Should include trek route or nearby temples
        trek_places = {"Bhairavnath Temple", "Ardhkuwari Cave", "Charan Paduka", "Nau Devi Cave Temple", "Baba Dhansar"}
        self.assertTrue(any(n in trek_places for n in names))

    def test_04_region_category_search(self):
        results = mongodb_tools.search_tourist_attraction("Jammu")
        self.assertTrue(len(results) >= 1)
        self.assertTrue(
            any("Jammu" in p.get("name", "") or "Jammu" in p.get("region", "") or "Jammu" in p.get("category", "") for p in results)
        )

    def test_05_aarti_timings(self):
        info = mongodb_tools.get_yatra_information("aarti_timings")
        self.assertIsNotNone(info)
        self.assertEqual(info.get("topic"), "aarti_timings")
        search_res = mongodb_tools.search_yatra_information("aarti")
        self.assertTrue(len(search_res) >= 1)
        self.assertEqual(search_res[0].get("topic"), "aarti_timings")

    def test_06_registration_information(self):
        info = mongodb_tools.get_yatra_information("registration")
        self.assertIsNotNone(info)
        self.assertEqual(info.get("topic"), "registration")
        search_res = mongodb_tools.search_yatra_information("registration")
        self.assertTrue(len(search_res) >= 1)
        self.assertEqual(search_res[0].get("topic"), "registration")

    def test_07_yatra_routes(self):
        info = mongodb_tools.get_yatra_information("routes")
        self.assertIsNotNone(info)
        self.assertEqual(info.get("topic"), "routes")
        search_res = mongodb_tools.search_yatra_information("route")
        self.assertTrue(len(search_res) >= 1)
        self.assertTrue(any(item.get("topic") == "routes" for item in search_res))

    def test_08_facilities_and_helpline(self):
        info = mongodb_tools.get_yatra_information("helpline")
        self.assertIsNotNone(info)
        self.assertEqual(info.get("topic"), "helpline")
        search_res = mongodb_tools.search_yatra_information("helpline")
        self.assertTrue(len(search_res) >= 1)
        self.assertEqual(search_res[0].get("topic"), "helpline")

    def test_09_langchain_tools_output_formatting(self):
        out_attraction = langchain_tools.tourism_search.run("Bhairavnath Temple")
        self.assertIn("Bhairavnath Temple", out_attraction)
        self.assertIn("Distance:", out_attraction)

        out_yatra = langchain_tools.yatra_information_search.run("aarti")
        self.assertIn("aarti_timings", out_yatra.lower())


class TestMongoDBCircuitBreaker(unittest.TestCase):
    """
    Phase 4: Connection health handling and circuit breaker behavior.
    """

    def setUp(self):
        mongo_db.reset_circuit_breaker()

    def tearDown(self):
        mongo_db.reset_circuit_breaker()

    def test_circuit_breaker_caching_ttl(self):
        # Force breaker into offline state
        mongo_db.mark_offline(Exception("Test failure"))
        self.assertFalse(mongo_db._circuit_breaker["is_available"])
        initial_check_time = mongo_db._circuit_breaker["last_check"]

        # Multiple calls within TTL (60s) should return cached False without re-probing
        time.sleep(0.05)
        self.assertFalse(mongo_db.is_available())
        self.assertEqual(mongo_db._circuit_breaker["last_check"], initial_check_time)

    def test_circuit_breaker_mark_offline(self):
        mongo_db.mark_offline(RuntimeError("Network down"))
        self.assertFalse(mongo_db._circuit_breaker["is_available"])
        self.assertIn("Network down", mongo_db._circuit_breaker["last_error"])

    def test_circuit_breaker_reset(self):
        mongo_db.mark_offline(RuntimeError("Network down"))
        self.assertFalse(mongo_db._circuit_breaker["is_available"])
        mongo_db.reset_circuit_breaker()
        self.assertIsNone(mongo_db._circuit_breaker["is_available"])


class TestCoordinatorMongoDBIntegration(unittest.TestCase):
    """
    Phase 3: Coordinator integration paths (Success vs Fallback).
    """

    def test_coordinator_success_uses_mongodb_llm_answer(self):
        mock_answer = "Bhairavnath Temple is located ~3 km uphill from the main Bhawan shrine. Darshan is traditionally required to complete the pilgrimage."
        mock_result = {
            "answer": mock_answer,
            "tool_results": [{"tool": "tourism_search", "arguments": {"query": "Bhairavnath Temple"}}],
            "status": "success",
            "source": "mongodb_llm",
            "response_source": "mongodb_llm",
            "knowledge_source": "atlas",
        }

        with patch("mongodb_agent.answer_mongodb_query", return_value=mock_result):
            res = coordinator.answer_tourism_query("Tell me about Bhairavnath Temple")

            self.assertEqual(res["intent"], "TOURISM")
            self.assertEqual(res["source"], "mongodb_llm")
            self.assertEqual(res["response_source"], "mongodb_llm")
            self.assertEqual(res["knowledge_source"], "atlas")
            self.assertEqual(res["reply"], mock_answer)
            self.assertEqual(res["mongodb_status"], "success")
            self.assertEqual(len(res["mongodb_tool_results"]), 1)
            self.assertEqual(res["last_tourism_place"], "Bhairavnath Temple")

    def test_coordinator_groq_failure_falls_back_to_local_knowledge(self):
        with patch("mongodb_agent.answer_mongodb_query", side_effect=RuntimeError("Groq API rate limit or outage")):
            res = coordinator.answer_tourism_query("Tell me about Bhairavnath Temple")

            self.assertEqual(res["intent"], "TOURISM")
            self.assertEqual(res["source"], "local_fallback")
            self.assertEqual(res["response_source"], "conversation_agent")
            self.assertEqual(res["knowledge_source"], "local_fallback")
            self.assertEqual(res["mongodb_status"], "error")
            self.assertTrue("Groq API rate limit" in res.get("mongodb_error", ""))
            self.assertIn("Bhairavnath Temple", res["reply"])
            # The system must not crash and must provide a helpful reply
            self.assertTrue(len(res["reply"]) > 50)

    def test_coordinator_empty_mongodb_result_falls_back_to_local_knowledge(self):
        mock_result = {
            "answer": "",
            "tool_results": [],
            "status": "fallback",
            "source": "local_fallback",
            "response_source": "conversation_agent",
            "knowledge_source": "local_fallback",
        }

        with patch("mongodb_agent.answer_mongodb_query", return_value=mock_result):
            res = coordinator.answer_tourism_query("What are the Aarti timings?")

            self.assertEqual(res["intent"], "TOURISM")
            self.assertEqual(res["source"], "local_fallback")
            self.assertEqual(res["response_source"], "conversation_agent")
            self.assertEqual(res["knowledge_source"], "local_fallback")
            self.assertEqual(res["mongodb_status"], "fallback")
            self.assertTrue(len(res["reply"]) > 20)

    def test_coordinator_mongodb_unavailable_falls_back(self):
        """When MongoDB Atlas is unavailable / circuit breaker offline."""
        mock_result = {
            "answer": "",
            "tool_results": [],
            "status": "fallback",
            "error": "MongoDB unavailable",
        }

        with patch("mongodb_agent.answer_mongodb_query", return_value=mock_result):
            res = coordinator.answer_tourism_query("Tell me about Gulmarg")

            self.assertEqual(res["intent"], "TOURISM")
            self.assertEqual(res["source"], "local_fallback")
            self.assertEqual(res["response_source"], "conversation_agent")
            self.assertEqual(res["knowledge_source"], "local_fallback")
            self.assertIn(res["mongodb_status"], ("fallback", "error"))

    def test_coordinator_llm_tool_fallback_provenance(self):
        """When LLM answers using fallback data because Atlas had no match."""
        mock_result = {
            "answer": "Gulmarg is a famous hill station and skiing destination.",
            "tool_results": [{"tool": "tourism_search", "result": "..."}],
            "status": "success",
            "source": "mongodb_llm",
            "response_source": "mongodb_llm",
            "knowledge_source": "local_fallback",
        }

        with patch("mongodb_agent.answer_mongodb_query", return_value=mock_result):
            res = coordinator.answer_tourism_query("Tell me about Gulmarg")

            self.assertEqual(res["intent"], "TOURISM")
            self.assertEqual(res["source"], "mongodb_llm")
            self.assertEqual(res["response_source"], "mongodb_llm")
            self.assertEqual(res["knowledge_source"], "local_fallback")
            self.assertEqual(res["mongodb_status"], "success")

    def test_non_tourism_responses_never_atlas(self):
        """Non-tourism queries must never be labelled as Atlas-backed."""
        # 1. Weather
        res_weather = coordinator.route_message("What is the weather in Katra?")
        self.assertEqual(res_weather.get("intent"), "WEATHER")
        self.assertNotEqual(res_weather.get("knowledge_source"), "atlas")
        self.assertEqual(res_weather.get("knowledge_source"), "weather_service")
        self.assertEqual(res_weather.get("response_source"), "weather_service")
        self.assertEqual(res_weather.get("source"), "weather_service")

        # 2. Availability
        res_avail = coordinator.route_message("Check slot availability for 2026-11-15")
        self.assertEqual(res_avail.get("intent"), "AVAILABILITY")
        self.assertNotEqual(res_avail.get("knowledge_source"), "atlas")
        self.assertEqual(res_avail.get("knowledge_source"), "rpa_playwright")
        self.assertEqual(res_avail.get("response_source"), "rpa_agent")
        self.assertEqual(res_avail.get("source"), "rpa_playwright")

        # 3. Booking
        res_book = coordinator.route_message("I want to book option 1")
        self.assertEqual(res_book.get("intent"), "BOOKING")
        self.assertNotEqual(res_book.get("knowledge_source"), "atlas")
        self.assertEqual(res_book.get("knowledge_source"), "rpa_playwright")
        self.assertEqual(res_book.get("response_source"), "rpa_agent")
        self.assertEqual(res_book.get("source"), "rpa_playwright")

        # 4. Itinerary
        dummy_req = {"origin": "Delhi", "pax": 2, "duration_days": 4}
        res_itin = coordinator.route_message("Show my itinerary", current_request=dummy_req)
        self.assertEqual(res_itin.get("intent"), "ITINERARY")
        self.assertNotEqual(res_itin.get("knowledge_source"), "atlas")
        self.assertEqual(res_itin.get("knowledge_source"), "itinerary_templates")
        self.assertEqual(res_itin.get("response_source"), "itinerary_agent")
        self.assertEqual(res_itin.get("source"), "itinerary_agent")

        # 5. Trip Planning
        res_trip = coordinator.route_message("Plan a 4 day trip from Delhi for 2 people")
        self.assertEqual(res_trip.get("intent"), "TRIP_PLANNING")
        self.assertNotEqual(res_trip.get("knowledge_source"), "atlas")
        self.assertEqual(res_trip.get("knowledge_source"), "local_catalog")
        self.assertEqual(res_trip.get("response_source"), "conversation_agent")


class TestRetrievalSourceTracking(unittest.TestCase):
    """
    Test granular retrieval tracking in mongodb_tools.
    """

    def setUp(self):
        mongodb_tools.clear_caches()
        mongo_db.reset_circuit_breaker()

    def tearDown(self):
        mongodb_tools.clear_caches()
        mongo_db.reset_circuit_breaker()

    def test_offline_retrieval_records_local_fallback_not_atlas(self):
        # Force circuit breaker offline
        mongo_db.mark_offline(Exception("Forced offline test"))

        token = mongodb_tools.start_retrieval_tracking()
        try:
            results = mongodb_tools.search_tourist_attraction("Bhairavnath Temple")
            self.assertTrue(len(results) >= 1)
            sources = mongodb_tools.get_tracked_sources()
            self.assertIn("local_fallback", sources)
            self.assertNotIn("atlas", sources)
        finally:
            mongodb_tools.clear_retrieval_tracking(token)

    def test_online_atlas_retrieval_records_atlas(self):
        # With active Atlas connection
        if not mongo_db.is_available():
            self.skipTest("MongoDB Atlas is not reachable in this environment")

        token = mongodb_tools.start_retrieval_tracking()
        try:
            results = mongodb_tools.search_tourist_attraction("Bhairavnath Temple")
            self.assertTrue(len(results) >= 1)
            sources = mongodb_tools.get_tracked_sources()
            self.assertIn("atlas", sources)
        finally:
            mongodb_tools.clear_retrieval_tracking(token)


if __name__ == "__main__":
    unittest.main()
