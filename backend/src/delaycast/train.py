"""Command-line training entry point kept small enough for a portfolio walkthrough."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from delaycast.model import train


def main() -> None:
    """Train from one normalised HSP export and print the held-out report."""
    parser = argparse.ArgumentParser()
    parser.add_argument("history", type=Path, help="normalised National Rail CSV")
    parser.add_argument(
        "--artifact", type=Path, default=Path("../artifacts/delaycast.joblib")
    )
    arguments = parser.parse_args()
    model = train(arguments.history, arguments.artifact)
    print(json.dumps(model.report, indent=2))
    print(f"Saved model and calibration.png under {arguments.artifact.parent}")


if __name__ == "__main__":
    main()
