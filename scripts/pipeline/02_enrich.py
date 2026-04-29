"""
Stage 2 — Claude API enrichment.

Usage:
    python scripts/pipeline/02_enrich.py                          # enrich all unenriched
    python scripts/pipeline/02_enrich.py "Surrey"                 # enrich one county only
    python scripts/pipeline/02_enrich.py "Surrey" --conservative  # use conservative trade prompt

Requires env vars:
    ANTHROPIC_API_KEY=<your key>
    GOOGLE_PLACES_KEY=<your key>   (for fetching website URLs via Place Details)

For each raw place not yet enriched, this script:
  1. Fetches the website URL from the Google Place Details endpoint
  2. Fetches and strips the homepage text (best-effort)
  3. Asks Claude to classify the business
  4. Stores the result in the enriched table
"""

import json
import os
import sys
import time

import anthropic
import googlemaps
import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.pipeline.staging_db import init_db, get_connection

SUPPLIER_TYPES = ["nursery", "garden_centre", "hard_landscaper", "furniture", "tools", "lighting", "other"]
CATEGORIES     = ["Trees", "Shrubs", "Perennials", "Grasses", "Alpine", "Hedging", "Climbers",
                  "Paving", "Gravel", "Decking", "Fencing", "Trellis", "Pergola/Arbour"]

SYSTEM_PROMPT_DEFAULTS = """\
You are classifying UK businesses for a trade supplier directory used by professional garden designers.
Respond ONLY with a valid JSON object — no explanation, no markdown.

Key rule for trade_only:
- nursery, hard_landscaper, soils_aggregates, timber: default to true unless the website
  explicitly says retail/public only (e.g. "open to public only", "no trade accounts").
  Most UK trade nurseries and landscaping suppliers do not advertise trade accounts
  prominently — assume trade unless proven otherwise.
- garden_centre, furniture, tools, lighting, other: default to false unless there is
  explicit evidence of trade accounts or wholesale pricing.
"""

SYSTEM_PROMPT_CONSERVATIVE = """\
You are classifying UK businesses for a trade supplier directory used by professional garden designers.
Respond ONLY with a valid JSON object — no explanation, no markdown.
"""

USER_PROMPT_DEFAULTS = """\
Classify this business:

Name: {name}
Address: {address}
Google categories: {google_types}
Website text (may be empty): {website_text}

Return JSON:
{{
  "relevant": true/false,          // Is this relevant to professional garden designers?
  "supplier_type": "...",          // One of: nursery, garden_centre, hard_landscaper, soils_aggregates, timber, furniture, tools, lighting, other
  "categories": [...],             // Subset of: {categories}
  "confidence": 0.0-1.0,
  "notes": "...",                  // One sentence on relevance and trade status
  "trade_only": true/false         // See system prompt rules — nurseries/landscapers default true
}}
"""

USER_PROMPT_CONSERVATIVE = """\
Classify this business:

Name: {name}
Address: {address}
Google categories: {google_types}
Website text (may be empty): {website_text}

Return JSON with these fields:
{{
  "relevant": true/false,          // Is this a trade supplier relevant to garden designers?
  "supplier_type": "...",          // One of: nursery, garden_centre, hard_landscaper, soils_aggregates, timber, furniture, tools, lighting, other
  "trade_only": true/false,        // Does it supply trade/wholesale (not just public retail)?
  "categories": [...],             // Subset of: {categories}
  "confidence": 0.0-1.0,
  "notes": "..."                   // One sentence explaining your reasoning
}}
"""


def fetch_website_url(gmaps, place_id: str) -> str | None:
    try:
        details = gmaps.place(place_id=place_id, fields=["website"])
        return details.get("result", {}).get("website")
    except Exception:
        return None


def fetch_website_text(url: str, max_chars: int = 3000) -> str:
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (compatible; TradeRootBot/1.0)"})
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:max_chars]
    except Exception:
        return ""


