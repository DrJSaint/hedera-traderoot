"""
Audit and clean up suppliers tagged to a given county in traderoot.db.
Non-matching suppliers are moved to the offcuts table (never deleted).
London suppliers are relabelled inferred_area='Greater London' in offcuts.

Usage:
    python scripts/pipeline/audit_county.py "West Sussex"           # report only
    python scripts/pipeline/audit_county.py "West Sussex" --apply   # move to offcuts
"""

import os
import re
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import app.db as main_db
from scripts.pipeline.staging_db import get_connection as staging_conn
from scripts.pipeline.county_config import COUNTY_INFO, LONDON_SIGNALS, LONDON_BOUNDS, in_bounds


COUNTY_GEOJSON_MAP = {
    "london": [
        "Barking and Dagenham", "Barnet", "Bexley", "Brent", "Bromley", "Camden",
        "City of London", "Croydon", "Ealing", "Enfield", "Greenwich", "Hackney",
        "Hammersmith and Fulham", "Haringey", "Harrow", "Havering", "Hillingdon",
        "Hounslow", "Islington", "Kensington and Chelsea", "Kingston upon Thames",
        "Lambeth", "Lewisham", "Merton", "Newham", "Redbridge", "Richmond upon Thames",
        "Southwark", "Sutton", "Tower Hamlets", "Waltham Forest", "Wandsworth", "Westminster",
    ],
    "berkshire": [
        "Bracknell Forest", "Reading", "Slough", "West Berkshire", "Windsor and Maidenhead", "Wokingham",
    ],
    "east sussex": ["East Sussex", "Brighton and Hove"],
    "bedfordshire": ["Bedford", "Central Bedfordshire", "Luton"],
}


def county_display_name(county_key: str) -> str:
    return " ".join(w.capitalize() for w in county_key.split())


def build_polygon_matcher():
    from shapely.geometry import Point, shape
    from shapely.ops import unary_union
    from shapely.prepared import prep

    root = Path(__file__).resolve().parents[2]
    geojson_path = root / "static" / "data" / "counties.geojson"
    if not geojson_path.exists():
        raise FileNotFoundError(f"GeoJSON file not found: {geojson_path}")

    with geojson_path.open("r", encoding="utf-8") as f:
        geojson = json.load(f)

    name_to_geom = {}
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        name = (
            props.get("CTYUA24NM")
            or props.get("CTYUA23NM")
            or props.get("CTYUA22NM")
            or props.get("ctyua23nm")
            or props.get("name")
            or props.get("NAME")
        )
        geom = feature.get("geometry")
        if not name or not geom:
            continue
        name_to_geom[name.lower()] = shape(geom)

    prepared_by_display = {}
    missing_keys = []
    for county_key in COUNTY_INFO.keys():
        display = county_display_name(county_key)
        geo_names = COUNTY_GEOJSON_MAP.get(county_key, [display])
        geoms = [name_to_geom[n.lower()] for n in geo_names if n.lower() in name_to_geom]
        if not geoms:
            missing_keys.append(county_key)
            continue

        merged = unary_union(geoms) if len(geoms) > 1 else geoms[0]
        prepared_by_display[display] = prep(merged)

    if not prepared_by_display:
        raise RuntimeError("No county polygon geometries could be prepared from GeoJSON")

    missing_displays = {county_display_name(k) for k in missing_keys}

    def match_counties(lat: float, lon: float) -> tuple[set[str], set[str]]:
        point = Point(float(lon), float(lat))
        polygon_matches = {display for display, prepared in prepared_by_display.items() if prepared.intersects(point)}
        return polygon_matches, missing_displays

    return match_counties

OFFCUTS_DDL = """
CREATE TABLE IF NOT EXISTS offcuts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    original_id    INTEGER NOT NULL,
    name           TEXT NOT NULL,
    type           TEXT,
    website        TEXT,
    phone          TEXT,
    email          TEXT,
    price_band     TEXT,
    notes          TEXT,
    latitude       REAL,
    longitude      REAL,
    address        TEXT,
    original_county TEXT,
    offcut_reason  TEXT NOT NULL,   -- 'out_of_county' or 'london'
    inferred_area  TEXT,            -- 'Greater London' for london bucket
    archived_at    TEXT DEFAULT (datetime('now'))
);
"""

