from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from app.ingestion.normalized import (
    NormalizedCapability,
    NormalizedDevice,
    NormalizedMeasurement,
    ScalarValue,
)


UNAVAILABLE_STATE_VALUES = {
    "unknown",
    "unavailable",
}


def parse_ha_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed


def ha_entity_domain(entity_id: str) -> str:
    if "." not in entity_id:
        return "unknown"

    return entity_id.split(".", 1)[0]


def coerce_ha_state_value(raw_state: Any) -> ScalarValue:
    if isinstance(raw_state, bool):
        return raw_state

    if isinstance(raw_state, (int, float)):
        return raw_state

    if raw_state is None:
        return "unknown"

    if not isinstance(raw_state, str):
        return str(raw_state)

    stripped = raw_state.strip()

    if stripped.lower() == "true":
        return True

    if stripped.lower() == "false":
        return False

    try:
        return float(stripped)
    except ValueError:
        return stripped


def value_type_for_value(value: ScalarValue) -> str:
    if isinstance(value, bool):
        return "boolean"

    if isinstance(value, (int, float)):
        return "number"

    return "string"


def value_type_from_state_and_attributes(state: dict[str, Any]) -> str:
    attributes = state.get("attributes") or {}
    device_class = attributes.get("device_class")
    state_class = attributes.get("state_class")
    unit = attributes.get("unit_of_measurement")

    if device_class in {
        "temperature",
        "humidity",
        "voltage",
        "power",
        "energy",
        "current",
        "pressure",
        "illuminance",
        "battery",
    }:
        return "number"

    if state_class in {"measurement", "total", "total_increasing"}:
        return "number"

    if isinstance(unit, str) and unit.strip():
        return "number"

    return value_type_for_value(coerce_ha_state_value(state.get("state")))


def capability_type_from_state(state: dict[str, Any]) -> str:
    entity_id = state["entity_id"]
    domain = ha_entity_domain(entity_id)
    attributes = state.get("attributes") or {}
    device_class = attributes.get("device_class")

    if isinstance(device_class, str) and device_class.strip():
        return f"home_assistant.{domain}.{device_class}"

    return f"home_assistant.{domain}.state"


def unit_from_state(state: dict[str, Any]) -> str | None:
    attributes = state.get("attributes") or {}
    unit = attributes.get("unit_of_measurement")

    if isinstance(unit, str) and unit.strip():
        return unit

    return None


def first_device_identifier(device_entry: dict[str, Any]) -> tuple[str, str] | None:
    identifiers = device_entry.get("identifiers")

    if not isinstance(identifiers, list):
        return None

    for item in identifiers:
        if (
            isinstance(item, list)
            and len(item) == 2
            and isinstance(item[0], str)
            and isinstance(item[1], str)
        ):
            return item[0], item[1]

    return None


def external_device_id_from_device_entry(device_entry: dict[str, Any]) -> str:
    identifier = first_device_identifier(device_entry)

    if identifier is not None:
        source, value = identifier
        return f"ha:device:{source}:{value}"

    ha_device_id = device_entry.get("id")

    if isinstance(ha_device_id, str) and ha_device_id.strip():
        return f"ha:device:{ha_device_id}"

    raise RuntimeError(f"Cannot build external device id from HA device entry: {device_entry}")


def fallback_external_device_id_from_state(state: dict[str, Any]) -> str:
    return f"ha:entity:{state['entity_id']}"


def capability_id_from_entity_entry(
    entity_entry: dict[str, Any] | None,
    state: dict[str, Any],
) -> str:
    if entity_entry is not None:
        unique_id = entity_entry.get("unique_id")
        if isinstance(unique_id, str) and unique_id.strip():
            return unique_id

    return state["entity_id"]


def semantic_capability_name_from_state(state: dict[str, Any]) -> str | None:
    attributes = state.get("attributes") or {}
    device_class = attributes.get("device_class")

    if isinstance(device_class, str) and device_class.strip():
        return device_class

    entity_id = state.get("entity_id")
    if not isinstance(entity_id, str) or "." not in entity_id:
        return None

    object_id = entity_id.split(".", 1)[1]

    # sensor.lab_mqtt_01_temperature_sensor -> temperature_sensor-ish fallback
    match = re.search(
        r"(temperature|humidity|voltage|power|energy|battery|status|current|pressure)",
        object_id,
    )

    if match:
        return match.group(1)

    return object_id


