"""
db.py
All data access lives here, backed by CSV files instead of a database.

- data/yatra_slots_dataset.csv, data/flights_dataset.csv,
  data/trains_dataset.csv, data/buses_dataset.csv and
  data/users_dataset.csv are the static, checked-in datasets (built
  once by build_dataset.py).
- On first run, these are copied into "live" working CSVs with actual
  calendar dates computed from each row's day_offset. All searching
  and seat-decrementing happen against these live copies.
- data/bookings.csv stores completed (mock) bookings. Bookings are
  transport-mode-generic: a booking stores its transport fields
  (mode, operator/airline, number, route, price) directly on the row
  instead of a foreign key into one specific mode's table, since a
  single booking can now be a flight, train, or bus.

PERSISTENT STORAGE (users + bookings only): Streamlit Cloud's local
filesystem is wiped on every redeploy/sleep-wake, so signups and
bookings would otherwise reset constantly. If airtable_store.py detects
Airtable credentials in Streamlit secrets, users and bookings are
read/written to Airtable instead of the local CSV, so they persist
across restarts. Without that configuration, everything falls back to
local CSV files exactly as before. See README.md -> "Persistent
storage" for setup (the bookings table's columns changed in this
version - see the README's Airtable section for the updated list).

NOTE on auth: passwords are stored as plain SHA-256 hashes with no
per-user salt. That's fine for a local prototype/demo, but it is NOT
production-grade auth.
"""

import hashlib
import os
import uuid
from datetime import date, datetime, timedelta

import pandas as pd

import airtable_store

DATA_DIR = "data"
YATRA_DATASET = f"{DATA_DIR}/yatra_slots_dataset.csv"
FLIGHTS_DATASET = f"{DATA_DIR}/flights_dataset.csv"
TRAINS_DATASET = f"{DATA_DIR}/trains_dataset.csv"
BUSES_DATASET = f"{DATA_DIR}/buses_dataset.csv"
HOTELS_DATASET = f"{DATA_DIR}/hotels_dataset.csv"
USERS_DATASET = f"{DATA_DIR}/users_dataset.csv"

YATRA_LIVE = f"{DATA_DIR}/yatra_slots_live.csv"
FLIGHTS_LIVE = f"{DATA_DIR}/flights_live.csv"
TRAINS_LIVE = f"{DATA_DIR}/trains_live.csv"
BUSES_LIVE = f"{DATA_DIR}/buses_live.csv"
HOTELS_LIVE = f"{DATA_DIR}/hotels_live.csv"
USERS_LIVE = f"{DATA_DIR}/users_live.csv"
BOOKINGS_FILE = f"{DATA_DIR}/bookings.csv"

BOOKINGS_COLUMNS = [
    "booking_id", "user_name", "pax_count",
    "yatra_slot_id", "category", "slot_date", "slot_time",
    "transport_mode", "transport_no", "transport_operator",
    "origin", "destination", "transport_date", "departure_time",
    "transport_price", "yatra_price",
    "hotel_id", "hotel_name", "hotel_category", "hotel_price_per_night", "hotel_nights", "hotel_total",
    "sightseeing_places",
    "total_price", "status", "created_at",
]
USERS_COLUMNS = ["username", "password_hash", "display_name", "created_at"]


def _build_live(dataset_path, live_path, date_column):
    if not os.path.exists(live_path):
        df = pd.read_csv(dataset_path)
        today = date.today()
        df[date_column] = df["day_offset"].apply(lambda d: (today + timedelta(days=int(d))).isoformat())
        df = df.drop(columns=["day_offset"])
        df.to_csv(live_path, index=False)


def ensure_live_data():
    """Create the mutable 'live' CSVs from the static dataset CSVs on first run."""
    os.makedirs(DATA_DIR, exist_ok=True)

    _build_live(YATRA_DATASET, YATRA_LIVE, "slot_date")
    _build_live(FLIGHTS_DATASET, FLIGHTS_LIVE, "flight_date")
    _build_live(TRAINS_DATASET, TRAINS_LIVE, "travel_date")
    _build_live(BUSES_DATASET, BUSES_LIVE, "travel_date")
    _build_live(HOTELS_DATASET, HOTELS_LIVE, "stay_date")

    if not os.path.exists(USERS_LIVE):
        if os.path.exists(USERS_DATASET):
            df = pd.read_csv(USERS_DATASET)
        else:
            df = pd.DataFrame(columns=USERS_COLUMNS)
        df.to_csv(USERS_LIVE, index=False)

    if not os.path.exists(BOOKINGS_FILE):
        pd.DataFrame(columns=BOOKINGS_COLUMNS).to_csv(BOOKINGS_FILE, index=False)


