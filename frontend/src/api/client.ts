import type {
  Device,
  DeviceStatesResponse,
  DeviceStateGroup,
  DeviceStateItem,
  DeviceWithState,
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