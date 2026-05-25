# Frontend — Tilapia IoT Dashboard

Dashboard web **Smart Water Change Alert System** dibangun dengan **React 19**, **TypeScript**, **Vite 8**, **Tailwind CSS 4**, dan **Recharts**.

> Dokumentasi lengkap: **[../DOCUMENTATION.md](../DOCUMENTATION.md)** · Arsitektur: **[../ARCHITECTURE.md](../ARCHITECTURE.md)**

---

## Stack

| Teknologi | Versi | Peran |
|-----------|-------|-------|
| React | 19 | UI framework |
| TypeScript | 6.x | Type safety |
| Vite | 8 | Dev server & build |
| Tailwind CSS | 4 | Styling (soft dark theme) |
| Recharts | 3.x | Grafik time-series |
| Lucide React | — | Icons (NotifBell, dll.) |
| nginx | Alpine | Production static server (Docker) |

---

## Struktur komponen

```
frontend/src/
├── App.tsx                 # Root — polling, layout
├── api.ts                  # Fetch helpers ke FastAPI
├── index.css               # Theme & global styles
└── components/
    ├── StatusPanel.tsx     # Status 4-level (Normal/Warning/Danger/Critical)
    ├── MetricCard.tsx      # Kartu suhu, pH, TDS + zone badge
    ├── SensorChart.tsx     # Line chart 24h + reference band
    ├── RecommendationBox.tsx # Prediksi 15 min + rekomendasi HRBAI
    ├── EventTimeline.tsx   # Riwayat perubahan status (PostgreSQL)
    └── NotifBell.tsx       # Bell + dropdown notifikasi
```

---

## API yang dipanggil

Base URL dari `VITE_API_BASE_URL` (default `http://localhost:8000`).

| Endpoint | Interval | Fungsi |
|----------|----------|--------|
| `GET /api/latest` | 30 detik | Snapshot sensor + prediksi + status |
| `GET /api/history` | 30 detik | Data 24 jam untuk grafik |
| `GET /api/notifications` | 30 detik | Daftar alert |
| `GET /api/events` | 30 detik | Timeline status |
| `GET /api/thresholds` | Saat mount | Batas ideal untuk reference band chart |
| `PATCH /api/notifications/{id}/read` | On click | Tandai notifikasi dibaca |

---

## Menjalankan (development)

```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

Buka http://localhost:5173 — pastikan backend FastAPI jalan di port 8000.

---

## Build production (Docker)

Frontend di-build ke image Docker dan disajikan via nginx di port **8081**:

```powershell
# Dari root proyek
docker compose up --build -d
```

Akses: http://localhost:8081

Build arg `VITE_API_BASE_URL` di-set di [`docker-compose.yml`](../docker-compose.yml).

---

## Environment

Salin [`frontend/.env.example`](.env.example):

```env
VITE_API_BASE_URL=http://localhost:8000
```

> **Penting:** variabel `VITE_*` ter-bake saat build. Jangan masukkan token InfluxDB atau secret ke frontend.

---

## Notifikasi browser

Dashboard meminta izin `Notification` API saat pertama kali dimuat. Alert muncul saat `action_required = true` atau status Danger/Critical dari `/api/latest`.

---

## Lint & build

```powershell
npm run lint
npm run build
```

---

_Group 1 — S2 / IoT Tilapia_
