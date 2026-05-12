"""
Supplier request routes: submit/update, list, cancel, admin review.
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import app.db as db
from app.auth import require_admin, require_designer_or_admin
from app.geocode import resolve_coordinates

router = APIRouter(prefix="/api/requests")


class RequestIn(BaseModel):
    request_type: str          # "add" or "edit"
    target_supplier_id: Optional[int] = None
    payload: dict              # the proposed field values


class ReviewIn(BaseModel):
    decision: str              # "approved" or "rejected"
    reviewer_notes: Optional[str] = None


@router.post("", status_code=201)
def submit_request(body: RequestIn, user: dict = Depends(require_designer_or_admin)):
    if body.request_type == "edit" and not body.target_supplier_id:
        raise HTTPException(status_code=400, detail="target_supplier_id required for edit requests")
    if body.request_type == "add" and body.target_supplier_id:
        raise HTTPException(status_code=400, detail="target_supplier_id must be omitted for add requests")
    if body.request_type not in ("add", "edit"):
        raise HTTPException(status_code=400, detail="request_type must be 'add' or 'edit'")

    requester_id = int(user["sub"])
    request_id = db.upsert_supplier_request(
        requester_id=requester_id,
        request_type=body.request_type,
        payload=json.dumps(body.payload),
        target_supplier_id=body.target_supplier_id,
    )
    return {"id": request_id}


@router.get("")
def list_requests(user: dict = Depends(require_designer_or_admin)):
    requester_id = int(user["sub"])
    if user["role"] == "admin":
        return db.get_pending_requests()
    return db.get_requests_for_user(requester_id)


@router.get("/mine")
def my_requests(user: dict = Depends(require_designer_or_admin)):
    return db.get_requests_for_user(int(user["sub"]))


@router.delete("/{request_id}", status_code=204)
def cancel_request(request_id: int, user: dict = Depends(require_designer_or_admin)):
    req = db.get_supplier_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req["requester_id"] != int(user["sub"]) and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not your request")
    db.cancel_supplier_request(request_id, req["requester_id"])


@router.patch("/{request_id}/review")
def review_request(request_id: int, body: ReviewIn, user: dict = Depends(require_admin)):
    req = db.get_supplier_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req["status"] != "pending":
        raise HTTPException(status_code=409, detail="Request is no longer pending")
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")

    db.review_supplier_request(request_id, body.decision, body.reviewer_notes)

    if body.decision == "approved":
        payload = json.loads(req["payload"])
        if req["request_type"] == "edit" and req["target_supplier_id"]:
            allowed = {
                "name", "type", "website", "phone", "email",
                "price_band", "notes", "address", "trade",
            }
            updates = {k: v for k, v in payload.items() if k in allowed}
            if updates:
                db.patch_supplier(req["target_supplier_id"], updates)
            if "category_ids" in payload:
                db.set_supplier_categories(req["target_supplier_id"], payload["category_ids"])
        elif req["request_type"] == "add":
            latitude, longitude = resolve_coordinates(
                payload.get("address"), payload.get("postcode")
            )
            supplier_id = db.add_supplier(
                name=payload.get("name", ""),
                supplier_type=payload.get("type", "other"),
                website=payload.get("website"),
                phone=payload.get("phone"),
                email=payload.get("email"),
                price_band=payload.get("price_band"),
                notes=payload.get("notes"),
                area_names=payload.get("areas", []),
                address=payload.get("address"),
                latitude=latitude,
                longitude=longitude,
                trade=payload.get("trade", True),
            )
            if "category_ids" in payload and payload["category_ids"]:
                db.set_supplier_categories(supplier_id, payload["category_ids"])

    return {"ok": True}
