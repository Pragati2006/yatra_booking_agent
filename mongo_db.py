import os
import time
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "yatra-booking-agent")

if not MONGO_URI:
    raise RuntimeError(
        "MONGO_URI is not set. Add your MongoDB Atlas connection string to .env"
    )

client = None
db = None
tourist_attractions = None
yatra_information = None

# Circuit-breaker / connection health cache (Phase 4)
HEALTH_CHECK_TTL_SECONDS = 60
_circuit_breaker = {
    "is_available": None,
    "last_check": 0.0,
    "last_error": None,
}

try:
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=2000,
        connectTimeoutMS=2000,
        socketTimeoutMS=2000,
    )
    db = client[MONGO_DB_NAME]
    tourist_attractions = db["tourist_attractions"]
    yatra_information = db["yatra_information"]
except Exception:
    pass


import atexit


def close_client():
    """Safely shut down MongoClient and free up resources."""
    global client
    if client is not None:
        try:
            client.close()
        except Exception:
            pass


atexit.register(close_client)


def test_connection(timeout_ms: int = 2000) -> bool:
    """Verify that MongoDB Atlas is reachable and authenticated."""
    global client, db, tourist_attractions, yatra_information
    if not MONGO_URI:
        return False
    try:
        if client is None:
            client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=timeout_ms,
                connectTimeoutMS=timeout_ms,
                socketTimeoutMS=timeout_ms,
            )
            db = client[MONGO_DB_NAME]
            tourist_attractions = db["tourist_attractions"]
            yatra_information = db["yatra_information"]
        client.admin.command("ping")
        _circuit_breaker["is_available"] = True
        _circuit_breaker["last_check"] = time.time()
        _circuit_breaker["last_error"] = None
        return True
    except Exception as exc:
        _circuit_breaker["is_available"] = False
        _circuit_breaker["last_check"] = time.time()
        _circuit_breaker["last_error"] = str(exc)
        return False


def is_available() -> bool:
    """
    Lightweight circuit breaker / connection health check.
    Prevents repeated 2-second connection delays when Atlas is already known to be unreachable.
    Caches the health state for HEALTH_CHECK_TTL_SECONDS (60s) before re-testing.
    """
    import time
    now = time.time()
    if (
        _circuit_breaker["is_available"] is not None
        and (now - _circuit_breaker["last_check"]) < HEALTH_CHECK_TTL_SECONDS
    ):
        return _circuit_breaker["is_available"]

    # Re-probe Atlas with a fast 1500ms timeout
    return test_connection(timeout_ms=1500)


def mark_offline(error: Exception = None):
    """Explicitly trips the circuit breaker when an active query encounters a connection error."""
    import time
    _circuit_breaker["is_available"] = False
    _circuit_breaker["last_check"] = time.time()
    if error:
        _circuit_breaker["last_error"] = str(error)


def reset_circuit_breaker():
    """Resets the circuit breaker state for immediate re-probing."""
    _circuit_breaker["is_available"] = None
    _circuit_breaker["last_check"] = 0.0
    _circuit_breaker["last_error"] = None


if __name__ == "__main__":
    if test_connection():
        print("MongoDB connection successful!")
        print(f"Database: {MONGO_DB_NAME}")
        print("Collections ready:")
        print(" - tourist_attractions")
        print(" - yatra_information")