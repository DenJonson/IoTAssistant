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
from app.repository import insert_ingestion_event

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "home/iot/v1").strip("/")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "iot-worker-dev")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://iot:iot_dev_password@localhost:5432/iot",
)

stop_event = threading.Event()

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
        print(f"failed to write ingestion_event error={db_exc}", flush=True)


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