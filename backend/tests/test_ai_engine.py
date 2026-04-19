"""Unit tests for rule engine and trend placeholder (no live Influx)."""

from datetime import datetime, timezone

import ai_engine


def test_water_quality_danger_ph_low():
    assert ai_engine.water_quality_status(30.0, 6.0, 100.0) == "Danger"


def test_water_quality_danger_tds():
    assert ai_engine.water_quality_status(30.0, 7.0, 600.0) == "Danger"


def test_water_quality_normal():
    assert ai_engine.water_quality_status(30.0, 7.2, 200.0) == "Normal"


def test_predict_status_insufficient_points():
    assert ai_engine.predict_status([]).reason == "insufficient_points"
    one = [
        {
            "_time": datetime.now(timezone.utc),
            "ph": 7.0,
            "tds": 100.0,
        }
    ]
    assert ai_engine.predict_status(one).reason == "insufficient_points"


def test_recommendation_change():
    assert "Change" in ai_engine.recommendation("WARNING_CHANGE_WATER", "Normal")


def test_recommendation_stay():
    assert ai_engine.recommendation("OK", "Normal") == "Stay Calm"
