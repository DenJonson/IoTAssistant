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

PUBLISH_INTERVAL_SEC = float(os.getenv("PUBLISH_INTERVAL_SEC", "1"))


class DeviceEmulator:

    TELEMETRY_QOS = int(os.getenv("TELEMETRY_QOS", "1"))

    def create_device_discovery_payload(self) -> dict:
        if(self.protocol == "mqtt"):
            return {
                "schema_version": 1,
                "device_id": self.device_id,
                "ts": str(datetime.now(timezone.utc)),
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
                        "id": "device_status", # пример свойства текущего сосотояния устройства (заупщен, остановлен, ошибка и тд)
                        "type": "device.status",
                        "direction": "ro",
                        "value_type": "string",
                    },
                ],
            }
        if(self.protocol == "home_assistant_mqtt"):
            return {
                    "name": "Temperature Sensor",
                    "unique_id": self.device_id + "-temperature",
                    "state_topic": "homeassistant/" + self.device_id + "/state",
                    "value_template": "{{ value_json.temperature }}",
                    "device_class": "temperature",
                    "state_class": "measurement",
                    "unit_of_measurement": "°C",
                    "device": {
                        "identifiers": [self.device_id],
                        "name": "Lab MQTT 01",
                        "manufacturer": "IoTAssistant Emulator",
                        "model": "MQTT Lab Device"
                    }
                    }

    def __init__(self, *, device_id: str = DEVICE_ID, protocol: str = "mqtt"):
        self.seq = 0
        self.temperature = 22.0
        self.humidity = 45.0
        self.voltage = 220.0
        self.power = 100.0
        self.device_status = "normal"
        self.is_running = True
        self.device_id = device_id
        self.client = mqtt.Client(client_id=f"emu-{self.device_id}")
        self.protocol = protocol

    def start(self):
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

        self.client.will_set(
            self.topic_availability(),
            payload=json.dumps({
                "schema_version": 1,
                "device_id": self.device_id,
                "ts": self.now_iso(),
                "status": "offline",
                "reason": "lwt",
            }, ensure_ascii=False),
            qos=1,
            retain=True,
        )

        self.client.connect(MQTT_HOST, MQTT_PORT, keepalive=KEEPALIVE_SEC)
        self.client.loop_start()

        self.publish_json(
            self.client,
            self.topic_discovery(),
            self.create_device_discovery_payload(),
            qos=1,
            retain=True,
        )

        if(self.protocol == "mqtt"):
            self.publish_json(
                self.client,
                self.topic_availability(),
                {
                    "schema_version": 1,
                    "device_id": self.device_id,
                    "ts": self.now_iso(),
                    "status": "online",
                    "reason": "connected",
                },
                qos=1,
                retain=True,
            )

        print(f"Emulator connected as emu-{self.device_id} to {MQTT_HOST}:{MQTT_PORT}")
        

    def stop(self):
        print("graceful shutdown requested")

        self.publish_json(
            self.client,
            self.topic_availability(),
            {
                "schema_version": 1,
                "device_id": self.device_id,
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

        print(f"emulator {self.device_id} stopped")

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def topic_availability(self) -> str:
        return f"{MQTT_TOPIC_PREFIX}/device/{self.device_id}/availability"
    
    def topic_telemetry(self) -> str:
        if(self.protocol == "mqtt"):
            return f"{MQTT_TOPIC_PREFIX}/device/{self.device_id}/telemetry"
        if(self.protocol == "home_assistant_mqtt"):
            return f"homeassistant/{self.device_id}/state"

    def topic_discovery(self) -> str:
        if(self.protocol == "mqtt"):
            return f"{MQTT_TOPIC_PREFIX}/discovery/{self.device_id}"
        if(self.protocol == "home_assistant_mqtt"):
            return f"homeassistant/sensor/{self.device_id}/temperature/config"

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
        if(self.protocol == "mqtt"):
            return {
                "schema_version": 1,
                "device_id": self.device_id,
                "ts": self.now_iso(),
                "seq": seq,
                "measurements": {
                    "temperature": round(temperature, 2),
                    "humidity": round(humidity, 2),
                    "voltage": round(230.0 + random.uniform(-3.0, 3.0), 2),
                    "power": round(10.0 + random.uniform(-2.0, 5.0), 2),
                    "unknown_param" : "unexpected_value", # пример невалидного параметра, который должен быть проигнорирован при обработке
                },
            }
        if(self.protocol == "home_assistant_mqtt"):
            return {
                    "temperature": round(temperature, 2),
                    "humidity": round(humidity, 2)
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

        print(f"telemetry for {self.device_id} published seq={self.seq}", flush=True)

        ##############################################################################



def main():
    device1 = DeviceEmulator(device_id = DEVICE_ID, protocol="mqtt")
    device1.start()
    device2 = DeviceEmulator(device_id = DEVICE_ID + "-2", protocol="mqtt")
    device2.start()
    device3 = DeviceEmulator(device_id = DEVICE_ID + "-ha", protocol="home_assistant_mqtt")
    device3.start()

    print("Press Ctrl+C to gracefully stop the emulator.")

    while device1.is_running and device2.is_running and device3.is_running:
        time.sleep(PUBLISH_INTERVAL_SEC)
        device1.publish_telemetry()  
        device2.publish_telemetry()
        device3.publish_telemetry()

    device1.stop()
    device2.stop()
    device3.stop()

if __name__ == "__main__":
    main()
