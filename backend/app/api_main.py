from typing import Any

from fastapi import FastAPI

from app.db import get_connection
from app.repository import list_devices

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
        return list_devices(conn)