export function EventsPage() {
    return (
        <section className="placeholder-page">
            <div className="section-header">
                <h2>Events</h2>
                <p>Availability history and ingestion diagnostics will be added here.</p>
            </div>

            <article className="panel">
                <h3>Planned</h3>
                <ul className="notes-list">
                    <li>Recent availability events.</li>
                    <li>Ingestion warnings and errors.</li>
                    <li>Unknown devices and unsupported metrics.</li>
                </ul>
            </article>
        </section>
    );
}