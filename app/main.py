"""
Hedera TradeRoot — FastAPI backend
Serves JSON API endpoints and the static frontend.
Run: uvicorn app.main:app --reload --port 8000
"""

import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import app.db as db

app = FastAPI(title="Hedera TradeRoot")

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    a = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return R * 2 * math.asin(math.sqrt(a))


# ── Areas ──────────────────────────────────────────────────────────────────────

@app.get("/api/areas")
def get_areas():
    return db.get_all_areas()


# ── Map data ───────────────────────────────────────────────────────────────────

@app.get("/api/map")
def get_map(area: str = None, type: str = None):
    return db.get_suppliers_with_coords(area=area, supplier_type=type)


@app.get("/api/map/near")
def get_near(lat: float, lon: float, radius: float = 25, type: str = None):
    candidates = db.get_suppliers_near(lat, lon, radius, supplier_type=type)
    for s in candidates:
        s["distance_miles"] = round(haversine(lat, lon, s["latitude"], s["longitude"]), 1)
    return sorted(
        [s for s in candidates if s["distance_miles"] <= radius],
        key=lambda s: s["distance_miles"]
    )


# ── Suppliers ──────────────────────────────────────────────────────────────────

@app.get("/api/suppliers")
def get_suppliers(area: str = None, type: str = None):
    return db.get_suppliers(area=area, supplier_type=type)


@app.get("/api/suppliers/{supplier_id}")
def get_supplier(supplier_id: int):
    s = db.get_supplier_by_id(supplier_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    s["areas"]      = db.get_supplier_areas(supplier_id)
    s["categories"] = db.get_supplier_categories(supplier_id)
    s["reviews"]    = db.get_reviews_for_supplier(supplier_id)
    return s


class SupplierIn(BaseModel):
    name: str
    type: str
    website:    Optional[str] = None
    phone:      Optional[str] = None
    email:      Optional[str] = None
    address:    Optional[str] = None
    postcode:   Optional[str] = None
    price_band: Optional[str] = None
    notes:      Optional[str] = None
    areas:      list[str] = []


def geocode_uk_postcode(postcode: str) -> tuple[float, float]:
    clean = ''.join((postcode or '').upper().split())
    if not clean:
        raise ValueError('Missing postcode')

    url = f"https://api.postcodes.io/postcodes/{urllib.parse.quote(clean)}"
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError('Postcode lookup service is unavailable right now.') from exc

    if payload.get('status') != 200 or not payload.get('result'):
        raise ValueError('Postcode not found. Please check and try again.')

    result = payload['result']
    return float(result['latitude']), float(result['longitude'])


def geocode_uk_address(address: str) -> tuple[float, float]:
    query = (address or '').strip()
    if not query:
        raise ValueError('Missing address')

    params = urllib.parse.urlencode({
        'q': f'{query}, UK',
        'format': 'jsonv2',
        'limit': 1,
    })
    req = urllib.request.Request(
        f'https://nominatim.openstreetmap.org/search?{params}',
        headers={'User-Agent': 'Hedera-TradeRoot/1.0'},
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            results = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError('Address lookup service is unavailable right now.') from exc

    if not results:
        raise ValueError('Address not found. Please check and try again.')

    first = results[0]
    return float(first['lat']), float(first['lon'])


@app.post("/api/suppliers", status_code=201)
def create_supplier(body: SupplierIn):
    latitude = None
    longitude = None
    if body.address:
        try:
            latitude, longitude = geocode_uk_address(body.address)
        except ValueError:
            # Fallback to postcode geocoding if address is too vague.
            if body.postcode:
                try:
                    latitude, longitude = geocode_uk_postcode(body.postcode)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                except RuntimeError as exc:
                    raise HTTPException(status_code=503, detail=str(exc)) from exc
            else:
                raise HTTPException(status_code=400, detail='Address not found. Please check and try again.')
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    elif body.postcode:
        try:
            latitude, longitude = geocode_uk_postcode(body.postcode)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    sid = db.add_supplier(
        body.name, body.type, body.website, body.phone,
        body.email, body.price_band, body.notes, body.areas,
        latitude=latitude, longitude=longitude, address=body.address
    )
    return {"id": sid}


class SupplierPatch(BaseModel):
    name:       Optional[str] = None
    type:       Optional[str] = None
    price_band: Optional[str] = None
    notes:      Optional[str] = None


@app.patch("/api/suppliers/{supplier_id}")
def patch_supplier(supplier_id: int, body: SupplierPatch):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Nothing to update")
    db.patch_supplier(supplier_id, updates)
    return {"ok": True}


@app.delete("/api/suppliers/{supplier_id}", status_code=204)
def delete_supplier(supplier_id: int):
    db.delete_supplier(supplier_id)


# ── Categories ─────────────────────────────────────────────────────────────────

@app.get("/api/categories")
def get_categories():
    return db.get_all_categories()


class CategoriesIn(BaseModel):
    category_ids: list[int]


@app.put("/api/suppliers/{supplier_id}/categories")
def set_categories(supplier_id: int, body: CategoriesIn):
    db.set_supplier_categories(supplier_id, body.category_ids)
    return {"ok": True}


# ── Reviews ────────────────────────────────────────────────────────────────────

class ReviewIn(BaseModel):
    designer_id: int
    rating:      int
    review_text: str
    job_area:    Optional[str] = None


@app.post("/api/suppliers/{supplier_id}/reviews", status_code=201)
def add_review(supplier_id: int, body: ReviewIn):
    db.add_review(supplier_id, body.designer_id, body.rating, body.review_text, body.job_area)
    return {"ok": True}


# ── Designers ──────────────────────────────────────────────────────────────────

@app.get("/api/designers")
def get_designers():
    return db.get_all_designers()


class DesignerIn(BaseModel):
    name:    str
    email:   str
    company: Optional[str] = None


@app.post("/api/designers", status_code=201)
def create_designer(body: DesignerIn):
    try:
        did = db.add_designer(body.name, body.email, body.company)
        return {"id": did}
    except Exception:
        raise HTTPException(status_code=409, detail="Email already registered")


# ── Static files (must be last) ────────────────────────────────────────────────

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
