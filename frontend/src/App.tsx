import { useEffect, useState } from "react";
import { loadDevicesWithState } from "./api/client";
import type { AppTab, DeviceWithState } from "./api/types";
import { AppShell } from "./components/AppShell";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { DevicesPage } from "./features/devices/DevicesPage";
import { EventsPage } from "./features/events/EventsPage";
import { MetricsPage } from "./features/metrics/MetricsPage";
import "./App.css";

type LoadState =
  | { status: "loading" }
  | { status: "loaded"; devices: DeviceWithState[] }
  | { status: "error"; message: string };

function App() {
  const [activeTab, setActiveTab] = useState<AppTab>("dashboard");
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

  function renderContent() {
    if (state.status === "loading") {
      return <p>Loading system state...</p>;
    }

    if (state.status === "error") {
      return (
        <section className="error-card">
          <h2>Failed to load system state</h2>
          <p>{state.message}</p>
        </section>
      );
    }

    if (activeTab === "dashboard") {
      return <DashboardPage devices={state.devices} />;
    }

    if (activeTab === "devices") {
      return <DevicesPage devices={state.devices} />;
    }

    if (activeTab === "metrics") {
      return <MetricsPage />;
    }

    return <EventsPage />;
  }

  return (
    <AppShell activeTab={activeTab} onTabChange={setActiveTab}>
      {renderContent()}
    </AppShell>
  );
}

export default App;