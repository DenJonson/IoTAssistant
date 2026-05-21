from http import client
import json
import os
import random
import signal
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "home/iot/v1").strip("/")

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
DEVICE_ID = os.getenv("DEVICE_ID", "lab-mqtt-01")
KEEPALIVE_SEC = int(os.getenv("KEEPALIVE", "30"))

PUBLISH_INTERVAL_SEC = float(os.getenv("PUBLISH_INTERVAL_SEC", "0.5"))


class DeviceEmulator:

    TELEMETRY_QOS = int(os.getenv("TELEMETRY_QOS", "1"))

    DEVICE_DISCOVERY_PAYLOAD = {
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
        }

    def __init__(self):
        self.seq = 0
        self.temperature = 22.0
        self.humidity = 45.0
        self.voltage = 220.0
        self.power = 100.0
        self.device_status = "normal"
        self.is_running = True
        self.start()

    def start(self):
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

        self.client = mqtt.Client(client_id=f"emu-{DEVICE_ID}")

        self.client.connect(MQTT_HOST, MQTT_PORT, keepalive=KEEPALIVE_SEC)
        self.client.loop_start()

        self.publish_json(
            self.client,
            self.topic_availability(),
            {
                "schema_version": 1,
                "device_id": DEVICE_ID,
                "ts": self.now_iso(),
                "status": "online",
                "reason": "connected",
            },
            qos=1,
            retain=True,
        )

        self.publish_json(
            self.client,
            self.topic_discovery(),
            self.DEVICE_DISCOVERY_PAYLOAD,
            qos=1,
            retain=True,
        )

        print(f"Emulator connected as emu-{DEVICE_ID} to {MQTT_HOST}:{MQTT_PORT}")
        print("Press Ctrl+C to gracefully stop the emulator.")

    def stop(self):
        print("graceful shutdown requested")

        self.publish_json(
            self.client,
            self.topic_availability(),
            {
                "schema_version": 1,
                "device_id": DEVICE_ID,
                "ts": self.now_iso(),
                "status": "offline",
                "reason": "graceful_disconnect",
            },
            qos=1,
            retain=True,
        )

        time.sleep(0.5)
        self.client.disconnect()
        self.client.loop_stop()

        print("emulator stopped")

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def topic_availability(self) -> str:
        return f"{MQTT_TOPIC_PREFIX}/device/{DEVICE_ID}/availability"
    
    def topic_telemetry(self) -> str:
        return f"{MQTT_TOPIC_PREFIX}/device/{DEVICE_ID}/telemetry"

    def topic_discovery(self) -> str:
        return f"{MQTT_TOPIC_PREFIX}/discovery/{DEVICE_ID}"

    def publish_json(self, client: mqtt.Client, topic: str, payload: dict, *, qos: int, retain: bool):
        client.publish(
            topic,
            json.dumps(payload, ensure_ascii=False),
            qos=qos,
            retain=retain,
        )

    def handle_signal(self, signum, frame):
        print("\nStopping loop...")
        self.is_running = False

    def build_telemetry_payload(self, seq: int, temperature: float, humidity: float) -> dict:
        return {
            "schema_version": 1,
            "device_id": DEVICE_ID,
            "ts": self.now_iso(),
            "seq": seq,
            "measurements": {
                "temperature": round(temperature, 2),
                "humidity": round(humidity, 2),
                "voltage": round(230.0 + random.uniform(-3.0, 3.0), 2),
                "power": round(10.0 + random.uniform(-2.0, 5.0), 2),
            },
        }
    
    def clamp(self, value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))
    
    def publish_telemetry(self):
        if(self.is_running == False):
            return
        
        self.seq += 1
        self.temperature = self.clamp(
            self.temperature + random.uniform(-0.15, 0.15),
            18.0,
            28.0
        )
        self.humidity = self.clamp(
            self.humidity + random.uniform(-0.25, 0.25),
            30.0,
            70.0
        )

        payload = self.build_telemetry_payload(self.seq, self.temperature, self.humidity)

        self.publish_json(
            self.client,
            self.topic_telemetry(),
            payload,
            qos=self.TELEMETRY_QOS,
            retain=False,
        )

        print(f"telemetry published seq={self.seq}", flush=True)

        ##############################################################################
 


def main():
    device = DeviceEmulator()

    while device.is_running:
        time.sleep(PUBLISH_INTERVAL_SEC)
        device.publish_telemetry()   

    device.stop()

if __name__ == "__main__":
    main()