def call_claude(client, prompt: str, system: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            message = client.messages.create(
                model      = "claude-haiku-4-5-20251001",
                max_tokens = 400,
                system     = system,
                messages   = [{"role": "user", "content": prompt}],
            )
            text = message.content[0].text.strip()
            if not text:
                raise ValueError("Empty response from Claude")
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except Exception as e:
            if attempt < retries - 1:
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                print(f" ⏳ retry {attempt+1} ({e}) waiting {wait}s…", end="", flush=True)
                time.sleep(wait)
            else:
                print(f" ✗ failed after {retries} attempts: {e}")
                return {"relevant": None, "supplier_type": None, "trade_only": None,
                        "categories": [], "confidence": 0.0, "notes": f"Error: {e}"}


def enrich(county: str | None = None, conservative: bool = False):
    api_key     = os.environ.get("ANTHROPIC_API_KEY")
    places_key  = os.environ.get("GOOGLE_PLACES_KEY")
    if not api_key:
        sys.exit("Set ANTHROPIC_API_KEY environment variable first.")
    if not places_key:
        sys.exit("Set GOOGLE_PLACES_KEY environment variable first.")

    init_db()
    client = anthropic.Anthropic(api_key=api_key)
    gmaps  = googlemaps.Client(key=places_key)
    conn   = get_connection()

    query = """
        SELECT r.place_id, r.name, r.address, r.google_types, r.search_county
        FROM raw_places r
        LEFT JOIN enriched e ON e.place_id = r.place_id
        WHERE e.place_id IS NULL
    """
    params = []
    if county:
        query += " AND r.search_county = ?"
        params.append(county)
    query += " ORDER BY r.fetched_at"

    rows = conn.execute(query, params).fetchall()
    mode = "conservative" if conservative else "type-defaults"
    print(f"Enriching {len(rows)} places{' in ' + county if county else ''}… (prompt: {mode})\n")

    system_prompt = SYSTEM_PROMPT_CONSERVATIVE if conservative else SYSTEM_PROMPT_DEFAULTS
    user_prompt_t = USER_PROMPT_CONSERVATIVE   if conservative else USER_PROMPT_DEFAULTS

    for i, row in enumerate(rows, 1):
        print(f"  [{i}/{len(rows)}] {row['name']}", end="", flush=True)

        # Get website URL via Place Details
        website_url  = fetch_website_url(gmaps, row["place_id"])
        website_text = fetch_website_text(website_url) if website_url else ""

        # Update website URL in raw_places while we have it
        if website_url:
            conn.execute("UPDATE raw_places SET website = ? WHERE place_id = ?",
                         (website_url, row["place_id"]))

        prompt = user_prompt_t.format(
            name         = row["name"],
            address      = row["address"] or "",
            google_types = row["google_types"] or "[]",
            website_text = website_text or "(none available)",
            categories   = ", ".join(CATEGORIES),
        )

        data = call_claude(client, prompt, system_prompt)

        trade_val = 1 if data.get("trade_only") else 0
        conn.execute("""
            INSERT OR REPLACE INTO enriched
                (place_id, relevant, supplier_type, categories, trade_only, trade_only_haiku, confidence, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["place_id"],
            1 if data.get("relevant") else 0,
            data.get("supplier_type"),
            json.dumps(data.get("categories", [])),
            trade_val,
            trade_val,
            data.get("confidence", 0.0),
            data.get("notes"),
        ))
        conn.commit()

        flag = "✓" if data.get("relevant") else "✗"
        print(f" {flag} {data.get('supplier_type','?')} (conf: {data.get('confidence',0):.0%})")
        time.sleep(1.5)  # ~40 RPM — safe for Tier 1 accounts

    conn.close()
    print("\nEnrichment complete.")


if __name__ == "__main__":
    args         = [a for a in sys.argv[1:] if not a.startswith("--")]
    conservative = "--conservative" in sys.argv
    county       = args[0] if args else None
    enrich(county, conservative)
