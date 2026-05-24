import { Bell, CheckCheck, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { NotifItem } from "../api";
import { fetchNotifications, fetchUnreadCount, markAllRead, markNotifRead } from "../api";

const SEVERITY_DOT: Record<string, string> = {
  critical: "bg-[#f87171]",
  danger: "bg-[#fca5a5]",
  warning: "bg-[#fcd34d]",
  info: "bg-[#7dd3fc]",
};

export default function NotifBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotifItem[]>([]);
  const [unread, setUnread] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    try {
      const [n, u] = await Promise.all([fetchNotifications(30), fetchUnreadCount()]);
      setItems(n.notifications);
      setUnread(u.unread);
    } catch {
      /* api offline */
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15_000);
    return () => clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const handleRead = async (id: number) => {
    await markNotifRead(id);
    setItems((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
    setUnread((u) => Math.max(0, u - 1));
  };

  const handleReadAll = async () => {
    await markAllRead();
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnread(0);
  };

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative rounded-lg p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-card)] hover:text-[var(--text-primary)]"
      >
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#f87171] px-1 text-[10px] font-bold text-white">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-80 max-h-96 overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--bg-surface)] shadow-xl sm:w-96">
          <div className="sticky top-0 flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-surface)] px-4 py-3">
            <span className="text-sm font-medium text-[var(--text-primary)]">Notifikasi</span>
            <div className="flex gap-2">
              {unread > 0 && (
                <button onClick={handleReadAll} className="text-xs text-[var(--accent-info)] hover:underline flex items-center gap-1">
                  <CheckCheck className="h-3.5 w-3.5" /> Tandai semua
                </button>
              )}
              <button onClick={() => setOpen(false)} className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {items.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">Belum ada notifikasi</p>
          ) : (
            <ul>
              {items.map((n) => (
                <li
                  key={n.id}
                  className={`border-b border-[var(--border)]/50 px-4 py-3 ${n.is_read ? "opacity-60" : ""} hover:bg-[var(--bg-card)]`}
                  onClick={() => !n.is_read && handleRead(n.id)}
                  role="button"
                >
                  <div className="flex items-start gap-2.5">
                    <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${SEVERITY_DOT[n.severity] ?? SEVERITY_DOT.info}`} />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-[var(--text-primary)] leading-snug">{n.title}</p>
                      <p className="mt-0.5 text-xs text-[var(--text-secondary)] leading-relaxed">{n.message}</p>
                      <p className="mt-1 text-[10px] text-[var(--text-muted)]">
                        {new Date(n.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
