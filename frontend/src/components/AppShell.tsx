import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

type AppShellProps = {
    children: ReactNode;
};

type NavItem = {
    to: string;
    label: string;
    end?: boolean;
};

type NavLinkClassNameProps = {
    isActive: boolean;
    isPending: boolean;
};

const navItems: NavItem[] = [
    { to: "/dashboard", label: "Dashboard" },
    { to: "/devices", label: "Devices" },
    { to: "/metrics", label: "Metrics" },
    { to: "/events", label: "Events" },
];

function getNavLinkClassName({
    isActive,
    isPending,
}: NavLinkClassNameProps): string {
    const classNames = ["app-shell__nav-link"];

    if (isActive) {
        classNames.push("app-shell__nav-link--active");
    }

    if (isPending) {
        classNames.push("app-shell__nav-link--pending");
    }

    return classNames.join(" ");
}

export function AppShell({ children }: AppShellProps) {
    const [showScrollTop, setShowScrollTop] = useState(false);

    useEffect(() => {
        function handleScroll() {
            setShowScrollTop(window.scrollY > 500);
        }

        handleScroll();

        window.addEventListener("scroll", handleScroll, {
            passive: true,
        });

        return () => {
            window.removeEventListener("scroll", handleScroll);
        };
    }, []);

    function scrollToTop() {
        window.scrollTo({
            top: 0,
            behavior: "smooth",
        });
    }

    return (
        <div className="app-shell">
            <header className="app-shell__header">
                <div className="app-shell__brand">
                    <h1>IoT Assistant</h1>
                    <p>Local smart-home observability</p>
                </div>

                <nav className="app-shell__nav" aria-label="Primary navigation">
                    {navItems.map((item) => (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            end={item.end}
                            className={getNavLinkClassName}
                        >
                            {item.label}
                        </NavLink>
                    ))}
                </nav>
            </header>

            <main className="app-shell__main">{children}</main>

            {showScrollTop ? (
                <button
                    type="button"
                    className="scroll-top-button"
                    onClick={scrollToTop}
                    aria-label="Back to top"
                    title="Back to top"
                >
                    ↑
                </button>
            ) : null}
        </div>
    );
}