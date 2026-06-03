import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
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

function formatDeviceOptionLabel(summary: DeviceSummary): string {
    return `${summary.device.name} · ${summary.device.device_id}`;
}

function getChartableCapabilities(summary: DeviceSummary): DeviceCapability[] {
    return summary.capabilities.filter((capability) => capability.chartable);
}

function buildMetricsUrl(deviceId: string, capabilityId: string): string {
    return `/metrics/${encodeURIComponent(deviceId)}/${encodeURIComponent(
        capabilityId,
    )}`;
}

function buildInitialSelection(devices: DeviceSummary[]): SelectedMetric | null {
    for (const summary of devices) {
        const firstCapability = getChartableCapabilities(summary)[0];

        if (firstCapability) {
            return {
                deviceId: summary.device.device_id,
                capabilityId: firstCapability.capability_id,
            };
        }
    }

    return null;
}

function isValidSelection(
    devices: DeviceSummary[],
    selection: SelectedMetric,
): boolean {
    const summary = devices.find(
        (item) => item.device.device_id === selection.deviceId,
    );

    if (!summary) {
        return false;
    }

    return getChartableCapabilities(summary).some(
        (capability) => capability.capability_id === selection.capabilityId,
    );
}

function formatDateTime(value: string): string {
    return new Date(value).toLocaleString();
}

function formatNumber(value: number | null, unit: string | null): string {
    if (value === null) {
        return "—";
    }

    const formattedValue = Number.isInteger(value)
        ? String(value)
        : value.toFixed(2);

    return unit ? `${formattedValue} ${unit}` : formattedValue;
}

type ChartPoint = {
    x: number;
    y: number;
    ts: string;
    value: number;
};

function buildChartPoints(points: MeasurementPoint[]): ChartPoint[] {
    const numericPoints = points.filter(
        (point): point is { ts: string; value: number } => point.value !== null,
    );

    if (numericPoints.length === 0) {
        return [];
    }

    const width = 720;
    const height = 240;
    const padding = 24;

    const values = numericPoints.map((point) => point.value);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const valueRange = maxValue - minValue || 1;

    const denominator = Math.max(numericPoints.length - 1, 1);

    return numericPoints.map((point, index) => {
        const x = padding + (index / denominator) * (width - padding * 2);

        const y =
            height -
            padding -
            ((point.value - minValue) / valueRange) * (height - padding * 2);

        return {
            x,
            y,
            ts: point.ts,
            value: point.value,
        };
    });
}

function buildPath(chartPoints: ChartPoint[]): string {
    return chartPoints
        .map((point, index) => {
            return `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(
                2,
            )}`;
        })
        .join(" ");
}

function MetricsChart({
    measurements,
}: {
    measurements: MeasurementsResponse;
}) {
    const points = measurements.points;
    const numericValues = points
        .map((point) => point.value)
        .filter((value): value is number => value !== null);

    const chartPoints = buildChartPoints(points);
    const path = buildPath(chartPoints);

    if (numericValues.length === 0 || !path) {
        return (
            <div className="metrics-chart metrics-chart--empty">
                No numeric measurements yet
            </div>
        );
    }

    const minValue = Math.min(...numericValues);
    const maxValue = Math.max(...numericValues);
    const latestValue = numericValues[numericValues.length - 1];

    return (
        <div className="metrics-chart">
            <div className="metrics-chart__summary">
                <span>
                    Latest:{" "}
                    <strong>{formatNumber(latestValue, measurements.unit)}</strong>
                </span>
                <span>
                    Min: <strong>{formatNumber(minValue, measurements.unit)}</strong>
                </span>
                <span>
                    Max: <strong>{formatNumber(maxValue, measurements.unit)}</strong>
                </span>
                <span>
                    Points: <strong>{points.length}</strong>
                </span>
            </div>

            <svg
                className="metrics-chart__svg"
                viewBox="0 0 720 240"
                role="img"
                aria-label="Measurement history chart"
            >
                <line
                    className="metrics-chart__axis"
                    x1="24"
                    y1="216"
                    x2="696"
                    y2="216"
                />
                <line
                    className="metrics-chart__axis"
                    x1="24"
                    y1="24"
                    x2="24"
                    y2="216"
                />
                <path className="metrics-chart__line" d={path} />


                {chartPoints.map((point) => (
                    <circle
                        className="metrics-chart__point"
                        key={`${point.ts}-${point.value}`}
                        cx={point.x}
                        cy={point.y}
                        r="3.5"
                    />
                ))}
            </svg>
        </div>
    );
}

