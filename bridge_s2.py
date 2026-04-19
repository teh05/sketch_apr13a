#!/usr/bin/env python3
"""
MQTT subscriber -> InfluxDB v2 (bucket tilapia_monitoring).
Konfigurasi via environment variables; lihat SETUP_STACK.md.
"""

import json
import logging
import os
import sys

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

INFLUX_URL = os.environ.get("INFLUX_URL", "http://127.0.0.1:8086")
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN", "").strip()
INFLUX_ORG = os.environ.get("INFLUX_ORG", "S2_Project")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "tilapia_monitoring")
INFLUX_MEASUREMENT = os.environ.get("INFLUX_MEASUREMENT", "tilapia")

MQTT_HOST = os.environ.get("MQTT_HOST", "192.168.43.130")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "s2/water/monitoring")

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
        if rc != 0:
            log.warning("[*] MQTT terputus (rc=%s), mencoba reconnect...", rc)

    mqttc = mqtt.Client(client_id="bridge_s2_python", protocol=mqtt.MQTTv311)
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message
    mqttc.on_disconnect = on_disconnect

    try:
        mqttc.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        mqttc.loop_forever()
    except KeyboardInterrupt:
        log.info("[*] Berhenti.")
    finally:
        mqttc.disconnect()
        influx.close()


if __name__ == "__main__":
    main()
