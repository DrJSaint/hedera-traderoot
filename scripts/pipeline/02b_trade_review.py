"""
Stage 2b — Sonnet second pass to review trade_only flags set by Haiku.

Preserves the original Haiku flag in trade_only_haiku and reports
which suppliers changed direction (false→true or true→false).

Usage:
    python scripts/pipeline/02b_trade_review.py "East Sussex"
    python scripts/pipeline/02b_trade_review.py             # all unenriched counties
"""

import os
import sys
import time

import anthropic

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.pipeline.staging_db import get_connection

SYSTEM_PROMPT = """\
You are reviewing whether a UK horticultural or garden trade business offers trade or wholesale accounts.
Answer ONLY with a JSON object: {"trade": true} or {"trade": false}. No explanation, no markdown.

Rules:
- nursery, hard_landscaper, soils_aggregates, timber: default true unless the evidence
  explicitly says retail/public only (e.g. "open to public only", "no trade accounts").
  Most UK trade suppliers in these categories do not advertise trade accounts prominently.
- garden_centre, furniture, tools, lighting, other: default false unless there is
  explicit evidence of trade accounts, wholesale pricing, or trade-only access.
"""

USER_PROMPT = """\
Business: {name}
Type: {supplier_type}
Address: {address}
Website text: {website_text}
Haiku's notes: {notes}

Does this business offer trade or wholesale accounts?
"""


def review_county(county: str | None = None):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Set ANTHROPIC_API_KEY environment variable first.")

    client = anthropic.Anthropic(api_key=api_key)
    conn   = get_connection()

    query = """
        SELECT e.place_id, r.name, r.address, r.website, e.supplier_type,
               e.trade_only, e.trade_only_haiku, e.notes
        FROM enriched e
        JOIN raw_places r ON r.place_id = e.place_id
        WHERE e.relevant = 1
    """
    params = []
    if county:
        query += " AND r.search_county = ?"
        params.append(county)
    query += " ORDER BY r.name"

    rows = conn.execute(query, params).fetchall()
    print(f"\nSonnet trade review — {county or 'all counties'} ({len(rows)} relevant suppliers)\n")

    flipped_to_true  = []
    flipped_to_false = []
    unchanged        = 0

    for i, row in enumerate(rows, 1):
        print(f"  [{i}/{len(rows)}] {row['name']}", end="", flush=True)

        # Fetch website text (reuse from raw_places website if available)
        from scripts.pipeline.staging_db import get_connection as gc
        website_text = ""
        if row["website"]:
            try:
                import httpx
                from bs4 import BeautifulSoup
                r = httpx.get(row["website"], timeout=8, follow_redirects=True,
                              headers={"User-Agent": "Mozilla/5.0"})
                soup = BeautifulSoup(r.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer"]):
                    tag.decompose()
                website_text = " ".join(soup.get_text(separator=" ").split())[:3000]
            except Exception:
                website_text = ""

        prompt = USER_PROMPT.format(
            name          = row["name"],
            supplier_type = row["supplier_type"] or "unknown",
            address       = row["address"] or "",
            website_text  = website_text or "(none available)",
            notes         = row["notes"] or "",
        )

        try:
            message = client.messages.create(
                model      = "claude-sonnet-4-6",
                max_tokens = 20,
                system     = SYSTEM_PROMPT,
                messages   = [{"role": "user", "content": prompt}],
            )
            import json
            result    = json.loads(message.content[0].text.strip())
            new_trade = 1 if result.get("trade") else 0
        except Exception as e:
            print(f" ✗ error: {e}")
            new_trade = row["trade_only"]  # keep original on failure

        old_trade = row["trade_only_haiku"]
        conn.execute(
            "UPDATE enriched SET trade_only = ? WHERE place_id = ?",
            (new_trade, row["place_id"])
        )

        if new_trade != old_trade:
            direction = "false→true" if new_trade else "true→false"
            print(f" FLIP {direction}  {row['name']}")
            if new_trade:
                flipped_to_true.append(row["name"])
            else:
                flipped_to_false.append(row["name"])
        else:
            print(f" {'trade' if new_trade else 'no trade'} (unchanged)")
            unchanged += 1

        conn.commit()
        time.sleep(0.5)

    conn.close()

    print(f"\n{'='*70}")
    print(f"  Unchanged: {unchanged}   Flipped to trade: {len(flipped_to_true)}   Flipped to no-trade: {len(flipped_to_false)}")

    if flipped_to_true:
        print(f"\n  false → TRUE (Sonnet added trade flag):")
        for name in flipped_to_true:
            print(f"    + {name}")

    if flipped_to_false:
        print(f"\n  true → FALSE (Sonnet removed trade flag):")
        for name in flipped_to_false:
            print(f"    - {name}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    county = sys.argv[1] if len(sys.argv) > 1 else None
    review_county(county)
