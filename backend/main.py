"""
FastAPI API for Tilapia monitoring: latest snapshot, 24h history, AI placeholder.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient

import ai_engine
from config import CORS_ORIGINS, INFLUX_TOKEN
from decision_log import append_decision
import influx_query

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tilapia_api")

_client: InfluxDBClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client
    if not INFLUX_TOKEN:
        log.warning("INFLUX_TOKEN not set — /api/latest and /api/history will fail.")
        _client = None
    else:
        _client = influx_query.get_client()
    yield
    if _client is not None:
        _client.close()
        _client = None


app = FastAPI(title="Tilapia Monitoring API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _float_or_none(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/latest")
def api_latest() -> dict[str, Any]:
    if _client is None:
        raise HTTPException(status_code=503, detail="InfluxDB not configured (INFLUX_TOKEN)")

    try:
        row = influx_query.query_latest(_client)
    except Exception as e:
        log.exception("Influx latest query failed")
        raise HTTPException(status_code=503, detail=f"influx_error: {e!s}") from e

    if not row:
        return {
            "time": None,
            "suhu": None,
            "ph": None,
            "tds": None,
            "water_quality_status": "Normal",
            "ai_status": "OK",
            "prediction_status": "OK",
            "predicted_ph": None,
            "predicted_tds": None,
            "horizon_minutes": 15,
            "recommendation": "Stay Calm",
            "action_required": False,
            "data_stale": True,
        }

    suhu = _float_or_none(row.get("suhu"))
    ph = _float_or_none(row.get("ph"))
    tds = _float_or_none(row.get("tds"))
    wq = ai_engine.water_quality_status(suhu, ph, tds)

    try:
        recent_rows = influx_query.query_recent_pivoted(_client, limit=60)
        pred = ai_engine.predict_status(recent_rows)
    except Exception as e:
        log.warning("AI prediction fallback: %s", e)
        pred = ai_engine.PredictionResult(
            ai_status="OK",
            predicted_ph=None,
            predicted_tds=None,
            horizon_minutes=15,
            reason=f"prediction_error:{e!s}",
        )

    rec = ai_engine.recommendation(pred.ai_status, wq)
    action_required = wq == "Danger" or pred.ai_status == "WARNING_CHANGE_WATER"

    if wq == "Danger" or pred.ai_status == "WARNING_CHANGE_WATER":
        try:
            append_decision(
                suhu=suhu,
                ph=ph,
                tds=tds,
                predicted_ph=pred.predicted_ph,
                predicted_tds=pred.predicted_tds,
                reason=pred.reason,
                status=f"{wq}|{pred.ai_status}",
            )
            log.info(
                "Decision logged: wq=%s ai=%s ph=%s tds=%s",
                wq,
                pred.ai_status,
                ph,
                tds,
            )
        except OSError as e:
            log.error("Could not write decision_logs.csv: %s", e)

    return {
        "time": row.get("time"),
        "suhu": suhu,
        "ph": ph,
        "tds": tds,
        "water_quality_status": wq,
        "ai_status": pred.ai_status,
        "prediction_status": pred.ai_status,
        "predicted_ph": pred.predicted_ph,
        "predicted_tds": pred.predicted_tds,
        "horizon_minutes": pred.horizon_minutes,
        "prediction_reason": pred.reason,
        "recommendation": rec,
        "action_required": action_required,
        "data_stale": False,
    }


@app.get("/api/history")
def api_history() -> dict[str, Any]:
    if _client is None:
        raise HTTPException(status_code=503, detail="InfluxDB not configured (INFLUX_TOKEN)")

    try:
        series = influx_query.query_history_24h(_client)
    except Exception as e:
        log.exception("Influx history query failed")
        raise HTTPException(status_code=503, detail=f"influx_error: {e!s}") from e

    return {"points": series, "count": len(series)}
