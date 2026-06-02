import { useEffect, useMemo, useState } from "react";
import { fetchDeviceSummaries } from "../../api/client";
import type { DeviceStateItem, DeviceSummary } from "../../api/types";

function formatValue(state: DeviceStateItem | undefined): string {
    if (!state || state.value === null || state.value === undefined) {
        return "—";
    }

    const value =
        typeof state.value === "number"
            ? Number(state.value.toFixed(2)).toString()
            : String(state.value);

    return state.unit ? `${value} ${state.unit}` : value;
}

function formatDateTime(value: string | null): string {
    if (!value) {
        return "never";
    }

    return new Date(value).toLocaleString();
}

function DeviceSummaryCard({ summary }: { summary: DeviceSummary }) {
    const stateByCapabilityId = useMemo(() => {
        const result = new Map<string, DeviceStateItem>();

        for (const state of summary.state) {
            result.set(state.capability_id, state);
        }

        return result;
    }, [summary.state]);

    return (
        <article className="device-card">
            <div className="device-card__header">
                <div>
                    <h3>{summary.device.name}</h3>
                    <p>{summary.device.device_id}</p>
                </div>

                <span className="device-card__protocol">
                    {summary.device.protocol}
                    {summary.device.transport ? ` / ${summary.device.transport}` : ""}
                </span>
            </div>

            <div className="device-card__meta">
                <span>
                    <strong>Manufacturer:</strong> {summary.device.manufacturer}
                </span>

                {summary.device.model ? (
                    <span>
                        <strong>Model:</strong> {summary.device.model}
                    </span>
                ) : null}

                <span>
                    <strong>Last seen:</strong> {formatDateTime(summary.device.last_seen_at)}
                </span>
            </div>

            <div className="device-card__capabilities">
                {summary.capabilities.length === 0 ? (
                    <p className="muted">No capabilities</p>
                ) : (
                    summary.capabilities.map((capability) => {
                        const state = stateByCapabilityId.get(capability.capability_id);

                        return (
                            <div className="device-card__capability" key={capability.capability_id}>
                                <div className="device-card__capability-main">
                                    <strong>{capability.display_name}</strong>
                                    <span>{capability.capability_type}</span>
                                </div>

                                <div className="device-card__value">{formatValue(state)}</div>
                            </div>
                        );
                    })
                )}
            </div>
        </article>
    );
}

export function DevicesPage() {
    const [summaries, setSummaries] = useState<DeviceSummary[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    useEffect(() => {
        let isCancelled = false;

        async function load() {
            try {
                const response = await fetchDeviceSummaries();

                if (!isCancelled) {
                    setSummaries(response.devices);
                    setErrorMessage(null);
                }
            } catch (error) {
                if (!isCancelled) {
                    setErrorMessage(error instanceof Error ? error.message : "Unknown error");
                }
            } finally {
                if (!isCancelled) {
                    setIsLoading(false);
                }
            }
        }

        load();

        const intervalId = window.setInterval(load, 5000);

        return () => {
            isCancelled = true;
            window.clearInterval(intervalId);
        };
    }, []);

    if (isLoading) {
        return <p>Loading devices…</p>;
    }

    if (errorMessage) {
        return <p className="error">Failed to load devices: {errorMessage}</p>;
    }

    return (
        <section>
            <div className="page-header">
                <h2>Devices</h2>
                <p>{summaries.length} devices</p>
            </div>

            <div className="device-grid">
                {summaries.map((summary) => (
                    <DeviceSummaryCard key={summary.device.device_id} summary={summary} />
                ))}
            </div>
        </section>
    );
}