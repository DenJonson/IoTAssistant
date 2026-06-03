import { useEffect, useState } from "react";
import { fetchIngestionEvents } from "../../api/client";
import type { IngestionEvent } from "../../api/types";

function formatDateTime(value: string): string {
    return new Date(value).toLocaleString();
}

function statusClassName(status: string): string {
    const normalized = status.toLowerCase();

    if (normalized === "accepted" || normalized === "ok" || normalized === "success") {
        return "events-status events-status--success";
    }

    if (normalized.includes("warning")) {
        return "events-status events-status--warning";
    }

    if (normalized === "error" || normalized === "failed" || normalized === "rejected") {
        return "events-status events-status--error";
    }

    return "events-status";
}

export function EventsPage() {
    const [events, setEvents] = useState<IngestionEvent[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    useEffect(() => {
        let isCancelled = false;

        async function loadEvents() {
            try {
                const response = await fetchIngestionEvents(100);

                if (!isCancelled) {
                    setEvents(response.events);
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

        loadEvents();

        const intervalId = window.setInterval(loadEvents, 5000);

        return () => {
            isCancelled = true;
            window.clearInterval(intervalId);
        };
    }, []);

    if (isLoading) {
        return <p>Loading events…</p>;
    }

    return (
        <section>
            <div className="page-header">
                <h2>Events</h2>
                <p>{events.length} latest ingestion events</p>
            </div>

            {errorMessage ? (
                <p className="error">Failed to load events: {errorMessage}</p>
            ) : null}

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
                        {events.map((event) => (
                            <tr key={event.id}>
                                <td>{formatDateTime(event.server_received_at)}</td>
                                <td>{event.message_type ?? "—"}</td>
                                <td>{event.device_external_id ?? "—"}</td>
                                <td>
                                    <span className={statusClassName(event.status)}>
                                        {event.status}
                                    </span>
                                </td>
                                <td>
                                    {event.error_code ? (
                                        <div>
                                            <strong>{event.error_code}</strong>
                                            {event.error_message ? <p>{event.error_message}</p> : null}
                                        </div>
                                    ) : (
                                        "—"
                                    )}
                                </td>
                                <td className="events-table__topic">{event.mqtt_topic}</td>
                                <td className="events-table__payload">
                                    {event.payload_preview ?? "—"}
                                </td>
                            </tr>
                        ))}

                        {events.length === 0 ? (
                            <tr>
                                <td colSpan={7}>No ingestion events yet</td>
                            </tr>
                        ) : null}
                    </tbody>
                </table>
            </div>
        </section>
    );
}