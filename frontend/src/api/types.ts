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