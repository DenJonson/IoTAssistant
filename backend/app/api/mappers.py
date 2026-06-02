from typing import Any


def scalar_value_from_db(
    value_num: float | None,
    value_text: str | None,
    value_bool: bool | None,
) -> float | str | bool | None:
    if value_num is not None:
        return value_num

    if value_bool is not None:
        return value_bool

    return value_text


def device_row_to_api(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "device_id": row["external_device_id"],
        "name": row["name"],
        "manufacturer": row["manufacturer"],
        "model": row["model"],
        "protocol": row["protocol"],
        "transport": row["transport"],
        "room": row["room"],
        "read_only": row["read_only"],
        "controllable": row["controllable"],
        "last_seen_at": row["last_seen_at"],
    }

def device_rows_to_api(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [device_row_to_api(row) for row in rows]


def state_row_to_api(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "capability_id": row["capability_id"],
        "capability_type": row["capability_type"],
        "value_type": row["value_type"],
        "unit": row["unit"],
        "value": scalar_value_from_db(
            value_num=row["value_num"],
            value_text=row["value_text"],
            value_bool=row["value_bool"],
        ),
        "event_ts": row["event_ts"],
        "server_received_at": row["server_received_at"],
    }

def state_rows_to_api(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [state_row_to_api(row) for row in rows]



def measurement_row_to_api(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ts": row["event_ts"],
        "value": row["value_num"],
    }

def measurement_rows_to_api(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [measurement_row_to_api(row) for row in rows]

def unit_from_measurement_rows(rows: list[dict[str, Any]]) -> str | None:
    for row in rows:
        if row["unit"] is not None:
            return row["unit"]

    return None


def capability_display_name_from_row(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") or {}

    if isinstance(metadata, dict):
        ha_original_name = metadata.get("ha_original_name")
        if isinstance(ha_original_name, str) and ha_original_name.strip():
            return ha_original_name.strip()

        semantic_name = metadata.get("semantic_name")
        if isinstance(semantic_name, str) and semantic_name.strip():
            return semantic_name.strip().replace("_", " ").replace("-", " ").title()

    capability_type = row.get("capability_type")
    if isinstance(capability_type, str) and capability_type.strip():
        last_part = capability_type.rsplit(".", 1)[-1]
        if last_part and last_part != "state":
            return last_part.replace("_", " ").replace("-", " ").title()

    capability_id = row["capability_id"]
    return str(capability_id).replace("_", " ").replace("-", " ").title()

def capability_row_to_api(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "display_name": capability_display_name_from_row(row),
        "capability_id": row["capability_id"],
        "capability_type": row["capability_type"],
        "direction": row["direction"],
        "unit": row["unit"],
        "value_type": row["value_type"],
        "source": row["source"],
        "chartable": row["value_type"] == "number",
    }

def capability_rows_to_api(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [capability_row_to_api(row) for row in rows]


def device_state_rows_to_api(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    devices_by_id: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        external_device_id = row["external_device_id"]

        if external_device_id not in devices_by_id:
            devices_by_id[external_device_id] = []

        devices_by_id[external_device_id].append(state_row_to_api(row))

    return [
        {
            "device_id": device_id,
            "state": state,
        }
        for device_id, state in devices_by_id.items()
    ]

def device_summary_row_to_api(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "device": device_row_to_api(row["device"]),
        "capabilities": capability_rows_to_api(row["capabilities"]),
        "state": state_rows_to_api(row["state"]),
    }

def device_summary_rows_to_api(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [device_summary_row_to_api(row) for row in rows]