"""InfluxDB Flux queries for latest snapshot and history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from influxdb_client import InfluxDBClient

from config import (
    INFLUX_BUCKET,
    INFLUX_MEASUREMENT,
    INFLUX_ORG,
    INFLUX_TOKEN,
    INFLUX_URL,
)


def get_client() -> InfluxDBClient:
    if not INFLUX_TOKEN:
        raise ValueError("INFLUX_TOKEN is not set")
    return InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)


def _parse_pivot_record(record: dict[str, Any]) -> dict[str, Any]:
    t = record.get("_time")
    if hasattr(t, "isoformat"):
        ts = t.isoformat()
    else:
        ts = str(t) if t else None
    return {
        "time": ts,
        "suhu": record.get("suhu"),
        "ph": record.get("ph"),
        "tds": record.get("tds"),
    }


def query_latest(client: InfluxDBClient) -> dict[str, Any] | None:
    """Single most recent row with suhu, ph, tds (pivoted)."""
    q = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -90d)
  |> filter(fn: (r) => r["_measurement"] == "{INFLUX_MEASUREMENT}")
  |> filter(fn: (r) => r["_field"] == "suhu" or r["_field"] == "ph" or r["_field"] == "tds")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 1)
'''
    tables = client.query_api().query(q, org=INFLUX_ORG)
    for table in tables:
        for record in table.records:
            r = record.values
            return _parse_pivot_record(r)
    return None


def query_history_24h(client: InfluxDBClient) -> list[dict[str, Any]]:
    q = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "{INFLUX_MEASUREMENT}")
  |> filter(fn: (r) => r["_field"] == "suhu" or r["_field"] == "ph" or r["_field"] == "tds")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: false)
'''
    out: list[dict[str, Any]] = []
    tables = client.query_api().query(q, org=INFLUX_ORG)
    for table in tables:
        for record in table.records:
            out.append(_parse_pivot_record(record.values))
    return out


@dataclass
class SeriesPoint:
    time: datetime
    ph: float
    tds: float


def query_recent_pivoted(
    client: InfluxDBClient, limit: int = 60
) -> list[dict[str, Any]]:
    """Last N pivoted rows (newest first from Flux), fields ph, tds, suhu optional."""
    q = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "{INFLUX_MEASUREMENT}")
  |> filter(fn: (r) => r["_field"] == "suhu" or r["_field"] == "ph" or r["_field"] == "tds")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: {limit})
'''
    rows: list[dict[str, Any]] = []
    tables = client.query_api().query(q, org=INFLUX_ORG)
    for table in tables:
        for record in table.records:
            rows.append(record.values)
    return rows
