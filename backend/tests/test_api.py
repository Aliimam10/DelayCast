"""Focused checks for the local prediction and live-status API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
from fastapi.testclient import TestClient

from delaycast.app import app
from delaycast.model import train


def _history(path: str) -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    rows = []
    for index in range(180):
        departure = start + timedelta(hours=index * 3)
        duration = 100 if index % 2 else 130
        delay = 16 if index % 5 in {0, 1} else 3
        rows.append(
            {
                "scheduled_departure": departure.isoformat(),
                "scheduled_arrival": (
                    departure + timedelta(minutes=duration)
                ).isoformat(),
                "actual_arrival": (
                    departure + timedelta(minutes=duration + delay)
                ).isoformat(),
                "origin": "EUS" if index % 2 else "KGX",
                "destination": "MAN" if index % 2 else "LDS",
                "operator": "Avanti West Coast" if index % 2 else "LNER",
                "cancelled": False,
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def test_api_scores_a_journey_when_a_local_model_exists(tmp_path, monkeypatch) -> None:
    """Serve a bounded score and an offline-safe Darwin response."""
    history, artifact = tmp_path / "history.csv", tmp_path / "artifact.joblib"
    _history(str(history))
    train(history, artifact)
    monkeypatch.setenv("MODEL_PATH", str(artifact))
    monkeypatch.delenv("DARWIN_USERNAME", raising=False)
    monkeypatch.delenv("DARWIN_PASSWORD", raising=False)
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            json={
                "origin": "EUS",
                "destination": "MAN",
                "operator": "Avanti West Coast",
                "scheduled_departure": "2025-01-01T18:20:00+00:00",
                "scheduled_duration_minutes": 126,
            },
        )
        live_response = client.get("/live-status?origin=EUS&destination=MAN")
    assert response.status_code == 200
    assert 0 <= response.json()["score"]["probability"] <= 1
    assert live_response.json()["available"] is False
