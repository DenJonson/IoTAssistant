import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { fetchIngestionEvents } from "../../api/client";
import type { IngestionEvent } from "../../api/types";
import { useSearchParams } from "react-router-dom";

type EventFilters = {
    searchQuery: string;
    status: string;
    deviceExternalId: string;
    messageType: string;
};

const ALL_FILTER_VALUE = "all";

const DEVICE_QUERY_PARAM = "device";

function deviceFilterFromSearchParams(
    searchParams: URLSearchParams,
): string {
    return searchParams.get(DEVICE_QUERY_PARAM) ?? ALL_FILTER_VALUE;
}

function formatDateTime(value: string): string {
    return new Date(value).toLocaleString();
}

function statusClassName(status: string): string {
    const normalized = status.toLowerCase();

    if (
        normalized === "accepted" ||
        normalized === "ok" ||
        normalized === "success"
    ) {
        return "events-status events-status--success";
    }

    if (normalized.includes("warning")) {
        return "events-status events-status--warning";
    }

    if (
        normalized === "error" ||
        normalized === "failed" ||
        normalized === "rejected"
    ) {
        return "events-status events-status--error";
    }

    return "events-status";
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

function highlightNullableText(
    value: string | null,
    query: string,
): ReactNode {
    if (!value) {
        return "—";
    }

    return highlightText(value, query);
}

function searchableEventParts(event: IngestionEvent): string[] {
    return [
        event.id,
        event.server_received_at,
        event.mqtt_topic,
        event.message_type,
        event.device_external_id,
        event.status,
        event.error_code,
        event.error_message,
        event.payload_preview,
    ].filter((part): part is string => Boolean(part && part.trim()));
}

function matchesSearch(event: IngestionEvent, query: string): boolean {
    const normalizedQuery = normalizeSearchText(query);

    if (!normalizedQuery) {
        return true;
    }

    return searchableEventParts(event).some((part) =>
        part.toLowerCase().includes(normalizedQuery),
    );
}

function uniqueSortedValues(
    events: IngestionEvent[],
    selector: (event: IngestionEvent) => string | null,
): string[] {
    return Array.from(
        new Set(
            events
                .map(selector)
                .filter((value): value is string => Boolean(value && value.trim())),
        ),
    ).sort((left, right) => left.localeCompare(right));
}

function applyFilters(
    events: IngestionEvent[],
    filters: EventFilters,
): IngestionEvent[] {
    return events.filter((event) => {
        if (!matchesSearch(event, filters.searchQuery)) {
            return false;
        }

        if (
            filters.status !== ALL_FILTER_VALUE &&
            event.status !== filters.status
        ) {
            return false;
        }

        if (
            filters.deviceExternalId !== ALL_FILTER_VALUE &&
            event.device_external_id !== filters.deviceExternalId
        ) {
            return false;
        }

        if (
            filters.messageType !== ALL_FILTER_VALUE &&
            event.message_type !== filters.messageType
        ) {
            return false;
        }

        return true;
    });
}

function hasActiveFilters(filters: EventFilters): boolean {
    return (
        normalizeSearchText(filters.searchQuery) !== "" ||
        filters.status !== ALL_FILTER_VALUE ||
        filters.deviceExternalId !== ALL_FILTER_VALUE ||
        filters.messageType !== ALL_FILTER_VALUE
    );
}

export function EventsPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const [events, setEvents] = useState<IngestionEvent[]>([]);
    const [filters, setFilters] = useState<EventFilters>(() => ({
        searchQuery: "",
        status: ALL_FILTER_VALUE,
        deviceExternalId: deviceFilterFromSearchParams(searchParams),
        messageType: ALL_FILTER_VALUE,
    }));
    const [isLoading, setIsLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    useEffect(() => {
        let isCancelled = false;

        async function loadEvents() {
            try {
                const response = await fetchIngestionEvents(200);

                if (!isCancelled) {
                    setEvents(response.events);
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

        loadEvents();

        const intervalId = window.setInterval(loadEvents, 5000);

        return () => {
            isCancelled = true;
            window.clearInterval(intervalId);
        };
    }, []);

    useEffect(() => {
        const deviceExternalId = deviceFilterFromSearchParams(searchParams);

        setFilters((current) => {
            if (current.deviceExternalId === deviceExternalId) {
                return current;
            }

            return {
                ...current,
                deviceExternalId,
            };
        });
    }, [searchParams]);

    const statusOptions = useMemo(
        () => uniqueSortedValues(events, (event) => event.status),
        [events],
    );

    const deviceOptions = useMemo(
        () => uniqueSortedValues(events, (event) => event.device_external_id),
        [events],
    );

    const messageTypeOptions = useMemo(
        () => uniqueSortedValues(events, (event) => event.message_type),
        [events],
    );

    const filteredEvents = useMemo(
        () => applyFilters(events, filters),
        [events, filters],
    );

    const normalizedSearchQuery = normalizeSearchText(filters.searchQuery);

    function updateFilters(patch: Partial<EventFilters>) {
        setFilters((current) => {
            const next = {
                ...current,
                ...patch,
            };

            if (patch.deviceExternalId !== undefined) {
                const nextSearchParams = new URLSearchParams(searchParams);

                if (next.deviceExternalId === ALL_FILTER_VALUE) {
                    nextSearchParams.delete(DEVICE_QUERY_PARAM);
                } else {
                    nextSearchParams.set(DEVICE_QUERY_PARAM, next.deviceExternalId);
                }

                setSearchParams(nextSearchParams, { replace: false });
            }

            return next;
        });
    }

    function clearFilters() {
        setFilters({
            searchQuery: "",
            status: ALL_FILTER_VALUE,
            deviceExternalId: ALL_FILTER_VALUE,
            messageType: ALL_FILTER_VALUE,
        });

        setSearchParams({}, { replace: false });
    }

    if (isLoading) {
        return <p>Loading events…</p>;
    }

    return (
        <section>
            <div className="page-header">
                <div>
                    <h2>Events</h2>
                    <p>
                        {filteredEvents.length} of {events.length} latest ingestion events
                    </p>
                </div>
            </div>

            {errorMessage ? (
                <p className="error">Failed to load events: {errorMessage}</p>
            ) : null}

            <div className="events-toolbar">
                <label className="events-toolbar__search">
                    <span>Search events</span>
                    <input
                        type="search"
                        value={filters.searchQuery}
                        placeholder="Device, topic, status, error, payload…"
                        onChange={(event) =>
                            updateFilters({
                                searchQuery: event.target.value,
                            })
                        }
                    />
                </label>

                <label>
                    <span>Status</span>
                    <select
                        value={filters.status}
                        onChange={(event) =>
                            updateFilters({
                                status: event.target.value,
                            })
                        }
                    >
                        <option value={ALL_FILTER_VALUE}>All statuses</option>
                        {statusOptions.map((status) => (
                            <option key={status} value={status}>
                                {status}
                            </option>
                        ))}
                    </select>
                </label>

                <label>
                    <span>Device</span>
                    <select
                        value={filters.deviceExternalId}
                        onChange={(event) =>
                            updateFilters({
                                deviceExternalId: event.target.value,
                            })
                        }
                    >
                        <option value={ALL_FILTER_VALUE}>All devices</option>
                        {deviceOptions.map((deviceExternalId) => (
                            <option key={deviceExternalId} value={deviceExternalId}>
                                {deviceExternalId}
                            </option>
                        ))}
                    </select>
                </label>

                <label>
                    <span>Message type</span>
                    <select
                        value={filters.messageType}
                        onChange={(event) =>
                            updateFilters({
                                messageType: event.target.value,
                            })
                        }
                    >
                        <option value={ALL_FILTER_VALUE}>All types</option>
                        {messageTypeOptions.map((messageType) => (
                            <option key={messageType} value={messageType}>
                                {messageType}
                            </option>
                        ))}
                    </select>
                </label>

                <div className="events-toolbar__actions">
                    <button
                        type="button"
                        onClick={clearFilters}
                        disabled={!hasActiveFilters(filters)}
                    >
                        Clear filters
                    </button>
                </div>
            </div>

            <div className="events-table">
                <table>
                    <thead>
                        <tr>
                            <th>Received</th>
                            <th>Type</th>
                            <th>Device</th>
                            <th>Status</th>
                            <th>Error</th>
                            <th>Topic</th>
                            <th>Payload</th>
                        </tr>
                    </thead>

                    <tbody>
                        {filteredEvents.map((event) => (
                            <tr key={event.id}>
                                <td>{formatDateTime(event.server_received_at)}</td>

                                <td>
                                    {highlightNullableText(
                                        event.message_type,
                                        filters.searchQuery,
                                    )}
                                </td>

                                <td className="events-table__device">
                                    {highlightNullableText(
                                        event.device_external_id,
                                        filters.searchQuery,
                                    )}
                                </td>

                                <td>
                                    <span className={statusClassName(event.status)}>
                                        {highlightText(event.status, filters.searchQuery)}
                                    </span>
                                </td>

                                <td>
                                    {event.error_code ? (
                                        <div className="events-table__error">
                                            <strong>
                                                {highlightText(event.error_code, filters.searchQuery)}
                                            </strong>

                                            {event.error_message ? (
                                                <p>
                                                    {highlightText(
                                                        event.error_message,
                                                        filters.searchQuery,
                                                    )}
                                                </p>
                                            ) : null}
                                        </div>
                                    ) : (
                                        "—"
                                    )}
                                </td>

                                <td className="events-table__topic">
                                    {highlightNullableText(event.mqtt_topic, filters.searchQuery)}
                                </td>

                                <td className="events-table__payload">
                                    {highlightNullableText(
                                        event.payload_preview,
                                        filters.searchQuery,
                                    )}
                                </td>
                            </tr>
                        ))}

                        {filteredEvents.length === 0 ? (
                            <tr>
                                <td colSpan={7}>
                                    {hasActiveFilters(filters)
                                        ? "No events match the current filters"
                                        : "No ingestion events yet"}
                                </td>
                            </tr>
                        ) : null}
                    </tbody>
                </table>
            </div>

            {normalizedSearchQuery ? (
                <p className="events-search-note">
                    Highlighting matches for <strong>{filters.searchQuery}</strong>
                </p>
            ) : null}
        </section>
    );
}