"""
Remove true duplicate suppliers: identical name (case-insensitive) + phone + email.
Keeps the entry that has the most reviews; ties broken by lowest ID.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.db as db


def run():
    conn = db.get_connection()

    # Find duplicate groups
    rows = conn.execute("""
        SELECT LOWER(name) AS lname, phone, email, COUNT(*) AS cnt
        FROM suppliers
        GROUP BY LOWER(name), phone, email
        HAVING cnt > 1
    """).fetchall()

    if not rows:
        print("No duplicates found.")
        conn.close()
        return

    print(f"Found {len(rows)} duplicate group(s).\n")
    deleted_total = 0

    for dup in rows:
        members = conn.execute("""
            SELECT s.id, s.name,
                   COUNT(r.id) AS review_count
            FROM suppliers s
            LEFT JOIN reviews r ON r.supplier_id = s.id
            WHERE LOWER(s.name) = ? AND s.phone IS ? AND s.email IS ?
            GROUP BY s.id
            ORDER BY review_count DESC, s.id ASC
        """, (dup["lname"], dup["phone"], dup["email"])).fetchall()

        keep = members[0]
        to_delete = members[1:]

        print(f"Group: '{members[0]['name']}' ({len(members)} copies)")
        print(f"  Keeping  id={keep['id']} (reviews={keep['review_count']})")
        for m in to_delete:
            print(f"  Deleting id={m['id']} (reviews={m['review_count']})")
            conn.execute("DELETE FROM suppliers WHERE id = ?", (m["id"],))
            deleted_total += 1

    conn.commit()
    conn.close()
    print(f"\nDone. Deleted {deleted_total} duplicate row(s).")


if __name__ == "__main__":
    run()
