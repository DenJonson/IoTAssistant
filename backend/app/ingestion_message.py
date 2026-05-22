import json
from dataclasses import dataclass
from typing import Any

from mqtt_topics import ParsedTopic


SUPPORTED_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class IngestionMessage:
    parsed_topic: ParsedTopic
    payload: dict[str, Any]
    raw_payload: str
    retain: bool
    qos: int


class IngestionValidationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def decode_json_payload(raw_bytes: bytes) -> tuple[str, dict[str, Any]]:
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IngestionValidationError(
            code="invalid_utf8",
            message=f"Payload is not valid UTF-8: {exc}",
        ) from exc

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise IngestionValidationError(
            code="invalid_json",
            message=f"Payload is not valid JSON: {exc}",
        ) from exc

    if not isinstance(payload, dict):
        raise IngestionValidationError(
            code="payload_not_object",
            message="Payload root must be a JSON object",
        )

    return raw_text, payload


def validate_common_payload(parsed_topic: ParsedTopic, payload: dict[str, Any]) -> None:
    schema_version = payload.get("schema_version")

    if schema_version is None:
        raise IngestionValidationError(
            code="missing_schema_version",
            message="Missing required field: schema_version",
        )

    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise IngestionValidationError(
            code="unsupported_schema_version",
            message=f"Unsupported schema_version={schema_version}",
        )

    payload_device_id = payload.get("device_id")

    if not isinstance(payload_device_id, str) or not payload_device_id:
        raise IngestionValidationError(
            code="missing_device_id",
            message="Missing or invalid required field: device_id",
        )

    if payload_device_id != parsed_topic.device_id:
        raise IngestionValidationError(
            code="device_id_mismatch",
            message=(
                f"Topic device_id={parsed_topic.device_id} "
                f"does not match payload device_id={payload_device_id}"
            ),
        )


def validate_message_specific_payload(
    parsed_topic: ParsedTopic,
    payload: dict[str, Any],
) -> None:
    message_type = parsed_topic.message_type

    if message_type == "discovery":
        capabilities = payload.get("capabilities")

        if not isinstance(capabilities, list):
            raise IngestionValidationError(
                code="missing_capabilities",
                message="Discovery payload must contain capabilities array",
            )

        return

    if message_type == "telemetry":
        measurements = payload.get("measurements")

        if not isinstance(measurements, dict):
            raise IngestionValidationError(
                code="missing_measurements",
                message="Telemetry payload must contain measurements object",
            )

        return

    if message_type == "availability":
        status = payload.get("status")

        if not isinstance(status, str) or not status:
            raise IngestionValidationError(
                code="missing_status",
                message="Availability payload must contain non-empty status string",
            )

        return

    return


def build_ingestion_message(
    parsed_topic: ParsedTopic,
    raw_payload_bytes: bytes,
    *,
    retain: bool,
    qos: int,
) -> IngestionMessage:
    raw_text, payload = decode_json_payload(raw_payload_bytes)

    validate_common_payload(parsed_topic, payload)
    validate_message_specific_payload(parsed_topic, payload)

    return IngestionMessage(
        parsed_topic=parsed_topic,
        payload=payload,
        raw_payload=raw_text,
        retain=retain,
        qos=qos,
    )