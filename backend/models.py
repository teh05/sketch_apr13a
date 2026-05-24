"""SQLAlchemy models for PostgreSQL analytics tables."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SensorSummary(Base):
    """Hourly aggregated sensor readings for long-term analysis."""

    __tablename__ = "sensor_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hour_bucket: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, unique=True)
    avg_suhu: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_suhu: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_suhu: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_tds: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_tds: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_tds: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WaterQualityEvent(Base):
    """Recorded whenever the water-quality status transitions (e.g. Normal→Warning)."""

    __tablename__ = "water_quality_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    prev_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30))
    suhu: Mapped[float | None] = mapped_column(Float, nullable=True)
    ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    tds: Mapped[float | None] = mapped_column(Float, nullable=True)
    trigger_param: Mapped[str | None] = mapped_column(String(20), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class Notification(Base):
    """In-app notifications displayed in the frontend bell icon."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="info")  # info | warning | danger | critical
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str] = mapped_column(String(30), default="water_quality")


class DecisionLog(Base):
    """AI/rule-engine decisions persisted for thesis analysis (replaces CSV)."""

    __tablename__ = "decision_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    suhu: Mapped[float | None] = mapped_column(Float, nullable=True)
    ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    tds: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_tds: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_suhu: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_quality: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ai_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)


class AdaptiveBaseline(Base):
    """Computed adaptive thresholds from recent data (simulated ML)."""

    __tablename__ = "adaptive_baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    param_name: Mapped[str] = mapped_column(String(20))  # ph | tds | suhu
    mean_val: Mapped[float] = mapped_column(Float)
    std_val: Mapped[float] = mapped_column(Float)
    adaptive_low: Mapped[float] = mapped_column(Float)
    adaptive_high: Mapped[float] = mapped_column(Float)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
