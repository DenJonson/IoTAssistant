import uuid
from typing import Any

import psycopg

def insert_ingestion_event(
    conn,
    *,
    mqtt_topic: str,
    message_type: str | None,
    device_external_id: str | None,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
    raw_payload_text: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion_event (
                id,
                mqtt_topic,
                message_type,
                device_external_id,
                status,
                error_code,
                error_message,
                raw_payload_text
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                str(uuid.uuid4()),
                mqtt_topic,
                message_type,
                device_external_id,
                status,
                error_code,
                error_message,
                raw_payload_text,
            ),
        )
        
def upsert_device_from_discovery(
    conn: psycopg.Connection,
    *,
    payload: dict[str, Any],
) -> str:
    external_device_id = payload["device_id"]

    name = payload.get("name") or external_device_id
    manufacturer = payload.get("manufacturer") or "unknown"
    model = payload.get("model")
    firmware_version = payload.get("firmware_version")
    protocol = payload.get("protocol") or "mqtt"
    transport = payload.get("transport")
    room = payload.get("room")
    read_only = bool(payload.get("read_only", True))
    controllable = bool(payload.get("controllable", False))

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO device (
                id,
                external_device_id,
                name,
                manufacturer,
                model,
                firmware_version,
                protocol,
                transport,
                room,
                read_only,
                controllable,
                updated_at,
                last_seen_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now()
            )
            ON CONFLICT (external_device_id)
            DO UPDATE SET
                name = EXCLUDED.name,
                manufacturer = EXCLUDED.manufacturer,
                model = EXCLUDED.model,
                firmware_version = EXCLUDED.firmware_version,
                protocol = EXCLUDED.protocol,
                transport = EXCLUDED.transport,
                room = EXCLUDED.room,
                read_only = EXCLUDED.read_only,
                controllable = EXCLUDED.controllable,
                updated_at = now(),
                last_seen_at = now()
            RETURNING id
            """,
            (
                str(uuid.uuid4()),
                external_device_id,
                name,
                manufacturer,
                model,
                firmware_version,
                protocol,
                transport,
                room,
                read_only,
                controllable,
            ),
        )

        row = cur.fetchone()

        if row is None:
            raise RuntimeError("Device upsert did not return id")

        return str(row[0])
    
def upsert_device_capability(
    conn: psycopg.Connection,
    *,
    device_id: str,
    capability: dict[str, Any],
) -> None:
    capability_id = capability["id"]
    capability_type = capability["type"]
    direction = capability.get("direction") or "ro"
    unit = capability.get("unit")
    value_type = capability.get("value_type") or "number"

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO device_capability (
                id,
                device_id,
                capability_id,
                capability_type,
                direction,
                unit,
                value_type,
                updated_at
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,now())
            ON CONFLICT (device_id, capability_id)
            DO UPDATE SET
                capability_type = EXCLUDED.capability_type,
                direction = EXCLUDED.direction,
                unit = EXCLUDED.unit,
                value_type = EXCLUDED.value_type,
                updated_at = now()
            """,
            (
                str(uuid.uuid4()),
                device_id,
                capability_id,
                capability_type,
                direction,
                unit,
                value_type,
            ),
        )
        
