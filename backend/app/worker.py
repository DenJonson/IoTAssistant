import os
import signal
import threading

import paho.mqtt.client as mqtt

from mqtt_topics import parse_topic
from ingestion_message import (
    IngestionValidationError,
    build_ingestion_message,
)


MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "home/iot/v1").strip("/")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "iot-worker-dev")

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


def on_message(client, userdata, msg):
    parsed = parse_topic(msg.topic, prefix=MQTT_TOPIC_PREFIX)

    if parsed is None:
        print(f"unsupported topic topic={msg.topic}", flush=True)
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
            f"invalid message \n"
            f"topic={msg.topic} \n"
            f"code={exc.code} \n"
            f"error={exc.message}\n\n",
            flush=True,
        )
        return

    print(
        f"valid message \n"
        f"type={ingestion_message.parsed_topic.message_type} \n"
        f"device_id={ingestion_message.parsed_topic.device_id} \n"
        f"retain={ingestion_message.retain} \n"
        f"qos={ingestion_message.qos}\n",
        flush=True,
    )


def main():
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

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