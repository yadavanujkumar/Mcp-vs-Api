import os
import uuid
from typing import Any, Dict, List

import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("supply-chain-mcp")

ERP_BASE_URL = os.getenv("ERP_BASE_URL", "http://localhost:8000")
TIMEOUT_SECONDS = 8


def _http_get(path: str) -> Dict[str, Any]:
    response = requests.get(f"{ERP_BASE_URL}{path}", timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _http_post(path: str, payload: Dict[str, Any]) -> Any:
    response = requests.post(f"{ERP_BASE_URL}{path}", json=payload, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


@mcp.tool(
    name="inspect_delayed_shipment",
    description=(
        "Inspect shipment status and lane context for incident triage. "
        "Use ONLY when shipment_id is known. "
        "Do NOT use for bulk listing or discovery of shipment IDs."
    ),
)
def inspect_delayed_shipment(shipment_id: str) -> Dict[str, Any]:
    shipment = _http_get(f"/shipments/{shipment_id}")
    return {
        "shipment_id": shipment["id"],
        "status": shipment["status"],
        "origin": shipment["origin"],
        "destination": shipment["destination"],
        "eta_hours": shipment["eta_hours"],
        "current_vendor": shipment["current_vendor"],
    }


@mcp.tool(
    name="find_alternate_vendor",
    description=(
        "Find alternate vendors for a specific lane with cost cap. "
        "Use when shipment status is DELAYED and reroute candidates are required. "
        "Do NOT use when origin/destination is missing or unknown."
    ),
)
def find_alternate_vendor(
    lane_origin: str,
    lane_destination: str,
    max_cost_increase_pct: float = 20.0,
) -> List[Dict[str, Any]]:
    payload = {
        "lane_origin": lane_origin,
        "lane_destination": lane_destination,
        "max_cost_increase_pct": max_cost_increase_pct,
    }
    options = _http_post("/vendors/alternate", payload)
    return sorted(options, key=lambda x: (x["predicted_eta_hours"], x["incremental_cost_pct"]))


@mcp.tool(
    name="execute_reroute",
    description=(
        "Execute shipment reroute mutation for a selected vendor. "
        "Use ONLY after confirming delay and selecting compliant vendor option. "
        "Do NOT call repeatedly with different vendors in one incident unless policy allows."
    ),
)
def execute_reroute(
    shipment_id: str,
    new_vendor_id: str,
    reason: str,
    idempotency_key: str = "",
) -> Dict[str, Any]:
    payload = {
        "shipment_id": shipment_id,
        "new_vendor_id": new_vendor_id,
        "reason": reason,
        "idempotency_key": idempotency_key or str(uuid.uuid4()),
    }
    return _http_post("/shipments/reroute", payload)


if __name__ == "__main__":
    mcp.run(transport="stdio")
