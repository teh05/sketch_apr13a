# Pseudocode — Tilapia IoT Monitoring

Dokumen ini merangkum **logika algoritmik** proyek dalam bahasa pseudocode agar mudah dibaca di GitHub (laporan, README, atau lampiran). Bukan salinan baris-per-baris kode sumber.

> Dokumentasi lengkap: **[DOCUMENTATION.md](DOCUMENTATION.md)** · Arsitektur: **[ARCHITECTURE.md](ARCHITECTURE.md)**

**File terkait:** [`sketch_apr13a.ino`](sketch_apr13a.ino), [`bridge_s2.py`](bridge_s2.py), [`backend/main.py`](backend/main.py), [`backend/ai_engine.py`](backend/ai_engine.py), [`backend/thresholds.py`](backend/thresholds.py), [`backend/notification_service.py`](backend/notification_service.py), [`frontend/src/App.tsx`](frontend/src/App.tsx).

---

## 1. Firmware ESP32 (`sketch_apr13a.ino`)

```
PROSEDUR setup():
    inisialisasi Serial, ADC 12-bit
    inisialisasi pin Buzzer, LED Safe, LED Danger
    inisialisasi OLED SSD1306 (I2C 0x3C)
    hubungkan WiFi (ssid, password)
    audit keamanan WiFi (WPA2)
    atur server MQTT (alamat, port)
    mulai sensor suhu DS18B20 (OneWire GPIO4)

PROSEDUR loop() — berulang terus:
    JIKA WiFi terhubung MAKA
        JIKA belum terhubung ke broker MQTT MAKA reconnect MQTT
        jalankan client.loop()
    akhir JIKA

    JIKA selisih waktu < 5000 ms MAKA KELUAR  // interval 5 detik
    tandai waktu_kirim = sekarang

  // --- BACA SENSOR ---
    baca suhu dari DS18B20
    baca TDS dari ADC GPIO35 → voltase → polinomial ppm
    baca pH dari ADC GPIO34 (rata-rata 20 sampel) → voltase
    pH ← (PH_SLOPE × voltase) + PH_INTERCEPT   // kalibrasi 2 titik

  // --- KLASIFIKASI & AKTUATOR ---
    status ← classifyStatus(suhu, pH, TDS)   // Ideal/Warning/Danger/Critical
    isDanger ← (status = Danger ATAU status = Critical)

    JIKA isDanger MAKA
        LED Safe ← OFF; LED Danger ← ON; buzzer ← ON (updateBuzzer)
    JIKA TIDAK MAKA
        LED Safe ← ON; LED Danger ← OFF; buzzer ← OFF
    akhir JIKA

    tampilkan suhu, pH, TDS, status pada OLED
    JIKA isDanger MAKA tampilkan "!! GANTI AIR !!" pada OLED

  // --- EDGE FILTER ---
    JIKA TIDAK significantChange(suhu, pH, TDS) MAKA
        log "No significant change, skipping MQTT"
        KELUAR
    akhir JIKA
    // delta: suhu ≥ 0.3°C, pH ≥ 0.05, TDS ≥ 5 ppm

    perbarui lastSuhu, lastPH, lastTDS

  // --- PAYLOAD + SHA256 ---
    payload ← JSON {suhu, ph, tds, status, device}
    sigInput ← suhu + "|" + ph + "|" + tds + "|" + PAYLOAD_SECRET
    sig ← SHA256_hex(sigInput)
    fullPayload ← payload + field "sig"

  // --- PUBLISH MQTT ---
    JIKA MQTT terhubung MAKA
        publish(fullPayload) ke topik "s2/water/monitoring"
    akhir JIKA
```

---

## 2. Bridge MQTT → InfluxDB (`bridge_s2.py`)

