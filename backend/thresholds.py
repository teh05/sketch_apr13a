"""Tilapia water-quality thresholds aligned with nila (tilapia) biology.

Zones (inner to outer):
  Ideal  → fish thriving, no action needed
  Warning → approaching limits, monitor closely
  Danger → immediate stress, prepare water change
  Critical → outside survival range, emergency action
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParamRange:
    ideal_low: float
    ideal_high: float
    warn_low: float
    warn_high: float
    danger_low: float
    danger_high: float
    unit: str


PH = ParamRange(
    ideal_low=6.5, ideal_high=8.5,
    warn_low=6.0, warn_high=9.0,
    danger_low=5.0, danger_high=9.5,
    unit="",
)

TDS = ParamRange(
    ideal_low=100, ideal_high=400,
    warn_low=50, warn_high=500,
    danger_low=0, danger_high=1000,
    unit="ppm",
)

SUHU = ParamRange(
    ideal_low=26, ideal_high=30,
    warn_low=22, warn_high=33,
    danger_low=20, danger_high=35,
    unit="°C",
)

ALL = {"ph": PH, "tds": TDS, "suhu": SUHU}


def zone_for_value(param: str, value: float | None) -> str:
    """Return 'ideal' | 'warning' | 'danger' | 'critical' | 'unknown'."""
    if value is None:
        return "unknown"
    r = ALL.get(param)
    if r is None:
        return "unknown"
    if r.ideal_low <= value <= r.ideal_high:
        return "ideal"
    if r.warn_low <= value <= r.warn_high:
        return "warning"
    if r.danger_low <= value <= r.danger_high:
        return "danger"
    return "critical"


def overall_status(suhu: float | None, ph: float | None, tds: float | None) -> str:
    """Worst-case zone across all three parameters → status string."""
    zones = [
        zone_for_value("suhu", suhu),
        zone_for_value("ph", ph),
        zone_for_value("tds", tds),
    ]
    severity = {"critical": 4, "danger": 3, "warning": 2, "ideal": 1, "unknown": 0}
    worst = max(zones, key=lambda z: severity.get(z, 0))
    label_map = {
        "critical": "Critical",
        "danger": "Danger",
        "warning": "Warning",
        "ideal": "Normal",
        "unknown": "Normal",
    }
    return label_map[worst]
