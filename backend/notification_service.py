"""Create and deduplicate in-app notifications + water-quality events."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models import Notification, WaterQualityEvent

log = logging.getLogger("tilapia_api")

_DEDUP_MINUTES = 30
_last_status: str | None = None


def _severity_from_status(status: str) -> str:
    return {
        "Critical": "critical",
        "Danger": "danger",
        "Warning": "warning",
    }.get(status, "info")


def _recent_duplicate(db: Session, title: str, minutes: int = _DEDUP_MINUTES) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return (
        db.query(Notification)
        .filter(Notification.title == title, Notification.created_at >= cutoff)
        .first()
        is not None
    )


def _build_messages(
    status: str,
    suhu: float | None,
    ph: float | None,
    tds: float | None,
    ai_status: str,
    predicted_ph: float | None,
    predicted_tds: float | None,
    predicted_suhu: float | None,
) -> list[tuple[str, str, str]]:
    """Return list of (title, message, category) tuples."""
    msgs: list[tuple[str, str, str]] = []

    if status == "Critical":
        msgs.append((
            "CRITICAL: Air di luar batas toleransi",
            f"Parameter kritis — Suhu: {suhu}, pH: {ph}, TDS: {tds}. Ganti air segera!",
            "water_quality",
        ))
    elif status == "Danger":
        parts = []
        if ph is not None and (ph < 6.5 or ph > 8.5):
            parts.append(f"pH {ph:.2f} di luar rentang ideal (6.5–8.5)")
        if tds is not None and tds > 500:
            parts.append(f"TDS {tds:.0f} ppm melebihi batas aman (500)")
        if suhu is not None and (suhu < 22 or suhu > 33):
            parts.append(f"Suhu {suhu:.1f}°C di luar rentang aman (22–33)")
        detail = "; ".join(parts) if parts else "Parameter di zona bahaya."
        msgs.append(("DANGER: Kualitas air buruk", detail, "water_quality"))

    elif status == "Warning":
        parts = []
        if ph is not None and (ph < 7.0 or ph > 8.0):
            parts.append(f"pH {ph:.2f} mendekati batas")
        if tds is not None and tds > 400:
            parts.append(f"TDS {tds:.0f} ppm mendekati batas")
        if suhu is not None and (suhu < 26 or suhu > 30):
            parts.append(f"Suhu {suhu:.1f}°C di luar rentang ideal")
        detail = "; ".join(parts) if parts else "Beberapa parameter mendekati batas."
        msgs.append(("WARNING: Parameter mendekati batas", detail, "water_quality"))

    if ai_status == "WARNING_CHANGE_WATER":
        pred_parts = []
        if predicted_ph is not None:
            pred_parts.append(f"pH→{predicted_ph:.2f}")
        if predicted_tds is not None:
            pred_parts.append(f"TDS→{predicted_tds:.0f}")
        if predicted_suhu is not None:
            pred_parts.append(f"Suhu→{predicted_suhu:.1f}")
        msgs.append((
            "PREDIKSI: Air akan memburuk",
            f"Dalam 15 menit, diprediksi: {', '.join(pred_parts)}. Siapkan pergantian air.",
            "prediction",
        ))

    return msgs


def process_status(
    db: Session,
    *,
    status: str,
    suhu: float | None,
    ph: float | None,
    tds: float | None,
    ai_status: str,
    predicted_ph: float | None = None,
    predicted_tds: float | None = None,
    predicted_suhu: float | None = None,
) -> list[int]:
    """Create notifications + event rows.  Returns list of new notification IDs."""
    global _last_status

    if status != _last_status and status != "Normal":
        trigger = None
        if ph is not None and (ph < 6.5 or ph > 8.5):
            trigger = "ph"
        elif tds is not None and tds > 500:
            trigger = "tds"
        elif suhu is not None and (suhu < 22 or suhu > 33):
            trigger = "suhu"

        event = WaterQualityEvent(
            prev_status=_last_status,
            new_status=status,
            suhu=suhu,
            ph=ph,
            tds=tds,
            trigger_param=trigger,
        )
        db.add(event)

    _last_status = status

    if status == "Normal" and ai_status == "OK":
        db.commit()
        return []

    msgs = _build_messages(status, suhu, ph, tds, ai_status, predicted_ph, predicted_tds, predicted_suhu)
    created_ids: list[int] = []
    for title, message, category in msgs:
        if _recent_duplicate(db, title):
            continue
        notif = Notification(
            severity=_severity_from_status(status),
            title=title,
            message=message,
            category=category,
        )
        db.add(notif)
        db.flush()
        created_ids.append(notif.id)

    db.commit()
    return created_ids