```
PROSEDUR main():
    muat variabel dari .env (INFLUX_*, MQTT_*, PAYLOAD_SECRET, VERIFY_SIGNATURE)
    JIKA INFLUX_TOKEN kosong MAKA cetak error; KELUAR
    akhir JIKA

    buka klien InfluxDB + write_api (sinkron)

    DEFINISIKAN on_connect(klien_mqtt):
        JIKA koneksi sukses MAKA subscribe ke MQTT_TOPIC

    DEFINISIKAN on_message(klien_mqtt, pesan):
        raw ← decode payload ke UTF-8
        COBA:
            data ← parse JSON
            validasi field: suhu, ph, tds
        TANGKAP error:
            log error; KELUAR

        JIKA VERIFY_SIGNATURE = true MAKA
            verifikasi field "sig" dengan SHA256(suhu|ph|tds|secret)
            JIKA gagal MAKA log "Invalid signature"; KELUAR
        akhir JIKA

        log "Masuk" + data

        COBA:
            bentuk Point(measurement=tilapia) dengan field suhu, ph, tds
            write_api.write(bucket, org, point)
            log sukses
        TANGKAP error:
            log gagal simpan Influx

    connect ke MQTT_HOST:MQTT_PORT
    loop_forever()
```

---

## 3. API FastAPI — snapshot terkini (`GET /api/latest`)

```
FUNGSI api_latest(db: PostgreSQL session):
    JIKA klien Influx tidak dikonfigurasi MAKA kembalikan HTTP 503

    row ← query_latest(Influx) — titik terakhir (pivot suhu, ph, tds)

    JIKA row kosong MAKA
        kembalikan JSON: nilai null, data_stale = true
    akhir JIKA

    suhu, ph, tds ← ekstrak angka dari row
    wq ← water_quality_status(suhu, ph, tds)   // 4 level, worst-case

    recent_rows ← query_recent_pivoted(limit = 60)
    adaptive ← compute_adaptive_thresholds(recent_rows)
    pred ← predict_status(recent_rows, adaptive)   // HRBAI

    rec ← recommendation(pred.ai_status, wq)
    zones ← zone per parameter (suhu_zone, ph_zone, tds_zone)

    action_required ← (wq ∈ {Danger, Critical})
                     ATAU (pred.ai_status = WARNING_CHANGE_WATER)

    // Side-effect PostgreSQL
    notification_service.check_and_notify(db, wq, pred, suhu, ph, tds)
    catat event jika status berubah (water_quality_events)
    JIKA action_required MAKA
        append_decision ke PostgreSQL decision_logs
    akhir JIKA

    kembalikan JSON: time, suhu, ph, tds, zones, wq,
                     ai_status, predicted_*, confidence, recommendation,
                     action_required, anomalies, adaptive, data_stale = false
```

---

## 4. API FastAPI — histori 24 jam (`GET /api/history`)

```
FUNGSI api_history():
    JIKA klien Influx tidak dikonfigurasi MAKA kembalikan HTTP 503

    points ← query_history_24h(Influx) — deret {time, suhu, ph, tds}
    kembalikan JSON { "points": points, "count": panjang(points) }
```

---

## 5. Mesin HRBAI (`ai_engine.py`)

### 5.1 Status kualitas air — 4 zona (`thresholds.py`)

```
FUNGSI water_quality_status(suhu, ph, tds):
    zone_ph   ← classify_zone(ph,   PH_THRESHOLDS)
    zone_tds  ← classify_zone(tds,  TDS_THRESHOLDS)
    zone_suhu ← classify_zone(suhu, SUHU_THRESHOLDS)

    kembalikan worst_case(zone_ph, zone_tds, zone_suhu)
    // ideal → Normal, warning → Warning, danger → Danger, critical → Critical
```

### 5.2 Adaptive baseline

```
FUNGSI compute_adaptive_thresholds(rows):
    UNTUK SETIAP parameter (ph, tds, suhu):
        mean ← rata-rata values
        std  ← standar deviasi sampel
        adaptive_low  ← max(biological_ideal_low,  mean − 1.5 × std)
        adaptive_high ← min(biological_ideal_high, mean + 1.5 × std)
    kembalikan AdaptiveThresholds
```

### 5.3 Prediksi trajectory (linear forecast 15 menit)

