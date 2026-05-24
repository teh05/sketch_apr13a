import { Lightbulb } from "lucide-react";
import type { LatestResponse } from "../api";

export default function RecommendationBox({ latest }: { latest: LatestResponse | null }) {
  if (!latest) return null;

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-5">
      <h3 className="mb-2 flex items-center gap-2 text-sm font-medium uppercase tracking-wide text-[var(--text-muted)]">
        <Lightbulb className="h-4 w-4" /> Rekomendasi AI
      </h3>
      <p className="text-[var(--text-primary)] leading-relaxed">{latest.recommendation}</p>

      {latest.predicted_ph != null && (
        <div className="mt-3 grid grid-cols-3 gap-3">
          {latest.predicted_suhu != null && (
            <div className="rounded-lg bg-[var(--bg-surface)] px-3 py-2">
              <p className="text-[10px] uppercase text-[var(--text-muted)]">Suhu ~{latest.horizon_minutes}m</p>
              <p className="text-sm font-medium text-[var(--chart-suhu)]">{latest.predicted_suhu.toFixed(1)} °C</p>
            </div>
          )}
          <div className="rounded-lg bg-[var(--bg-surface)] px-3 py-2">
            <p className="text-[10px] uppercase text-[var(--text-muted)]">pH ~{latest.horizon_minutes}m</p>
            <p className="text-sm font-medium text-[var(--chart-ph)]">{latest.predicted_ph.toFixed(2)}</p>
          </div>
          {latest.predicted_tds != null && (
            <div className="rounded-lg bg-[var(--bg-surface)] px-3 py-2">
              <p className="text-[10px] uppercase text-[var(--text-muted)]">TDS ~{latest.horizon_minutes}m</p>
              <p className="text-sm font-medium text-[var(--chart-tds)]">{Math.round(latest.predicted_tds)} ppm</p>
            </div>
          )}
        </div>
      )}

      {latest.adaptive && latest.adaptive.sample_count > 0 && (
        <div className="mt-3 rounded-lg bg-[var(--bg-surface)] px-3 py-2">
          <p className="text-[10px] uppercase text-[var(--text-muted)] mb-1">Adaptive Baseline ({latest.adaptive.sample_count} samples)</p>
          <div className="flex gap-4 text-xs text-[var(--text-secondary)]">
            <span>pH: {latest.adaptive.ph_adaptive_low.toFixed(1)}–{latest.adaptive.ph_adaptive_high.toFixed(1)}</span>
            <span>TDS: {latest.adaptive.tds_adaptive_low.toFixed(0)}–{latest.adaptive.tds_adaptive_high.toFixed(0)}</span>
            <span>Suhu: {latest.adaptive.suhu_adaptive_low.toFixed(1)}–{latest.adaptive.suhu_adaptive_high.toFixed(1)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
