import type { AppTab } from "../api/types";

type AppShellProps = {
    activeTab: AppTab;
    onTabChange: (tab: AppTab) => void;
    children: React.ReactNode;
};

const tabs: { id: AppTab; label: string }[] = [
    { id: "dashboard", label: "Dashboard" },
    { id: "devices", label: "Devices" },
    { id: "metrics", label: "Metrics" },
    { id: "events", label: "Events" },
];

export function AppShell({
    activeTab,
    onTabChange,
    children,
}: AppShellProps) {
    return (
        <main className="page">
            <header className="page-header">
                <div>
                    <h1>IoTAssistant</h1>
                    <p>Read-only home IoT console</p>
                </div>
            </header>

            <nav className="tabs" aria-label="Main navigation">
                {tabs.map((tab) => (
                    <button
                        className={
                            tab.id === activeTab ? "tab-button active" : "tab-button"
                        }
                        key={tab.id}
                        onClick={() => onTabChange(tab.id)}
                        type="button"
                    >
                        {tab.label}
                    </button>
                ))}
            </nav>

            <section className="tab-content">{children}</section>
        </main>
    );
}