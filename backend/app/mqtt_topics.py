from dataclasses import dataclass
import re

DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class ParsedTopic:
    message_type: str
    device_id: str
    raw_topic: str


def is_valid_device_id(device_id: str) -> bool:
    return bool(DEVICE_ID_RE.fullmatch(device_id))


def parse_topic(topic: str, prefix: str = "home/iot/v1") -> ParsedTopic | None:
    """
    Parse MQTT topic according to Home IoT Device MQTT API.

    Supported:
        <prefix>/discovery/<device_id>
        <prefix>/device/<device_id>/<message_type>

    Returns ParsedTopic or None if topic is unsupported/invalid.
    """
    normalized_prefix = prefix.strip("/")
    parts = topic.strip("/").split("/")
    prefix_parts = normalized_prefix.split("/")

    if parts[:len(prefix_parts)] != prefix_parts:
        return None

    rest = parts[len(prefix_parts):]

    # home/iot/v1/discovery/<device_id>
    if len(rest) == 2 and rest[0] == "discovery":
        device_id = rest[1]

        if not is_valid_device_id(device_id):
            return None

        return ParsedTopic(
            message_type="discovery",
            device_id=device_id,
            raw_topic=topic,
        )

    # home/iot/v1/device/<device_id>/<message_type>
    if len(rest) == 3 and rest[0] == "device":
        device_id = rest[1]
        message_type = rest[2]

        if not is_valid_device_id(device_id):
            return None

        if message_type not in {
            "availability",
            "telemetry",
            "state",
            "command",
            "command_ack",
            "error",
        }:
            return None

        return ParsedTopic(
            message_type=message_type,
            device_id=device_id,
            raw_topic=topic,
        )

    return None