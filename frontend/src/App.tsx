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

type LoadState =
  | { status: "loading" }
  | { status: "loaded"; devices: Device[] }
  | { status: "error"; message: string };

function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    async function loadDevices() {
      try {
        const response = await fetch("/api/devices");

        if (!response.ok) {
          throw new Error(`API returned ${response.status}`);
        }

        const devices = (await response.json()) as Device[];
        setState({ status: "loaded", devices });
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unknown error";

        setState({ status: "error", message });
      }
    }

    loadDevices();
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
          {state.devices.map((device) => (
            <article className="device-card" key={device.device_id}>
              <div className="device-card-header">
                <h2>{device.name}</h2>
                <span>{device.protocol}</span>
              </div>

              <dl>
                <div>
                  <dt>Device ID</dt>
                  <dd>{device.device_id}</dd>
                </div>

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
                  <dt>Last seen</dt>
                  <dd>{device.last_seen_at ?? "—"}</dd>
                </div>
              </dl>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}

export default App;