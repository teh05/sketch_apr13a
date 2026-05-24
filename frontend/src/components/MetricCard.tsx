import type { ReactNode } from "react";
import type { Zone, HistoryPoint } from "../api";
import { ResponsiveContainer, LineChart, Line } from "recharts";

const ZONE_RING: Record<string, string> = {
  ideal: "ring-[#6ee7b7]/25",
  warning: "ring-[#fcd34d]/30",
  danger: "ring-[#fca5a5]/35",
  critical: "ring-[#f87171]/40",
  unknown: "ring-[var(--border)]",
};

const ZONE_LABEL: Record<string, { text: string; color: string }> = {
  ideal: { text: "Ideal", color: "text-[#6ee7b7]" },
  warning: { text: "Warning", color: "text-[#fcd34d]" },
  danger: { text: "Danger", color: "text-[#fca5a5]" },
  critical: { text: "Critical", color: "text-[#f87171]" },
  unknown: { text: "—", color: "text-[var(--text-muted)]" },
};

interface MetricCardProps {
  icon: ReactNode;
  label: string;
  unit: string;
  value: number | null | undefined;
  decimals: number;
  zone: Zone;
  chartColor: string;
  sparkData: HistoryPoint[];
  dataKey: "suhu" | "ph" | "tds";
}

export default function MetricCard({
  icon,
  label,
  unit,
  value,
  decimals,
  zone,
  chartColor,
  sparkData,
  dataKey,
}: MetricCardProps) {
  const ring = ZONE_RING[zone] ?? ZONE_RING.unknown;
  const zoneInfo = ZONE_LABEL[zone] ?? ZONE_LABEL.unknown;
  const display =
    value == null || Number.isNaN(value) ? "—" : `${value.toFixed(decimals)}${unit ? ` ${unit}` : ""}`;

  const sparkPoints = sparkData.slice(-30).map((p) => ({ v: p[dataKey] ?? undefined }));

  return (
    <div className={`rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-5 ring-1 ${ring}`}>
      <div className="mb-1 flex items-center justify-between">
        <div className="flex items-center gap-2 text-[var(--text-secondary)]">
          {icon}
          <span className="text-sm font-medium">{label}</span>
        </div>
        <span className={`text-xs font-medium ${zoneInfo.color}`}>{zoneInfo.text}</span>
      </div>

      <p className="mt-1 text-3xl font-semibold tabular-nums text-[var(--text-primary)]">{display}</p>

      {sparkPoints.length > 2 && (
        <div className="mt-3 h-10 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={sparkPoints}>
              <Line type="monotone" dataKey="v" stroke={chartColor} dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
