"""Persist AI/rule-engine decisions to PostgreSQL (replaces CSV)."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from models import DecisionLog

log = logging.getLogger("tilapia_api")


def append_decision(
    db: Session,
    *,
    suhu: float | None,
    ph: float | None,
    tds: float | None,
    predicted_ph: float | None,
    predicted_tds: float | None,
    predicted_suhu: float | None,
    water_quality: str | None,
    ai_status: str | None,
    reason: str,
    recommendation: str | None = None,
) -> None:
    row = DecisionLog(
        suhu=suhu,
        ph=ph,
        tds=tds,
        predicted_ph=predicted_ph,
        predicted_tds=predicted_tds,
        predicted_suhu=predicted_suhu,
        water_quality=water_quality,
        ai_status=ai_status,
        reason=reason,
        recommendation=recommendation,
    )
    db.add(row)
    db.commit()
