#!/usr/bin/env python3
"""
MQTT subscriber -> InfluxDB v2 (bucket tilapia_monitoring).

Features:
  - Validates JSON payload structure
  - Optional SHA256 signature verification (if 'sig' field present)
  - Structured logging with timestamps
"""

import hashlib
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
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
MQTT_CLIENT_ID = os.environ.get(
    "MQTT_CLIENT_ID", f"bridge_s2_{uuid.uuid4().hex[:10]}"
)
MQTT_KEEPALIVE = int(os.environ.get("MQTT_KEEPALIVE", "120"))

PAYLOAD_SECRET = os.environ.get("PAYLOAD_SECRET", "tilapia_iot_s2_key")
VERIFY_SIGNATURE = os.environ.get("VERIFY_SIGNATURE", "false").lower() == "true"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("bridge_s2")


def verify_sig(suhu: float, ph: float, tds: float, sig: str) -> bool:
    """Verify SHA256 signature from ESP32 payload."""
    raw = f"{suhu:.1f}|{ph:.2f}|{tds:.0f}|{PAYLOAD_SECRET}"
    expected = hashlib.sha256(raw.encode()).hexdigest()
    return sig == expected


def parse_payload(raw: str) -> dict:
    data = json.loads(raw)
    suhu = float(data["suhu"])
    ph = float(data["ph"])
    tds = data["tds"]
    if isinstance(tds, float):
        tds = int(round(tds))
    else:
        tds = int(tds)

    result = {"suhu": suhu, "ph": ph, "tds": tds}

    if "status" in data:
        result["status"] = str(data["status"])
    if "device" in data:
        result["device"] = str(data["device"])

    sig = data.get("sig")
    if sig and VERIFY_SIGNATURE:
        if not verify_sig(suhu, ph, tds, sig):
            raise ValueError("Signature mismatch — payload may be tampered")
        log.info("Signature verified OK")
    elif sig:
        log.debug("Signature present but VERIFY_SIGNATURE=false, skipping check")

    return result


def main() -> None:
    if not INFLUX_TOKEN:
        log.error("Set environment variable INFLUX_TOKEN (InfluxDB API token).")
        sys.exit(1)

    influx = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = influx.write_api(write_options=SYNCHRONOUS)

    def on_connect(client, _userdata, _flags, rc):
        if rc == 0:
            log.info("Connected to MQTT broker %s:%s", MQTT_HOST, MQTT_PORT)
            client.subscribe(MQTT_TOPIC)
            log.info("Subscribed: %s", MQTT_TOPIC)
        else:
            log.error("MQTT connect failed, rc=%s", rc)

    def on_message(client, _userdata, msg):
        raw = msg.payload.decode("utf-8", errors="replace")
        ts = datetime.now(timezone.utc).isoformat()
        try:
            fields = parse_payload(raw)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            log.error("Invalid payload: %s | error=%s", raw, e)
            return

        log.info(
            "Received: suhu=%.1f ph=%.2f tds=%d status=%s device=%s",
            fields["suhu"],
            fields["ph"],
            fields["tds"],
            fields.get("status", "—"),
            fields.get("device", "—"),
        )

        try:
            point = (
                Point(INFLUX_MEASUREMENT)
                .field("suhu", fields["suhu"])
                .field("ph", fields["ph"])
                .field("tds", fields["tds"])
            )
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
            log.info("Written to InfluxDB bucket=%s", INFLUX_BUCKET)
        except Exception as e:
            log.error("InfluxDB write failed: %s", e)

    def on_disconnect(client, _userdata, rc):
        if rc == 0:
            log.info("MQTT disconnect normal (rc=0).")
        else:
            hint = " (conn_lost: check client_id conflict, broker, WiFi)" if rc == 7 else ""
            log.warning("MQTT disconnected (rc=%s)%s — reconnecting...", rc, hint)

    mqttc = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv311)
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message
    mqttc.on_disconnect = on_disconnect
    mqttc.reconnect_delay_set(min_delay=1, max_delay=60)

    try:
        log.info("MQTT client_id=%s", MQTT_CLIENT_ID)
        log.info("VERIFY_SIGNATURE=%s", VERIFY_SIGNATURE)
        mqttc.connect(MQTT_HOST, MQTT_PORT, keepalive=MQTT_KEEPALIVE)
        mqttc.loop_forever()
    except KeyboardInterrupt:
        log.info("Stopped by user.")
    finally:
        mqttc.disconnect()
        influx.close()


if __name__ == "__main__":
    main()
