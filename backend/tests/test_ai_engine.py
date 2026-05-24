"""Unit tests for the adaptive AI engine (no live Influx / Postgres)."""

from datetime import datetime, timedelta, timezone

import ai_engine
import thresholds


def test_water_quality_danger_ph_low():
    assert ai_engine.water_quality_status(30.0, 5.5, 100.0) == "Danger"


def test_water_quality_danger_tds():
    assert ai_engine.water_quality_status(30.0, 7.0, 600.0) == "Danger"


def test_water_quality_critical_ph():
    assert ai_engine.water_quality_status(30.0, 4.0, 200.0) == "Critical"


def test_water_quality_critical_suhu():
    assert ai_engine.water_quality_status(18.0, 7.0, 200.0) == "Critical"


def test_water_quality_warning_suhu():
    assert ai_engine.water_quality_status(23.0, 7.5, 200.0) == "Warning"


def test_water_quality_normal():
    assert ai_engine.water_quality_status(28.0, 7.2, 200.0) == "Normal"


def test_predict_status_insufficient_points():
    assert ai_engine.predict_status([]).reason == "insufficient_points"


def test_predict_status_trajectory_ok():
    now = datetime.now(timezone.utc)
    rows = [
        {"_time": now - timedelta(minutes=10), "ph": 7.0, "tds": 200.0, "suhu": 28.0},
        {"_time": now - timedelta(minutes=5), "ph": 7.1, "tds": 210.0, "suhu": 28.1},
        {"_time": now, "ph": 7.2, "tds": 220.0, "suhu": 28.2},
    ]
    result = ai_engine.predict_status(rows)
    assert result.ai_status == "OK"
    assert result.predicted_ph is not None
    assert result.confidence > 0


def test_compute_adaptive_thresholds():
    rows = [
        {"ph": 7.0, "tds": 250, "suhu": 28.0},
        {"ph": 7.2, "tds": 260, "suhu": 28.5},
        {"ph": 7.1, "tds": 240, "suhu": 27.8},
    ]
    a = ai_engine.compute_adaptive_thresholds(rows)
    assert a.sample_count == 3
    assert 6.5 <= a.ph_adaptive_low <= 7.5
    assert a.tds_adaptive_high <= 400


def test_recommendation_critical():
    rec = ai_engine.recommendation("OK", "Critical")
    assert "EMERGENCY" in rec


def test_recommendation_change():
    rec = ai_engine.recommendation("WARNING_CHANGE_WATER", "Normal")
    assert "30%" in rec


def test_recommendation_calm():
    assert "ideal" in ai_engine.recommendation("OK", "Normal").lower()


def test_zone_for_value():
    assert thresholds.zone_for_value("ph", 7.5) == "ideal"
    assert thresholds.zone_for_value("ph", 6.2) == "warning"
    assert thresholds.zone_for_value("ph", 5.5) == "danger"
    assert thresholds.zone_for_value("ph", 4.0) == "critical"
    assert thresholds.zone_for_value("tds", 250) == "ideal"
    assert thresholds.zone_for_value("suhu", 28) == "ideal"
    assert thresholds.zone_for_value("suhu", 36) == "critical"
