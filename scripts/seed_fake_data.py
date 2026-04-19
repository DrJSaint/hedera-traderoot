"""
Seed fake designers, reviews, and random categories for demo purposes.
Run from scripts/ folder: python seed_fake_data.py
"""

import sqlite3
import random

DB_PATH = "../database/traderoot.db"

FAKE_DESIGNERS = [
    ("Sophie Alderton",   "sophie@aldertongarden.co.uk"),
    ("James Whitfield",   "james@whitfielddesigns.co.uk"),
    ("Priya Sharma",      "priya@sharmagardens.co.uk"),
    ("Tom Blackwell",     "tom@blackwelllandscape.co.uk"),
    ("Fiona Drummond",    "fiona@drummondgardendesign.co.uk"),
    ("Eleanor",           "eleanor@hederagardendesign.co.uk"),
]

REVIEW_TEXTS = [
    "Really reliable, good stock and staff know their stuff.",
    "Prices are competitive but delivery can be slow.",
    "Excellent quality plants, always healthy on arrival.",
    "Good range but occasionally out of stock on popular lines.",
    "Wouldn't use again — poor communication.",
    "Brilliant service, went above and beyond.",
    "Decent enough, nothing special.",
    "Fantastic nursery, highly recommend for specimen trees.",
    "Good for hard landscaping materials, very knowledgeable.",
    "Hit and miss — sometimes great, sometimes disappointing.",
    "Great value, will definitely use again.",
    "Staff were helpful and the quality was excellent.",
    "Delivery was prompt and plants arrived in great condition.",
    "A bit pricey but the quality justifies it.",
]

JOB_AREAS = [
    "West Sussex", "Surrey", "Kent", "East Sussex",
    "Hampshire", "Hertfordshire", "London"
]

def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    # ── Designers ──────────────────────────────────────────────────────────────
    for name, email in FAKE_DESIGNERS:
        conn.execute(
            "INSERT OR IGNORE INTO designers (name, email) VALUES (?, ?)",
            (name, email)
        )
    conn.commit()
    print(f"Seeded {len(FAKE_DESIGNERS)} designers.")

    # ── Random categories per supplier ────────────────────────────────────────
    suppliers = conn.execute("SELECT id, type FROM suppliers").fetchall()
    categories = conn.execute("SELECT id, group_name FROM categories").fetchall()

    living_cats    = [c[0] for c in categories if c[1] == "Living"]
    nonliving_cats = [c[0] for c in categories if c[1] == "Non-living"]

    for supplier_id, stype in suppliers:
        conn.execute(
            "DELETE FROM supplier_categories WHERE supplier_id = ?",
            (supplier_id,)
        )
        if stype == "nursery":
            chosen = random.sample(living_cats, k=random.randint(2, 5))
        elif stype == "hard_landscaper":
            chosen = random.sample(nonliving_cats, k=random.randint(2, 4))
        elif stype == "furniture":
            chosen = random.sample(nonliving_cats, k=random.randint(1, 3))
        else:
            chosen = (
                random.sample(living_cats, k=random.randint(1, 3)) +
                random.sample(nonliving_cats, k=random.randint(1, 3))
            )
        for cat_id in chosen:
            conn.execute(
                "INSERT OR IGNORE INTO supplier_categories (supplier_id, category_id) VALUES (?, ?)",
                (supplier_id, cat_id)
            )

    conn.commit()
    print(f"Assigned categories to {len(suppliers)} suppliers.")

    # ── Fake reviews — clear existing first ───────────────────────────────────
    conn.execute("DELETE FROM reviews")
    conn.commit()

    designers = conn.execute("SELECT id FROM designers").fetchall()
    designer_ids = [d[0] for d in designers]

    review_count = 0
    for supplier_id, _ in suppliers:
        # 40% get 1 review, 30% get 2, 15% get 3, rest get none
        roll = random.random()
        if roll < 0.15:
            num_reviews = 3
        elif roll < 0.45:
            num_reviews = 2
        elif roll < 0.75:
            num_reviews = 1
        else:
            num_reviews = 0

        # Pick distinct designers for this supplier
        reviewers = random.sample(designer_ids, k=min(num_reviews, len(designer_ids)))

        for designer_id in reviewers:
            conn.execute(
                """INSERT INTO reviews
                   (supplier_id, designer_id, rating, review_text, job_area)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    supplier_id,
                    designer_id,
                    random.randint(2, 5),
                    random.choice(REVIEW_TEXTS),
                    random.choice(JOB_AREAS)
                )
            )
            review_count += 1

    conn.commit()
    print(f"Added {review_count} fake reviews.")

    # Summary
    avg = conn.execute(
        "SELECT AVG(rating) FROM reviews"
    ).fetchone()[0]
    print(f"Average rating across all reviews: {avg:.2f}")

    conn.close()

if __name__ == "__main__":
    seed()
