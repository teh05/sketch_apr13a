"""
FastAPI backend for Tilapia IoT monitoring.

Endpoints:
  /api/health            — healthcheck
  /api/latest            — current readings + AI status + predictions
  /api/history           — 24h time-series from InfluxDB
  /api/notifications     — in-app alert list (PostgreSQL)
  /api/notifications/{id}/read — mark notification read
  /api/notifications/unread-count
  /api/events            — water-quality status transitions
  /api/analytics/summary — hourly aggregates from PostgreSQL
  /api/analytics/baseline — current adaptive thresholds
  /api/thresholds        — static biological thresholds for frontend charts
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

import ai_engine
import influx_query
import notification_service
import thresholds as th
from config import CORS_ORIGINS, INFLUX_TOKEN
from database import get_db, init_db
from decision_log import append_decision
from models import (
    AdaptiveBaseline,
    DecisionLog,
    Notification,
    SensorSummary,
    WaterQualityEvent,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tilapia_api")

_influx: InfluxDBClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _influx
    init_db()
    log.info("PostgreSQL tables created / verified.")

    if not INFLUX_TOKEN:
        log.warning("INFLUX_TOKEN not set — InfluxDB endpoints will fail.")
        _influx = None
    else:
        _influx = influx_query.get_client()
    yield
    if _influx is not None:
        _influx.close()
        _influx = None


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


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Static thresholds (for frontend reference bands)
# ---------------------------------------------------------------------------

@app.get("/api/thresholds")
def get_thresholds() -> dict[str, Any]:
    """Return biological threshold ranges so the frontend can draw reference bands."""
    out = {}
    for name, r in th.ALL.items():
        out[name] = {
            "ideal_low": r.ideal_low,
            "ideal_high": r.ideal_high,
            "warn_low": r.warn_low,
            "warn_high": r.warn_high,
            "danger_low": r.danger_low,
            "danger_high": r.danger_high,
            "unit": r.unit,
        }
    return out


# ---------------------------------------------------------------------------
# Latest reading
# ---------------------------------------------------------------------------

@app.get("/api/latest")
def api_latest(db: Session = Depends(get_db)) -> dict[str, Any]:
    if _influx is None:
        raise HTTPException(status_code=503, detail="InfluxDB not configured")

    try:
        row = influx_query.query_latest(_influx)
    except Exception as e:
        log.exception("Influx latest query failed")
        raise HTTPException(status_code=503, detail=f"influx_error: {e!s}") from e

    if not row:
        return {
            "time": None, "suhu": None, "ph": None, "tds": None,
            "suhu_zone": "unknown", "ph_zone": "unknown", "tds_zone": "unknown",
            "water_quality_status": "Normal",
            "ai_status": "OK", "prediction_status": "OK",
            "predicted_ph": None, "predicted_tds": None, "predicted_suhu": None,
            "horizon_minutes": 15, "confidence": 0,
            "recommendation": "Tidak ada data sensor.",
            "action_required": False, "data_stale": True,
            "anomalies": [],
        }

    suhu = _float_or_none(row.get("suhu"))
    ph = _float_or_none(row.get("ph"))
    tds = _float_or_none(row.get("tds"))
    wq = ai_engine.water_quality_status(suhu, ph, tds)

    try:
        recent_rows = influx_query.query_recent_pivoted(_influx, limit=60)
        adaptive = ai_engine.compute_adaptive_thresholds(recent_rows)
        pred = ai_engine.predict_status(recent_rows, adaptive)
    except Exception as e:
        log.warning("AI prediction fallback: %s", e)
        adaptive = ai_engine.AdaptiveThresholds()
        pred = ai_engine.PredictionResult(
            ai_status="OK", predicted_ph=None, predicted_tds=None,
            predicted_suhu=None, horizon_minutes=15, confidence=0.0,
            reason=f"prediction_error:{e!s}",
        )

    rec = ai_engine.recommendation(pred.ai_status, wq)
    action_required = wq in ("Danger", "Critical") or pred.ai_status == "WARNING_CHANGE_WATER"

    notification_service.process_status(
        db,
        status=wq,
        suhu=suhu, ph=ph, tds=tds,
        ai_status=pred.ai_status,
        predicted_ph=pred.predicted_ph,
        predicted_tds=pred.predicted_tds,
        predicted_suhu=pred.predicted_suhu,
    )

    if action_required:
        try:
            append_decision(
                db, suhu=suhu, ph=ph, tds=tds,
                predicted_ph=pred.predicted_ph,
                predicted_tds=pred.predicted_tds,
                predicted_suhu=pred.predicted_suhu,
                water_quality=wq,
                ai_status=pred.ai_status,
                reason=pred.reason,
                recommendation=rec,
            )
        except Exception as e:
            log.error("Could not write decision log: %s", e)

    return {
        "time": row.get("time"),
        "suhu": suhu, "ph": ph, "tds": tds,
        "suhu_zone": th.zone_for_value("suhu", suhu),
        "ph_zone": th.zone_for_value("ph", ph),
        "tds_zone": th.zone_for_value("tds", tds),
        "water_quality_status": wq,
        "ai_status": pred.ai_status,
        "prediction_status": pred.ai_status,
        "predicted_ph": pred.predicted_ph,
        "predicted_tds": pred.predicted_tds,
        "predicted_suhu": pred.predicted_suhu,
        "horizon_minutes": pred.horizon_minutes,
        "confidence": pred.confidence,
        "prediction_reason": pred.reason,
        "recommendation": rec,
        "action_required": action_required,
        "data_stale": False,
        "anomalies": pred.anomalies,
        "adaptive": {
            "ph_mean": adaptive.ph_mean,
            "ph_adaptive_low": adaptive.ph_adaptive_low,
            "ph_adaptive_high": adaptive.ph_adaptive_high,
            "tds_mean": adaptive.tds_mean,
            "tds_adaptive_low": adaptive.tds_adaptive_low,
            "tds_adaptive_high": adaptive.tds_adaptive_high,
            "suhu_mean": adaptive.suhu_mean,
            "suhu_adaptive_low": adaptive.suhu_adaptive_low,
            "suhu_adaptive_high": adaptive.suhu_adaptive_high,
            "sample_count": adaptive.sample_count,
        },
    }


# ---------------------------------------------------------------------------
# History (InfluxDB time-series)
# ---------------------------------------------------------------------------

@app.get("/api/history")
def api_history() -> dict[str, Any]:
    if _influx is None:
        raise HTTPException(status_code=503, detail="InfluxDB not configured")
    try:
        series = influx_query.query_history_24h(_influx)
    except Exception as e:
        log.exception("Influx history query failed")
        raise HTTPException(status_code=503, detail=f"influx_error: {e!s}") from e
    return {"points": series, "count": len(series)}


# ---------------------------------------------------------------------------
# Notifications (PostgreSQL)
# ---------------------------------------------------------------------------

@app.get("/api/notifications")
def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    q = db.query(Notification).order_by(desc(Notification.created_at))
    if unread_only:
        q = q.filter(Notification.is_read == False)  # noqa: E712
    rows = q.limit(limit).all()
    return {
        "notifications": [
            {
                "id": n.id,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "severity": n.severity,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "category": n.category,
            }
            for n in rows
        ],
        "count": len(rows),
    }


@app.get("/api/notifications/unread-count")
def unread_count(db: Session = Depends(get_db)) -> dict[str, int]:
    cnt = db.query(func.count(Notification.id)).filter(Notification.is_read == False).scalar()  # noqa: E712
    return {"unread": cnt or 0}


@app.patch("/api/notifications/{notif_id}/read")
def mark_read(notif_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    n = db.query(Notification).filter(Notification.id == notif_id).first()
    if not n:
        raise HTTPException(404, "Notification not found")
    n.is_read = True
    db.commit()
    return {"status": "ok"}


@app.patch("/api/notifications/read-all")
def mark_all_read(db: Session = Depends(get_db)) -> dict[str, int]:
    updated = (
        db.query(Notification)
        .filter(Notification.is_read == False)  # noqa: E712
        .update({Notification.is_read: True})
    )
    db.commit()
    return {"marked": updated}


# ---------------------------------------------------------------------------
# Events timeline (PostgreSQL)
# ---------------------------------------------------------------------------

@app.get("/api/events")
def list_events(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        db.query(WaterQualityEvent)
        .order_by(desc(WaterQualityEvent.timestamp))
        .limit(limit)
        .all()
    )
    return {
        "events": [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "prev_status": e.prev_status,
                "new_status": e.new_status,
                "suhu": e.suhu,
                "ph": e.ph,
                "tds": e.tds,
                "trigger_param": e.trigger_param,
                "detail": e.detail,
            }
            for e in rows
        ],
        "count": len(rows),
    }


# ---------------------------------------------------------------------------
# Analytics (PostgreSQL aggregates)
# ---------------------------------------------------------------------------

@app.get("/api/analytics/summary")
def analytics_summary(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (
        db.query(SensorSummary)
        .filter(SensorSummary.hour_bucket >= cutoff)
        .order_by(SensorSummary.hour_bucket)
        .all()
    )
    return {
        "summaries": [
            {
                "hour": s.hour_bucket.isoformat() if s.hour_bucket else None,
                "avg_suhu": s.avg_suhu, "min_suhu": s.min_suhu, "max_suhu": s.max_suhu,
                "avg_ph": s.avg_ph, "min_ph": s.min_ph, "max_ph": s.max_ph,
                "avg_tds": s.avg_tds, "min_tds": s.min_tds, "max_tds": s.max_tds,
                "sample_count": s.sample_count,
            }
            for s in rows
        ],
        "count": len(rows),
    }


@app.get("/api/analytics/baseline")
def analytics_baseline() -> dict[str, Any]:
    if _influx is None:
        raise HTTPException(status_code=503, detail="InfluxDB not configured")
    try:
        recent = influx_query.query_recent_pivoted(_influx, limit=120)
        a = ai_engine.compute_adaptive_thresholds(recent)
    except Exception as e:
        log.warning("Baseline computation failed: %s", e)
        a = ai_engine.AdaptiveThresholds()
    return {
        "ph": {"mean": a.ph_mean, "std": a.ph_std, "adaptive_low": a.ph_adaptive_low, "adaptive_high": a.ph_adaptive_high},
        "tds": {"mean": a.tds_mean, "std": a.tds_std, "adaptive_low": a.tds_adaptive_low, "adaptive_high": a.tds_adaptive_high},
        "suhu": {"mean": a.suhu_mean, "std": a.suhu_std, "adaptive_low": a.suhu_adaptive_low, "adaptive_high": a.suhu_adaptive_high},
        "sample_count": a.sample_count,
        "method": "adaptive_baseline_v1",
    }


# ---------------------------------------------------------------------------
# Decision logs (PostgreSQL — for thesis Bab 4)
# ---------------------------------------------------------------------------

@app.get("/api/decisions")
def list_decisions(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        db.query(DecisionLog)
        .order_by(desc(DecisionLog.timestamp))
        .limit(limit)
        .all()
    )
    return {
        "decisions": [
            {
                "id": d.id,
                "timestamp": d.timestamp.isoformat() if d.timestamp else None,
                "suhu": d.suhu, "ph": d.ph, "tds": d.tds,
                "predicted_ph": d.predicted_ph,
                "predicted_tds": d.predicted_tds,
                "predicted_suhu": d.predicted_suhu,
                "water_quality": d.water_quality,
                "ai_status": d.ai_status,
                "reason": d.reason,
                "recommendation": d.recommendation,
            }
            for d in rows
        ],
        "count": len(rows),
    }
