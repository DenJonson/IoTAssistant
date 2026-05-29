from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.ingestion.normalized import (
    NormalizedCapability,
    NormalizedDevice,
    NormalizedMeasurement,
    ScalarValue,
)


UNKNOWN_STATE_VALUES = {
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


def ha_external_device_id(entity_id: str) -> str:
    return f"ha:{entity_id}"


def friendly_name_for_state(state: dict[str, Any]) -> str:
    attributes = state.get("attributes") or {}
    friendly_name = attributes.get("friendly_name")

    if isinstance(friendly_name, str) and friendly_name.strip():
        return friendly_name

    return state.get("entity_id", "unknown")


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


def normalized_device_from_ha_state(state: dict[str, Any]) -> NormalizedDevice:
    entity_id = state["entity_id"]
    domain = ha_entity_domain(entity_id)
    attributes = state.get("attributes") or {}
    value = coerce_ha_state_value(state.get("state"))

    unit = attributes.get("unit_of_measurement")
    if not isinstance(unit, str):
        unit = None

    return NormalizedDevice(
        external_device_id=ha_external_device_id(entity_id),
        name=friendly_name_for_state(state),
        manufacturer="Home Assistant",
        model=domain,
        firmware_version=None,
        protocol="home_assistant",
        transport="websocket",
        room=None,
        read_only=True,
        controllable=False,
        metadata={
            "ha_entity_id": entity_id,
            "ha_domain": domain,
            "ha_attributes": attributes,
        },
        capabilities=[
            NormalizedCapability(
                capability_id="state",
                capability_type=f"home_assistant.{domain}.state",
                direction="ro",
                value_type=value_type_for_value(value),
                unit=unit,
                source="integration",
                metadata={
                    "ha_entity_id": entity_id,
                    "ha_domain": domain,
                },
            )
        ],
    )


def normalized_measurement_from_ha_state(
    state: dict[str, Any],
    *,
    server_received_at: datetime,
) -> NormalizedMeasurement:
    entity_id = state["entity_id"]
    attributes = state.get("attributes") or {}

    unit = attributes.get("unit_of_measurement")
    if not isinstance(unit, str):
        unit = None

    event_ts = parse_ha_datetime(
        state.get("last_updated")
        or state.get("last_changed")
    )

    value = coerce_ha_state_value(state.get("state"))

    return NormalizedMeasurement(
        external_device_id=ha_external_device_id(entity_id),
        capability_id="state",
        metric="state",
        value=value,
        event_ts=event_ts,
        server_received_at=server_received_at,
        unit=unit,
        seq=None,
        raw_payload_text=json.dumps(state, ensure_ascii=False),
    )