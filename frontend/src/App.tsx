import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { DevicesPage } from "./features/devices/DevicesPage";
import { EventsPage } from "./features/events/EventsPage";
import { MetricsPage } from "./features/metrics/MetricsPage";
import "./App.css";

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/devices" element={<DevicesPage />} />
        <Route path="/metrics" element={<MetricsPage />} />
        <Route
          path="/metrics/:deviceId/:capabilityId"
          element={<MetricsPage />}
        />
        <Route path="/events" element={<EventsPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AppShell>
  );
}