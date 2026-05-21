from http import client
import json
import os
import signal
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "home/iot/v1").strip("/")

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
DEVICE_ID = os.getenv("DEVICE_ID", "lab-mqtt-01")
KEEPALIVE_SEC = int(os.getenv("KEEPALIVE", "30"))

is_running = True

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def topic_availability() -> str:
    return f"{MQTT_TOPIC_PREFIX}/device/{DEVICE_ID}/availability"

def topic_discovery() -> str:
    return f"{MQTT_TOPIC_PREFIX}/discovery/{DEVICE_ID}"

def publish_json(client: mqtt.Client, topic: str, payload: dict, *, qos: int, retain: bool):
    client.publish(
        topic,
        json.dumps(payload, ensure_ascii=False),
        qos=qos,
        retain=retain,
    )

def handle_signal(signum, frame):
    global is_running
    is_running = False

def main():
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    client = mqtt.Client(client_id=f"emu-{DEVICE_ID}")

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=KEEPALIVE_SEC)
    client.loop_start()

    publish_json(
        client,
        topic_availability(),
        {
            "schema_version": 1,
            "device_id": DEVICE_ID,
            "ts": now_iso(),
            "status": "online",
            "reason": "connected",
        },
        qos=1,
        retain=True,
    )

    publish_json(
        client,
        topic_discovery(),
        {
            "schema_version": 1,
            "device_id": DEVICE_ID,
            "name": "Lab MQTT Device 01",
            "manufacturer": "DIY",
            "model": "pc-emulator-v1",
            "firmware_version": "0.1.0",
            "protocol": "mqtt",
            "transport": "tcp",
            "room": "cabinet",
            "read_only": True,
            "controllable": False,
            "capabilities": [
                {
                    "id": "temperature",
                    "type": "sensor.temperature",
                    "direction": "ro",
                    "unit": "°C",
                    "value_type": "number",
                },
                {
                    "id": "humidity",
                    "type": "sensor.humidity",
                    "direction": "ro",
                    "unit": "%",
                    "value_type": "number",
                },
                {
                    "id": "voltage",
                    "type": "meter.voltage",
                    "direction": "ro",
                    "unit": "V",
                    "value_type": "number",
                },
                {
                    "id": "power",
                    "type": "meter.power",
                    "direction": "ro",
                    "unit": "W",
                    "value_type": "number",
                },
                {
                    "id": "device_status",
                    "type": "device.status",
                    "direction": "ro",
                    "value_type": "string",
                },
            ],
        },
        qos=1,
        retain=True,
    )

    print(f"Emulator connected as emu-{DEVICE_ID} to {MQTT_HOST}:{MQTT_PORT}")
    print("Press Ctrl+C to gracefully stop the emulator.")

    while is_running:
        time.sleep(0.5)

    print("graceful shutdown requested")

    publish_json(
        client,
        topic_availability(),
        {
            "schema_version": 1,
            "device_id": DEVICE_ID,
            "ts": now_iso(),
            "status": "offline",
            "reason": "graceful_disconnect",
        },
        qos=1,
        retain=True,
    )

    time.sleep(0.5)
    client.disconnect()
    client.loop_stop()

    print("emulator stopped")


if __name__ == "__main__":
    main()
