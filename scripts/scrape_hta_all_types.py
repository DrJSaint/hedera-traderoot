"""
HTA Member Directory Scraper — All Types
Fetches members across multiple HTA member types and saves to CSV.
Run from scripts/ folder: python scrape_hta_all_types.py
"""

import urllib.request
import json
import csv
import os
import time

# All available HTA member types
MEMBER_TYPES = [
    "Landscaper",
    "Grower",
    "Retailer",
    "Online Retailer",
    "Service Provider",
]

BASE_URL = "https://hta.org.uk/umbraco/api/memberslistingapi/getmembers"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://hta.org.uk/hta-memberships/members-directory",
    "Origin": "https://hta.org.uk",
}

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.normpath(os.path.join(_SCRIPTS_DIR, "..", "data", "hta_members_all.csv"))


def fetch_members(member_type: str) -> list:
    url = (
        f"{BASE_URL}?location=&name=&pageIndex=1&pageSize=500"
        f"&type={urllib.parse.quote(member_type)}"
    )
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
        members = data.get("items", [])
        total   = data.get("totalItems", 0)
        print(f"  {member_type}: {len(members)} of {total} fetched")
        return members
    except Exception as e:
        print(f"  {member_type}: FAILED — {e}")
        return []


def save_to_csv(all_members: list):
    fields = ["name", "address", "county", "territory", "phone",
              "email", "website", "lat", "lng", "tags", "member_type"]

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for m in all_members:
            writer.writerow({
                "name":        m.get("name", ""),
                "address":     m.get("address", ""),
                "county":      m.get("county", ""),
                "territory":   m.get("territory", ""),
                "phone":       m.get("phone", ""),
                "email":       m.get("email", ""),
                "website":     m.get("website", ""),
                "lat":         m.get("pos", {}).get("lat", ""),
                "lng":         m.get("pos", {}).get("lng", ""),
                "tags":        ", ".join(m.get("tags") or []),
                "member_type": m.get("_member_type", ""),
            })
    print(f"\nSaved {len(all_members)} members to {CSV_PATH}")


if __name__ == "__main__":
    import urllib.parse

    all_members = []
    seen_ids = set()

    print("Fetching HTA members by type...\n")
    for member_type in MEMBER_TYPES:
        members = fetch_members(member_type)
        for m in members:
            # Deduplicate by ID
            if m.get("id") not in seen_ids:
                seen_ids.add(m.get("id"))
                m["_member_type"] = member_type
                all_members.append(m)
        time.sleep(0.5)  # be polite to the server

    print(f"\nTotal unique members: {len(all_members)}")
    save_to_csv(all_members)