def search_yatra_slots(start_date, end_date, category=None, min_seats=1):
    ensure_live_data()
    df = pd.read_csv(YATRA_LIVE)
    mask = (df["slot_date"] >= start_date) & (df["slot_date"] <= end_date) & (df["seats_available"] >= min_seats)
    if category:
        mask &= df["category"] == category
    result = df[mask].sort_values(["slot_date", "price"])
    return result.to_dict("records")


def search_flights(origin, start_date, end_date, min_seats=1):
    ensure_live_data()
    df = pd.read_csv(FLIGHTS_LIVE)
    mask = (
        (df["origin"] == origin)
        & (df["flight_date"] >= start_date) & (df["flight_date"] <= end_date)
        & (df["seats_available"] >= min_seats)
    )
    result = df[mask].sort_values(["flight_date", "price"]).rename(columns={"flight_date": "travel_date"})
    records = result.to_dict("records")
    for r in records:
        r["mode"] = "flight"
        r["operator"] = r.pop("airline")
        r["transport_no"] = r.pop("flight_no")
    return records


def search_trains(origin, start_date, end_date, min_seats=1):
    ensure_live_data()
    df = pd.read_csv(TRAINS_LIVE)
    mask = (
        (df["origin"] == origin)
        & (df["travel_date"] >= start_date) & (df["travel_date"] <= end_date)
        & (df["seats_available"] >= min_seats)
    )
    result = df[mask].sort_values(["travel_date", "price"])
    records = result.to_dict("records")
    for r in records:
        r["mode"] = "train"
        r["operator"] = "Indian Railways"
        r["transport_no"] = f'{r.pop("train_no")} ({r.pop("travel_class")})'
    return records



def search_buses(origin, start_date, end_date, min_seats=1):
    ensure_live_data()
    df = pd.read_csv(BUSES_LIVE)
    mask = (
        (df["origin"] == origin)
        & (df["travel_date"] >= start_date) & (df["travel_date"] <= end_date)
        & (df["seats_available"] >= min_seats)
    )
    result = df[mask].sort_values(["travel_date", "price"])
    records = result.to_dict("records")
    for r in records:
        r["mode"] = "bus"
        r["transport_no"] = r.pop("operator")
        r["operator"] = r["transport_no"]
    return records


def search_hotels(check_in_date, category=None, min_rooms=1):
    """Searches hotels available on a given check-in date (bookings are
    modeled as a single stay-date snapshot per property - the same
    property/price row is reused across the length of stay, since real
    per-night rate variation data isn't available; see README)."""
    ensure_live_data()
    df = pd.read_csv(HOTELS_LIVE)
    mask = (df["stay_date"] == check_in_date) & (df["rooms_available"] >= min_rooms)
    if category:
        mask &= df["category"] == category
    result = df[mask].sort_values(["price_per_night"])
    return result.to_dict("records")


def get_distinct_origins():
    """All cities served by at least one transport mode."""
    ensure_live_data()
    origins = set()
    for path in (FLIGHTS_LIVE, TRAINS_LIVE, BUSES_LIVE):
        origins |= set(pd.read_csv(path)["origin"].unique().tolist())
    return sorted(origins)


def _load_bookings_df():
    if airtable_store.is_configured():
        return airtable_store.read_df("bookings", BOOKINGS_COLUMNS)
    ensure_live_data()
    return pd.read_csv(BOOKINGS_FILE)


