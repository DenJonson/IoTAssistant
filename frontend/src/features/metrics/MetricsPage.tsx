import { useEffect, useMemo, useState } from "react";
import {
    fetchDeviceMeasurements,
    fetchDeviceSummaries,
} from "../../api/client";
import type {
    DeviceCapability,
    DeviceSummary,
    MeasurementPoint,
    MeasurementsResponse,
} from "../../api/types";

type SelectedMetric = {
    deviceId: string;
    capabilityId: string;
};

function formatValue(value: number | null, unit: string | null): string {
    if (value === null || value === undefined) {
        return "—";
    }

    const formatted = Number(value.toFixed(2)).toString();

    return unit ? `${formatted} ${unit}` : formatted;
}

function formatDateTime(value: string): string {
    return new Date(value).toLocaleString();
}

function findCapability(
    summaries: DeviceSummary[],
    selected: SelectedMetric | null,
): DeviceCapability | null {
    if (!selected) {
        return null;
    }

    const summary = summaries.find(
        (item) => item.device.device_id === selected.deviceId,
    );

    if (!summary) {
        return null;
    }

    return (
        summary.capabilities.find(
            (capability) => capability.capability_id === selected.capabilityId,
        ) ?? null
    );
}

function getChartableCapabilities(summary: DeviceSummary): DeviceCapability[] {
    return summary.capabilities.filter((capability) => capability.chartable);
}

function buildInitialSelection(
    summaries: DeviceSummary[],
): SelectedMetric | null {
    for (const summary of summaries) {
        const capability = getChartableCapabilities(summary)[0];

        if (capability) {
            return {
                deviceId: summary.device.device_id,
                capabilityId: capability.capability_id,
            };
        }
    }

    return null;
}

function LineChart({
    points,
    unit,
}: {
    points: MeasurementPoint[];
    unit: string | null;
}) {
    const numericPoints = points.filter(
        (point): point is MeasurementPoint & { value: number } =>
            typeof point.value === "number",
    );

    if (numericPoints.length < 2) {
        return (
            <div className="metrics-chart metrics-chart--empty">
                Not enough data for chart
            </div>
        );
    }

    const width = 720;
    const height = 260;
    const padding = 32;

    const values = numericPoints.map((point) => point.value);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const valueRange = maxValue - minValue || 1;

    const pointsForSvg = numericPoints.map((point, index) => {
        const x =
            padding +
            (index / Math.max(numericPoints.length - 1, 1)) * (width - padding * 2);

        const y =
            padding +
            ((maxValue - point.value) / valueRange) * (height - padding * 2);

        return { x, y, point };
    });

    const polylinePoints = pointsForSvg
        .map((item) => `${item.x},${item.y}`)
        .join(" ");

    const latest = numericPoints[numericPoints.length - 1];

    return (
        <div className="metrics-chart">
            <div className="metrics-chart__summary">
                <span>
                    Min: <strong>{formatValue(minValue, unit)}</strong>
                </span>
                <span>
                    Max: <strong>{formatValue(maxValue, unit)}</strong>
                </span>
                <span>
                    Latest: <strong>{formatValue(latest.value, unit)}</strong>
                </span>
            </div>

            <svg
                className="metrics-chart__svg"
                viewBox={`0 0 ${width} ${height}`}
                role="img"
                aria-label="Measurements line chart"
            >
                <line
                    x1={padding}
                    y1={height - padding}
                    x2={width - padding}
                    y2={height - padding}
                    className="metrics-chart__axis"
                />
                <line
                    x1={padding}
                    y1={padding}
                    x2={padding}
                    y2={height - padding}
                    className="metrics-chart__axis"
                />

                <polyline
                    points={polylinePoints}
                    fill="none"
                    className="metrics-chart__line"
                />

                {pointsForSvg.map((item) => (
                    <circle
                        key={`${item.point.ts}-${item.x}`}
                        cx={item.x}
                        cy={item.y}
                        r="3"
                        className="metrics-chart__point"
                    />
                ))}
            </svg>
        </div>
    );
}