export function MetricsPage() {
    const navigate = useNavigate();

    const params = useParams<{
        deviceId?: string;
        capabilityId?: string;
    }>();

    const routeSelection = useMemo<SelectedMetric | null>(() => {
        if (!params.deviceId || !params.capabilityId) {
            return null;
        }

        return {
            deviceId: decodeURIComponent(params.deviceId),
            capabilityId: decodeURIComponent(params.capabilityId),
        };
    }, [params.deviceId, params.capabilityId]);

    const [summaries, setSummaries] = useState<DeviceSummary[]>([]);
    const [selected, setSelected] = useState<SelectedMetric | null>(null);
    const [measurements, setMeasurements] =
        useState<MeasurementsResponse | null>(null);
    const [isLoadingSummaries, setIsLoadingSummaries] = useState(true);
    const [isLoadingMeasurements, setIsLoadingMeasurements] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    useEffect(() => {
        let isCancelled = false;

        async function loadSummaries() {
            try {
                setIsLoadingSummaries(true);

                const response = await fetchDeviceSummaries();

                if (isCancelled) {
                    return;
                }

                setSummaries(response.devices);

                if (routeSelection && isValidSelection(response.devices, routeSelection)) {
                    setSelected(routeSelection);
                    setErrorMessage(null);
                    return;
                }

                const fallbackSelection = buildInitialSelection(response.devices);
                setSelected(fallbackSelection);

                if (routeSelection && fallbackSelection) {
                    navigate(
                        buildMetricsUrl(
                            fallbackSelection.deviceId,
                            fallbackSelection.capabilityId,
                        ),
                        { replace: true },
                    );
                }

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
    }, [navigate, routeSelection]);

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

    const selectedSummary = selected
        ? summaries.find((summary) => summary.device.device_id === selected.deviceId)
        : undefined;

    const selectedCapabilities = selectedSummary
        ? getChartableCapabilities(selectedSummary)
        : [];

    const selectedCapability =
        selected && selectedSummary
            ? selectedCapabilities.find(
                (capability) => capability.capability_id === selected.capabilityId,
            )
            : undefined;

    if (isLoadingSummaries) {
        return <p>Loading metrics…</p>;
    }

    return (
        <section>
            <div className="page-header">
                <div>
                    <h2>Metrics</h2>
                    <p>Numeric measurement history</p>
                </div>
            </div>

            {errorMessage ? (
                <p className="error">Failed to load metrics: {errorMessage}</p>
            ) : null}

            {summaries.length === 0 ? (
                <p>No devices discovered yet</p>
            ) : (
                <>
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

                                    if (!firstCapability) {
                                        setSelected(null);
                                        navigate("/metrics");
                                        return;
                                    }

                                    navigate(
                                        buildMetricsUrl(deviceId, firstCapability.capability_id),
                                    );
                                }}
                            >
                                {summaries.map((summary) => (
                                    <option
                                        key={summary.device.device_id}
                                        value={summary.device.device_id}
                                    >
                                        {formatDeviceOptionLabel(summary)}
                                    </option>
                                ))}
                            </select>
                        </label>

                        <label>
                            Capability
                            <select
                                value={selected?.capabilityId ?? ""}
                                disabled={!selectedSummary || selectedCapabilities.length === 0}
                                onChange={(event) => {
                                    const selectedDeviceId = selected?.deviceId;

                                    if (!selectedDeviceId) {
                                        return;
                                    }

                                    navigate(
                                        buildMetricsUrl(selectedDeviceId, event.target.value),
                                    );
                                }}
                            >
                                {selectedCapabilities.map((capability) => (
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

                    {!selected || !selectedSummary || !selectedCapability ? (
                        <p>No chartable capabilities available</p>
                    ) : (
                        <div className="metrics-panel">
                            <div className="metrics-panel__header">
                                <div>
                                    <h3>{selectedCapability.display_name}</h3>
                                    <p>
                                        {selectedSummary.device.name} ·{" "}
                                        {selectedCapability.capability_type}
                                    </p>
                                </div>

                                <span className="metrics-panel__status">
                                    {isLoadingMeasurements ? "Refreshing…" : "Auto-refresh 5s"}
                                </span>
                            </div>

                            {measurements ? (
                                <>
                                    <MetricsChart measurements={measurements} />

                                    <div className="metrics-table">
                                        <table>
                                            <thead>
                                                <tr>
                                                    <th>Timestamp</th>
                                                    <th>Value</th>
                                                </tr>
                                            </thead>

                                            <tbody>
                                                {measurements.points.map((point) => (
                                                    <tr key={`${point.ts}-${point.value ?? "null"}`}>
                                                        <td>{formatDateTime(point.ts)}</td>
                                                        <td>{formatNumber(point.value, measurements.unit)}</td>
                                                    </tr>
                                                ))}

                                                {measurements.points.length === 0 ? (
                                                    <tr>
                                                        <td colSpan={2}>No measurements yet</td>
                                                    </tr>
                                                ) : null}
                                            </tbody>
                                        </table>
                                    </div>
                                </>
                            ) : (
                                <div className="metrics-chart metrics-chart--empty">
                                    No measurements loaded
                                </div>
                            )}
                        </div>
                    )}
                </>
            )}
        </section>
    );
}