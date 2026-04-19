"""
Placeholder for LSTM inference; uses linear trend extrapolation for 15-minute horizon.

Replace predict_status() body with model.load + model.predict when .h5/.pkl is ready.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

AiStatus = Literal["OK", "WARNING_CHANGE_WATER"]


@dataclass
class PredictionResult:
    ai_status: AiStatus
    predicted_ph: float | None
    predicted_tds: float | None
    horizon_minutes: int
    reason: str


def _linear_forecast(
    times: list[datetime], values: list[float], ahead_seconds: float
) -> float | None:
    if len(values) < 2 or len(times) < 2:
        return values[-1] if values else None
    t0 = times[0].timestamp()
    t1 = times[-1].timestamp()
    span = max(t1 - t0, 1e-6)
    slope = (values[-1] - values[0]) / span
    last_t = times[-1].timestamp()
    return values[-1] + slope * ahead_seconds


def _danger_zone(
    ph: float, tds: float
) -> tuple[bool, str]:
    if ph < 6.5 or ph > 8.5:
        return True, "pH outside safe range"
    if tds > 500:
        return True, "TDS above threshold"
    return False, ""


def predict_status(rows: list[dict[str, Any]]) -> PredictionResult:
    """
    rows: pivoted Influx records (newest first or mixed — we sort by time asc).
    Placeholder until LSTM: extrapolate ph/tds 15 minutes ahead; warn if trajectory
    crosses danger thresholds.
    """
    horizon_min = 15
    ahead = horizon_min * 60.0

    parsed: list[tuple[datetime, float, float]] = []
    for r in rows:
        t_raw = r.get("_time")
        if isinstance(t_raw, datetime):
            t = t_raw if t_raw.tzinfo else t_raw.replace(tzinfo=timezone.utc)
        else:
            continue
        ph = r.get("ph")
        tds = r.get("tds")
        if ph is None or tds is None:
            continue
        try:
            parsed.append((t, float(ph), float(tds)))
        except (TypeError, ValueError):
            continue

    parsed.sort(key=lambda x: x[0])
    if len(parsed) < 2:
        return PredictionResult(
            ai_status="OK",
            predicted_ph=None,
            predicted_tds=None,
            horizon_minutes=horizon_min,
            reason="insufficient_points",
        )

    times = [p[0] for p in parsed]
    phs = [p[1] for p in parsed]
    tdss = [p[2] for p in parsed]

    pred_ph = _linear_forecast(times, phs, ahead)
    pred_tds = _linear_forecast(times, tdss, ahead)

    if pred_ph is None or pred_tds is None:
        return PredictionResult(
            ai_status="OK",
            predicted_ph=pred_ph,
            predicted_tds=pred_tds,
            horizon_minutes=horizon_min,
            reason="forecast_failed",
        )

    last_ph, last_tds = phs[-1], tdss[-1]
    cur_danger, _ = _danger_zone(last_ph, last_tds)
    pred_danger, pred_reason = _danger_zone(pred_ph, pred_tds)

    if not cur_danger and pred_danger:
        return PredictionResult(
            ai_status="WARNING_CHANGE_WATER",
            predicted_ph=pred_ph,
            predicted_tds=pred_tds,
            horizon_minutes=horizon_min,
            reason=f"trajectory_to_danger:{pred_reason}",
        )

    return PredictionResult(
        ai_status="OK",
        predicted_ph=pred_ph,
        predicted_tds=pred_tds,
        horizon_minutes=horizon_min,
        reason="trajectory_ok",
    )


def water_quality_status(suhu: float | None, ph: float | None, tds: float | None) -> str:
    """Current snapshot classification (not prediction)."""
    if ph is None or tds is None:
        return "Normal"
    try:
        phf = float(ph)
        tdsf = float(tds)
    except (TypeError, ValueError):
        return "Normal"
    if phf < 6.5 or phf > 8.5 or tdsf > 500:
        return "Danger"
    if tdsf > 400 or phf < 7.0 or phf > 8.0:
        return "Warning"
    return "Normal"


def recommendation(ai_status: AiStatus, wq: str) -> str:
    if wq == "Danger" or ai_status == "WARNING_CHANGE_WATER":
        return "Change 30% of water now"
    return "Stay Calm"
