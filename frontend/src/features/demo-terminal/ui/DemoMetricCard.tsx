type DemoMetricCardProps = {
  label: string;
  value: string;
};

export function DemoMetricCard({ label, value }: DemoMetricCardProps) {
  return (
    <article className="metricCard">
      <div className="metricLabel">{label}</div>
      <div className="metricValue">{value}</div>
    </article>
  );
}
