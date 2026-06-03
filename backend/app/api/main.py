from typing import Any

from fastapi import FastAPI, HTTPException

from app.db import get_connection
from app.repository import (
    list_device_rows,
    list_device_state_rows, 
    get_device_state_rows, 
    get_measurement_rows,
    get_device_capability_rows,
    list_device_summaries,
    list_ingestion_events,
)
from app.api.mappers import (
    state_rows_to_api, 
    device_rows_to_api, 
    measurement_rows_to_api,
    unit_from_measurement_rows,
    capability_rows_to_api,
    device_state_rows_to_api,
    device_summary_rows_to_api,
    ingestion_event_rows_to_api,
)

app = FastAPI(
    title="IoTAssistant API",
    version="0.1.0",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/api/devices")
def get_devices() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = list_device_rows(conn)

    return device_rows_to_api(rows)
    
@app.get("/api/device-states")
def get_all_device_states() -> dict[str, Any]:
    with get_connection() as conn:
        rows = list_device_state_rows(conn)

    return {
        "devices": device_state_rows_to_api(rows),
    }

@app.get("/api/devices/{device_id}/state")
def get_state(device_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        rows = get_device_state_rows(conn, device_id)

    if rows is None:
        raise HTTPException(status_code=404, detail="Device not found")

    return {
        "device_id": device_id,
        "state": state_rows_to_api(rows),
    }

@app.get("/api/devices/{device_id}/measurements")
def get_measurements(
    device_id: str,
    capability_id: str,
    limit: int = 1000,
) -> dict[str, Any]:
    safe_limit = min(max(limit, 1), 5000)

    with get_connection() as conn:
        rows = get_measurement_rows(
            conn=conn,
            external_device_id=device_id,
            capability_id=capability_id,
            limit=safe_limit,
        )

    if rows is None:
        raise HTTPException(status_code=404, detail="Device not found")

    return {
        "device_id": device_id,
        "capability_id": capability_id,
        "unit": unit_from_measurement_rows(rows),
        "points": measurement_rows_to_api(rows),
    }

@app.get("/api/devices/{device_id}/capabilities")
def get_capabilities(device_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        rows = get_device_capability_rows(conn, device_id)

    if rows is None:
        raise HTTPException(status_code=404, detail="Device not found")

    return {
        "device_id": device_id,
        "capabilities": capability_rows_to_api(rows),
    }


@app.get("/api/device-summaries")
def get_device_summaries() -> dict[str, Any]:
    with get_connection() as conn:
        rows = list_device_summaries(conn=conn)

    return {
        "devices": device_summary_rows_to_api(rows),
    }


@app.get("/api/ingestion-events")
def get_ingestion_events(limit: int = 100) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 500))

    with get_connection() as conn:
        rows = list_ingestion_events(
            conn=conn,
            limit=safe_limit,
        )

    return {
        "events": ingestion_event_rows_to_api(rows),
    }