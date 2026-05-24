import { Droplets, Gauge, Thermometer, Activity } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { HistoryPoint, LatestResponse, ThresholdRange } from "./api";
import { fetchHistory, fetchLatest, fetchThresholds } from "./api";

import EventTimeline from "./components/EventTimeline";
import MetricCard from "./components/MetricCard";
import NotifBell from "./components/NotifBell";
import RecommendationBox from "./components/RecommendationBox";
import SensorChart from "./components/SensorChart";
import StatusPanel from "./components/StatusPanel";

const POLL_MS = 30_000;

export default function App() {
  const [latest, setLatest] = useState<LatestResponse | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [thresholds, setThresholds] = useState<Record<string, ThresholdRange>>({});
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const lastNotifyKey = useRef<string>("");

  const load = useCallback(async () => {
    setErr(null);
    try {
      const [l, h] = await Promise.all([fetchLatest(), fetchHistory()]);
      setLatest(l);
      setHistory(h.points || []);

      if (l.action_required && "Notification" in window && Notification.permission === "granted") {
        const key = `${l.ai_status}|${l.water_quality_status}`;
        if (key !== lastNotifyKey.current) {
          lastNotifyKey.current = key;
          new Notification("Tilapia — Perhatian", {
            body: l.recommendation,
          });
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
    fetchThresholds().then(setThresholds).catch(() => {});
    const id = setInterval(() => void load(), POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  useEffect(() => {
    if ("Notification" in window && Notification.permission === "default") {
      void Notification.requestPermission();
    }
  }, []);

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--bg-surface)]/80 px-4 py-3 backdrop-blur-md md:px-8">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="h-7 w-7 text-[var(--accent-safe)]" />
            <div>
              <h1 className="text-lg font-semibold tracking-tight">Tilapia Water Quality</h1>
              <p className="text-xs text-[var(--text-muted)]">IoT Dashboard — Real-time Monitoring</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {loading && <span className="text-xs text-[var(--text-muted)]">Memuat…</span>}
            <NotifBell />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-5 md:px-8">
        {/* Error banner */}
        {err && (
          <div className="rounded-xl border border-[var(--accent-warning)]/30 bg-[var(--accent-warning)]/5 px-4 py-3 text-sm text-[var(--accent-warning)]">
            API error: {err}
          </div>
        )}

        {/* Status */}
        <StatusPanel latest={latest} />

        {/* Metric cards */}
        <section className="grid gap-4 sm:grid-cols-3">
          <MetricCard
            icon={<Thermometer className="h-5 w-5" />}
            label="Suhu"
            unit="°C"
            value={latest?.suhu}
            decimals={1}
            zone={latest?.suhu_zone ?? "unknown"}
            chartColor="var(--chart-suhu)"
            sparkData={history}
            dataKey="suhu"
          />
          <MetricCard
            icon={<Droplets className="h-5 w-5" />}
            label="pH"
            unit=""
            value={latest?.ph}
            decimals={2}
            zone={latest?.ph_zone ?? "unknown"}
            chartColor="var(--chart-ph)"
            sparkData={history}
            dataKey="ph"
          />
          <MetricCard
            icon={<Gauge className="h-5 w-5" />}
            label="TDS"
            unit="ppm"
            value={latest?.tds}
            decimals={0}
            zone={latest?.tds_zone ?? "unknown"}
            chartColor="var(--chart-tds)"
            sparkData={history}
            dataKey="tds"
          />
        </section>

        {/* Recommendation */}
        <RecommendationBox latest={latest} />

        {/* Individual sensor charts with reference bands */}
        <section className="grid gap-4 lg:grid-cols-3">
          <SensorChart
            title="Suhu (°C)"
            dataKey="suhu"
            color="var(--chart-suhu)"
            unit="°C"
            points={history}
            threshold={thresholds.suhu}
            predicted={latest?.predicted_suhu}
          />
          <SensorChart
            title="pH"
            dataKey="ph"
            color="var(--chart-ph)"
            unit=""
            points={history}
            threshold={thresholds.ph}
            predicted={latest?.predicted_ph}
          />
          <SensorChart
            title="TDS (ppm)"
            dataKey="tds"
            color="var(--chart-tds)"
            unit="ppm"
            points={history}
            threshold={thresholds.tds}
            predicted={latest?.predicted_tds}
          />
        </section>

        {/* Event timeline */}
        <EventTimeline />
      </main>
    </div>
  );
}
