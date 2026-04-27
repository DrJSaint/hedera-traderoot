"""
Audit and clean up Surrey-tagged suppliers in traderoot.db.

Usage:
    python scripts/pipeline/audit_surrey.py           # print report
    python scripts/pipeline/audit_surrey.py --apply   # move non-Surrey suppliers to offcuts table
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import app.db as main_db
from scripts.pipeline.staging_db import get_connection as staging_conn

# Postcodes that confirm a Surrey (county) address.
#   GU1-10, GU15-27  Guildford/Woking/Farnham/Camberley (GU11-14 = Aldershot/Farnborough = Hants)
#   KT6-8, KT10-24   Surrey Elmbridge + wider Surrey (KT1-5,9 = London)
#   RH1-14           Reigate/Redhill/Horsham border
#   TW15-20          Staines-upon-Thames area (Surrey, not London)
SURREY_SIGNALS = re.compile(
    r"\bSurrey\b"
    r"|GU([1-9]|10|1[5-9]|2[0-7])\b"
    r"|KT([6-8]|1[0-9]|2[0-4])\b"
    r"|RH([1-9]|1[0-4])\b"
    r"|TW(1[5-9]|20)\b",
    re.IGNORECASE,
)

# Strings that mark a Greater London address.
# Negative lookahead avoids matching "London Rd/Road/Street" (common street names in Surrey).
LONDON_SIGNALS = re.compile(
    r"\bLondon(?!\s+R(?:oad?|d\.?)\b|\s+St(?:reet)?\b|\s+(?:Ln|Lane|Way|Ave|Cl)\b)\b"
    r"|\b(SW|SE|EC|WC|NW)[0-9]"
    r"|\bW[1-9]\b|\bW1[0-9]\b"
    r"|\bN[1-9]\b|\bN1[0-9]\b"
    r"|\bE[1-9]\b|\bE1[0-9]\b",
    re.IGNORECASE,
)

OFFCUTS_DDL = """
CREATE TABLE IF NOT EXISTS offcuts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    original_id   INTEGER NOT NULL,
    name          TEXT NOT NULL,
    type          TEXT,
    website       TEXT,
    phone         TEXT,
    email         TEXT,
    price_band    TEXT,
    notes         TEXT,
    latitude      REAL,
    longitude     REAL,
    address       TEXT,
    offcut_reason TEXT NOT NULL,   -- 'out_of_county' or 'london'
    inferred_area TEXT,            -- 'Greater London' for london bucket
    archived_at   TEXT DEFAULT (datetime('now'))
);
"""


def categorise(address: str) -> str:
    """Return 'keep', 'london', or 'out_of_county'."""
    if not address:
        return "out_of_county"
    if re.search(r"\bBC\b|Canada", address, re.IGNORECASE):
        return "out_of_county"
    if SURREY_SIGNALS.search(address):
        return "keep"
    if LONDON_SIGNALS.search(address):
        return "london"
    return "out_of_county"


def load_data():
    mconn = main_db.get_connection()
    sconn = staging_conn()

    surrey_rows = mconn.execute("""
        SELECT s.id, s.name, s.type, s.website, s.phone, s.email,
               s.price_band, s.notes, s.latitude, s.longitude
        FROM suppliers s
        JOIN supplier_areas sa ON sa.supplier_id = s.id
        JOIN areas a ON a.id = sa.area_id
        WHERE LOWER(a.name) = 'surrey'
        ORDER BY s.name
    """).fetchall()

    results = []
    for s in surrey_rows:
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
            "bucket":     categorise(address),
        })

    mconn.close()
    sconn.close()
    return results


def print_report(rows):
    buckets = {"keep": [], "london": [], "out_of_county": []}
    for r in rows:
        buckets[r["bucket"]].append(r)

    labels = {
        "keep":         ("KEEP         -- Surrey address confirmed",    "+"),
        "london":       ("OFFCUTS/LON  -- London address (relabelled)", "L"),
        "out_of_county":("OFFCUTS/OUT  -- Clearly out of county",       "X"),
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
            name  = r["name"][:37]
            stype = r["type"][:17]
            addr  = (r["address"] or "(no address)")[:60]
            print(f"  {name:<38} {stype:<18}  {addr}")

    total_offcuts = len(buckets["london"]) + len(buckets["out_of_county"])
    print(f"\n{'-'*80}")
    print(f"  SUMMARY:  keep={len(buckets['keep'])}  "
          f"offcuts/london={len(buckets['london'])}  "
          f"offcuts/out_of_county={len(buckets['out_of_county'])}  "
          f"total moving to offcuts={total_offcuts}")
    print(f"  Run with --apply to move non-Surrey suppliers to the offcuts table.")
    print(f"{'-'*80}\n")


def apply_cleanup(rows):
    to_offcut = [r for r in rows if r["bucket"] != "keep"]

    if not to_offcut:
        print("Nothing to move.")
        return

    london_count    = sum(1 for r in to_offcut if r["bucket"] == "london")
    other_count     = sum(1 for r in to_offcut if r["bucket"] == "out_of_county")
    print(f"\nAbout to move {len(to_offcut)} suppliers to offcuts "
          f"({london_count} London -> inferred_area=Greater London, "
          f"{other_count} out-of-county):")
    for r in to_offcut:
        tag = "[LON]" if r["bucket"] == "london" else "[OUT]"
        print(f"  {tag}  {r['name'][:50]}  |  {r['address'][:55]}")

    confirm = input("\nProceed? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    mconn = main_db.get_connection()
    mconn.execute(OFFCUTS_DDL)

    surrey_id = mconn.execute(
        "SELECT id FROM areas WHERE LOWER(name) = 'surrey'"
    ).fetchone()[0]

    moved = 0
    for r in to_offcut:
        inferred = "Greater London" if r["bucket"] == "london" else None

        mconn.execute("""
            INSERT INTO offcuts
                (original_id, name, type, website, phone, email,
                 price_band, notes, latitude, longitude, address,
                 offcut_reason, inferred_area)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            r["id"], r["name"], r["type"], r["website"], r["phone"],
            r["email"], r["price_band"], r["notes"],
            r["latitude"], r["longitude"], r["address"],
            r["bucket"], inferred,
        ))

        other_areas = mconn.execute(
            """SELECT COUNT(*) FROM supplier_areas sa
               JOIN areas a ON a.id = sa.area_id
               WHERE sa.supplier_id = ? AND LOWER(a.name) != 'surrey'""",
            (r["id"],)
        ).fetchone()[0]

        if other_areas > 0:
            mconn.execute(
                "DELETE FROM supplier_areas WHERE supplier_id = ? AND area_id = ?",
                (r["id"], surrey_id)
            )
        else:
            mconn.execute("DELETE FROM suppliers WHERE id = ?", (r["id"],))

        moved += 1

    mconn.commit()
    mconn.close()
    print(f"\nDone. {moved} suppliers moved to offcuts table.")


if __name__ == "__main__":
    args  = sys.argv[1:]
    apply = "--apply" in args

    rows = load_data()
    print_report(rows)

    if apply:
        apply_cleanup(rows)
