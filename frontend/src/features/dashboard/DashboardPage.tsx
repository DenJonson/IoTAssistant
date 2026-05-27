import type { DeviceStateItem, DeviceWithState } from "../../api/types";
import { StatCard } from "../../components/StatCard";

type DashboardPageProps = {
    devices: DeviceWithState[];
};

function getAvailability(state: DeviceStateItem[]): string {
    const availability = state.find(
        (item) => item.capability_id === "availability",
    );

    return typeof availability?.value === "string"
        ? availability.value
        : "unknown";
}

function countByAvailability(devices: DeviceWithState[]) {
    let online = 0;
    let offline = 0;
    let unknown = 0;
    let degraded = 0;

    for (const item of devices) {
        const availability = getAvailability(item.state);

        if (availability === "online") {
            online += 1;
        } else if (availability === "offline") {
            offline += 1;
        } else if (availability === "degraded") {
            degraded += 1;
        } else {
            unknown += 1;
        }
    }

    return { online, offline, unknown, degraded };
}

function getLastSeen(devices: DeviceWithState[]): string {
    const timestamps = devices
        .map((item) => item.device.last_seen_at)
        .filter((value): value is string => value !== null)
        .sort();

    if (timestamps.length === 0) {
        return "—";
    }

    return timestamps[timestamps.length - 1];
}

export function DashboardPage({ devices }: DashboardPageProps) {
    const availability = countByAvailability(devices);
    const devicesWithoutState = devices.filter(
        (item) => item.state.length === 0,
    ).length;

    return (
        <section className="dashboard-page">
            <div className="section-header">
                <h2>Dashboard</h2>
                <p>Current system overview based on device state.</p>
            </div>

            <section className="stats-grid">
                <StatCard title="Total devices" value={devices.length} />
                <StatCard title="Online" value={availability.online} />
                <StatCard title="Offline" value={availability.offline} />
                <StatCard title="Unknown" value={availability.unknown} />
                <StatCard title="Degraded" value={availability.degraded} />
                <StatCard
                    title="Without state"
                    value={devicesWithoutState}
                    hint="Known devices without current state rows"
                />
            </section>

            <section className="panel">
                <h3>System notes</h3>
                <ul className="notes-list">
                    <li>Device status is calculated from the `availability` capability.</li>
                    <li>Hardware resource monitoring is not implemented yet.</li>
                    <li>Last seen: {getLastSeen(devices)}</li>
                </ul>
            </section>
        </section>
    );
}