export function MetricsPage() {
    const [summaries, setSummaries] = useState<DeviceSummary[]>([]);
    const [selected, setSelected] = useState<SelectedMetric | null>(null);
    const [measurements, setMeasurements] = useState<MeasurementsResponse | null>(
        null,
    );
    const [isLoadingSummaries, setIsLoadingSummaries] = useState(true);
    const [isLoadingMeasurements, setIsLoadingMeasurements] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    const selectedCapability = useMemo(
        () => findCapability(summaries, selected),
        [summaries, selected],
    );

    useEffect(() => {
        let isCancelled = false;

        async function loadSummaries() {
            try {
                const response = await fetchDeviceSummaries();

                if (isCancelled) {
                    return;
                }

                setSummaries(response.devices);
                setSelected((current) => current ?? buildInitialSelection(response.devices));
                setErrorMessage(null);
            } catch (error) {
                if (!isCancelled) {
                    setErrorMessage(
                        error instanceof Error ? error.message : "Unknown error",
                    );
                }
            } finally {
                if (!isCancelled) {
                    setIsLoadingSummaries(false);
                }
            }
        }

        loadSummaries();

        return () => {
            isCancelled = true;
        };
    }, []);

    useEffect(() => {
        if (!selected) {
            setMeasurements(null);
            return;
        }

        const deviceId = selected.deviceId;
        const capabilityId = selected.capabilityId;

        let isCancelled = false;

        async function loadMeasurements() {
            try {
                setIsLoadingMeasurements(true);

                const response = await fetchDeviceMeasurements(
                    deviceId,
                    capabilityId,
                    100,
                );

                if (!isCancelled) {
                    setMeasurements(response);
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
                    setIsLoadingMeasurements(false);
                }
            }
        }

        loadMeasurements();

        const intervalId = window.setInterval(loadMeasurements, 5000);

        return () => {
            isCancelled = true;
            window.clearInterval(intervalId);
        };
    }, [selected]);
    if (isLoadingSummaries) {
        return <p>Loading metrics…</p>;
    }

    const chartableDeviceSummaries = summaries.filter(
        (summary) => getChartableCapabilities(summary).length > 0,
    );

    if (chartableDeviceSummaries.length === 0) {
        return (
            <section>
                <div className="page-header">
                    <h2>Metrics</h2>
                    <p>No chartable capabilities found</p>
                </div>
            </section>
        );
    }

    return (
        <section>
            <div className="page-header">
                <h2>Metrics</h2>
                <p>Historical measurements</p>
            </div>

            {errorMessage ? (
                <p className="error">Failed to load metrics: {errorMessage}</p>
            ) : null}

            <div className="metrics-controls">
                <label>
                    Device
                    <select
                        value={selected?.deviceId ?? ""}
                        onChange={(event) => {
                            const deviceId = event.target.value;
                            const summary = summaries.find(
                                (item) => item.device.device_id === deviceId,
                            );
                            const firstCapability = summary
                                ? getChartableCapabilities(summary)[0]
                                : undefined;

                            setSelected(
                                firstCapability
                                    ? {
                                        deviceId,
                                        capabilityId: firstCapability.capability_id,
                                    }
                                    : null,
                            );
                        }}
                    >
                        {chartableDeviceSummaries.map((summary) => (
                            <option
                                key={summary.device.device_id}
                                value={summary.device.device_id}
                            >
                                {summary.device.name} / {summary.device.device_id}
                            </option>
                        ))}
                    </select>
                </label>

                <label>
                    Capability
                    <select
                        value={selected?.capabilityId ?? ""}
                        onChange={(event) => {
                            const selectedDeviceId = selected?.deviceId;

                            if (!selectedDeviceId) {
                                return;
                            }

                            setSelected({
                                deviceId: selectedDeviceId,
                                capabilityId: event.target.value,
                            });
                        }}
                    >
                        {summaries
                            .find((summary) => summary.device.device_id === selected?.deviceId)
                            ?.capabilities.filter((capability) => capability.chartable)
                            .map((capability) => (
                                <option
                                    key={capability.capability_id}
                                    value={capability.capability_id}
                                >
                                    {capability.display_name}
                                </option>
                            ))}
                    </select>
                </label>
            </div>

            <div className="metrics-panel">
                <div className="metrics-panel__header">
                    <div>
                        <h3>{selectedCapability?.display_name ?? "Metric"}</h3>
                        <p>{selectedCapability?.capability_type}</p>
                    </div>

                    {isLoadingMeasurements ? (
                        <span className="metrics-panel__status">Refreshing…</span>
                    ) : null}
                </div>

                <LineChart
                    points={measurements?.points ?? []}
                    unit={measurements?.unit ?? selectedCapability?.unit ?? null}
                />

                <div className="metrics-table">
                    <table>
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Value</th>
                            </tr>
                        </thead>
                        <tbody>
                            {(measurements?.points ?? []).slice(0, 20).map((point) => (
                                <tr key={`${point.ts}-${point.value}`}>
                                    <td>{formatDateTime(point.ts)}</td>
                                    <td>
                                        {formatValue(
                                            point.value,
                                            measurements?.unit ?? selectedCapability?.unit ?? null,
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>
    );
}