import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Droplets,
  Gauge,
  Thermometer,
} from "lucide-react";
import type { ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HistoryPoint, LatestResponse } from "./api";
import { fetchHistory, fetchLatest } from "./api";

const POLL_MS = 30_000;

function chartRows(points: HistoryPoint[]) {
  return points.map((p) => ({
    t: p.time ? new Date(p.time).toLocaleTimeString() : "",
    suhu: p.suhu ?? undefined,
    ph: p.ph ?? undefined,
    tds: p.tds ?? undefined,
  }));
}

export default function App() {
  const [latest, setLatest] = useState<LatestResponse | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const lastNotifyRef = useRef<string>("");

  const load = useCallback(async () => {
    setErr(null);
    try {
      const [l, h] = await Promise.all([fetchLatest(), fetchHistory()]);
      setLatest(l);
      setHistory(h.points || []);
      const need =
        l.action_required ||
        l.ai_status === "WARNING_CHANGE_WATER" ||
        l.water_quality_status === "Danger";
      if (need) {
        setModalOpen(true);
        const key = `${l.ai_status}|${l.water_quality_status}|${l.recommendation}`;
        if (key !== lastNotifyRef.current && "Notification" in window) {
          lastNotifyRef.current = key;
          if (Notification.permission === "granted") {
            new Notification("Tilapia pond — action required", {
              body:
                l.ai_status === "WARNING_CHANGE_WATER"
                  ? "Peringatan: Kualitas air diprediksi memburuk. Siapkan pergantian air."
                  : "High TDS or pH risk. Replace 30% of pond water and check the filter.",
            });
          } else if (Notification.permission === "default") {
            void Notification.requestPermission();
          }
        }
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), POLL_MS);
    return () => window.clearInterval(id);
  }, [load]);

  useEffect(() => {
    if ("Notification" in window && Notification.permission === "default") {
      void Notification.requestPermission();
    }
  }, []);

  const actionRequired =
    latest?.action_required ||
    latest?.water_quality_status === "Danger" ||
    latest?.ai_status === "WARNING_CHANGE_WATER";

  const cardGlow = actionRequired
    ? "shadow-[0_0_28px_rgba(239,68,68,0.35)] ring-2 ring-red-500/60"
    : "shadow-[0_0_24px_rgba(34,197,94,0.25)] ring-2 ring-emerald-500/40";

  const rows = chartRows(history);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="border-b border-zinc-800 bg-zinc-900/80 px-4 py-4 backdrop-blur md:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <Activity className="h-8 w-8 text-emerald-400" />
            <div>
              <h1 className="text-xl font-semibold tracking-tight md:text-2xl">
                Tilapia Water Quality
              </h1>
              <p className="text-sm text-zinc-400">
                IoT dashboard — real-time + 24h history
              </p>
            </div>
          </div>
          {loading && (
            <span className="text-sm text-zinc-500">Loading…</span>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-4 py-6 md:px-8">
        {err && (
          <div
            className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-200"
            role="alert"
          >
            API error: {err}. Pastikan backend jalan di{" "}
            <code className="rounded bg-zinc-800 px-1">VITE_API_BASE_URL</code>
          </div>
        )}

        {/* Current status panel */}
        <section
          className={`rounded-2xl border border-zinc-800 bg-zinc-900/90 p-6 ${cardGlow}`}
        >
          <h2 className="mb-4 text-lg font-medium text-zinc-200">Current status</h2>
          <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
            {actionRequired ? (
              <>
                <div className="flex items-center gap-3 text-red-400">
                  <AlertTriangle className="h-12 w-12 shrink-0 animate-pulse" />
                  <div>
                    <p className="text-lg font-semibold">Action required</p>
                    <p className="text-sm text-zinc-400">
                      {latest?.recommendation || "Check sensors and water exchange."}
                    </p>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex items-center gap-3 text-emerald-400">
                <CheckCircle2 className="h-12 w-12 shrink-0" />
                <div>
                  <p className="text-lg font-semibold">Air Sehat</p>
                  <p className="text-sm text-zinc-400">
                    Parameters within expected range
                  </p>
                </div>
              </div>
            )}
            {latest && (
              <div className="text-right text-xs text-zinc-500">
                <div>WQ: {latest.water_quality_status}</div>
                <div>AI: {latest.ai_status}</div>
                {latest.data_stale && <div className="text-amber-400">No data in Influx</div>}
              </div>
            )}
          </div>
        </section>

        {/* Cards */}
        <section className="grid gap-4 sm:grid-cols-3">
          <MetricCard
            icon={<Thermometer className="h-6 w-6" />}
            label="Temperature"
            unit="°C"
            value={latest?.suhu}
            decimals={1}
            tone="emerald"
          />
          <MetricCard
            icon={<Droplets className="h-6 w-6" />}
            label="pH"
            unit=""
            value={latest?.ph}
            decimals={2}
            tone="sky"
          />
          <MetricCard
            icon={<Gauge className="h-6 w-6" />}
            label="TDS"
            unit="ppm"
            value={latest?.tds}
            decimals={0}
            tone="orange"
          />
        </section>

        {/* Recommendation box */}
        {latest && (
          <section className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5">
            <h3 className="mb-2 text-sm font-medium uppercase tracking-wide text-zinc-500">
              Recommendation
            </h3>
            <p className="text-zinc-200">
              {latest.recommendation === "Change 30% of water now"
                ? "Saran: Ganti 30% volume air kolam untuk menstabilkan pH dan TDS. Periksa filter dan sirkulasi."
                : latest.recommendation}
            </p>
            {latest.predicted_ph != null && (
              <p className="mt-2 text-sm text-zinc-500">
                Forecast (~{latest.horizon_minutes} min): pH ≈{" "}
                {latest.predicted_ph.toFixed(2)}, TDS ≈{" "}
                {latest.predicted_tds != null ? Math.round(latest.predicted_tds) : "—"}
              </p>
            )}
          </section>
        )}

        {/* Chart */}
        <section className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-4 md:p-6">
          <h2 className="mb-4 text-lg font-medium">24-hour trend</h2>
          <div className="h-72 w-full min-w-0">
            {rows.length === 0 ? (
              <p className="text-sm text-zinc-500">No history points yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
                  <XAxis dataKey="t" tick={{ fontSize: 10 }} stroke="#71717a" />
                  <YAxis yAxisId="left" tick={{ fontSize: 10 }} stroke="#71717a" />
                  <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10 }} stroke="#71717a" />
                  <Tooltip
                    contentStyle={{
                      background: "#18181b",
                      border: "1px solid #27272a",
                      borderRadius: "8px",
                    }}
                  />
                  <Legend />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="suhu"
                    name="Suhu (°C)"
                    stroke="#34d399"
                    dot={false}
                    strokeWidth={2}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="ph"
                    name="pH"
                    stroke="#38bdf8"
                    dot={false}
                    strokeWidth={2}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="tds"
                    name="TDS"
                    stroke="#fb923c"
                    dot={false}
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>
      </main>

      {modalOpen && latest && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="max-w-lg rounded-2xl border border-red-500/40 bg-zinc-900 p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-red-400">Water change notice</h3>
            <p className="mt-3 text-zinc-300">
              High TDS or pH risk detected. Please replace 30% of pond water and check the
              filter.
            </p>
            {latest.ai_status === "WARNING_CHANGE_WATER" && (
              <p className="mt-2 text-sm text-amber-200">
                Peringatan: Kualitas air diprediksi memburuk dalam {latest.horizon_minutes}{" "}
                menit. Siapkan pergantian air.
              </p>
            )}
            <button
              type="button"
              className="mt-6 rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-900 hover:bg-white"
              onClick={() => setModalOpen(false)}
            >
              Understood
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({
  icon,
  label,
  unit,
  value,
  decimals,
  tone,
}: {
  icon: ReactNode;
  label: string;
  unit: string;
  value: number | null | undefined;
  decimals: number;
  tone: "emerald" | "sky" | "orange";
}) {
  const ring =
    tone === "emerald"
      ? "ring-emerald-500/30"
      : tone === "sky"
        ? "ring-sky-500/30"
        : "ring-orange-500/30";
  const display =
    value == null || Number.isNaN(value)
      ? "—"
      : `${value.toFixed(decimals)}${unit ? ` ${unit}` : ""}`;

  return (
    <div
      className={`rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 ring-1 ${ring}`}
    >
      <div className="mb-3 flex items-center gap-2 text-zinc-400">
        {icon}
        <span className="text-sm font-medium">{label}</span>
      </div>
      <p className="text-3xl font-semibold tabular-nums text-zinc-50">{display}</p>
    </div>
  );
}
