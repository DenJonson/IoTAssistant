from app.ingestion.normalized import (
    NormalizedAvailabilityEvent,
    NormalizedDevice,
    NormalizedMeasurement,
    NormalizedStateValue,
)
from app.processing_errors import IngestionProcessingError
from app.repository import (
    get_device_capability_by_id,
    get_device_id_by_external_id,
    insert_device_availability_event,
    insert_measurement_raw,
    update_device_last_seen,
    upsert_device_capability,
    upsert_device_from_discovery,
    upsert_device_state_current,
)


def write_device(conn, device: NormalizedDevice) -> str:
    """
    Upsert device and its capabilities into the canonical DB model.

    Returns internal DB device UUID as string.
    """
    payload = {
        "device_id": device.external_device_id,
        "name": device.name,
        "manufacturer": device.manufacturer,
        "model": device.model,
        "firmware_version": device.firmware_version,
        "protocol": device.protocol,
        "transport": device.transport,
        "room": device.room,
        "read_only": device.read_only,
        "controllable": device.controllable,
        "metadata": device.metadata,
    }

    device_id = upsert_device_from_discovery(conn, payload=payload)

    for capability in device.capabilities:
        capability_payload = {
            "id": capability.capability_id,
            "type": capability.capability_type,
            "direction": capability.direction,
            "unit": capability.unit,
            "value_type": capability.value_type,
            "source": capability.source,
            "metadata": capability.metadata,
        }

        upsert_device_capability(conn, device_id=device_id, capability=capability_payload)

    return device_id


def write_state_value(conn, state: NormalizedStateValue) -> None:
    """
    Upsert one current state value.
    """
    device_id = get_device_id_by_external_id(
        conn,
        external_device_id=state.external_device_id,
    )

    if device_id is None:
        raise IngestionProcessingError(
            "unknown_device",
            f"Unknown device: {state.external_device_id}",
        )

    capability = get_device_capability_by_id(
        conn,
        device_id=device_id,
        capability_id=state.capability_id,
    )

    if capability is None:
        raise IngestionProcessingError(
            "unknown_capability",
            (
                f"Unknown capability '{state.capability_id}' "
                f"for device '{state.external_device_id}'"
            ),
        )

    _capability_ref, stored_capability_id, stored_unit = capability

    upsert_device_state_current(
        conn=conn,
        device_id=device_id,
        capability_id=stored_capability_id,
        event_ts=state.event_ts,
        server_received_at=state.server_received_at,
        value=state.value,
        unit=state.unit if state.unit is not None else stored_unit,
    )

    update_device_last_seen(conn, device_id=device_id)


def write_measurement(conn, measurement: NormalizedMeasurement) -> None:
    """
    Insert raw measurement and update current state for the same capability.
    """
    device_id = get_device_id_by_external_id(
        conn,
        external_device_id=measurement.external_device_id,
    )

    if device_id is None:
        raise IngestionProcessingError(
            "unknown_device",
            f"Unknown device: {measurement.external_device_id}",
        )

    capability = get_device_capability_by_id(
        conn,
        device_id=device_id,
        capability_id=measurement.capability_id,
    )

    if capability is None:
        raise IngestionProcessingError(
            "unknown_capability",
            (
                f"Unknown capability '{measurement.capability_id}' "
                f"for device '{measurement.external_device_id}'"
            ),
        )

    capability_ref, stored_capability_id, stored_unit = capability
    unit = measurement.unit if measurement.unit is not None else stored_unit

    insert_measurement_raw(
        conn=conn,
        event_ts=measurement.event_ts,
        server_received_at=measurement.server_received_at,
        device_id=device_id,
        capability_ref=capability_ref,
        metric=measurement.metric,
        capability_id=stored_capability_id,
        value=measurement.value,
        unit=unit,
        seq=measurement.seq,
        raw_payload_text=measurement.raw_payload_text,
    )

    upsert_device_state_current(
        conn=conn,
        device_id=device_id,
        capability_id=stored_capability_id,
        event_ts=measurement.event_ts,
        server_received_at=measurement.server_received_at,
        value=measurement.value,
        unit=unit,
    )

    update_device_last_seen(conn, device_id=device_id)


def write_availability_event(
    conn,
    event: NormalizedAvailabilityEvent,
) -> None:
    """
    Insert availability event and update current availability state.
    """
    device_id = get_device_id_by_external_id(
        conn,
        external_device_id=event.external_device_id,
    )

    if device_id is None:
        raise IngestionProcessingError(
            "unknown_device",
            f"Unknown device: {event.external_device_id}",
        )

    capability = get_device_capability_by_id(
        conn,
        device_id=device_id,
        capability_id="availability",
    )

    if capability is None:
        raise IngestionProcessingError(
            "unknown_capability",
            (
                "Unknown capability 'availability' "
                f"for device '{event.external_device_id}'"
            ),
        )

    _capability_ref, stored_capability_id, stored_unit = capability

    insert_device_availability_event(
        conn=conn,
        device_id=device_id,
        event_ts=event.event_ts,
        server_received_at=event.server_received_at,
        status=event.status,
        reason=event.reason,
        raw_payload_text=event.raw_payload_text,
    )

    upsert_device_state_current(
        conn=conn,
        device_id=device_id,
        capability_id=stored_capability_id,
        event_ts=event.event_ts,
        server_received_at=event.server_received_at,
        value=event.status,
        unit=stored_unit,
    )

    update_device_last_seen(conn, device_id=device_id)