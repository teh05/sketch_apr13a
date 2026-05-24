"""
Adaptive intelligence engine for tilapia water-quality monitoring.

Features:
  - 4-level status: Normal / Warning / Danger / Critical
  - Temperature (suhu) included in all evaluations
  - Adaptive thresholds from running statistics (simulated ML)
  - Linear-trend prediction for pH, TDS, suhu with confidence score
  - Anomaly detection via z-score
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

import thresholds

AiStatus = Literal["OK", "WARNING_CHANGE_WATER"]


@dataclass
class PredictionResult:
    ai_status: AiStatus
    predicted_ph: float | None
    predicted_tds: float | None
    predicted_suhu: float | None
    horizon_minutes: int
    confidence: float
    reason: str
    anomalies: list[str] = field(default_factory=list)


@dataclass
class AdaptiveThresholds:
    """Computed from recent data — acts as the 'trained model' output."""

    ph_mean: float = 7.0
    ph_std: float = 0.5
    ph_adaptive_low: float = 6.5
    ph_adaptive_high: float = 8.5
    tds_mean: float = 250.0
    tds_std: float = 80.0
    tds_adaptive_low: float = 100.0
    tds_adaptive_high: float = 400.0
    suhu_mean: float = 28.0
    suhu_std: float = 1.5
    suhu_adaptive_low: float = 26.0
    suhu_adaptive_high: float = 30.0
    sample_count: int = 0


def compute_adaptive_thresholds(rows: list[dict[str, Any]]) -> AdaptiveThresholds:
    """Build adaptive thresholds from recent pivoted InfluxDB rows."""
    phs: list[float] = []
    tdss: list[float] = []
    suhus: list[float] = []

    for r in rows:
        try:
            ph = r.get("ph")
            tds = r.get("tds")
            suhu = r.get("suhu")
            if ph is not None:
                phs.append(float(ph))
            if tds is not None:
                tdss.append(float(tds))
            if suhu is not None:
                suhus.append(float(suhu))
        except (TypeError, ValueError):
            continue

    def _stats(vals: list[float]) -> tuple[float, float]:
        if not vals:
            return 0.0, 0.0
        n = len(vals)
        mean = sum(vals) / n
        variance = sum((v - mean) ** 2 for v in vals) / max(n - 1, 1)
        return mean, math.sqrt(variance)

    ph_mean, ph_std = _stats(phs) if phs else (7.0, 0.5)
    tds_mean, tds_std = _stats(tdss) if tdss else (250.0, 80.0)
    suhu_mean, suhu_std = _stats(suhus) if suhus else (28.0, 1.5)

    return AdaptiveThresholds(
        ph_mean=ph_mean,
        ph_std=max(ph_std, 0.1),
        ph_adaptive_low=max(thresholds.PH.ideal_low, ph_mean - 1.5 * max(ph_std, 0.1)),
        ph_adaptive_high=min(thresholds.PH.ideal_high, ph_mean + 1.5 * max(ph_std, 0.1)),
        tds_mean=tds_mean,
        tds_std=max(tds_std, 5.0),
        tds_adaptive_low=max(thresholds.TDS.ideal_low, tds_mean - 1.5 * max(tds_std, 5.0)),
        tds_adaptive_high=min(thresholds.TDS.ideal_high, tds_mean + 1.5 * max(tds_std, 5.0)),
        suhu_mean=suhu_mean,
        suhu_std=max(suhu_std, 0.3),
        suhu_adaptive_low=max(thresholds.SUHU.ideal_low, suhu_mean - 1.5 * max(suhu_std, 0.3)),
        suhu_adaptive_high=min(thresholds.SUHU.ideal_high, suhu_mean + 1.5 * max(suhu_std, 0.3)),
        sample_count=max(len(phs), len(tdss), len(suhus)),
    )


def _linear_forecast(
    times: list[datetime], values: list[float], ahead_seconds: float
) -> float | None:
    if len(values) < 2 or len(times) < 2:
        return values[-1] if values else None
    t0 = times[0].timestamp()
    t1 = times[-1].timestamp()
    span = max(t1 - t0, 1e-6)
    slope = (values[-1] - values[0]) / span
    return values[-1] + slope * ahead_seconds


def _compute_confidence(n_points: int, span_seconds: float) -> float:
    """Heuristic confidence: more points + longer span = higher confidence."""
    point_score = min(n_points / 60.0, 1.0)
    span_score = min(span_seconds / 3600.0, 1.0)
    return round(0.5 * point_score + 0.5 * span_score, 2)


def _z_score(value: float, mean: float, std: float) -> float:
    if std < 1e-9:
        return 0.0
    return abs(value - mean) / std


def _detect_anomalies(
    ph: float | None,
    tds: float | None,
    suhu: float | None,
    adaptive: AdaptiveThresholds,
) -> list[str]:
    anomalies: list[str] = []
    if ph is not None:
        z = _z_score(ph, adaptive.ph_mean, adaptive.ph_std)
        if z > 2.5:
            anomalies.append(f"pH anomaly (z={z:.1f})")
    if tds is not None:
        z = _z_score(tds, adaptive.tds_mean, adaptive.tds_std)
        if z > 2.5:
            anomalies.append(f"TDS anomaly (z={z:.1f})")
    if suhu is not None:
        z = _z_score(suhu, adaptive.suhu_mean, adaptive.suhu_std)
        if z > 2.5:
            anomalies.append(f"Suhu anomaly (z={z:.1f})")
    return anomalies


def predict_status(
    rows: list[dict[str, Any]],
    adaptive: AdaptiveThresholds | None = None,
) -> PredictionResult:
    """
    Extrapolate pH, TDS, suhu 15 minutes ahead.  Flag WARNING_CHANGE_WATER
    if trajectory enters danger zone while currently safe.
    """
    horizon_min = 15
    ahead = horizon_min * 60.0

    parsed: list[tuple[datetime, float, float, float]] = []
    for r in rows:
        t_raw = r.get("_time")
        if isinstance(t_raw, datetime):
            t = t_raw if t_raw.tzinfo else t_raw.replace(tzinfo=timezone.utc)
        else:
            continue
        ph = r.get("ph")
        tds = r.get("tds")
        suhu = r.get("suhu")
        if ph is None or tds is None:
            continue
        try:
            parsed.append((t, float(ph), float(tds), float(suhu) if suhu is not None else 28.0))
        except (TypeError, ValueError):
            continue

    parsed.sort(key=lambda x: x[0])
    if len(parsed) < 2:
        return PredictionResult(
            ai_status="OK",
            predicted_ph=None,
            predicted_tds=None,
            predicted_suhu=None,
            horizon_minutes=horizon_min,
            confidence=0.0,
            reason="insufficient_points",
        )

    times = [p[0] for p in parsed]
    phs = [p[1] for p in parsed]
    tdss = [p[2] for p in parsed]
    suhus = [p[3] for p in parsed]

    span_sec = max((times[-1] - times[0]).total_seconds(), 1e-6)

    pred_ph = _linear_forecast(times, phs, ahead)
    pred_tds = _linear_forecast(times, tdss, ahead)
    pred_suhu = _linear_forecast(times, suhus, ahead)
    confidence = _compute_confidence(len(parsed), span_sec)

    anomalies: list[str] = []
    if adaptive:
        anomalies = _detect_anomalies(phs[-1], tdss[-1], suhus[-1], adaptive)

    if pred_ph is None or pred_tds is None:
        return PredictionResult(
            ai_status="OK",
            predicted_ph=pred_ph,
            predicted_tds=pred_tds,
            predicted_suhu=pred_suhu,
            horizon_minutes=horizon_min,
            confidence=confidence,
            reason="forecast_failed",
            anomalies=anomalies,
        )

    cur_status = thresholds.overall_status(suhus[-1], phs[-1], tdss[-1])
    pred_status = thresholds.overall_status(pred_suhu, pred_ph, pred_tds)

    cur_safe = cur_status in ("Normal", "Warning")
    pred_unsafe = pred_status in ("Danger", "Critical")

    if cur_safe and pred_unsafe:
        reasons = []
        if thresholds.zone_for_value("ph", pred_ph) in ("danger", "critical"):
            reasons.append(f"pH→{pred_ph:.2f}")
        if thresholds.zone_for_value("tds", pred_tds) in ("danger", "critical"):
            reasons.append(f"TDS→{pred_tds:.0f}")
        if pred_suhu and thresholds.zone_for_value("suhu", pred_suhu) in ("danger", "critical"):
            reasons.append(f"Suhu→{pred_suhu:.1f}")
        return PredictionResult(
            ai_status="WARNING_CHANGE_WATER",
            predicted_ph=pred_ph,
            predicted_tds=pred_tds,
            predicted_suhu=pred_suhu,
            horizon_minutes=horizon_min,
            confidence=confidence,
            reason=f"trajectory_to_danger:{','.join(reasons)}",
            anomalies=anomalies,
        )

    return PredictionResult(
        ai_status="OK",
        predicted_ph=pred_ph,
        predicted_tds=pred_tds,
        predicted_suhu=pred_suhu,
        horizon_minutes=horizon_min,
        confidence=confidence,
        reason="trajectory_ok",
        anomalies=anomalies,
    )


def water_quality_status(
    suhu: float | None, ph: float | None, tds: float | None
) -> str:
    """Current snapshot → 4-level classification using biological thresholds."""
    return thresholds.overall_status(suhu, ph, tds)


def recommendation(ai_status: AiStatus, wq: str) -> str:
    if wq == "Critical":
        return "EMERGENCY: Parameter di luar batas toleransi hidup ikan. Ganti air segera dan periksa semua sistem."
    if wq == "Danger" or ai_status == "WARNING_CHANGE_WATER":
        return "Ganti 30% air kolam sekarang. Periksa filter dan sirkulasi."
    if wq == "Warning":
        return "Parameter mendekati batas. Monitor ketat, siapkan air pengganti."
    return "Kondisi air ideal. Tidak perlu tindakan."