def create_booking(user_name, pax_count, yatra_slot, transport, total_price, hotel=None, hotel_nights=0,
                    sightseeing_places=None):
    """
    yatra_slot: dict from search_yatra_slots (has id, category, slot_date, slot_time, price)
    transport: dict from search_flights/search_trains/search_buses (has mode,
               transport_no, operator, origin, destination, travel_date,
               departure_time, price, seats_available)
    hotel: optional dict from search_hotels (has id, name, category,
           price_per_night, rooms_available). One room is booked
           regardless of pax_count (simplification - see README).
    hotel_nights: number of nights, used only for the total_price already
                  computed by the caller and for display in the booking.
    sightseeing_places: optional list of place names (from
               explore_data.get_places()) the pilgrim plans to visit
               after darshan. Informational only - not bookable/priced,
               same as the rest of the Explore Katra content - so it
               doesn't affect total_price. Stored as a single
               semicolon-joined string for simple CSV/Airtable storage.
    """
    ensure_live_data()
    booking_id = "VD" + uuid.uuid4().hex[:8].upper()

    if yatra_slot and yatra_slot.get("id"):
        slots = pd.read_csv(YATRA_LIVE)
        idx = slots.index[slots["id"] == yatra_slot["id"]]
        if len(idx) and slots.loc[idx[0], "seats_available"] >= pax_count:
            slots.loc[idx[0], "seats_available"] -= pax_count
            slots.to_csv(YATRA_LIVE, index=False)

    live_map = {"flight": FLIGHTS_LIVE, "train": TRAINS_LIVE, "bus": BUSES_LIVE}
    live_path = live_map.get(transport.get("mode"))
    if live_path and transport.get("id"):
        tdf = pd.read_csv(live_path)
        idx = tdf.index[tdf["id"] == transport["id"]]
        if len(idx) and tdf.loc[idx[0], "seats_available"] >= pax_count:
            tdf.loc[idx[0], "seats_available"] -= pax_count
            tdf.to_csv(live_path, index=False)

    if hotel and hotel.get("id"):
        hdf = pd.read_csv(HOTELS_LIVE)
        idx = hdf.index[hdf["id"] == hotel["id"]]
        if len(idx) and hdf.loc[idx[0], "rooms_available"] >= 1:
            hdf.loc[idx[0], "rooms_available"] -= 1
            hdf.to_csv(HOTELS_LIVE, index=False)

    new_row = {
        "booking_id": booking_id,
        "user_name": user_name,
        "pax_count": pax_count,
        "yatra_slot_id": yatra_slot.get("id") if yatra_slot else None,
        "category": yatra_slot.get("category") if yatra_slot else None,
        "slot_date": yatra_slot.get("slot_date") if yatra_slot else None,
        "slot_time": yatra_slot.get("slot_time") if yatra_slot else None,
        "transport_mode": transport.get("mode"),
        "transport_no": transport.get("transport_no"),
        "transport_operator": transport.get("operator"),
        "origin": transport.get("origin"),
        "destination": transport.get("destination"),
        "transport_date": transport.get("travel_date"),
        "departure_time": transport.get("departure_time"),
        "transport_price": transport.get("price"),
        "yatra_price": yatra_slot.get("price") if yatra_slot else None,
        "hotel_id": hotel.get("id") if hotel else None,
        "hotel_name": hotel.get("name") if hotel else None,
        "hotel_category": hotel.get("category") if hotel else None,
        "hotel_price_per_night": hotel.get("price_per_night") if hotel else None,
        "hotel_nights": hotel_nights if hotel else None,
        "hotel_total": (hotel.get("price_per_night", 0) * hotel_nights) if hotel else None,
        "sightseeing_places": "; ".join(sightseeing_places) if sightseeing_places else None,
        "total_price": total_price,
        "status": "CONFIRMED",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    if airtable_store.is_configured():
        airtable_store.append_row("bookings", BOOKINGS_COLUMNS, new_row)
    else:
        bookings = pd.read_csv(BOOKINGS_FILE)
        bookings = pd.concat([bookings, pd.DataFrame([new_row])], ignore_index=True)
        bookings.to_csv(BOOKINGS_FILE, index=False)

    return booking_id


def get_booking(booking_id):
    ensure_live_data()
    bookings = _load_bookings_df()
    row = bookings[bookings["booking_id"] == booking_id]
    if row.empty:
        return None
    return row.iloc[0].to_dict()


def list_bookings(user_name=None):
    ensure_live_data()
    bookings = _load_bookings_df()
    if bookings.empty:
        return []
    if user_name:
        bookings = bookings[bookings["user_name"] == user_name]
        if bookings.empty:
            return []
    return bookings.sort_values("created_at", ascending=False).to_dict("records")


# ---------------------------------------------------------------------
# User accounts (demo auth for the login page)
# ---------------------------------------------------------------------

def _hash_pw(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _load_users_df():
    if airtable_store.is_configured():
        df = airtable_store.read_df("users", USERS_COLUMNS)
        if os.path.exists(USERS_DATASET):
            seed = pd.read_csv(USERS_DATASET)
            df = pd.concat([seed, df], ignore_index=True).drop_duplicates("username", keep="last")
        return df
    ensure_live_data()
    return pd.read_csv(USERS_LIVE)


def create_user(username, password, display_name):
    username = username.strip().lower()
    if not username or not password:
        return False, "Username and password are required."

    users = _load_users_df()
    if (users["username"] == username).any():
        return False, "That username is already taken."

    new_row = {
        "username": username,
        "password_hash": _hash_pw(password),
        "display_name": display_name.strip() or username,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    if airtable_store.is_configured():
        airtable_store.append_row("users", USERS_COLUMNS, new_row)
    else:
        ensure_live_data()
        users = pd.read_csv(USERS_LIVE)
        users = pd.concat([users, pd.DataFrame([new_row])], ignore_index=True)
        users.to_csv(USERS_LIVE, index=False)

    return True, None


def verify_user(username, password):
    username = username.strip().lower()
    users = _load_users_df()
    match = users[users["username"] == username]
    if match.empty:
        return None
    if str(match.iloc[0]["password_hash"]) == _hash_pw(password):
        return match.iloc[0]["display_name"]
    return None
