import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
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

function buildMetricUrl(deviceId: string, capabilityId: string): string {
    return `/metrics/${encodeURIComponent(deviceId)}/${encodeURIComponent(
        capabilityId,
    )}`;
}

function normalizeSearchText(value: string): string {
    return value.trim().toLowerCase();
}

function escapeRegExp(value: string): string {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightText(value: string, query: string): ReactNode {
    const normalizedQuery = normalizeSearchText(query);

    if (!normalizedQuery) {
        return value;
    }

    const pattern = new RegExp(`(${escapeRegExp(normalizedQuery)})`, "ig");
    const parts = value.split(pattern);

    return parts.map((part, index) => {
        if (part.toLowerCase() === normalizedQuery) {
            return (
                <mark className="search-highlight" key={`${part}-${index}`}>
                    {part}
                </mark>
            );
        }

        return part;
    });
}

function highlightNullableText(value: string | null, query: string): ReactNode {
    if (!value) {
        return "—";
    }

    return highlightText(value, query);
}

function searchableParts(summary: DeviceSummary): string[] {
    const device = summary.device;

    return [
        device.name,
        device.device_id,
        device.protocol,
        device.transport,
        device.manufacturer,
        device.model,
        device.room,
        ...summary.capabilities.flatMap((capability) => [
            capability.display_name,
            capability.capability_id,
            capability.capability_type,
            capability.unit,
            capability.value_type,
            capability.source,
        ]),
    ].filter((part): part is string => Boolean(part && part.trim()));
}

function matchesSearch(summary: DeviceSummary, query: string): boolean {
    const normalizedQuery = normalizeSearchText(query);

    if (!normalizedQuery) {
        return true;
    }

    return searchableParts(summary).some((part) =>
        part.toLowerCase().includes(normalizedQuery),
    );
}

function toggleDeviceId(
    expandedDeviceIds: Set<string>,
    deviceId: string,
): Set<string> {
    const next = new Set(expandedDeviceIds);

    if (next.has(deviceId)) {
        next.delete(deviceId);
    } else {
        next.add(deviceId);
    }

    return next;
}

function DeviceCapabilityRow({
    summary,
    capability,
    searchQuery,
}: {
    summary: DeviceSummary;
    capability: DeviceCapability;
    searchQuery: string;
}) {
    const state = findStateForCapability(
        summary.state,
        capability.capability_id,
    );

    const content = (
        <>
            <div className="devices-accordion__capability-main">
                <strong>{highlightText(capability.display_name, searchQuery)}</strong>
                <span>{highlightText(capability.capability_type, searchQuery)}</span>
                <small>{highlightText(capability.capability_id, searchQuery)}</small>
            </div>

            <div className="devices-accordion__capability-value">
                {highlightText(formatValue(state), searchQuery)}
            </div>
        </>
    );

    if (capability.chartable) {
        return (
            <Link
                className="devices-accordion__capability devices-accordion__capability--clickable"
                to={buildMetricUrl(
                    summary.device.device_id,
                    capability.capability_id,
                )}
            >
                {content}
                <span className="devices-accordion__metric-link">Open metric</span>
            </Link>
        );
    }

    return <div className="devices-accordion__capability">{content}</div>;
}

function DeviceAccordionItem({
    summary,
    isExpanded,
    searchQuery,
    onToggle,
}: {
    summary: DeviceSummary;
    isExpanded: boolean;
    searchQuery: string;
    onToggle: () => void;
}) {
    const chartableCount = summary.capabilities.filter(
        (capability) => capability.chartable,
    ).length;

    return (
        <article className="devices-accordion__item">
            <button
                type="button"
                className="devices-accordion__summary"
                onClick={onToggle}
                aria-expanded={isExpanded}
            >
                <span className="devices-accordion__chevron">
                    {isExpanded ? "▾" : "▸"}
                </span>

                <span className="devices-accordion__identity">
                    <strong>{highlightText(summary.device.name, searchQuery)}</strong>
                    <small>{highlightText(summary.device.device_id, searchQuery)}</small>
                </span>

                <span className="devices-accordion__badges">
                    <span className="devices-accordion__badge">
                        {highlightText(summary.device.protocol, searchQuery)}
                    </span>
                    <span className="devices-accordion__badge">
                        {summary.capabilities.length} capabilities
                    </span>
                    <span className="devices-accordion__badge">
                        {summary.state.length} states
                    </span>
                    <span className="devices-accordion__badge">
                        {chartableCount} metrics
                    </span>
                </span>

                <span className="devices-accordion__last-seen">
                    {formatDateTime(summary.device.last_seen_at)}
                </span>
            </button>

            {isExpanded ? (
                <div className="devices-accordion__details">
                    <div className="devices-accordion__meta">
                        <div>
                            <strong>Manufacturer</strong>
                            <span>{highlightNullableText(summary.device.manufacturer, searchQuery)}</span>
                        </div>

                        <div>
                            <strong>Model</strong>
                            <span>{highlightNullableText(summary.device.model, searchQuery)}</span>
                        </div>

                        <div>
                            <strong>Transport</strong>
                            <span>{highlightNullableText(summary.device.transport, searchQuery)}</span>
                        </div>

                        <div>
                            <strong>Room</strong>
                            <span>{highlightNullableText(summary.device.room, searchQuery)}</span>
                        </div>

                        <div>
                            <strong>Read only</strong>
                            <span>{summary.device.read_only ? "yes" : "no"}</span>
                        </div>

                        <div>
                            <strong>Controllable</strong>
                            <span>{summary.device.controllable ? "yes" : "no"}</span>
                        </div>
                    </div>

                    <div className="devices-accordion__capabilities">
                        {summary.capabilities.map((capability) => (
                            <DeviceCapabilityRow
                                key={capability.capability_id}
                                summary={summary}
                                capability={capability}
                                searchQuery={searchQuery}
                            />
                        ))}

                        {summary.capabilities.length === 0 ? (
                            <p className="muted">No capabilities discovered yet</p>
                        ) : null}
                    </div>
                </div>
            ) : null}
        </article>
    );
}

export function DevicesPage() {
    const [devices, setDevices] = useState<DeviceSummary[]>([]);
    const [expandedDeviceIds, setExpandedDeviceIds] = useState<Set<string>>(
        () => new Set(),
    );
    const [searchQuery, setSearchQuery] = useState("");
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

    const normalizedSearchQuery = normalizeSearchText(searchQuery);

    const filteredDevices = useMemo(() => {
        return devices.filter((summary) => matchesSearch(summary, searchQuery));
    }, [devices, searchQuery]);

    const visibleExpandedDeviceIds = useMemo(() => {
        if (normalizedSearchQuery) {
            return new Set(
                filteredDevices.map((summary) => summary.device.device_id),
            );
        }

        return expandedDeviceIds;
    }, [expandedDeviceIds, filteredDevices, normalizedSearchQuery]);

    function expandAllVisibleDevices() {
        setExpandedDeviceIds(
            new Set(filteredDevices.map((summary) => summary.device.device_id)),
        );
    }

    function collapseAllDevices() {
        setExpandedDeviceIds(new Set());
    }

    function clearSearch() {
        setSearchQuery("");
    }

    if (isLoading) {
        return <p>Loading devices…</p>;
    }

    return (
        <section>
            <div className="page-header">
                <div>
                    <h2>Devices</h2>
                    <p>
                        {filteredDevices.length} of {devices.length} discovered devices
                    </p>
                </div>
            </div>

            {errorMessage ? (
                <p className="error">Failed to load devices: {errorMessage}</p>
            ) : null}

            <div className="devices-toolbar">
                <label className="devices-toolbar__search">
                    <span>Search devices</span>
                    <input
                        type="search"
                        value={searchQuery}
                        placeholder="Name, id, protocol, capability…"
                        onChange={(event) => setSearchQuery(event.target.value)}
                    />
                </label>

                <div className="devices-toolbar__actions">
                    <button type="button" onClick={expandAllVisibleDevices}>
                        Expand all
                    </button>

                    <button type="button" onClick={collapseAllDevices}>
                        Collapse all
                    </button>

                    <button
                        type="button"
                        onClick={clearSearch}
                        disabled={!normalizedSearchQuery}
                    >
                        Clear search
                    </button>
                </div>
            </div>

            <div className="devices-accordion">
                {filteredDevices.map((summary) => {
                    const deviceId = summary.device.device_id;
                    const isExpanded = visibleExpandedDeviceIds.has(deviceId);

                    return (
                        <DeviceAccordionItem
                            key={deviceId}
                            summary={summary}
                            isExpanded={isExpanded}
                            searchQuery={searchQuery}
                            onToggle={() => {
                                setExpandedDeviceIds((current) =>
                                    toggleDeviceId(current, deviceId),
                                );
                            }}
                        />
                    );
                })}

                {filteredDevices.length === 0 ? (
                    <div className="devices-accordion__empty">
                        No devices match the current search
                    </div>
                ) : null}
            </div>
        </section>
    );
}