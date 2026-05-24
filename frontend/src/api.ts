const base =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type Zone = "ideal" | "warning" | "danger" | "critical" | "unknown";

export interface AdaptiveInfo {
  ph_mean: number;
  ph_adaptive_low: number;
  ph_adaptive_high: number;
  tds_mean: number;
  tds_adaptive_low: number;
  tds_adaptive_high: number;
  suhu_mean: number;
  suhu_adaptive_low: number;
  suhu_adaptive_high: number;
  sample_count: number;
}

export interface LatestResponse {
  time: string | null;
  suhu: number | null;
  ph: number | null;
  tds: number | null;
  suhu_zone: Zone;
  ph_zone: Zone;
  tds_zone: Zone;
  water_quality_status: string;
  ai_status: string;
  prediction_status: string;
  predicted_ph: number | null;
  predicted_tds: number | null;
  predicted_suhu: number | null;
  horizon_minutes: number;
  confidence: number;
  prediction_reason?: string;
  recommendation: string;
  action_required: boolean;
  data_stale?: boolean;
  anomalies: string[];
  adaptive: AdaptiveInfo;
}

export interface HistoryPoint {
  time: string | null;
  suhu?: number | null;
  ph?: number | null;
  tds?: number | null;
}

export interface NotifItem {
  id: number;
  created_at: string;
  severity: string;
  title: string;
  message: string;
  is_read: boolean;
  category: string;
}

export interface EventItem {
  id: number;
  timestamp: string;
  prev_status: string | null;
  new_status: string;
  suhu: number | null;
  ph: number | null;
  tds: number | null;
  trigger_param: string | null;
}

export interface ThresholdRange {
  ideal_low: number;
  ideal_high: number;
  warn_low: number;
  warn_high: number;
  danger_low: number;
  danger_high: number;
  unit: string;
}

export interface HourlySummary {
  hour: string;
  avg_suhu: number | null;
  min_suhu: number | null;
  max_suhu: number | null;
  avg_ph: number | null;
  min_ph: number | null;
  max_ph: number | null;
  avg_tds: number | null;
  min_tds: number | null;
  max_tds: number | null;
  sample_count: number;
}

/* ------------------------------------------------------------------ */
/*  Fetchers                                                           */
/* ------------------------------------------------------------------ */

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${base}${path}`);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

export const fetchLatest = () => get<LatestResponse>("/api/latest");

export const fetchHistory = () =>
  get<{ points: HistoryPoint[]; count: number }>("/api/history");

export const fetchNotifications = (limit = 50) =>
  get<{ notifications: NotifItem[]; count: number }>(`/api/notifications?limit=${limit}`);

export const fetchUnreadCount = () =>
  get<{ unread: number }>("/api/notifications/unread-count");

export const fetchEvents = (limit = 30) =>
  get<{ events: EventItem[]; count: number }>(`/api/events?limit=${limit}`);

export const fetchThresholds = () =>
  get<Record<string, ThresholdRange>>("/api/thresholds");

export const fetchHourlySummary = (hours = 24) =>
  get<{ summaries: HourlySummary[]; count: number }>(`/api/analytics/summary?hours=${hours}`);

export const fetchBaseline = () =>
  get<{
    ph: { mean: number; std: number; adaptive_low: number; adaptive_high: number };
    tds: { mean: number; std: number; adaptive_low: number; adaptive_high: number };
    suhu: { mean: number; std: number; adaptive_low: number; adaptive_high: number };
    sample_count: number;
    method: string;
  }>("/api/analytics/baseline");

export async function markNotifRead(id: number): Promise<void> {
  await fetch(`${base}/api/notifications/${id}/read`, { method: "PATCH" });
}

export async function markAllRead(): Promise<void> {
  await fetch(`${base}/api/notifications/read-all`, { method: "PATCH" });
}
