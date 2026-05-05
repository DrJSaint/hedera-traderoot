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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import app.db as main_db
from scripts.pipeline.staging_db import get_connection as staging_conn
from scripts.pipeline.county_config import COUNTY_INFO, LONDON_SIGNALS, LONDON_BOUNDS, in_bounds

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


def categorise(address: str, county_key: str, lat: float = None, lon: float = None) -> str:
    """Return 'keep', 'london', or 'out_of_county'.
    Uses lat/lon bounding box first; falls back to postcode regex."""
    if address and re.search(r"\bBC\b|Canada", address, re.IGNORECASE):
        return "out_of_county"

    info = COUNTY_INFO.get(county_key)

    if lat is not None and lon is not None:
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
            "bucket":     categorise(address, county_key, s["latitude"], s["longitude"]),
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
            print(f"  {r['name'][:37]:<38} {r['type'][:17]:<18}  {(r['address'] or '(no address)')[:60]}")

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
