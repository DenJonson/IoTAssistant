import os
import signal
import threading
import json

import paho.mqtt.client as mqtt
import psycopg
from psycopg.rows import dict_row

from app.mqtt_topics import parse_topic
from app.ingestion_message import (
    IngestionValidationError,
    IngestionMessage,
    build_ingestion_message,
)
from app.db import check_db_connection, get_connection
from app.repository import (
    get_device_capability_by_id,
    get_device_id_by_external_id,
    insert_ingestion_event,
    insert_measurement_raw,
    insert_device_availability_event,
    update_device_last_seen,
    upsert_device_capability,
    upsert_device_from_discovery,
    upsert_device_state_current,
)
from app.processing_errors import IngestionProcessingError
from app.processing_result import ProcessingResult, ProcessingWarning

from app.ingestion.normalized import (
    NormalizedAvailabilityEvent,
    NormalizedDevice,
    NormalizedMeasurement,
    NormalizedStateValue,
    NormalizedCapability,
)
from app.ingestion.writer import (
    write_availability_event,
    write_device,
    write_measurement,
    write_state_value,
)

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "home/iot/v1").strip("/")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "iot-worker-dev")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://iot:iot_dev_password@localhost:5432/iot",
)

stop_event = threading.Event()

def normalized_capability_from_payload(
    capability: dict,
    *,
    default_source: str = "device_discovery",
) -> NormalizedCapability:
    return NormalizedCapability(
        capability_id=capability["id"],
        capability_type=capability["type"],
        direction=capability.get("direction", "ro"),
        value_type=capability.get("value_type", "number"),
        unit=capability.get("unit"),
        source=capability.get("source", default_source),
        metadata=capability.get("metadata", {}),
    )

def is_supported_scalar_value(value: object) -> bool:
    return isinstance(value, (bool, int, float, str))

def backend_availability_capability() -> NormalizedCapability:
    return NormalizedCapability(
        capability_id="availability",
        capability_type="device.availability",
        direction="ro",
        value_type="string",
        unit=None,
        source="backend",
        metadata={},
    )

def handle_discovery_message(conn, ingestion_message: IngestionMessage) -> ProcessingResult:
    payload = ingestion_message.payload

    discovered_capabilities = [
        normalized_capability_from_payload(capability)
        for capability in payload["capabilities"]
    ]

    device = NormalizedDevice(
        external_device_id=payload["device_id"],
        name=payload.get("name") or payload["device_id"],
        manufacturer=payload.get("manufacturer") or "unknown",
        model=payload.get("model"),
        firmware_version=payload.get("firmware_version"),
        protocol=payload.get("protocol") or "mqtt",
        transport=payload.get("transport"),
        room=payload.get("room"),
        read_only=payload.get("read_only", True),
        controllable=payload.get("controllable", False),
        metadata=payload.get("metadata", {}),
        capabilities=[
            *discovered_capabilities,
            backend_availability_capability(),
        ],
    )

    write_device(conn, device)

    return ProcessingResult()

def handle_telemetry_message(conn, ingestion_message: IngestionMessage) -> ProcessingResult:
    payload = ingestion_message.payload
    external_device_id = payload["device_id"]

    device_id = get_device_id_by_external_id(
        conn=conn,
        external_device_id=external_device_id,
    )

    if device_id is None:
        raise IngestionProcessingError(
            "unknown_device",
            f"Unknown device: {external_device_id}",
        )

    warnings: list[ProcessingWarning] = []

    raw_seq = payload.get("seq")
    seq: int | None

    if raw_seq is None:
        seq = None
    elif isinstance(raw_seq, int):
        seq = raw_seq
    else:
        seq = None
        warnings.append(
            ProcessingWarning(
                code="invalid_seq",
                message=(
                    f"Invalid seq for device '{external_device_id}': "
                    f"expected integer, got {type(raw_seq).__name__}"
                ),
            )
        )

    measurements = payload["measurements"]

    for metric, value in measurements.items():
        capability = get_device_capability_by_id(
            conn=conn,
            device_id=device_id,
            capability_id=metric,
        )

        if capability is None:
            warnings.append(
                ProcessingWarning(
                    code="unknown_metric",
                    message=(
                        f"Unknown metric '{metric}' "
                        f"for device '{external_device_id}'"
                    ),
                )
            )
            continue

        _capability_ref, stored_capability_id, stored_unit = capability

        if not is_supported_scalar_value(value):
            warnings.append(
                ProcessingWarning(
                    code="unsupported_value_type",
                    message=(
                        f"Unsupported value type for metric '{metric}' "
                        f"on device '{external_device_id}': "
                        f"{type(value).__name__}"
                    ),
                )
            )
            continue

        measurement = NormalizedMeasurement(
            external_device_id=external_device_id,
            capability_id=stored_capability_id,
            metric=metric,
            value=value,
            event_ts=ingestion_message.event_ts,
            server_received_at=ingestion_message.server_received_at,
            unit=stored_unit,
            seq=seq,
            raw_payload_text=ingestion_message.raw_payload,
        )

        write_measurement(
            conn=conn,
            measurement=measurement,
        )

    return ProcessingResult(warnings=warnings)

def handle_availability_message(conn, ingestion_message: IngestionMessage) -> ProcessingResult:
    payload = ingestion_message.payload

    event = NormalizedAvailabilityEvent(
        external_device_id=payload["device_id"],
        status=payload["status"],
        reason=payload.get("reason"),
        event_ts=ingestion_message.event_ts,
        server_received_at=ingestion_message.server_received_at,
        raw_payload_text=ingestion_message.raw_payload,
    )

    write_availability_event(conn, event)

    return ProcessingResult()

