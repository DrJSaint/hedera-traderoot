"""
Restore legitimate Essex suppliers from offcuts back into the live database.
These were moved by audit_county.py because Southend-on-Sea, Thurrock etc.
fall outside the strict Essex administrative polygon.

Usage:
    python scripts/pipeline/restore_essex_offcuts.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.pipeline.live_db_helpers import begin, connect, execute, fetch_all, fetch_one, fetch_scalar

RESTORE_NAMES = [
    "CED Stone Landscape - Vange Park Depot",
    "Elm Horticulture Ltd",
    "Essex Fencing Ltd",
    "Highgate Furniture",
    "Leigh Lighting",
    "Lightstyle",
    "Luxury Chandeliers & Lighting | Light Trend Ltd.",
    "SBR Supplies Ltd",
]

with begin() as conn:
    area_id = fetch_scalar(
        conn,
        "SELECT id FROM areas WHERE LOWER(name) = 'essex'",
    )
    if not area_id:
        sys.exit("Essex area not found in database.")

    for name in RESTORE_NAMES:
        row = fetch_one(
            conn,
            "SELECT * FROM offcuts WHERE name ILIKE :name AND original_county = 'Essex'",
            {"name": f"%{name}%"},
        )
        if not row:
            print(f"  NOT FOUND in offcuts: {name}")
            continue

        # Re-insert into suppliers
        result = conn.execute(
            __import__('sqlalchemy').text(
                """INSERT INTO suppliers
                    (name, type, website, phone, email, price_band, notes,
                     address, latitude, longitude, trade)
                   VALUES (:name, :type, :website, :phone, :email, :price_band,
                           :notes, :address, :latitude, :longitude, 0)
                   RETURNING id"""
            ),
            {
                "name":       row["name"],
                "type":       row["type"],
                "website":    row["website"],
                "phone":      row["phone"],
                "email":      row["email"],
                "price_band": row["price_band"],
                "notes":      row["notes"],
                "address":    row["address"],
                "latitude":   row["latitude"],
                "longitude":  row["longitude"],
            },
        )
        new_id = result.scalar_one()

        # Link to Essex area
        conn.execute(
            __import__('sqlalchemy').text(
                "INSERT INTO supplier_areas (supplier_id, area_id) VALUES (:sid, :aid)"
            ),
            {"sid": new_id, "aid": area_id},
        )
        conn.execute(
            __import__('sqlalchemy').text(
                "UPDATE suppliers SET primary_area_id = :aid WHERE id = :sid"
            ),
            {"aid": area_id, "sid": new_id},
        )

        # Remove from offcuts
        conn.execute(
            __import__('sqlalchemy').text("DELETE FROM offcuts WHERE id = :id"),
            {"id": row["id"]},
        )

        print(f"  RESTORED: {row['name']}")

print("\nDone.")
