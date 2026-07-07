from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List

app = FastAPI(title="Legacy Logistics API", version="1.0.0")

# Demo in-memory state (replace with persistent data stores in production).
SHIPMENTS = {
    "SHP-1001": {
        "id": "SHP-1001",
        "status": "DELAYED",
        "origin": "SGSIN",
        "destination": "NLRTM",
        "eta_hours": 72,
        "current_vendor": "VENDOR_A",
    },
    "SHP-1002": {
        "id": "SHP-1002",
        "status": "IN_TRANSIT",
        "origin": "USLAX",
        "destination": "DEHAM",
        "eta_hours": 16,
        "current_vendor": "VENDOR_B",
    },
}


class AlternateVendorRequest(BaseModel):
    lane_origin: str = Field(..., description="Origin UN/LOCODE.")
    lane_destination: str = Field(..., description="Destination UN/LOCODE.")
    max_cost_increase_pct: float = Field(20.0, ge=0, le=100)


class AlternateVendor(BaseModel):
    vendor_id: str
    predicted_eta_hours: int
    incremental_cost_pct: float
    confidence: float


class RerouteRequest(BaseModel):
    shipment_id: str
    new_vendor_id: str
    reason: str
    idempotency_key: str


@app.get("/shipments/{shipment_id}")
def get_shipment(shipment_id: str):
    shipment = SHIPMENTS.get(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return shipment


@app.post("/vendors/alternate", response_model=List[AlternateVendor])
def get_alternate_vendors(req: AlternateVendorRequest):
    # Demo candidate options; production should call external optimization services.
    candidates = [
        AlternateVendor(
            vendor_id="VENDOR_X",
            predicted_eta_hours=30,
            incremental_cost_pct=12.0,
            confidence=0.88,
        ),
        AlternateVendor(
            vendor_id="VENDOR_Y",
            predicted_eta_hours=36,
            incremental_cost_pct=6.0,
            confidence=0.81,
        ),
        AlternateVendor(
            vendor_id="VENDOR_Z",
            predicted_eta_hours=22,
            incremental_cost_pct=28.0,
            confidence=0.90,
        ),
    ]
    return [c for c in candidates if c.incremental_cost_pct <= req.max_cost_increase_pct]


@app.post("/shipments/reroute")
def reroute_shipment(req: RerouteRequest):
    shipment = SHIPMENTS.get(req.shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # Simple idempotency check for demo; persist in durable storage in production.
    if shipment["status"] == "REROUTED" and shipment.get("last_idempotency_key") == req.idempotency_key:
        return {"result": "NOOP", "message": "Idempotent replay accepted"}

    shipment["current_vendor"] = req.new_vendor_id
    shipment["status"] = "REROUTED"
    shipment["last_idempotency_key"] = req.idempotency_key

    return {
        "result": "OK",
        "shipment_id": req.shipment_id,
        "new_vendor": req.new_vendor_id,
    }
