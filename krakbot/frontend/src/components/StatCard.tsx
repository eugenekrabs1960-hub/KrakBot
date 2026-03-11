type Props = { label: string; value: string | number; hint?: string };

export default function StatCard({ label, value, hint }: Props) {
  return (
    <div className="card">
      <div className="muted">{label}</div>
      <div className="kpi-value">{value}</div>
      {hint && <div className="muted">{hint}</div>}
    </div>
  );
}
