# Setup stack — InfluxDB, PostgreSQL, Grafana, bridge MQTT

Panduan menjalankan seluruh infrastruktur proyek **Smart Water Change Alert System — Tilapia IoT**.

> Dokumentasi lengkap: **[DOCUMENTATION.md](DOCUMENTATION.md)** · Arsitektur: **[ARCHITECTURE.md](ARCHITECTURE.md)**

---

## 1. Prasyarat

| Prasyarat | Keterangan |
|-----------|------------|
| Docker Desktop | Menjalankan 5 container |
| Python 3.12+ | `bridge_s2.py` dan pytest |
| Node.js 22+ | Dev frontend (opsional) |
| MQTT Broker | Aktif di LAN (mis. Mosquitto di `192.168.43.130:1883`) |
| ESP32 | Firmware `sketch_apr13a.ino` ter-upload |

---

## 2. Jalankan Docker Compose

Di folder root proyek:

```powershell
docker compose up --build -d
```

Cek status:

```powershell
docker ps
```

Container yang harus **Up**:

| Container | Port | Layanan |
|-----------|------|---------|
| `influxdb_s2` | 8086 | InfluxDB v2 |
| `tilapia_postgres` | 5432 | PostgreSQL 16 |
| `tilapia_backend` | 8000 | FastAPI |
| `tilapia_frontend` | 8081 | React + nginx |
| `grafana_s2` | 3000 | Grafana |

---

## 3. Token API InfluxDB

InfluxDB di-init otomatis oleh `docker-compose.yml`:

| Field | Nilai default |
|-------|---------------|
| Username | `admin_tilapia` |
| Password | `password_s2_tilapia` |
| Organization | `S2_Project` |
| Bucket | `tilapia_monitoring` |

**Generate token API:**

1. Buka http://localhost:8086
2. Login dengan kredensial di atas
3. **Load Data** → **API Tokens** → **Generate API Token** → **All Access Token**
4. Salin token (hanya ditampilkan sekali)

---

## 4. Variabel lingkungan

### Root `.env` (untuk `bridge_s2.py`)

Salin dari [`.env.example`](.env.example):

```env
INFLUX_URL=http://127.0.0.1:8086
INFLUX_TOKEN=<token-dari-langkah-3>
INFLUX_ORG=S2_Project
INFLUX_BUCKET=tilapia_monitoring
INFLUX_MEASUREMENT=tilapia

MQTT_HOST=192.168.43.130
MQTT_PORT=1883
MQTT_TOPIC=s2/water/monitoring

PAYLOAD_SECRET=tilapia_iot_s2_key
VERIFY_SIGNATURE=false
```

| Variabel | Default | Keterangan |
|----------|---------|------------|
| `INFLUX_URL` | `http://127.0.0.1:8086` | Bridge di **host** — pakai localhost |
| `MQTT_HOST` | `192.168.43.130` | IP broker MQTT (sesuaikan jaringan) |
| `VERIFY_SIGNATURE` | `false` | Set `true` untuk tolak payload tanpa/tidak valid SHA256 |

### `backend/.env` (untuk FastAPI + Docker backend)

Salin dari [`backend/.env.example`](backend/.env.example):

```env
INFLUX_URL=http://127.0.0.1:8086
INFLUX_TOKEN=<token-sama-dengan-root>
INFLUX_ORG=S2_Project
INFLUX_BUCKET=tilapia_monitoring

DATABASE_URL=postgresql://tilapia:tilapia_s2_secure@127.0.0.1:5432/tilapia_analytics
CORS_ORIGINS=http://localhost:5173,http://localhost:8081,http://127.0.0.1:5173,http://127.0.0.1:8081
```

> Di dalam Docker, `DATABASE_URL` di-override oleh `docker-compose.yml` ke hostname `postgres`.

### `frontend/.env`

```env
VITE_API_BASE_URL=http://localhost:8000
```

---

## 5. Dependensi Python & bridge MQTT

