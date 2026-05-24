import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import type { EventItem } from "../api";
import { fetchEvents } from "../api";

const STATUS_COLOR: Record<string, string> = {
  Critical: "bg-[#f87171]",
  Danger: "bg-[#fca5a5]",
  Warning: "bg-[#fcd34d]",
  Normal: "bg-[#6ee7b7]",
};

export default function EventTimeline() {
  const [events, setEvents] = useState<EventItem[]>([]);

  useEffect(() => {
    fetchEvents(20).then((d) => setEvents(d.events)).catch(() => {});
    const id = setInterval(() => {
      fetchEvents(20).then((d) => setEvents(d.events)).catch(() => {});
    }, 30_000);
    return () => clearInterval(id);
  }, []);

  if (events.length === 0) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-4">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-[var(--text-secondary)]">
        <Clock className="h-4 w-4" /> Status Timeline
      </h3>
      <div className="space-y-2 max-h-60 overflow-y-auto">
        {events.map((e) => (
          <div key={e.id} className="flex items-center gap-3 rounded-lg bg-[var(--bg-surface)] px-3 py-2">
            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${STATUS_COLOR[e.new_status] ?? STATUS_COLOR.Normal}`} />
            <div className="min-w-0 flex-1">
              <span className="text-xs text-[var(--text-primary)]">
                {e.prev_status ?? "—"} → <span className="font-medium">{e.new_status}</span>
              </span>
              {e.trigger_param && (
                <span className="ml-2 text-[10px] text-[var(--text-muted)]">({e.trigger_param})</span>
              )}
            </div>
            <span className="text-[10px] text-[var(--text-muted)] shrink-0">
              {new Date(e.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
