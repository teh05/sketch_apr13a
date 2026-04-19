# InfluxDB, Grafana, dan bridge MQTT (`bridge_s2.py`)

## 1. Jalankan Docker

Di folder proyek ini:

```bash
docker compose up -d
```

Cek: `docker ps` — container `influxdb_s2` dan `grafana_s2` harus **Up**.

## 2. Token API InfluxDB

1. Buka [http://localhost:8086](http://localhost:8086).
2. Login dengan user/password dari [docker-compose.yml](docker-compose.yml) (`admin_tilapia` / `password_s2_tilapia`).
3. **Load Data** → **API Tokens** → **Generate API Token** → **All Access Token**, nama misalnya `PythonBridge`.
4. Salin token (hanya ditampilkan sekali).

## 3. Variabel lingkungan untuk bridge

Wajib:

- `INFLUX_TOKEN` — token dari langkah 2.

Opsional (default sudah cocok dengan compose + firmware):

| Variabel | Default | Keterangan |
|----------|---------|------------|
| `INFLUX_URL` | `http://127.0.0.1:8086` | Bridge jalan di **host**; gunakan localhost, bukan nama container. |
| `INFLUX_ORG` | `S2_Project` | |
| `INFLUX_BUCKET` | `tilapia_monitoring` | |
| `INFLUX_MEASUREMENT` | `tilapia` | Nama measurement di Influx. |
| `MQTT_HOST` | `192.168.43.130` | Broker MQTT (sama dengan ESP32). |
| `MQTT_PORT` | `1883` | |
| `MQTT_TOPIC` | `s2/water/monitoring` | |

**PowerShell (sesi saat ini):**

```powershell
$env:INFLUX_TOKEN = "paste-token-di-sini"
python bridge_s2.py
```

## 4. Dependensi Python

```bash
pip install -r requirements.txt
```

## 5. Grafana — data source InfluxDB

1. Buka [http://localhost:3000](http://localhost:3000) (default `admin` / `admin`).
2. **Connections** → **Add data source** → **InfluxDB**.
3. **Query language:** Flux.
4. **URL:** `http://influxdb:8086` — ini hostname **service** Docker (bukan `localhost`), karena Grafana berjalan **di dalam** jaringan compose.
5. Isi **Organization**, **Token**, **Default Bucket** sama seperti di atas.

Bridge di host tetap memakai `http://127.0.0.1:8086`; hanya Grafana di container yang memakai `http://influxdb:8086`.

## 6. Verifikasi

- Log bridge: baris `[*] Masuk: ...` dan `[OK] Berhasil disimpan ...`.
- Log InfluxDB: `docker logs -f influxdb_s2`.
- Di Grafana, buat dashboard **Time series** dengan query Flux ke bucket `tilapia_monitoring`.

## Prasyarat jaringan

- Broker MQTT harus aktif di alamat yang dipakai ESP32 (mis. `192.168.43.130`).
- PC yang menjalankan Docker + `bridge_s2.py` harus bisa mencapai broker tersebut (subnet/firewall).
