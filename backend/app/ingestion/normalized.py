from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


ScalarValue = float | int | str | bool


@dataclass(frozen=True)
class NormalizedCapability:
    capability_id: str
    capability_type: str
    direction: str
    value_type: str
    unit: str | None = None
    source: str = "integration"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedDevice:
    external_device_id: str
    name: str
    manufacturer: str
    protocol: str
    model: str | None = None
    firmware_version: str | None = None
    transport: str | None = None
    room: str | None = None
    read_only: bool = True
    controllable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    capabilities: list[NormalizedCapability] = field(default_factory=list)


@dataclass(frozen=True)
class NormalizedStateValue:
    external_device_id: str
    capability_id: str
    value: ScalarValue
    event_ts: datetime
    server_received_at: datetime
    unit: str | None = None


@dataclass(frozen=True)
class NormalizedMeasurement:
    external_device_id: str
    capability_id: str
    metric: str
    value: ScalarValue
    event_ts: datetime
    server_received_at: datetime
    unit: str | None = None
    seq: int | None = None
    raw_payload_text: str | None = None


@dataclass(frozen=True)
class NormalizedAvailabilityEvent:
    external_device_id: str
    status: str
    event_ts: datetime
    server_received_at: datetime
    reason: str | None = None
    raw_payload_text: str | None = None