# Migrate: add original_county column if an older offcuts table exists without it
MIGRATE_DDL = "ALTER TABLE offcuts ADD COLUMN original_county TEXT"


def safe_console_text(text: str) -> str:
    """Return text safe for current stdout encoding (Windows cp1252-safe)."""
    enc = (getattr(sys.stdout, "encoding", None) or "utf-8")
    return text.encode(enc, errors="replace").decode(enc, errors="replace")


def categorise(
    address: str,
    county_key: str,
    lat: float = None,
    lon: float = None,
    polygon_matcher=None,
) -> str:
    """Return 'keep', 'london', or 'out_of_county'.
    Uses lat/lon bounding box first; falls back to postcode regex."""
    if address and re.search(r"\bBC\b|Canada", address, re.IGNORECASE):
        return "out_of_county"

    info = COUNTY_INFO.get(county_key)
    target_display = county_display_name(county_key)

    if lat is not None and lon is not None:
        if polygon_matcher:
            polygon_matches, missing_displays = polygon_matcher(lat, lon)
            fallback_needed = target_display in missing_displays or "London" in missing_displays

            if target_display in polygon_matches:
                return "keep"
            if county_key != "london" and "London" in polygon_matches:
                return "london"
            if county_key == "london" and polygon_matches:
                return "out_of_county"
            if polygon_matches:
                return "out_of_county"

            # No polygon match found. If key polygons are missing, fall back to bounds/regex.
            if not fallback_needed:
                return "out_of_county"

        if info and in_bounds(lat, lon, info["bounds"]):
            if county_key == "surrey":
                if info["signals"].search(address or ""):
                    return "keep"
                # Within Surrey's box but no Surrey postcode — could be a London
                # borough or a West Sussex border town (Crawley, Horsham)
                return "london" if in_bounds(lat, lon, LONDON_BOUNDS) else "out_of_county"
            return "keep"
        if in_bounds(lat, lon, LONDON_BOUNDS):
            if county_key == "london":
                return "keep"
            return "london"
        return "out_of_county"

    # Fallback: postcode regex
    if info and info["signals"].search(address or ""):
        return "keep"
    if LONDON_SIGNALS.search(address or ""):
        if county_key == "london":
            return "keep"
        return "london"
    return "out_of_county"


def load_data(county: str) -> list[dict]:
    mconn = main_db.get_connection()
    sconn = staging_conn()

    polygon_matcher = None
    try:
        polygon_matcher = build_polygon_matcher()
        print("Using polygon county matching from static/data/counties.geojson")
    except Exception as exc:
        print(f"Polygon matching unavailable ({exc}); using bounds/regex fallback.")

    rows = mconn.execute("""
        SELECT s.id, s.name, s.type, s.website, s.phone, s.email,
               s.price_band, s.notes, s.latitude, s.longitude
        FROM suppliers s
        JOIN supplier_areas sa ON sa.supplier_id = s.id
        JOIN areas a ON a.id = sa.area_id
        WHERE LOWER(a.name) = LOWER(?)
        ORDER BY s.name
    """, (county,)).fetchall()

    county_key = county.lower()
    results = []
    for s in rows:
        pipe_row = sconn.execute(
            "SELECT address FROM raw_places WHERE LOWER(name) = LOWER(?)",
            (s["name"],)
        ).fetchone()
        address = pipe_row["address"] if pipe_row else ""
        results.append({
            "id":         s["id"],
            "name":       s["name"],
            "type":       s["type"],
            "website":    s["website"],
            "phone":      s["phone"],
            "email":      s["email"],
            "price_band": s["price_band"],
            "notes":      s["notes"],
            "latitude":   s["latitude"],
            "longitude":  s["longitude"],
            "address":    address,
            "bucket":     categorise(
                address,
                county_key,
                s["latitude"],
                s["longitude"],
                polygon_matcher=polygon_matcher,
            ),
        })

    mconn.close()
    sconn.close()
    return results


