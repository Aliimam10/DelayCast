"""Focused checks for the chronological CatBoost training boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
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


def test_training_uses_chronological_split_and_writes_calibration(tmp_path) -> None:
    """Train the one model and retain its chronological evaluation evidence."""
    history, artifact = (
        tmp_path / "history.csv",
        tmp_path / "artifacts" / "artifact.joblib",
    )
    _history(str(history))
    model = train(history, artifact)
    assert model.report["split"] == {"train": 125, "validation": 28, "test": 27}
    assert set(model.report) == {
        "split",
        "historical_route_rate",
        "calibrated_catboost",
    }
    assert artifact.exists()
    assert (tmp_path / "artifacts" / "calibration.png").exists()
