import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDeviceSummaries } from "../../api/client";
import type {
    DeviceCapability,
    DeviceStateItem,
    DeviceSummary,
} from "../../api/types";

function formatDateTime(value: string | null): string {
    if (!value) {
        return "—";
    }

    return new Date(value).toLocaleString();
}

function formatValue(state: DeviceStateItem | undefined): string {
    if (!state || state.value === null || state.value === undefined) {
        return "—";
    }

    const value = state.value;

    if (typeof value === "boolean") {
        return value ? "true" : "false";
    }

    if (typeof value === "number") {
        const formattedValue = Number.isInteger(value)
            ? String(value)
            : value.toFixed(2);

        return state.unit ? `${formattedValue} ${state.unit}` : formattedValue;
    }

    return state.unit ? `${value} ${state.unit}` : value;
}

function findStateForCapability(
    state: DeviceStateItem[],
    capabilityId: string,
): DeviceStateItem | undefined {
    return state.find((item) => item.capability_id === capabilityId);
}

function buildMetricUrl(
    deviceId: string,
    capabilityId: string,
): string {
    return `/metrics/${encodeURIComponent(deviceId)}/${encodeURIComponent(
        capabilityId,
    )}`;
}

function DeviceCapabilityRow({
    summary,
    capability,
}: {
    summary: DeviceSummary;
    capability: DeviceCapability;
}) {
    const state = findStateForCapability(
        summary.state,
        capability.capability_id,
    );

    const content = (
        <>
            <div className="device-card__capability-main">
                <strong>{capability.display_name}</strong>
                <span>{capability.capability_type}</span>
            </div>

            <div className="device-card__value">{formatValue(state)}</div>
        </>
    );

    if (capability.chartable) {
        return (
            <Link
                className="device-card__capability device-card__capability--clickable"
                to={buildMetricUrl(
                    summary.device.device_id,
                    capability.capability_id,
                )}
            >
                {content}
            </Link>
        );
    }

    return <div className="device-card__capability">{content}</div>;
}

function DeviceSummaryCard({ summary }: { summary: DeviceSummary }) {
    return (
        <article className="device-card">
            <div className="device-card__header">
                <div>
                    <h3>{summary.device.name}</h3>
                    <p>{summary.device.device_id}</p>
                </div>

                <span className="device-card__protocol">
                    {summary.device.protocol}
                </span>
            </div>

            <div className="device-card__meta">
                <div>
                    <strong>Manufacturer</strong>
                    <br />
                    {summary.device.manufacturer ?? "—"}
                </div>

                <div>
                    <strong>Model</strong>
                    <br />
                    {summary.device.model ?? "—"}
                </div>

                <div>
                    <strong>Last seen</strong>
                    <br />
                    {formatDateTime(summary.device.last_seen_at)}
                </div>
            </div>

            <div className="device-card__capabilities">
                {summary.capabilities.map((capability) => (
                    <DeviceCapabilityRow
                        key={capability.capability_id}
                        summary={summary}
                        capability={capability}
                    />
                ))}

                {summary.capabilities.length === 0 ? (
                    <p>No capabilities discovered yet</p>
                ) : null}
            </div>
        </article>
    );
}

export function DevicesPage() {
    const [devices, setDevices] = useState<DeviceSummary[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    useEffect(() => {
        let isCancelled = false;

        async function loadDevices() {
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

        loadDevices();

        const intervalId = window.setInterval(loadDevices, 5000);

        return () => {
            isCancelled = true;
            window.clearInterval(intervalId);
        };
    }, []);

    if (isLoading) {
        return <p>Loading devices…</p>;
    }

    return (
        <section>
            <div className="page-header">
                <h2>Devices</h2>
                <p>{devices.length} discovered devices</p>
            </div>

            {errorMessage ? (
                <p className="error">Failed to load devices: {errorMessage}</p>
            ) : null}

            <div className="device-grid">
                {devices.map((summary) => (
                    <DeviceSummaryCard
                        key={summary.device.device_id}
                        summary={summary}
                    />
                ))}

                {devices.length === 0 ? <p>No devices discovered yet</p> : null}
            </div>
        </section>
    );
}