"""Create a tiny fictional CSV only for a safe manual walkthrough."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd


def main() -> None:
    """Write 180 deterministic fictional completed services to the requested path."""
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    path = parser.parse_args().path
    start = datetime(2025, 1, 1, tzinfo=UTC)
    rows = []
    for index in range(180):
        departure = start + timedelta(hours=index * 3)
        duration = 126 if index % 2 else 133
        delay = 14 if index % 5 in {0, 1} else 2
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
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


if __name__ == "__main__":
    main()
