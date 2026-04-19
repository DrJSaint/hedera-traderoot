"""
HTA Member Directory Scraper
"""

import urllib.request
import json
import csv

API_URL = (
    "https://hta.org.uk/umbraco/api/memberslistingapi/getmembers"
    "?location=&name=&pageIndex=1&pageSize=200"
    "&type=Manufacturer%20and%20Supplier"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://hta.org.uk/hta-memberships/members-directory",
    "Origin": "https://hta.org.uk",
}

def fetch_members():
    req = urllib.request.Request(API_URL, headers=HEADERS)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
    return data["items"], data["totalItems"]

def save_to_csv(members, filename="../data/hta_members.csv"):
    fields = ["name", "address", "county", "territory", "phone", "email", "website", "lat", "lng", "tags"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for m in members:
            writer.writerow({
                "name":      m.get("name", ""),
                "address":   m.get("address", ""),
                "county":    m.get("county", ""),
                "territory": m.get("territory", ""),
                "phone":     m.get("phone", ""),
                "email":     m.get("email", ""),
                "website":   m.get("website", ""),
                "lat":       m.get("pos", {}).get("lat", ""),
                "lng":       m.get("pos", {}).get("lng", ""),
                "tags":      ", ".join(m.get("tags") or [])
            })
    print(f"Saved {len(members)} members to {filename}")

if __name__ == "__main__":
    print("Fetching HTA members...")
    members, total = fetch_members()
    print(f"Total members: {total}, fetched: {len(members)}")
    save_to_csv(members)
    # Preview first 3
    for m in members[:3]:
        print(f"  {m['name']} — {m.get('county','')} — lat:{m.get('pos',{}).get('lat','')}")
