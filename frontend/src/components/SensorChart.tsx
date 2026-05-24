import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HistoryPoint, ThresholdRange } from "../api";

interface SensorChartProps {
  title: string;
  dataKey: "suhu" | "ph" | "tds";
  color: string;
  unit: string;
  points: HistoryPoint[];
  threshold?: ThresholdRange;
  predicted?: number | null;
}

function formatTime(t: string | null | undefined) {
  if (!t) return "";
  return new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function SensorChart({
  title,
  dataKey,
  color,
  unit,
  points,
  threshold,
  predicted,
}: SensorChartProps) {
  const rows = points.map((p) => ({
    t: formatTime(p.time),
    v: p[dataKey] ?? undefined,
  }));

  const values = rows.map((r) => r.v).filter((v): v is number => v !== undefined);
  const minVal = values.length ? Math.min(...values) : 0;
  const maxVal = values.length ? Math.max(...values) : 100;

  let domainLow = minVal;
  let domainHigh = maxVal;
  if (threshold) {
    domainLow = Math.min(domainLow, threshold.warn_low);
    domainHigh = Math.max(domainHigh, threshold.warn_high);
  }
  const padding = (domainHigh - domainLow) * 0.1 || 1;
  domainLow = Math.floor(domainLow - padding);
  domainHigh = Math.ceil(domainHigh + padding);

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-medium text-[var(--text-secondary)]">{title}</h3>
        {predicted != null && (
          <span className="text-xs text-[var(--text-muted)]">
            Prediksi 15m: {typeof predicted === "number" ? predicted.toFixed(dataKey === "tds" ? 0 : 2) : "—"}{" "}
            {unit}
          </span>
        )}
      </div>

      <div className="h-52 w-full">
        {rows.length === 0 ? (
          <p className="flex h-full items-center justify-center text-sm text-[var(--text-muted)]">
            Belum ada data
          </p>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
              <XAxis dataKey="t" tick={{ fontSize: 10 }} stroke="var(--text-muted)" />
              <YAxis domain={[domainLow, domainHigh]} tick={{ fontSize: 10 }} stroke="var(--text-muted)" />
              <Tooltip
                contentStyle={{
                  background: "var(--bg-card)",
                  border: "1px solid var(--border)",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                formatter={(val) => [`${val != null ? val : "—"} ${unit}`, title]}
              />

              {threshold && (
                <>
                  <ReferenceArea
                    y1={threshold.ideal_low}
                    y2={threshold.ideal_high}
                    fill="#6ee7b7"
                    fillOpacity={0.06}
                  />
                  <ReferenceArea
                    y1={threshold.warn_low}
                    y2={threshold.ideal_low}
                    fill="#fcd34d"
                    fillOpacity={0.04}
                  />
                  <ReferenceArea
                    y1={threshold.ideal_high}
                    y2={threshold.warn_high}
                    fill="#fcd34d"
                    fillOpacity={0.04}
                  />
                </>
              )}

              <Line
                type="monotone"
                dataKey="v"
                stroke={color}
                dot={false}
                strokeWidth={2}
                name={title}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
