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