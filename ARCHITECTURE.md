# Arsitektur sistem — Tilapia IoT

Dokumen ini menjelaskan **alur data** dan **komponen** proyek agar mudah dipahami di GitHub. Diagram memakai [Mermaid](https://mermaid.js.org/); GitHub merender Mermaid secara native di file `.md`.

---

## 1. Alur data utama (sensor → penyimpanan → aplikasi)

Alur waktu-nyata: sensor di kolam → broker MQTT → skrip bridge menulis ke InfluxDB → API dan dashboard membaca dari InfluxDB.

```mermaid
flowchart LR
  ESP32["ESP32\nsketch_apr13a.ino"]
  MQTT["MQTT_broker\nLAN"]
  Bridge["bridge_s2.py\nhost"]
  Influx["InfluxDB_v2\nbucket_tilapia"]
  API["FastAPI\nbackend"]
  UI["React_dashboard\nfrontend"]
  Graf["Grafana"]
  Browser["Browser"]

  ESP32 -->|"topic_JSON\ns2_water_monitoring"| MQTT
  MQTT -->|"subscribe"| Bridge
  Bridge -->|"write_API"| Influx
  API -->|"Flux_query"| Influx
  Graf -->|"Flux_query"| Influx
  Browser -->|"HTTP"| UI
  Browser -->|"HTTP"| Graf
  UI -->|"REST\napi_latest_history"| API
```

**Payload JSON (contoh):** `{"suhu": float, "ph": float, "tds": int}` — selaras dengan firmware dan parser `bridge_s2.py`.

---

## 2. Stack Docker Compose (jaringan kontainer)

Layanan yang biasanya dijalankan bersama dengan `docker compose up`. Backend berbicara ke InfluxDB lewat **hostname layanan** `influxdb`, bukan `localhost`.

```mermaid
flowchart TB
  subgraph compose [Docker_network_sketch_apr13a]
    influxdb_s2["influxdb_s2\nInfluxDB_:8086"]
    grafana_s2["grafana_s2\nGrafana_:3000"]
    tilapia_backend["tilapia_backend\nFastAPI_:8000"]
    tilapia_frontend["tilapia_frontend\nnginx_:80_ke_host_8081"]
  end
  HostBridge["bridge_s2.py\ndi_host"]
  HostBridge -->|"localhost_8086"| influxdb_s2
  tilapia_backend -->|"http_influxdb_8086"| influxdb_s2
  grafana_s2 -->|"http_influxdb_8086"| influxdb_s2
  tilapia_frontend -->|"HTTP_ke_host\nVITE_API_BASE_URL"| tilapia_backend
```

| Layanan | Port host | Peran |
|---------|-----------|--------|
| `influxdb_s2` | 8086 | Time-series DB, bucket `tilapia_monitoring` |
| `grafana_s2` | 3000 | Dashboard analitis (Flux) |
| `tilapia_backend` | 8000 | REST `/api/latest`, `/api/history`, log CSV |
| `tilapia_frontend` | 8081 | UI React (static + nginx) |

---

## 3. Permintaan dashboard (baca data)

```mermaid
sequenceDiagram
  participant B as Browser
  participant F as Frontend_nginx
  participant A as FastAPI
  participant I as InfluxDB

  B->>F: GET /
  F-->>B: SPA_static
  loop setiap_30_detik
    B->>A: GET /api/latest
    A->>I: Flux_latest
    I-->>A: titik_terbaru
    A-->>B: JSON_status_rekomendasi
    B->>A: GET /api/history
    A->>I: Flux_24h
    I-->>A: deret_waktu
    A-->>B: points_untuk_grafik
  end
```

---

## 4. File & konfigurasi penting

| Lokasi | Fungsi |
|--------|--------|
| [`sketch_apr13a.ino`](sketch_apr13a.ino) | Firmware ESP32, publish MQTT |
| [`bridge_s2.py`](bridge_s2.py) | Subscriber MQTT → tulis Influx |
| [`backend/main.py`](backend/main.py) | API, integrasi `ai_engine`, log `decision_logs.csv` |
| [`frontend/src/App.tsx`](frontend/src/App.tsx) | Dashboard, Recharts, polling |
| [`.env`](.env) (root) | Token Influx untuk bridge |
| [`backend/.env`](backend/.env) | Token & org/bucket untuk API (Docker & lokal) |
| [`docker-compose.yml`](docker-compose.yml) | Orkestrasi layanan |

---

## 5. Catatan keamanan

- **Token InfluxDB** hanya dipakai di **host bridge** dan **backend** — jangan memasukkan token ke frontend atau repositori publik.
- Variabel `VITE_*` di frontend **terbaking** saat build; hanya URL API, bukan rahasia DB.

---

_Group 1 — S2 / IoT Tilapia_
