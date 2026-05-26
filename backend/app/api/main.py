from typing import Any

from fastapi import FastAPI, HTTPException

from app.db import get_connection
from app.repository import (
    get_device_state_rows, 
    list_device_rows
)
from app.api.mappers import (state_rows_to_api, device_rows_to_api)

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