def handle_signal(signum, frame):
    print(f"signal received: {signum}", flush=True)
    stop_event.set()

def status_from_processing_result(result: ProcessingResult) -> tuple[str, str | None, str | None]:
    if not result.has_warnings:
        return "accepted", None, None

    if len(result.warnings) == 1:
        warning = result.warnings[0]
        return "accepted_with_warnings", warning.code, warning.message

    return (
        "accepted_with_warnings",
        "multiple_warnings",
        "; ".join(f"{warning.code}: {warning.message}" for warning in result.warnings),
    )

def on_connect(client, userdata, flags, reason_code, properties=None):
    print(
        f"connected to MQTT broker host={MQTT_HOST} port={MQTT_PORT} reason_code={reason_code}",
        flush=True,
    )

    topic_filter = f"{MQTT_TOPIC_PREFIX}/#"
    client.subscribe(topic_filter, qos=1)

    print(f"subscribed to {topic_filter}", flush=True)


def on_disconnect(client, userdata, DisconnectFlag, reason_code, properties=None, rc=0):
    print(f"disconnected from MQTT broker reason_code={reason_code}", flush=True)

def payload_to_text(raw_payload: bytes) -> str:
    try:
        return raw_payload.decode("utf-8")
    except UnicodeDecodeError:
        return "<non-utf8 payload>"

def on_message(client, userdata, msg):
    raw_payload_text = payload_to_text(msg.payload)

    parsed = parse_topic(msg.topic, prefix=MQTT_TOPIC_PREFIX)

    if parsed is None:
        print(f"unsupported topic topic={msg.topic}", flush=True)

        try:
            with get_connection() as conn:
                insert_ingestion_event(
                    conn,
                    mqtt_topic=msg.topic,
                    message_type=None,
                    device_external_id=None,
                    status="error",
                    error_code="unsupported_topic",
                    error_message="MQTT topic does not match Device MQTT API",
                    raw_payload_text=raw_payload_text,
                )
                conn.commit()
        except Exception as db_exc:
            print(f"failed to write ingestion_event error={db_exc}", flush=True)

        return

    try:
        ingestion_message = build_ingestion_message(
            parsed,
            msg.payload,
            retain=msg.retain,
            qos=msg.qos,
        )
    except IngestionValidationError as exc:
        print(
            f"invalid message "
            f"topic={msg.topic} "
            f"code={exc.code} "
            f"error={exc.message}",
            flush=True,
        )

        try:
            with get_connection() as conn:
                insert_ingestion_event(
                    conn,
                    mqtt_topic=msg.topic,
                    message_type=parsed.message_type,
                    device_external_id=parsed.device_id,
                    status="error",
                    error_code=exc.code,
                    error_message=exc.message,
                    raw_payload_text=raw_payload_text,
                )
                conn.commit()
        except Exception as db_exc:
            print(f"failed to write ingestion_event error={db_exc}", flush=True)

        return

    print(
        f"valid message "
        f"type={ingestion_message.parsed_topic.message_type} "
        f"device_id={ingestion_message.parsed_topic.device_id} "
        f"event_ts={ingestion_message.event_ts.isoformat()} "
        f"server_received_at={ingestion_message.server_received_at.isoformat()} "
        f"retain={ingestion_message.retain} "
        f"qos={ingestion_message.qos}",
        flush=True,
    )

    try:
        with get_connection() as conn:
            message_type = ingestion_message.parsed_topic.message_type

            if message_type == "discovery":
                result = handle_discovery_message(conn, ingestion_message)
            elif message_type == "telemetry":
                result = handle_telemetry_message(conn, ingestion_message)
            elif message_type == "availability":
                result = handle_availability_message(conn, ingestion_message)
            else:
                result = ProcessingResult()

            status, detail_code, detail_message = status_from_processing_result(result)

            insert_ingestion_event(
                conn,
                mqtt_topic=msg.topic,
                message_type=message_type,
                device_external_id=ingestion_message.parsed_topic.device_id,
                status=status,
                error_code=detail_code,
                error_message=detail_message,
                raw_payload_text=ingestion_message.raw_payload,
            )

            conn.commit()

            print(
                f"processed message "
                f"type={message_type} "
                f"device_id={ingestion_message.parsed_topic.device_id} "
                f"status={status}",
                flush=True,
            )

    except IngestionProcessingError as exc:
        print(
            f"processing error "
            f"topic={msg.topic} "
            f"code={exc.code} "
            f"error={exc.message}",
            flush=True,
        )

        try:
            with get_connection() as conn:
                insert_ingestion_event(
                    conn,
                    mqtt_topic=msg.topic,
                    message_type=ingestion_message.parsed_topic.message_type,
                    device_external_id=ingestion_message.parsed_topic.device_id,
                    status="error",
                    error_code=exc.code,
                    error_message=exc.message,
                    raw_payload_text=ingestion_message.raw_payload,
                )
                conn.commit()
        except Exception as db_exc:
            print(f"failed to write processing error ingestion_event error={db_exc}", flush=True)

    except Exception as db_exc:
        print(f"failed to process valid message error={db_exc}", flush=True)



def main():
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print("checking database connection", flush=True)
    check_db_connection()
    print("database connection ok", flush=True)

    client = mqtt.Client(
        client_id=MQTT_CLIENT_ID,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    print(
        f"starting worker mqtt_host={MQTT_HOST} mqtt_port={MQTT_PORT} client_id={MQTT_CLIENT_ID}",
        flush=True,
    )

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()

    while not stop_event.is_set():
        stop_event.wait(timeout=0.5)

    print("worker shutdown requested", flush=True)

    client.disconnect()
    client.loop_stop()

    print("worker stopped", flush=True)


if __name__ == "__main__":
    main()