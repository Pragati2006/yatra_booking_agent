import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "yatra_booking_agent")

if not MONGO_URI:
    raise RuntimeError(
        "MONGO_URI is not set. Add your MongoDB Atlas connection string to .env"
    )

client = None
db = None
tourist_attractions = None
yatra_information = None

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


def test_connection():
    """Verify that MongoDB Atlas is reachable."""
    global client
    if client is None:
        try:
            client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=2000,
                connectTimeoutMS=2000,
                socketTimeoutMS=2000,
            )
        except Exception:
            return False
    try:
        client.admin.command("ping")
        return True
    except Exception:
        return False


if __name__ == "__main__":
    if test_connection():
        print("MongoDB connection successful!")
        print(f"Database: {MONGO_DB_NAME}")
        print("Collections ready:")
        print(" - tourist_attractions")
        print(" - yatra_information")