import type { DeviceWithState, DeviceStateItem } from "../api/types";

type DeviceCardProps = {
    item: DeviceWithState;
};

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

export function DeviceCard({ item }: DeviceCardProps) {
    const { device, state } = item;
    const availability = getAvailabilityLabel(state);

    return (
        <article className="device-card">
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

                {state.length === 0 ? (
                    <p className="muted">No state received yet.</p>
                ) : (
                    <dl className="state-list">
                        {state.map((stateItem) => (
                            <div key={stateItem.capability_id}>
                                <dt>{stateItem.capability_id}</dt>
                                <dd>{formatValue(stateItem)}</dd>
                            </div>
                        ))}
                    </dl>
                )}
            </section>
        </article>
    );
}