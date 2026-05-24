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
        
def get_device_id_by_external_id(
    conn: psycopg.Connection,
    *,
    external_device_id: str,
) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id
            FROM device
            WHERE external_device_id = %s
            """,
            (external_device_id,),
        )

        row = cur.fetchone()

        if row is None:
            return None

        return str(row[0])
    
def get_device_capability_by_id(
    conn: psycopg.Connection,
    *,
    device_id: str,
    capability_id: str,
) -> tuple[str, str, str | None] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, capability_id , unit
            FROM device_capability
            WHERE device_id = %s
                AND capability_id = %s
            """,
            (device_id, capability_id),
        )

        row = cur.fetchone()

        if row is None:
            return None

        capability_ref = str(row[0])
        stored_capability_id  = row[1]
        unit = row[2]

        return capability_ref, stored_capability_id, unit
    
def insert_measurement_raw(
    conn,
    *,
    event_ts,
    server_received_at,
    device_id: str,
    capability_ref: str | None,
    metric: str,
    capability_id: str,
    value,
    unit: str | None,
    source: str,
    seq: int | None,
    raw_payload_text: str | None = None,
) -> None:
    value_num = None
    value_text = None
    value_bool = None

    if isinstance(value, bool):
        value_bool = value
    elif isinstance(value, (int, float)):
        value_num = float(value)
    elif isinstance(value, str):
        value_text = value
    else:
        return

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO measurement_raw (
                event_ts,
                server_received_at,
                device_id,
                capability_ref,
                metric,
                capability_id,
                value_num,
                value_text,
                value_bool,
                unit,
                source,
                seq,
                raw_payload_text
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                event_ts,
                server_received_at,
                device_id,
                capability_ref,
                metric,
                capability_id,
                value_num,
                value_text,
                value_bool,
                unit,
                source,
                seq,
                raw_payload_text,
            ),
        )
        
def upsert_device_state_current(
    conn: psycopg.Connection,
    *,
    device_id: str,
    capability_id: str,
    event_ts,
    server_received_at,
    value,
    unit: str | None,
    source: str,
) -> None:
    value_num = None
    value_text = None
    value_bool = None
    value_json = None

    if isinstance(value, bool):
        value_bool = value
    elif isinstance(value, (int, float)):
        value_num = float(value)
    elif isinstance(value, str):
        value_text = value
    else:
        value_json = None

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO device_state_current (
                device_id,
                capability_id,
                event_ts,
                server_received_at,
                value_num,
                value_text,
                value_bool,
                value_json,
                unit,
                source
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (device_id, capability_id)
            DO UPDATE SET
                event_ts = EXCLUDED.event_ts,
                server_received_at = EXCLUDED.server_received_at,
                value_num = EXCLUDED.value_num,
                value_text = EXCLUDED.value_text,
                value_bool = EXCLUDED.value_bool,
                value_json = EXCLUDED.value_json,
                unit = EXCLUDED.unit,
                source = EXCLUDED.source
            """,
            (
                device_id,
                capability_id,
                event_ts,
                server_received_at,
                value_num,
                value_text,
                value_bool,
                value_json,
                unit,
                source,
            ),
        )
        
def update_device_last_seen(
    conn: psycopg.Connection,
    *,
    device_id: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE device
            SET last_seen_at = now(),
                updated_at = now()
            WHERE id = %s
            """,
            (device_id,),
        )