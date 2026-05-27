import { useEffect, useState } from "react";
import "./App.css";

type Device = {
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

type DeviceStateItem = {
  capability_id: string;
  capability_type: string | null;
  value_type: string | null;
  unit: string | null;
  value: number | string | boolean | null;
  event_ts: string;
  server_received_at: string;
};

type DeviceStateGroup = {
  device_id: string;
  state: DeviceStateItem[];
};

type DeviceStatesResponse = {
  devices: DeviceStateGroup[];
};

type DeviceWithState = {
  device: Device;
  state: DeviceStateItem[];
};

type LoadState =
  | { status: "loading" }
  | { status: "loaded"; devices: DeviceWithState[] }
  | { status: "error"; message: string };

function formatValue(item: DeviceStateItem): string {
  if (item.value === null) {
    return "—";
  }

  const value =
    typeof item.value === "boolean" ? String(item.value) : item.value;

  return item.unit ? `${value} ${item.unit}` : String(value);
}

function getAvailabilityLabel(state: DeviceStateItem[]): string {
  const availability = state.find(
    (item) => item.capability_id === "availability",
  );

  if (availability?.value === "online") {
    return "online";
  }

  if (availability?.value === "offline") {
    return "offline";
  }

  return "unknown";
}

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

async function loadDevicesWithState(): Promise<DeviceWithState[]> {
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

function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    async function load() {
      try {
        const devices = await loadDevicesWithState();
        setState({ status: "loaded", devices });
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unknown error";

        setState({ status: "error", message });
      }
    }

    load();
  }, []);

  return (
    <main className="page">
      <header className="page-header">
        <div>
          <h1>IoTAssistant</h1>
          <p>Read-only device dashboard</p>
        </div>
      </header>

      {state.status === "loading" && <p>Loading devices...</p>}

      {state.status === "error" && (
        <section className="error-card">
          <h2>Failed to load devices</h2>
          <p>{state.message}</p>
        </section>
      )}

      {state.status === "loaded" && (
        <section className="devices-grid">
          {state.devices.map(({ device, state: deviceState }) => {
            const availability = getAvailabilityLabel(deviceState);

            return (
              <article className="device-card" key={device.device_id}>
                <div className="device-card-header">
                  <div>
                    <h2>{device.name}</h2>
                    <p>{device.device_id}</p>
                  </div>

                  <span className={`status-pill status-${availability}`}>
                    {availability}
                  </span>
                </div>

                <dl className="device-meta">
                  <div>
                    <dt>Manufacturer</dt>
                    <dd>{device.manufacturer}</dd>
                  </div>

                  <div>
                    <dt>Model</dt>
                    <dd>{device.model ?? "—"}</dd>
                  </div>

                  <div>
                    <dt>Room</dt>
                    <dd>{device.room ?? "—"}</dd>
                  </div>

                  <div>
                    <dt>Protocol</dt>
                    <dd>{device.protocol}</dd>
                  </div>

                  <div>
                    <dt>Last seen</dt>
                    <dd>{device.last_seen_at ?? "—"}</dd>
                  </div>
                </dl>

                <section className="state-section">
                  <h3>Current state</h3>

                  {deviceState.length === 0 ? (
                    <p className="muted">No state received yet.</p>
                  ) : (
                    <dl className="state-list">
                      {deviceState.map((item) => (
                        <div key={item.capability_id}>
                          <dt>{item.capability_id}</dt>
                          <dd>{formatValue(item)}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </section>
              </article>
            );
          })}
        </section>
      )}
    </main>
  );
}

export default App;