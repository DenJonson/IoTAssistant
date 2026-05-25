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

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "home/iot/v1").strip("/")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "iot-worker-dev")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://iot:iot_dev_password@localhost:5432/iot",
)

stop_event = threading.Event()

def handle_discovery_message(conn, ingestion_message) -> ProcessingResult:
    payload = ingestion_message.payload

    device_id = upsert_device_from_discovery(
        conn,
        payload=payload,
    )

    discovered_capabilities = payload["capabilities"]

    system_capabilities = [
        {
            "id": "availability",
            "type": "device.availability",
            "unit": None,
            "value_type": "string",
            "direction": "ro",
            "source": "backend",
        }
    ]

    capabilities = [
        *discovered_capabilities,
        *system_capabilities,
    ]


    for capability in capabilities:
        upsert_device_capability(
            conn,
            device_id=device_id,
            capability=capability,
        )
    
    return ProcessingResult()

def handle_telemetry_message(conn, ingestion_message) -> ProcessingResult:
    parsed_topic = ingestion_message.parsed_topic
    payload = ingestion_message.payload

    external_device_id = parsed_topic.device_id

    device_id = get_device_id_by_external_id(
        conn,
        external_device_id=external_device_id,
    )

    if device_id is None:
        raise IngestionProcessingError(
            code="unknown_device",
            message=f"Unknown device external_device_id={external_device_id}",
        )

    warnings: list[ProcessingWarning] = []

    measurements = payload["measurements"]
    seq = payload.get("seq")

    if seq is not None and not isinstance(seq, int):
        warnings.append(
            ProcessingWarning(
                code="invalid_seq",
                message=f"Invalid seq type for device={external_device_id}",
            )
        )
        seq = None

    for metric, value in measurements.items():
        capability = get_device_capability_by_id(
            conn,
            device_id=device_id,
            capability_id=metric,
        )

        if capability is None:
            warnings.append(
                ProcessingWarning(
                    code="unknown_metric",
                    message=(
                        f"Unknown metric ignored "
                        f"device={external_device_id} metric={metric}"
                    ),
                )
            )
            continue

        capability_ref, stored_capability_id, unit = capability

        if not isinstance(value, (int, float, str, bool)):
            warnings.append(
                ProcessingWarning(
                    code="unsupported_value_type",
                    message=(
                        f"Unsupported value type ignored "
                        f"device={external_device_id} metric={metric} "
                        f"type={type(value).__name__}"
                    ),
                )
            )
            continue

        insert_measurement_raw(
            conn,
            event_ts=ingestion_message.event_ts,
            server_received_at=ingestion_message.server_received_at,
            device_id=device_id,
            capability_ref=capability_ref,
            metric=metric,
            capability_id=stored_capability_id,
            value=value,
            unit=unit,
            seq=seq,
            raw_payload_text=ingestion_message.raw_payload,
        )

        upsert_device_state_current(
            conn,
            device_id=device_id,
            capability_id=metric,
            event_ts=ingestion_message.event_ts,
            server_received_at=ingestion_message.server_received_at,
            value=value,
            unit=unit,
        )

    update_device_last_seen(conn, device_id=device_id)

    return ProcessingResult(warnings=warnings)

def handle_availability_message(conn, ingestion_message) -> ProcessingResult:
    parsed_topic = ingestion_message.parsed_topic
    payload = ingestion_message.payload

    external_device_id = parsed_topic.device_id

    device_id = get_device_id_by_external_id(
        conn,
        external_device_id=external_device_id,
    )

    if device_id is None:
        raise IngestionProcessingError(
            code="unknown_device",
            message=f"Unknown device external_device_id={external_device_id}",
        )

    status = payload["status"]
    reason = payload.get("reason")

    if reason is not None and not isinstance(reason, str):
        reason = str(reason)

    insert_device_availability_event(
        conn,
        device_id=device_id,
        event_ts=ingestion_message.event_ts,
        server_received_at=ingestion_message.server_received_at,
        status=status,
        reason=reason,
        raw_payload_text=ingestion_message.raw_payload,
    )

    upsert_device_state_current(
        conn,
        device_id=device_id,
        capability_id="availability",
        event_ts=ingestion_message.event_ts,
        server_received_at=ingestion_message.server_received_at,
        value=status,
        unit=None,
    )

    update_device_last_seen(conn, device_id=device_id)

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