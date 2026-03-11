export default function PageHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <header className="page-header">
      <h2>{title}</h2>
      <p className="page-sub">{subtitle}</p>
    </header>
  );
}
