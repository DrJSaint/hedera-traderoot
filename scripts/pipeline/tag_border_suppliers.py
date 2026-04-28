"""
Tag suppliers to additional counties when their lat/lon falls within
multiple county bounding boxes.

Run after each county import to keep border suppliers multi-tagged.

Usage:
    python scripts/pipeline/tag_border_suppliers.py          # report only
    python scripts/pipeline/tag_border_suppliers.py --apply  # write tags
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import app.db as main_db
from scripts.pipeline.county_config import COUNTY_INFO, LONDON_BOUNDS, in_bounds


def find_extra_tags(dry_run: bool = True):
    conn = main_db.get_connection()

    area_rows = conn.execute("SELECT id, name FROM areas").fetchall()
    area_map  = {r["name"].lower(): r["id"] for r in area_rows}

    suppliers = conn.execute("""
        SELECT s.id, s.name, s.latitude, s.longitude,
               GROUP_CONCAT(a.name, '|') AS current_areas
        FROM suppliers s
        LEFT JOIN supplier_areas sa ON sa.supplier_id = s.id
        LEFT JOIN areas a ON a.id = sa.area_id
        WHERE s.latitude IS NOT NULL AND s.longitude IS NOT NULL
        GROUP BY s.id
    """).fetchall()

    additions = []  # (supplier_id, supplier_name, county_display, area_id)

    for s in suppliers:
        lat     = s["latitude"]
        lon     = s["longitude"]
        current = set((s["current_areas"] or "").lower().split("|"))

        for county_key, info in COUNTY_INFO.items():
            if not in_bounds(lat, lon, info["bounds"]):
                continue

            # Surrey's box overlaps Greater London — skip London-located suppliers
            if county_key == "surrey" and in_bounds(lat, lon, LONDON_BOUNDS):
                continue

            county_display = " ".join(w.capitalize() for w in county_key.split())

            if county_display.lower() in current:
                continue  # already tagged

            area_id = area_map.get(county_display.lower())
            if area_id is None:
                continue  # county not yet in areas table

            additions.append((s["id"], s["name"], county_display, area_id))

    if not additions:
        print("No border suppliers need extra tags.")
        conn.close()
        return

    by_supplier: dict[int, dict] = {}
    for sid, sname, county, _ in additions:
        by_supplier.setdefault(sid, {"name": sname, "counties": []})["counties"].append(county)

    print(f"\n{'DRY RUN -- ' if dry_run else ''}Border suppliers to multi-tag "
          f"({len(by_supplier)} suppliers, {len(additions)} new links):\n")
    for sid, data in sorted(by_supplier.items(), key=lambda x: x[1]["name"]):
        print(f"  {data['name'][:55]:<56} + {', '.join(data['counties'])}")

    if dry_run:
        print(f"\nRun with --apply to write these tags.")
        conn.close()
        return

    for sid, sname, county, area_id in additions:
        conn.execute(
            "INSERT OR IGNORE INTO supplier_areas (supplier_id, area_id) VALUES (?, ?)",
            (sid, area_id)
        )
    conn.commit()
    print(f"{len(additions)} area links added.")

    # Recalculate primary_area_id for affected suppliers using closest county centre
    area_map = {r["name"].lower(): r["id"] for r in conn.execute("SELECT id, name FROM areas").fetchall()}
    affected_ids = list({sid for sid, *_ in additions})
    recalculated = 0

    for sid in affected_ids:
        row = conn.execute("SELECT latitude, longitude FROM suppliers WHERE id = ?", (sid,)).fetchone()
        if not row or not row["latitude"]:
            continue
        lat, lon = row["latitude"], row["longitude"]
        tagged = {r["name"].lower() for r in conn.execute(
            "SELECT a.name FROM areas a JOIN supplier_areas sa ON sa.area_id = a.id WHERE sa.supplier_id = ?",
            (sid,)
        ).fetchall()}

        best_county, best_dist = None, float("inf")
        for county_key, info in COUNTY_INFO.items():
            county_display = " ".join(w.capitalize() for w in county_key.split())
            if county_display.lower() not in tagged:
                continue
            dist = math.sqrt((lat - info["lat"]) ** 2 + (lon - info["lon"]) ** 2)
            if dist < best_dist:
                best_dist, best_county = dist, county_display

        if best_county:
            area_id = area_map.get(best_county.lower())
            if area_id:
                conn.execute("UPDATE suppliers SET primary_area_id = ? WHERE id = ?", (area_id, sid))
                recalculated += 1

    conn.commit()
    conn.close()
    print(f"{recalculated} primary areas recalculated.")
    print(f"\nDone.")


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    find_extra_tags(dry_run=not apply)
