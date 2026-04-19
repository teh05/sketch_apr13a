# Pseudocode — Tilapia IoT Monitoring

Dokumen ini merangkum **logika algoritmik** proyek dalam bahasa pseudocode agar mudah dibaca di GitHub (tesis, README, atau lampiran). Bukan salinan baris-per-baris kode sumber.

**File terkait:** [`sketch_apr13a.ino`](sketch_apr13a.ino), [`bridge_s2.py`](bridge_s2.py), [`backend/main.py`](backend/main.py), [`backend/ai_engine.py`](backend/ai_engine.py), [`frontend/src/App.tsx`](frontend/src/App.tsx).

---

## 1. Firmware ESP32 (`sketch_apr13a.ino`)

```
PROSEDUR setup():
    inisialisasi Serial, OLED, WiFi
    hubungkan ke WiFi (ssid, password)
    atur server MQTT (alamat, port)
    mulai sensor suhu (OneWire / Dallas)

PROSEDUR loop() — berulang terus:
    JIKA WiFi terhubung MAKA
        JIKA belum terhubung ke broker MQTT MAKA
            reconnect MQTT dengan client_id acak
        akhir JIKA
        jalankan client.loop() untuk menjaga sesi MQTT
    akhir JIKA

    JIKA selisih waktu sekarang dengan kirim_terakhir > 5000 ms MAKA
        tandai kirim_terakhir = sekarang

        baca suhu dari sensor Dallas
        baca TDS dari ADC → voltase → konversi ke ppm (polinomial)
        baca pH dari ADC (rata-rata 10 sampel) → voltase → kalibrasi ke skala pH

        tampilkan suhu, pH, TDS pada OLED

        JIKA MQTT terhubung MAKA
            bentuk string JSON: {"suhu", "ph", "tds"}
            publish(JSON) ke topik "s2/water/monitoring"
        akhir JIKA
    akhir JIKA
```

---

## 2. Bridge MQTT → InfluxDB (`bridge_s2.py`)

```
PROSEDUR main():
    muat variabel dari file .env (INFLUX_*, MQTT_*)
    JIKA INFLUX_TOKEN kosong MAKA
        cetak error dan keluar
    akhir JIKA

    buka klien InfluxDB + write_api (sinkron)

    DEFINISIKAN on_connect(klien_mqtt):
        JIKA koneksi sukses MAKA
            subscribe ke topik MQTT_TOPIC
        akhir JIKA

    DEFINISIKAN on_message(klien_mqtt, pesan):
        raw ← decode payload pesan ke teks UTF-8
        COBA:
            fields ← parse JSON: suhu, ph, tds (tds sebagai integer)
        TANGKAP error:
            log error; KELUAR dari handler
        log "Masuk" + fields

        COBA:
            bentuk Point(measurement) dengan field suhu, ph, tds
            write_api.write(bucket, org, point)
            log sukses
        TANGKAP error:
            log gagal simpan Influx

    DEFINISIKAN on_disconnect:
        JIKA kode putus ≠ 0 MAKA log peringatan (opsional: rc=7 = koneksi hilang)

    buat klien MQTT dengan client_id unik
    set reconnect_delay (min, max)
    connect ke MQTT_HOST:MQTT_PORT
    loop_forever() — blok sampai Ctrl+C

    tutup MQTT dan Influx
```

---

## 3. API FastAPI — snapshot terkini (`GET /api/latest`)

```
FUNGSI api_latest():
    JIKA klien Influx tidak dikonfigurasi MAKA
        kembalikan HTTP 503
    akhir JIKA

    row ← query_latest(Influx) — satu baris terakhir (pivot suhu, ph, tds)

    JIKA row kosong MAKA
        kembalikan JSON default: nilai null, status Normal, data_stale = true
    akhir JIKA

    suhu, ph, tds ← ekstrak angka dari row
    wq ← water_quality_status(suhu, ph, tds)   // aturan ambang saat ini

    recent_rows ← query_recent_pivoted(limit = 60)
    pred ← predict_status(recent_rows)         // placeholder AI / tren 15 menit

    rec ← recommendation(pred.ai_status, wq)

    action_required ← (wq = Danger) ATAU (pred.ai_status = WARNING_CHANGE_WATER)

    JIKA Danger ATAU WARNING_CHANGE_WATER MAKA
        append_decision ke CSV (timestamp, nilai, prediksi, alasan, status)
        log INFO keputusan
    akhir JIKA

    kembalikan JSON: waktu, suhu, ph, tds, wq, ai_status, prediksi, rec,
                     action_required, data_stale = false
```

