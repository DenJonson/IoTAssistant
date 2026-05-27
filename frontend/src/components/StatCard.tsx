type StatCardProps = {
    title: string;
    value: string | number;
    hint?: string;
};

export function StatCard({ title, value, hint }: StatCardProps) {
    return (
        <article className="stat-card">
            <p>{title}</p>
            <strong>{value}</strong>
            {hint && <span>{hint}</span>}
        </article>
    );
}