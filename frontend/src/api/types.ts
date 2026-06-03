export type Device = {
  device_id: string;
  name: string;
  manufacturer: string;
  model: string | null;
  protocol: string;
  transport: string | null;
  room: string | null;
  read_only: boolean;
  controllable: boolean;
  last_seen_at: string | null;
};

export type DeviceStateItem = {
  capability_id: string;
  capability_type: string | null;
  value_type: string | null;
  unit: string | null;
  value: number | string | boolean | null;
  event_ts: string;
  server_received_at: string;
};

export type DeviceStateGroup = {
  device_id: string;
  state: DeviceStateItem[];
};

export type DeviceStatesResponse = {
  devices: DeviceStateGroup[];
};

export type DeviceWithState = {
  device: Device;
  state: DeviceStateItem[];
};

export type AppTab = "dashboard" | "devices" | "metrics" | "events";

export type DeviceCapability = {
  capability_id: string;
  display_name: string;
  capability_type: string;
  direction: string;
  unit: string | null;
  value_type: string;
  source: string;
  chartable: boolean;
};

export type DeviceSummary = {
  device: Device;
  capabilities: DeviceCapability[];
  state: DeviceStateItem[];
};

export type DeviceSummariesResponse = {
  devices: DeviceSummary[];
};

export type MeasurementPoint = {
  ts: string;
  value: number | null;
};

export type MeasurementsResponse = {
  device_id: string;
  capability_id: string;
  unit: string | null;
  points: MeasurementPoint[];
};

export type IngestionEvent = {
  id: string;
  server_received_at: string;
  mqtt_topic: string;
  message_type: string | null;
  device_external_id: string | null;
  status: string;
  error_code: string | null;
  error_message: string | null;
  payload_preview: string | null;
};

export type IngestionEventsResponse = {
  events: IngestionEvent[];
};