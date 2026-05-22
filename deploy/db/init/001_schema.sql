CREATE TABLE device (
    id UUID PRIMARY KEY,
    external_device_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    manufacturer TEXT NOT NULL,
    model TEXT,
    firmware_version TEXT,
    protocol TEXT NOT NULL,
    transport TEXT,
    room TEXT,
    read_only BOOLEAN NOT NULL DEFAULT TRUE,
    controllable BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ
);

CREATE TABLE device_capability (
    id UUID PRIMARY KEY,
    device_id UUID NOT NULL REFERENCES device(id) ON DELETE CASCADE,
    capability_id TEXT NOT NULL,
    capability_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    unit TEXT,
    value_type TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (device_id, capability_id)
);

CREATE TABLE measurement_raw (
    event_ts TIMESTAMPTZ NOT NULL,
    server_received_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    device_id UUID NOT NULL REFERENCES device(id) ON DELETE CASCADE,
    capability_ref UUID REFERENCES device_capability(id) ON DELETE SET NULL,

    metric TEXT NOT NULL,
    capability_id TEXT NOT NULL,

    value_num DOUBLE PRECISION,
    value_text TEXT,
    value_bool BOOLEAN,
    value_json JSONB,

    unit TEXT,
    source TEXT NOT NULL,
    seq BIGINT,
    quality SMALLINT NOT NULL DEFAULT 100,

    raw_payload JSONB
);

CREATE TABLE device_state_current (
    device_id UUID NOT NULL REFERENCES device(id) ON DELETE CASCADE,
    capability_id TEXT NOT NULL,
    capability_type TEXT NOT NULL,

    event_ts TIMESTAMPTZ NOT NULL,
    server_received_at TIMESTAMPTZ NOT NULL,

    value_num DOUBLE PRECISION,
    value_text TEXT,
    value_bool BOOLEAN,
    value_json JSONB,

    unit TEXT,
    source TEXT NOT NULL,

    PRIMARY KEY(device_id, capability_id)
);

CREATE TABLE device_availability_event (
    id UUID PRIMARY KEY,
    device_id UUID NOT NULL REFERENCES device(id) ON DELETE CASCADE,

    event_ts TIMESTAMPTZ NOT NULL,
    server_received_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    status TEXT NOT NULL,
    reason TEXT,
    source TEXT NOT NULL,
    raw_payload JSONB
);

CREATE TABLE ingestion_event (
    id UUID PRIMARY KEY,
    server_received_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    mqtt_topic TEXT NOT NULL,
    message_type TEXT,
    device_external_id TEXT,

    status TEXT NOT NULL,
    error_code TEXT,
    error_message TEXT,

    raw_payload JSONB
);

CREATE INDEX idx_device_external_device_id
ON device (external_device_id);

CREATE INDEX idx_capability_device_capability_id
ON device_capability (device_id, capability_id);

CREATE INDEX idx_measurement_device_metric_ts
ON measurement_raw (device_id, metric, event_ts DESC);

CREATE INDEX idx_measurement_capability_type_ts
ON measurement_raw (capability_type, event_ts DESC);

CREATE INDEX idx_availability_device_ts
ON device_availability_event (device_id, event_ts DESC);

CREATE INDEX idx_ingestion_event_received_at
ON ingestion_event (server_received_at DESC);