```powershell
pip install -r requirements.txt
python bridge_s2.py
```

Log sukses:

```
[*] Masuk: {'suhu': 29.8, 'ph': 6.73, 'tds': 58, ...}
[OK] Berhasil disimpan → bucket=tilapia_monitoring
```

**Catatan jaringan:** bridge di host memakai `http://127.0.0.1:8086`; Grafana di container memakai `http://influxdb:8086`.

---

## 6. Grafana

Grafana di-provision otomatis dari folder [`grafana/provisioning/`](grafana/provisioning/) dan dashboard [`grafana/dashboards/tilapia-water-quality.json`](grafana/dashboards/tilapia-water-quality.json).

| Field | Nilai |
|-------|-------|
| URL | http://localhost:3000 |
| Username | `admin` |
| Password | `tilapia_grafana_s2` |

Datasource InfluxDB (Flux) dan dashboard **Tilapia Water Quality** seharusnya sudah tersedia setelah container healthy.

**Jika datasource kosong (manual fallback):**

1. **Connections** → **Add data source** → **InfluxDB**
2. Query language: **Flux**
3. URL: `http://influxdb:8086` (hostname Docker, bukan localhost)
4. Organization: `S2_Project`, Token: sama dengan `.env`, Bucket: `tilapia_monitoring`

---

## 7. PostgreSQL

| Field | Nilai |
|-------|-------|
| Host | `localhost:5432` |
| Username | `tilapia` |
| Password | `tilapia_s2_secure` |
| Database | `tilapia_analytics` |

Cek tabel:

```powershell
docker exec tilapia_postgres psql -U tilapia -d tilapia_analytics -c "\dt"
```

Tabel: `notifications`, `water_quality_events`, `decision_logs`, `sensor_summaries`, `adaptive_baselines`.

---

## 8. ESP32 & MQTT

Pastikan firmware [`sketch_apr13a.ino`](sketch_apr13a.ino) memakai IP broker yang sama dengan `MQTT_HOST` di `.env`:

| Field firmware | Default |
|----------------|---------|
| MQTT Server | `192.168.43.130` |
| MQTT Port | `1883` |
| Topic | `s2/water/monitoring` |

---

## 9. Verifikasi end-to-end

```powershell
# Health API
Invoke-RestMethod http://127.0.0.1:8000/api/health

# Data terbaru + prediksi HRBAI
Invoke-RestMethod http://127.0.0.1:8000/api/latest

# Notifikasi di PostgreSQL
docker exec tilapia_postgres psql -U tilapia -d tilapia_analytics -c "SELECT COUNT(*) FROM notifications;"

# Unit test backend
cd backend
python -m pytest tests/ -v
```

| # | Skenario | Bukti |
|---|----------|-------|
| 1 | ESP32 publish MQTT | Serial log `[MQTT] Sent: {...}` |
| 2 | Bridge → InfluxDB | Log `Written to InfluxDB` |
| 3 | Backend baca Influx | `/api/latest` return suhu/ph/tds |
| 4 | AI prediksi | Field `predicted_ph`, `confidence` di response |
| 5 | PostgreSQL notif | Tabel `notifications` terisi |
| 6 | Dashboard chart | 3 SensorChart di http://localhost:8081 |
| 7 | Grafana panel | Dashboard Tilapia Water Quality |

---

## 10. Menghentikan stack

```powershell
docker compose down
```

Volume data (`influxdb_data`, `postgres_data`, `grafana_data`) tetap tersimpan. Tambahkan `-v` jika ingin hapus data.

---

## Prasyarat jaringan

- Broker MQTT harus aktif di alamat yang dipakai ESP32 dan `bridge_s2.py`
- PC yang menjalankan Docker + bridge harus bisa reach broker (subnet/firewall)
- ESP32 dan PC harus pada jaringan WiFi LAN yang sama

---

_Group 1 — S2 / IoT Tilapia_
