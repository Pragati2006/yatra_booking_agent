"""
Seed existing Yatra Booking Agent data into MongoDB Atlas.

Collections:
- tourist_attractions
- yatra_information

Safe to run multiple times: existing records are updated instead of duplicated.
"""

from mongo_db import tourist_attractions, yatra_information
import explore_data
import yatra_info


def seed_tourist_attractions():
    """Insert/update all tourism destinations from explore_data.py."""

    places = explore_data.get_places()

    inserted = 0
    updated = 0

    for place in places:
        # Use the place name as the unique identifier.
        name = place.get("name")

        if not name:
            continue

        document = {
            "name": name,
            "category": place.get("category"),
            "region": place.get("region", "Jammu"),
            "district": place.get("district"),
            "distance": place.get("distance"),
            "location_route": place.get("location_route"),
            "timings": place.get("timings"),
            "entry_fee": place.get("entry_fee"),
            "description": place.get("description"),
            "historical_background": place.get("historical_background"),
            "video_search": place.get("video_search"),
            "image": place.get("image"),
            "image_file": place.get("image_file"),
        }

        result = tourist_attractions.update_one(
            {"name": name},
            {"$set": document},
            upsert=True
        )

        if result.upserted_id:
            inserted += 1
        else:
            updated += 1

    print("\nTourist attractions:")
    print(f"  Inserted: {inserted}")
    print(f"  Updated:  {updated}")
    print(f"  Total:    {tourist_attractions.count_documents({})}")


def seed_yatra_information():
    """Insert/update Yatra information from yatra_info.py."""

    records = [
        {
            "topic": "aarti_timings",
            "title": "Aarti Timings",
            "content": yatra_info.get_aarti_timings(),
            "category": "Yatra Essentials",
        },
        {
            "topic": "registration",
            "title": "Yatra Registration",
            "content": yatra_info.get_registration_info(),
            "category": "Yatra Essentials",
        },
        {
            "topic": "routes",
            "title": "Routes to Bhawan",
            "content": yatra_info.get_route_options(),
            "category": "Yatra Essentials",
        },
        {
            "topic": "facilities",
            "title": "Yatra Facilities",
            "content": yatra_info.get_facilities(),
            "category": "Yatra Essentials",
        },
        {
            "topic": "packing",
            "title": "Packing Guidance",
            "content": yatra_info.get_packing_guidance(),
            "category": "Yatra Essentials",
        },
        {
            "topic": "helpline",
            "title": "Official Yatra Helpline",
            "content": yatra_info.get_helpline(),
            "category": "Yatra Essentials",
        },
    ]

    inserted = 0
    updated = 0

    for record in records:
        result = yatra_information.update_one(
            {"topic": record["topic"]},
            {"$set": record},
            upsert=True
        )

        if result.upserted_id:
            inserted += 1
        else:
            updated += 1

    print("\nYatra information:")
    print(f"  Inserted: {inserted}")
    print(f"  Updated:  {updated}")
    print(f"  Total:    {yatra_information.count_documents({})}")


def main():
    print("=" * 60)
    print("YATRA BOOKING AGENT - MONGODB SEED")
    print("=" * 60)

    print("\nSeeding MongoDB Atlas...")

    seed_tourist_attractions()
    seed_yatra_information()

    print("\n" + "=" * 60)
    print("SEEDING COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()