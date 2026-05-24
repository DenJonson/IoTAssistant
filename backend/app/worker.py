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
    update_device_last_seen,
    upsert_device_capability,
    upsert_device_from_discovery,
    upsert_device_state_current,
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

def handle_discovery_message(conn, ingestion_message) -> None:
    payload = ingestion_message.payload

    device_id = upsert_device_from_discovery(
        conn,
        payload=payload,
    )

    capabilities = payload["capabilities"]

    for capability in capabilities:
        upsert_device_capability(
            conn,
            device_id=device_id,
            capability=capability,
        )

def handle_telemetry_message(conn, ingestion_message) -> None:
    parsed_topic = ingestion_message.parsed_topic
    payload = ingestion_message.payload

    external_device_id = parsed_topic.device_id

    device_id = get_device_id_by_external_id(
        conn,
        external_device_id=external_device_id,
    )

    if device_id is None:
        raise RuntimeError(f"unknown_device external_device_id={external_device_id}")

    measurements = payload["measurements"]
    seq = payload.get("seq")

    if seq is not None and not isinstance(seq, int):
        seq = None

    for metric, value in measurements.items():
        capability = get_device_capability_by_id(
            conn,
            device_id=device_id,
            capability_id=metric,
        )

        if capability is None:
            print(
                f"unknown metric ignored "
                f"device_id={external_device_id} "
                f"metric={metric}",
                flush=True,
            )
            continue

        capability_ref, stored_capability_id, unit = capability

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
            source="mqtt",
            seq=seq,
        )

        upsert_device_state_current(
            conn,
            device_id=device_id,
            capability_id=metric,
            event_ts=ingestion_message.event_ts,
            server_received_at=ingestion_message.server_received_at,
            value=value,
            unit=unit,
            source="mqtt",
        )

    update_device_last_seen(conn, device_id=device_id)

def handle_signal(signum, frame):
    print(f"signal received: {signum}", flush=True)
    stop_event.set()


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
            if ingestion_message.parsed_topic.message_type == "discovery":
                handle_discovery_message(conn, ingestion_message)
            if ingestion_message.parsed_topic.message_type == "telemetry":
                handle_telemetry_message(conn, ingestion_message)

            insert_ingestion_event(
                conn,
                mqtt_topic=msg.topic,
                message_type=ingestion_message.parsed_topic.message_type,
                device_external_id=ingestion_message.parsed_topic.device_id,
                status="accepted",
                raw_payload_text=ingestion_message.raw_payload,
            )

            conn.commit()
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