---

## 4. API FastAPI — histori 24 jam (`GET /api/history`)

```
FUNGSI api_history():
    JIKA klien Influx tidak dikonfigurasi MAKA
        kembalikan HTTP 503
    akhir JIKA

    points ← query_history_24h(Influx) — deret {time, suhu, ph, tds}

    kembalikan JSON { "points": points, "count": panjang(points) }
```

---

## 5. Mesin aturan & prediksi (`ai_engine.py`)

### 5.1 Status kualitas air (nilai **sekarang**)

```
FUNGSI water_quality_status(suhu, ph, tds):
    JIKA ph atau tds tidak ada MAKA kembalikan "Normal"

    JIKA ph < 6.5 ATAU ph > 8.5 ATAU tds > 500 MAKA
        kembalikan "Danger"
    JIKA TIDAK JIKA tds > 400 ATAU ph di luar rentang aman mendekati batas MAKA
        kembalikan "Warning"   // sesuai implementasi
    JIKA TIDAK
        kembalikan "Normal"
```

### 5.2 Prediksi trajectory (placeholder; ganti dengan LSTM nanti)

```
FUNGSI predict_status(rows_pivoted_dari_Influx):
    urutkan rows menaik menurut waktu
    ekstrak deret waktu, ph, tds

    JIKA titik data < 2 MAKA
        kembalikan ai_status = OK, alasan = insufficient_points
    akhir JIKA

    pred_ph ← linear_forecast(waktu, ph, horizon = 15 menit dalam detik)
    pred_tds ← linear_forecast(waktu, tds, horizon yang sama)

    cur_danger ← apakah (ph_terakhir, tds_terakhir) di zona bahaya
    pred_danger ← apakah (pred_ph, pred_tds) di zona bahaya

    JIKA BUKAN cur_danger DAN pred_danger MAKA
        kembalikan WARNING_CHANGE_WATER + prediksi + alasan trajectory_to_danger
    JIKA TIDAK
        kembalikan OK + prediksi + alasan trajectory_ok
```

```
FUNGSI recommendation(ai_status, water_quality_status):
    JIKA water_quality_status = "Danger" ATAU ai_status = WARNING_CHANGE_WATER MAKA
        kembalikan teks "Change 30% of water now"
    JIKA TIDAK
        kembalikan "Stay Calm"
```

---

## 6. Log keputusan (`decision_log.py`)

```
PROSEDUR append_decision(suhu, ph, tds, predicted_ph, predicted_tds, reason, status):
    pastikan folder logs ada
    pastikan file CSV punya header jika file baru

    baris ← [timestamp_ISO_UTC, suhu, ph, tds, predicted_ph, predicted_tds, reason, status]
    tambahkan baris ke decision_logs.csv (append)
```

---

## 7. Dashboard React (`frontend/src/App.tsx`)

```
PROSEDUR komponen App:
    state: latest, history, error, loading, modal_terbuka

    PROSEDUR load_data():
        COBA:
            parallel: fetch GET /api/latest, GET /api/history
            simpan ke state
            JIKA action_required atau Danger atau WARNING MAKA
                buka modal
                JIKA izin Notification granted MAKA
                    tampilkan notifikasi browser (teks sesuai kondisi)
                akhir JIKA
        TANGKAP error:
            simpan pesan error

    saat mount:
        panggil load_data()
        set interval setiap 30 detik → load_data()

    saat mount (sekali):
        minta izin Notification jika belum ditentukan

    render:
        header judul
        panel status besar: hijau "Air sehat" ATAU merah "Action required"
        tiga kartu: suhu, pH, TDS dari latest
        kotak rekomendasi + teks prediksi opsional
        grafik garis (Recharts) dari history.points — sumbu waktu vs suhu, ph, tds
        JIKA modal_terbuka MAKA overlay instruksi ganti air + tombol tutup
```

---

## 8. Ringkasan alur end-to-end

```
ESP32 → (JSON MQTT) → broker → bridge_s2 → InfluxDB
                                    ↑
Browser → React → FastAPI ─────────┘ (baca + aturan + prediksi + CSV log)
Grafana → InfluxDB (visualisasi terpisah)
```

---

_Untuk diagram arsitektur, lihat [ARCHITECTURE.md](ARCHITECTURE.md)._
