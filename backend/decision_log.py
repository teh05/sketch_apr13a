"""Append thesis-oriented decision rows to CSV (Bab 4 analysis)."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from config import DECISION_LOG_CSV, LOGS_DIR


def ensure_log_header(path: Path) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "timestamp_iso",
                "suhu",
                "ph",
                "tds",
                "predicted_ph",
                "predicted_tds",
                "reason",
                "status",
            ]
        )


def append_decision(
    *,
    suhu: float | None,
    ph: float | None,
    tds: float | None,
    predicted_ph: float | None,
    predicted_tds: float | None,
    reason: str,
    status: str,
) -> None:
    ensure_log_header(DECISION_LOG_CSV)
    ts = datetime.now(timezone.utc).isoformat()
    with DECISION_LOG_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            [
                ts,
                suhu,
                ph,
                tds,
                predicted_ph,
                predicted_tds,
                reason,
                status,
            ]
        )
