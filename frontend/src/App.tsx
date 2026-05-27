import { useEffect, useState } from "react";
import { loadDevicesWithState } from "./api/client";
import type { DeviceWithState } from "./api/types";
import { DeviceGrid } from "./components/DeviceGrid";
import "./App.css";

type LoadState =
  | { status: "loading" }
  | { status: "loaded"; devices: DeviceWithState[] }
  | { status: "error"; message: string };

function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        const devices = await loadDevicesWithState();

        if (isMounted) {
          setState({ status: "loaded", devices });
        }
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unknown error";

        if (isMounted) {
          setState({ status: "error", message });
        }
      }
    }

    load();

    const intervalId = window.setInterval(() => {
      load();
    }, 5000);

    return () => {
      isMounted = false;
      window.clearInterval(intervalId);
    };
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
        <DeviceGrid devices={state.devices} />
      )}
    </main>
  );
}

export default App;