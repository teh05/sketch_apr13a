const base =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export type LatestResponse = {
  time: string | null;
  suhu: number | null;
  ph: number | null;
  tds: number | null;
  water_quality_status: string;
  ai_status: string;
  prediction_status: string;
  predicted_ph: number | null;
  predicted_tds: number | null;
  horizon_minutes: number;
  prediction_reason?: string;
  recommendation: string;
  action_required: boolean;
  data_stale?: boolean;
};

export type HistoryPoint = {
  time: string | null;
  suhu?: number | null;
  ph?: number | null;
  tds?: number | null;
};

export async function fetchLatest(): Promise<LatestResponse> {
  const r = await fetch(`${base}/api/latest`);
  if (!r.ok) throw new Error(`latest ${r.status}`);
  return r.json();
}

export async function fetchHistory(): Promise<{ points: HistoryPoint[]; count: number }> {
  const r = await fetch(`${base}/api/history`);
  if (!r.ok) throw new Error(`history ${r.status}`);
  return r.json();
}
