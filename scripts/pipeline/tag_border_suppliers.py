"""
Tag suppliers to additional counties when their lat/lon falls within
multiple county polygons.

Primary mode uses static/data/counties.geojson (polygon matching via Shapely).
If GeoJSON/Shapely is unavailable, falls back to the historical bounds logic.

Run after each county import to keep border suppliers multi-tagged.

Usage:
    python scripts/pipeline/tag_border_suppliers.py          # report only
    python scripts/pipeline/tag_border_suppliers.py --apply  # write tags
"""

import math
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import app.db as main_db
from scripts.pipeline.county_config import COUNTY_INFO, LONDON_BOUNDS, in_bounds


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


def bounds_counties_for_point(lat: float, lon: float, county_keys: list[str] = None) -> list[str]:
    matches = []
    keys = county_keys or list(COUNTY_INFO.keys())
    for county_key in keys:
        info = COUNTY_INFO[county_key]
        if not in_bounds(lat, lon, info["bounds"]):
            continue

        # Surrey's box overlaps Greater London — skip London-located suppliers
        if county_key == "surrey" and in_bounds(lat, lon, LONDON_BOUNDS):
            continue

        matches.append(county_display_name(county_key))
    return matches


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

    def match_counties(lat: float, lon: float) -> list[str]:
        point = Point(float(lon), float(lat))
        return [display for display, prepared in prepared_by_display.items() if prepared.intersects(point)]

    return match_counties, missing_keys


def find_extra_tags(dry_run: bool = True):
    conn = main_db.get_connection()

    match_counties = None
    missing_polygon_keys = []
    mode = "bounds"
    try:
        match_counties, missing_polygon_keys = build_polygon_matcher()
        mode = "polygon"
        print("Using polygon county matching from static/data/counties.geojson")
        if missing_polygon_keys:
            missing_display = ", ".join(sorted(county_display_name(k) for k in missing_polygon_keys))
            print(f"Polygon data missing for: {missing_display}")
            print("Falling back to bounds checks for the missing counties only.")
    except Exception as exc:
        print(f"Polygon matching unavailable ({exc}); using bounds fallback.")

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

        matched = set()
        if match_counties:
            matched.update(match_counties(lat, lon))
            if missing_polygon_keys:
                matched.update(bounds_counties_for_point(lat, lon, county_keys=missing_polygon_keys))
        else:
            matched.update(bounds_counties_for_point(lat, lon))

        for county_display in matched:

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
    print(f"Matching mode: {mode}\n")
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