```
FUNGSI predict_status(rows, adaptive):
    urutkan rows menaik menurut waktu
    JIKA titik data < 2 MAKA kembalikan ai_status = OK, alasan = insufficient_points

    pred_ph   ← linear_forecast(waktu, ph,   horizon = 15 menit)
    pred_tds  ← linear_forecast(waktu, tds,  horizon = 15 menit)
    pred_suhu ← linear_forecast(waktu, suhu, horizon = 15 menit)

    anomalies ← deteksi z-score > 2.5 per parameter
    confidence ← f(jumlah_titik, rentang_waktu)

    cur_zone   ← water_quality_status(suhu_terakhir, ph_terakhir, tds_terakhir)
    pred_zone  ← water_quality_status(pred_suhu, pred_ph, pred_tds)

    JIKA cur_zone aman DAN pred_zone ∈ {Danger, Critical} MAKA
        kembalikan WARNING_CHANGE_WATER + prediksi + alasan trajectory_to_danger
    JIKA TIDAK
        kembalikan OK + prediksi + alasan trajectory_ok
```

### 5.4 Rekomendasi

```
FUNGSI recommendation(ai_status, water_quality_status):
    JIKA water_quality_status = Critical MAKA
        kembalikan "EMERGENCY: ganti air segera"
    JIKA wq = Danger ATAU ai_status = WARNING_CHANGE_WATER MAKA
        kembalikan "Ganti 30% air kolam"
    JIKA wq = Warning MAKA
        kembalikan "Monitor ketat, siapkan air pengganti"
    JIKA TIDAK
        kembalikan "Kondisi air ideal"
```

---

## 6. Notifikasi (`notification_service.py`)

```
FUNGSI check_and_notify(db, wq, pred, suhu, ph, tds):
    JIKA wq ∈ {Danger, Critical} ATAU pred.ai_status = WARNING_CHANGE_WATER MAKA
        JIKA belum ada notifikasi serupa dalam window dedup MAKA
            INSERT ke notifications (severity, title, message, category)
        akhir JIKA
    akhir JIKA

FUNGSI record_status_change(db, prev_status, new_status, suhu, ph, tds):
    JIKA prev_status ≠ new_status MAKA
        INSERT ke water_quality_events
    akhir JIKA
```

---

## 7. Log keputusan (`decision_log.py`)

```
PROSEDUR append_decision(db, suhu, ph, tds, predicted_ph, predicted_tds, reason, status):
    INSERT ke PostgreSQL decision_logs
        (timestamp, suhu, ph, tds, predicted_ph, predicted_tds, reason, status)

    // Opsional: append baris ke backend/logs/decision_logs.csv
```

---

## 8. Dashboard React (`frontend/src/App.tsx` + components)

```
PROSEDUR komponen App:
    state: latest, history, notifications, events, error, loading

    PROSEDUR load_data():
        parallel fetch:
            GET /api/latest
            GET /api/history
            GET /api/notifications
            GET /api/events
        simpan ke state

        JIKA latest.action_required ATAU severity tinggi MAKA
            JIKA izin Notification granted MAKA tampilkan browser notification
        akhir JIKA

    saat mount:
        panggil load_data()
        set interval 30 detik → load_data()
        minta izin Notification (sekali)

    render:
        StatusPanel      ← latest.water_quality_status (4 level)
        MetricCard ×3    ← suhu, pH, TDS + zone badge + sparkline
        SensorChart ×3   ← history 24h + reference band ideal
        RecommendationBox← prediksi 15 min + rekomendasi AI
        EventTimeline    ← GET /api/events
        NotifBell        ← GET /api/notifications + unread count
```

---

## 9. Ringkasan alur end-to-end

```
Sensor (DS18B20 | pH 4502C | TDS)
    → ESP32 (classify + edge filter + SHA256)
    → MQTT broker
    → bridge_s2.py
    → InfluxDB (time-series)

Browser → React Dashboard
    → FastAPI (HRBAI + thresholds)
        → InfluxDB (baca histori)
        → PostgreSQL (notif, events, decisions)
    → tampilkan chart + alert

Grafana → InfluxDB (visualisasi analitik terpisah)
```

---

## 10. Placeholder pengembangan lanjutan

```
// ai_engine.py — rencana pengganti linear forecast:
FUNGSI predict_status_lstm(rows):
    muat model LSTM (.h5 / .pkl)
    pred_ph, pred_tds, pred_suhu ← model.predict(sequence)
    // belum diimplementasi pada fase prototipe saat ini
```

---

_Untuk diagram arsitektur, lihat [ARCHITECTURE.md](ARCHITECTURE.md). Untuk setup dan kredensial, lihat [SETUP_STACK.md](SETUP_STACK.md)._