def print_report(rows: list[dict], county: str):
    buckets = {"keep": [], "london": [], "out_of_county": []}
    for r in rows:
        buckets[r["bucket"]].append(r)

    labels = {
        "keep":          ("KEEP         -- county address confirmed",    "+"),
        "london":        ("OFFCUTS/LON  -- London address (relabelled)", "L"),
        "out_of_county": ("OFFCUTS/OUT  -- Clearly out of county",       "X"),
    }

    for key in ("keep", "london", "out_of_county"):
        group = buckets[key]
        title, icon = labels[key]
        print(f"\n{'-'*80}")
        print(f"  [{icon}]  {title}  ({len(group)} suppliers)")
        print(f"{'-'*80}")
        print(f"  {'NAME':<38} {'TYPE':<18}  ADDRESS")
        print(f"  {'-'*37} {'-'*17}  {'-'*40}")
        for r in sorted(group, key=lambda x: x["name"]):
            line = f"  {r['name'][:37]:<38} {r['type'][:17]:<18}  {(r['address'] or '(no address)')[:60]}"
            print(safe_console_text(line))

    total_offcuts = len(buckets["london"]) + len(buckets["out_of_county"])
    print(f"\n{'-'*80}")
    print(f"  {county} SUMMARY:  keep={len(buckets['keep'])}  "
          f"offcuts/london={len(buckets['london'])}  "
          f"offcuts/out_of_county={len(buckets['out_of_county'])}  "
          f"total to offcuts={total_offcuts}")
    if COUNTY_INFO.get(county.lower()):
        print(f"  (postcode signals configured for this county)")
    else:
        print(f"  WARNING: no postcode config for '{county}' -- all suppliers kept")
    print(f"  Run with --apply to move non-county suppliers to offcuts.")
    print(f"{'-'*80}\n")


def apply_cleanup(rows: list[dict], county: str):
    to_offcut = [r for r in rows if r["bucket"] != "keep"]
    if not to_offcut:
        print("Nothing to move.")
        return

    london_count = sum(1 for r in to_offcut if r["bucket"] == "london")
    other_count  = sum(1 for r in to_offcut if r["bucket"] == "out_of_county")
    print(f"\nAbout to move {len(to_offcut)} suppliers to offcuts "
          f"({london_count} London, {other_count} out-of-county):")
    for r in to_offcut:
        tag = "[LON]" if r["bucket"] == "london" else "[OUT]"
        print(f"  {tag}  {r['name'][:50]}  |  {(r['address'] or '')[:55]}")

    confirm = input("\nProceed? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    mconn = main_db.get_connection()
    mconn.execute(OFFCUTS_DDL)
    try:
        mconn.execute(MIGRATE_DDL)
        mconn.commit()
    except Exception:
        pass  # column already exists

    area_row = mconn.execute(
        "SELECT id FROM areas WHERE LOWER(name) = LOWER(?)", (county,)
    ).fetchone()
    if not area_row:
        print(f"Area '{county}' not found in database. Aborted.")
        return
    area_id = area_row[0]

    moved = 0
    for r in to_offcut:
        inferred = "Greater London" if r["bucket"] == "london" else None
        mconn.execute("""
            INSERT INTO offcuts
                (original_id, name, type, website, phone, email,
                 price_band, notes, latitude, longitude, address,
                 original_county, offcut_reason, inferred_area)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            r["id"], r["name"], r["type"], r["website"], r["phone"],
            r["email"], r["price_band"], r["notes"],
            r["latitude"], r["longitude"], r["address"],
            county, r["bucket"], inferred,
        ))

        other_areas = mconn.execute(
            """SELECT COUNT(*) FROM supplier_areas sa
               JOIN areas a ON a.id = sa.area_id
               WHERE sa.supplier_id = ? AND a.id != ?""",
            (r["id"], area_id)
        ).fetchone()[0]

        if other_areas > 0:
            mconn.execute(
                "DELETE FROM supplier_areas WHERE supplier_id = ? AND area_id = ?",
                (r["id"], area_id)
            )
        else:
            mconn.execute("DELETE FROM suppliers WHERE id = ?", (r["id"],))

        moved += 1

    mconn.commit()
    mconn.close()
    print(f"\nDone. {moved} suppliers moved to offcuts table.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        sys.exit("Usage: python audit_county.py <county> [--apply]")

    county = args[0]
    apply  = "--apply" in args

    if county.lower() not in COUNTY_INFO:
        print(f"Warning: '{county}' not in COUNTY_INFO. Add it to county_config.py first.")

    rows = load_data(county)
    print_report(rows, county)

    if apply:
        apply_cleanup(rows, county)
