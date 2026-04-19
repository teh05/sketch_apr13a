#!/usr/bin/env python3
"""
MQTT subscriber -> InfluxDB v2 (bucket tilapia_monitoring).
Konfigurasi via file .env (lokal) atau environment variables; lihat SETUP_STACK.md.
"""

import json
import logging
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

load_dotenv(Path(__file__).resolve().parent / ".env")

INFLUX_URL = os.environ.get("INFLUX_URL", "http://127.0.0.1:8086")
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN", "").strip()
INFLUX_ORG = os.environ.get("INFLUX_ORG", "S2_Project")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "tilapia_monitoring")
INFLUX_MEASUREMENT = os.environ.get("INFLUX_MEASUREMENT", "tilapia")

MQTT_HOST = os.environ.get("MQTT_HOST", "192.168.43.130")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "s2/water/monitoring")
# ID unik bawaan menghindari bentrok (rc=7 loop): dua bridge / broker kick sesi lama.
MQTT_CLIENT_ID = os.environ.get(
    "MQTT_CLIENT_ID", f"bridge_s2_{uuid.uuid4().hex[:10]}"
)
MQTT_KEEPALIVE = int(os.environ.get("MQTT_KEEPALIVE", "120"))

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("bridge_s2")


def parse_payload(raw: str) -> dict:
    data = json.loads(raw)
    suhu = float(data["suhu"])
    ph = float(data["ph"])
    tds = data["tds"]
    if isinstance(tds, float):
        tds = int(round(tds))
    else:
        tds = int(tds)
    return {"suhu": suhu, "ph": ph, "tds": tds}


def main() -> None:
    if not INFLUX_TOKEN:
        log.error("[ERR] Set environment variable INFLUX_TOKEN (InfluxDB API token).")
        sys.exit(1)

    influx = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = influx.write_api(write_options=SYNCHRONOUS)

    def on_connect(client, _userdata, _flags, rc):
        if rc == 0:
            log.info("[*] Terhubung ke MQTT broker %s:%s", MQTT_HOST, MQTT_PORT)
            client.subscribe(MQTT_TOPIC)
            log.info("[*] Subscribe: %s", MQTT_TOPIC)
        else:
            log.error("[ERR] MQTT connect gagal, rc=%s", rc)

    def on_message(client, _userdata, msg):
        raw = msg.payload.decode("utf-8", errors="replace")
        try:
            fields = parse_payload(raw)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            log.error("[ERR] Payload tidak valid: %s | error=%s", raw, e)
            return
        log.info("[*] Masuk: %s", fields)
        try:
            point = (
                Point(INFLUX_MEASUREMENT)
                .field("suhu", fields["suhu"])
                .field("ph", fields["ph"])
                .field("tds", fields["tds"])
            )
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
            log.info("[OK] Berhasil disimpan ke InfluxDB bucket=%s", INFLUX_BUCKET)
        except Exception as e:
            log.error("[ERR] Gagal menyimpan ke InfluxDB: %s", e)

    def on_disconnect(client, _userdata, rc):
        if rc == 0:
            log.info("[*] MQTT disconnect normal (rc=0).")
        else:
            # Paho: 7 = MQTT_ERR_CONN_LOST (koneksi putus dari broker/jaringan)
            hint = " (conn_lost: cek bentrok client_id, broker, WiFi)" if rc == 7 else ""
            log.warning("[*] MQTT terputus (rc=%s)%s — reconnect...", rc, hint)

    mqttc = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv311)
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message
    mqttc.on_disconnect = on_disconnect
    mqttc.reconnect_delay_set(min_delay=1, max_delay=60)

    try:
        log.info("[*] MQTT client_id=%s (set MQTT_CLIENT_ID untuk nilai tetap)", MQTT_CLIENT_ID)
        mqttc.connect(MQTT_HOST, MQTT_PORT, keepalive=MQTT_KEEPALIVE)
        mqttc.loop_forever()
    except KeyboardInterrupt:
        log.info("[*] Berhenti.")
    finally:
        mqttc.disconnect()
        influx.close()


if __name__ == "__main__":
    main()
