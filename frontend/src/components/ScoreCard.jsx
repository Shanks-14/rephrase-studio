export default function ScoreCard({ label, score, colorVar = "--pos-noun", testId }) {
  const size = 96;
  const stroke = 8;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = score == null ? 0 : Math.max(0, Math.min(100, score));
  const dash = (pct / 100) * c;

  const status =
    score == null ? "—" : pct >= 70 ? "High" : pct >= 40 ? "Medium" : "Safe";
  const statusColor =
    score == null
      ? "text-muted-foreground"
      : pct >= 70
      ? "text-rose-500"
      : pct >= 40
      ? "text-amber-500"
      : "text-emerald-500";

  return (
    <div
      className="flex flex-col items-center gap-1.5 p-3 rounded-2xl border border-border bg-background"
      data-testid={testId}
    >
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="hsl(var(--muted))"
            strokeWidth={stroke}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={`var(${colorVar})`}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${dash} ${c}`}
            style={{ transition: "stroke-dasharray 700ms cubic-bezier(0.22,1,0.36,1)" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-semibold tabular-nums">
            {score == null ? "—" : `${pct}%`}
          </span>
        </div>
      </div>
      <div className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div className={`text-[11px] font-mono ${statusColor}`}>{status}</div>
    </div>
  );
}