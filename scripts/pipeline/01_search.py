"""
Stage 1 — Google Places text search.

Usage:
    python scripts/pipeline/01_search.py "Surrey"
    python scripts/pipeline/01_search.py "West Sussex"

Requires env var:  GOOGLE_PLACES_KEY=<your key>

Searches Google Places for each trade keyword x county, paginates up to 3 pages,
deduplicates by place_id, validates the returned address is actually in the target
county, and stores raw results in pipeline.db.
"""

import json
import os
import sys
import time

import googlemaps

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.pipeline.staging_db import init_db, get_connection
from scripts.pipeline.county_config import COUNTY_INFO, in_bounds

SEARCH_TERMS = [
    "wholesale nursery",
    "trade nursery",
    "horticultural supplier",
    "hard landscaping supplier",
    "landscaping materials supplier",
    "garden furniture trade supplier",
    "outdoor lighting trade supplier",
    "fencing supplier trade",
    "garden tools wholesale",
]


def is_in_county(address: str, county_key: str, lat: float = None, lon: float = None) -> bool:
    """Return True if the place is in the target county.
    Prefers lat/lon bounding box; falls back to postcode regex if coords unavailable."""
    info = COUNTY_INFO.get(county_key)
    if not info:
        return True  # no config — accept everything

    if lat is not None and lon is not None:
        if not in_bounds(lat, lon, info["bounds"]):
            return False
        # Surrey's bounding box overlaps London and West Sussex border towns,
        # so also require a Surrey postcode match
        if county_key == "surrey":
            return bool(info["signals"].search(address or ""))
        return True

    # Fallback: postcode regex only
    return bool(info["signals"].search(address or ""))


def search_county(county: str):
    api_key = os.environ.get("GOOGLE_PLACES_KEY")
    if not api_key:
        sys.exit("Set GOOGLE_PLACES_KEY environment variable first.")

    county_key = county.lower()
    county_cfg = COUNTY_INFO.get(county_key)
    if county_cfg:
        location   = (county_cfg["lat"], county_cfg["lon"])
        radius_m   = county_cfg["radius_m"]
        print(f"Geographic bias: centre {location}, radius {radius_m/1000:.0f} km")
    else:
        location = None
        radius_m = None
        print(f"Warning: no county config for '{county}' — no geographic bias or address filter.")

    db_path = init_db()
    print(f"Staging DB: {db_path}")
    print(f"Searching county: {county}\n")

    gmaps     = googlemaps.Client(key=api_key)
    conn      = get_connection()
    total_new = 0
    skipped   = 0

    for term in SEARCH_TERMS:
        query = f"{term} {county} UK"
        print(f"  '{query}'", end="", flush=True)
        page_token = None
        page       = 0
        term_new   = 0

        while page < 3:
            try:
                if page_token:
                    time.sleep(2)
                    result = gmaps.places(query=query, page_token=page_token)
                elif location:
                    result = gmaps.places(query=query, location=location, radius=radius_m)
                else:
                    result = gmaps.places(query=query)
            except Exception as e:
                print(f" (pagination stopped: {e})", end="")
                break

            for place in result.get("results", []):
                place_id = place["place_id"]

                if conn.execute(
                    "SELECT 1 FROM raw_places WHERE place_id = ?", (place_id,)
                ).fetchone():
                    continue

                address = place.get("formatted_address", "")
                loc     = place.get("geometry", {}).get("location", {})
                lat     = loc.get("lat")
                lng     = loc.get("lng")
                if county_cfg and not is_in_county(address, county_key, lat, lng):
                    skipped += 1
                    continue
                conn.execute("""
                    INSERT INTO raw_places
                        (place_id, name, address, phone, website, lat, lon,
                         google_types, search_term, search_county)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    place_id,
                    place.get("name"),
                    address,
                    place.get("formatted_phone_number"),
                    None,
                    lat,
                    lng,
                    json.dumps(place.get("types", [])),
                    term,
                    county,
                ))
                term_new += 1

            conn.commit()
            page_token = result.get("next_page_token")
            page += 1
            if not page_token:
                break

        total_new += term_new
        print(f" -> {term_new} new")

    conn.close()
    total_all = get_connection().execute(
        "SELECT COUNT(*) FROM raw_places WHERE search_county = ?", (county,)
    ).fetchone()[0]
    print(f"\nDone. {total_new} new places added, {skipped} filtered out (wrong county).")
    print(f"{total_all} total in staging for {county}.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: python 01_search.py <county>")
    search_county(sys.argv[1])
