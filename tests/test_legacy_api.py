from fastapi.testclient import TestClient

from legacy_api import SHIPMENTS, app


def test_get_shipment_returns_expected_context():
    client = TestClient(app)

    response = client.get("/shipments/SHP-1001")

    assert response.status_code == 200
    assert response.json() == {
        "id": "SHP-1001",
        "status": "DELAYED",
        "origin": "SGSIN",
        "destination": "NLRTM",
        "eta_hours": 72,
        "current_vendor": "VENDOR_A",
    }


def test_alternate_vendors_respect_cost_cap():
    client = TestClient(app)

    response = client.post(
        "/vendors/alternate",
        json={
            "lane_origin": "SGSIN",
            "lane_destination": "NLRTM",
            "max_cost_increase_pct": 10,
        },
    )

    assert response.status_code == 200
    options = response.json()
    assert [option["vendor_id"] for option in options] == ["VENDOR_Y"]
    assert all(option["incremental_cost_pct"] <= 10 for option in options)


def test_reroute_is_idempotent_for_repeated_key():
    client = TestClient(app)
    original_shipment = SHIPMENTS["SHP-1001"].copy()

    try:
        payload = {
            "shipment_id": "SHP-1001",
            "new_vendor_id": "VENDOR_X",
            "reason": "pytest reroute validation",
            "idempotency_key": "pytest-reroute-key",
        }

        first_response = client.post("/shipments/reroute", json=payload)
        replay_response = client.post("/shipments/reroute", json=payload)

        assert first_response.status_code == 200
        assert first_response.json()["result"] == "OK"
        assert replay_response.status_code == 200
        assert replay_response.json() == {
            "result": "NOOP",
            "message": "Idempotent replay accepted",
        }
    finally:
        SHIPMENTS["SHP-1001"].clear()
        SHIPMENTS["SHP-1001"].update(original_shipment)