def normalized_capability_from_ha_registry_state(
    state: dict[str, Any],
    *,
    entity_entry: dict[str, Any] | None,
) -> NormalizedCapability:
    entity_id = state["entity_id"]
    attributes = state.get("attributes") or {}

    return NormalizedCapability(
        capability_id=capability_id_from_entity_entry(
            entity_entry,
            state,
        ),
        capability_type=capability_type_from_state(state),
        direction="ro",
        value_type=value_type_from_state_and_attributes(state),
        unit=unit_from_state(state),
        source="integration",
        metadata={
            "ha_entity_id": entity_id,
            "ha_unique_id": entity_entry.get("unique_id") if entity_entry else None,
            "ha_entity_registry_id": entity_entry.get("id") if entity_entry else None,
            "ha_device_id": entity_entry.get("device_id") if entity_entry else None,
            "ha_platform": entity_entry.get("platform") if entity_entry else None,
            "ha_original_name": entity_entry.get("original_name") if entity_entry else None,
            "ha_device_class": attributes.get("device_class"),
            "ha_state_class": attributes.get("state_class"),
            "semantic_name": semantic_capability_name_from_state(state),
        },
    )


def normalized_device_from_ha_registry_state(
    state: dict[str, Any],
    *,
    entity_entry: dict[str, Any] | None,
    device_entry: dict[str, Any] | None,
) -> NormalizedDevice:
    capability = normalized_capability_from_ha_registry_state(
        state,
        entity_entry=entity_entry,
    )

    if device_entry is None:
        # Fallback для HA entities без device registry.
        entity_id = state["entity_id"]
        attributes = state.get("attributes") or {}
        friendly_name = attributes.get("friendly_name")

        return NormalizedDevice(
            external_device_id=fallback_external_device_id_from_state(state),
            name=friendly_name if isinstance(friendly_name, str) else entity_id,
            manufacturer="Home Assistant",
            model=ha_entity_domain(entity_id),
            firmware_version=None,
            protocol="home_assistant",
            transport="websocket",
            room=None,
            read_only=True,
            controllable=False,
            metadata={
                "ha_entity_id": entity_id,
                "ha_mapping_mode": "entity_fallback",
            },
            capabilities=[capability],
        )

    name = (
        device_entry.get("name_by_user")
        or device_entry.get("name")
        or "Home Assistant Device"
    )

    manufacturer = device_entry.get("manufacturer") or "Home Assistant"
    model = device_entry.get("model")

    return NormalizedDevice(
        external_device_id=external_device_id_from_device_entry(device_entry),
        name=str(name),
        manufacturer=str(manufacturer),
        model=str(model) if model is not None else None,
        firmware_version=(
            str(device_entry["sw_version"])
            if device_entry.get("sw_version") is not None
            else None
        ),
        protocol="home_assistant",
        transport="websocket",
        room=None,
        read_only=True,
        controllable=False,
        metadata={
            "ha_device_id": device_entry.get("id"),
            "ha_identifiers": device_entry.get("identifiers"),
            "ha_connections": device_entry.get("connections"),
            "ha_config_entries": device_entry.get("config_entries"),
            "ha_area_id": device_entry.get("area_id"),
            "ha_mapping_mode": "device_registry",
        },
        capabilities=[capability],
    )


def normalized_measurement_from_ha_registry_state(
    state: dict[str, Any],
    *,
    entity_entry: dict[str, Any] | None,
    device_entry: dict[str, Any] | None,
    server_received_at: datetime,
) -> NormalizedMeasurement | None:
    raw_state = state.get("state")

    if isinstance(raw_state, str) and raw_state in UNAVAILABLE_STATE_VALUES:
        return None

    if device_entry is not None:
        external_device_id = external_device_id_from_device_entry(device_entry)
    else:
        external_device_id = fallback_external_device_id_from_state(state)

    return NormalizedMeasurement(
        external_device_id=external_device_id,
        capability_id=capability_id_from_entity_entry(
            entity_entry,
            state,
        ),
        metric=state["entity_id"],
        value=coerce_ha_state_value(raw_state),
        event_ts=parse_ha_datetime(
            state.get("last_updated")
            or state.get("last_changed")
        ),
        server_received_at=server_received_at,
        unit=unit_from_state(state),
        seq=None,
        raw_payload_text=json.dumps(state, ensure_ascii=False),
    )