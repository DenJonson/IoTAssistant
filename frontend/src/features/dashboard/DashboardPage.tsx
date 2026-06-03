import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDeviceSummaries } from "../../api/client";
import type { DeviceSummary } from "../../api/types";

const STALE_AFTER_MS = 5 * 60 * 1000;

function formatDateTime(value: string | null): string {
    if (!value) {
        return "—";
    }

    return new Date(value).toLocaleString();
}

function isRecentlyUpdated(lastSeenAt: string | null): boolean {
    if (!lastSeenAt) {
        return false;
    }

    const timestamp = new Date(lastSeenAt).getTime();

    if (Number.isNaN(timestamp)) {
        return false;
    }

    return Date.now() - timestamp <= STALE_AFTER_MS;
}

function countByProtocol(devices: DeviceSummary[]): Map<string, number> {
    const result = new Map<string, number>();

    for (const summary of devices) {
        const protocol = summary.device.protocol || "unknown";
        result.set(protocol, (result.get(protocol) ?? 0) + 1);
    }

    return result;
}

function compareLastSeenDesc(a: DeviceSummary, b: DeviceSummary): number {
    const left = a.device.last_seen_at
        ? new Date(a.device.last_seen_at).getTime()
        : 0;

    const right = b.device.last_seen_at
        ? new Date(b.device.last_seen_at).getTime()
        : 0;

    return right - left;
}

export function DashboardPage() {
    const [devices, setDevices] = useState<DeviceSummary[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    useEffect(() => {
        let isCancelled = false;

        async function loadDashboard() {
            try {
                const response = await fetchDeviceSummaries();

                if (!isCancelled) {
                    setDevices(response.devices);
                    setErrorMessage(null);
                }
            } catch (error) {
                if (!isCancelled) {
                    setErrorMessage(
                        error instanceof Error ? error.message : "Unknown error",
                    );
                }
            } finally {
                if (!isCancelled) {
                    setIsLoading(false);
                }
            }
        }

        loadDashboard();

        const intervalId = window.setInterval(loadDashboard, 5000);

        return () => {
            isCancelled = true;
            window.clearInterval(intervalId);
        };
    }, []);

    const dashboard = useMemo(() => {
        const totalDevices = devices.length;
        const devicesWithState = devices.filter(
            (summary) => summary.state.length > 0,
        ).length;
        const devicesWithoutState = totalDevices - devicesWithState;

        const totalCapabilities = devices.reduce(
            (sum, summary) => sum + summary.capabilities.length,
            0,
        );

        const chartableCapabilities = devices.reduce(
            (sum, summary) =>
                sum +
                summary.capabilities.filter((capability) => capability.chartable)
                    .length,
            0,
        );

        const recentlyUpdated = devices.filter((summary) =>
            isRecentlyUpdated(summary.device.last_seen_at),
        ).length;

        const staleOrNeverSeen = totalDevices - recentlyUpdated;

        const protocols = Array.from(countByProtocol(devices).entries()).sort(
            ([left], [right]) => left.localeCompare(right),
        );

        const latestDevices = [...devices]
            .sort(compareLastSeenDesc)
            .slice(0, 6);

        const devicesWithoutStateList = devices
            .filter((summary) => summary.state.length === 0)
            .slice(0, 6);

        return {
            totalDevices,
            devicesWithState,
            devicesWithoutState,
            totalCapabilities,
            chartableCapabilities,
            recentlyUpdated,
            staleOrNeverSeen,
            protocols,
            latestDevices,
            devicesWithoutStateList,
        };
    }, [devices]);

    if (isLoading) {
        return <p>Loading dashboard…</p>;
    }

    return (
        <section>
            <div className="page-header">
                <div>
                    <h2>Dashboard</h2>
                    <p>System overview based on discovered devices and current state</p>
                </div>
            </div>

            {errorMessage ? (
                <p className="error">Failed to load dashboard: {errorMessage}</p>
            ) : null}

            <div className="dashboard-grid">
                <div className="dashboard-card">
                    <span>Total devices</span>
                    <strong>{dashboard.totalDevices}</strong>
                </div>

                <div className="dashboard-card">
                    <span>With state</span>
                    <strong>{dashboard.devicesWithState}</strong>
                </div>

                <div className="dashboard-card">
                    <span>Without state</span>
                    <strong>{dashboard.devicesWithoutState}</strong>
                </div>

                <div className="dashboard-card">
                    <span>Capabilities</span>
                    <strong>{dashboard.totalCapabilities}</strong>
                </div>

                <div className="dashboard-card">
                    <span>Chartable metrics</span>
                    <strong>{dashboard.chartableCapabilities}</strong>
                </div>

                <div className="dashboard-card">
                    <span>Updated &lt; 5 min</span>
                    <strong>{dashboard.recentlyUpdated}</strong>
                </div>

                <div className="dashboard-card">
                    <span>Stale / never seen</span>
                    <strong>{dashboard.staleOrNeverSeen}</strong>
                </div>
            </div>

            <div className="dashboard-panels">
                <section className="panel">
                    <div className="panel__header">
                        <h3>Protocols</h3>
                        <p>Integration split</p>
                    </div>

                    <div className="dashboard-list">
                        {dashboard.protocols.map(([protocol, count]) => (
                            <div className="dashboard-list__row" key={protocol}>
                                <span>{protocol}</span>
                                <strong>{count}</strong>
                            </div>
                        ))}

                        {dashboard.protocols.length === 0 ? (
                            <p className="muted">No protocols yet</p>
                        ) : null}
                    </div>
                </section>

                <section className="panel">
                    <div className="panel__header">
                        <h3>Latest updates</h3>
                        <p>Most recently seen devices</p>
                    </div>

                    <div className="dashboard-list">
                        {dashboard.latestDevices.map((summary) => (
                            <Link
                                className="dashboard-list__row dashboard-list__row--link"
                                key={summary.device.device_id}
                                to="/devices"
                            >
                                <span>
                                    <strong>{summary.device.name}</strong>
                                    <small>{summary.device.device_id}</small>
                                </span>
                                <time>{formatDateTime(summary.device.last_seen_at)}</time>
                            </Link>
                        ))}

                        {dashboard.latestDevices.length === 0 ? (
                            <p className="muted">No device updates yet</p>
                        ) : null}
                    </div>
                </section>

                <section className="panel">
                    <div className="panel__header">
                        <h3>Without state</h3>
                        <p>Discovered but no current values</p>
                    </div>

                    <div className="dashboard-list">
                        {dashboard.devicesWithoutStateList.map((summary) => (
                            <Link
                                className="dashboard-list__row dashboard-list__row--link"
                                key={summary.device.device_id}
                                to="/devices"
                            >
                                <span>
                                    <strong>{summary.device.name}</strong>
                                    <small>{summary.device.device_id}</small>
                                </span>
                                <em>{summary.device.protocol}</em>
                            </Link>
                        ))}

                        {dashboard.devicesWithoutStateList.length === 0 ? (
                            <p className="muted">All discovered devices have current state</p>
                        ) : null}
                    </div>
                </section>
            </div>
        </section>
    );
}