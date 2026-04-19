"""Load settings from environment (docker-compose or .env)."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")

INFLUX_URL = os.environ.get("INFLUX_URL", "http://127.0.0.1:8086")
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN", "").strip()
INFLUX_ORG = os.environ.get("INFLUX_ORG", "S2_Project")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "tilapia_monitoring")
INFLUX_MEASUREMENT = os.environ.get("INFLUX_MEASUREMENT", "tilapia")

CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:8081,http://127.0.0.1:5173,http://127.0.0.1:8081",
).split(",")

LOGS_DIR = Path(__file__).resolve().parent / "logs"
DECISION_LOG_CSV = LOGS_DIR / "decision_logs.csv"
