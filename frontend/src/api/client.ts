import type {
  Device,
  DeviceStatesResponse,
  DeviceSummariesResponse,
  DeviceStateGroup,
  DeviceStateItem,
  DeviceWithState,
  MeasurementsResponse,
  IngestionEventsResponse,
} from "./types";

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }

  return (await response.json()) as T;
}

function buildStateByDeviceId(
  stateGroups: DeviceStateGroup[],
): Map<string, DeviceStateItem[]> {
  return new Map(
    stateGroups.map((group) => [group.device_id, group.state]),
  );
}

export async function loadDevicesWithState(): Promise<DeviceWithState[]> {
  const [devices, deviceStates] = await Promise.all([
    fetchJson<Device[]>("/api/devices"),
    fetchJson<DeviceStatesResponse>("/api/device-states"),
  ]);

  const stateByDeviceId = buildStateByDeviceId(deviceStates.devices);

  return devices.map((device) => ({
    device,
    state: stateByDeviceId.get(device.device_id) ?? [],
  }));
}

export async function fetchDeviceSummaries(): Promise<DeviceSummariesResponse> {
  const response = await fetch("/api/device-summaries");

  if (!response.ok) {
    throw new Error(`Failed to fetch device summaries: ${response.status}`);
  }

  return response.json();
}

export async function fetchDeviceMeasurements(
  deviceId: string,
  capabilityId: string,
  limit = 100,
): Promise<MeasurementsResponse> {
  const response = await fetch(
    `/api/devices/${encodeURIComponent(deviceId)}/measurements?` +
      new URLSearchParams({
        capability_id: capabilityId,
        limit: String(limit),
      }),
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch measurements: ${response.status}`);
  }

  return response.json();
}

export async function fetchIngestionEvents(
  limit = 100,
): Promise<IngestionEventsResponse> {
  const response = await fetch(
    `/api/ingestion-events?${new URLSearchParams({
      limit: String(limit),
    })}`,
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch ingestion events: ${response.status}`);
  }

  return response.json();
}