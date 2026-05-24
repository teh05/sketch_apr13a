import { Activity, AlertTriangle, CheckCircle2, ShieldAlert, XOctagon } from "lucide-react";
import type { LatestResponse } from "../api";

const STATUS_CONFIG: Record<string, { icon: typeof Activity; color: string; glow: string; label: string }> = {
  Normal: {
    icon: CheckCircle2,
    color: "text-[#6ee7b7]",
    glow: "shadow-[0_0_24px_rgba(110,231,183,0.18)] ring-1 ring-[#6ee7b7]/30",
    label: "Air Sehat — Semua Parameter Ideal",
  },
  Warning: {
    icon: AlertTriangle,
    color: "text-[#fcd34d]",
    glow: "shadow-[0_0_24px_rgba(252,211,77,0.18)] ring-1 ring-[#fcd34d]/30",
    label: "Perhatian — Parameter Mendekati Batas",
  },
  Danger: {
    icon: ShieldAlert,
    color: "text-[#fca5a5]",
    glow: "shadow-[0_0_28px_rgba(252,165,165,0.25)] ring-1 ring-[#fca5a5]/40",
    label: "Bahaya — Siapkan Pergantian Air",
  },
  Critical: {
    icon: XOctagon,
    color: "text-[#f87171]",
    glow: "shadow-[0_0_32px_rgba(248,113,113,0.35)] ring-1 ring-[#f87171]/50",
    label: "KRITIS — Ganti Air Segera!",
  },
};

export default function StatusPanel({ latest }: { latest: LatestResponse | null }) {
  const status = latest?.water_quality_status ?? "Normal";
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.Normal;
  const Icon = cfg.icon;
  const animate = status === "Danger" || status === "Critical";

  return (
    <section className={`rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-5 ${cfg.glow}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Icon className={`h-10 w-10 shrink-0 ${cfg.color} ${animate ? "animate-pulse" : ""}`} />
          <div>
            <p className={`text-lg font-semibold ${cfg.color}`}>{cfg.label}</p>
            <p className="text-sm text-[var(--text-secondary)]">
              {latest?.recommendation ?? "Memuat data..."}
            </p>
          </div>
        </div>

        {latest && (
          <div className="flex flex-col items-end gap-0.5 text-xs text-[var(--text-muted)]">
            <span>WQ: {latest.water_quality_status}</span>
            <span>AI: {latest.ai_status}</span>
            {latest.confidence > 0 && (
              <span>Confidence: {Math.round(latest.confidence * 100)}%</span>
            )}
            {latest.data_stale && <span className="text-[var(--accent-warning)]">Belum ada data</span>}
          </div>
        )}
      </div>

      {latest?.anomalies && latest.anomalies.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {latest.anomalies.map((a, i) => (
            <span
              key={i}
              className="rounded-full bg-[var(--accent-warning)]/10 px-2.5 py-0.5 text-xs font-medium text-[var(--accent-warning)]"
            >
              {a}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
