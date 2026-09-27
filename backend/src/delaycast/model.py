"""Training, chronological evaluation, and inference kept deliberately compact."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import joblib
import matplotlib.pyplot as plt
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    brier_score_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

from delaycast.contracts import Journey, Score

FEATURES = [
    "origin",
    "destination",
    "operator",
    "departure_hour",
    "weekday",
    "month",
    "scheduled_duration_minutes",
    "route_late_rate",
    "operator_late_rate",
]
CATEGORICAL = ["origin", "destination", "operator"]
REQUIRED_COLUMNS = {
    "scheduled_departure",
    "scheduled_arrival",
    "actual_arrival",
    "origin",
    "destination",
    "operator",
    "cancelled",
}


class DatasetError(ValueError):
    """A clear failure for a data file that cannot support the portfolio model."""


@dataclass
class DelayModel:
    """Everything needed for local API inference, stored as one joblib file."""

    classifier: CatBoostClassifier
    calibrator: IsotonicRegression
    route_rates: dict[str, float]
    operator_rates: dict[str, float]
    default_rate: float
    cutoff: str
    route_hours: dict[str, list[int]]
    importances: list[str]
    report: dict[str, Any]

    def score(self, journey: Journey) -> Score:
        """Return the calibrated chance of an arrival at least 10 minutes late."""
        row = _inference_row(journey, self.route_rates, self.operator_rates)
        raw = self.classifier.predict_proba(pd.DataFrame([row])[FEATURES])[0][1]
        probability = float(self.calibrator.predict([raw])[0])
        return Score(
            probability=round(probability, 3),
            risk="High"
            if probability >= 0.6
            else "Moderate"
            if probability >= 0.3
            else "Low",
            factors=_factor_text(journey, row, self.importances),
            data_cutoff=self.cutoff,
        )


def load_history(path: Path) -> pd.DataFrame:
    """Load a small normalised export of completed National Rail services.

    The raw HSP response varies by subscription. Keep its parsing out of the ML
    story: export these seven documented columns once, then this project stays
    easy to inspect and rerun.
    """
    frame = pd.read_csv(path)
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise DatasetError(f"missing required columns: {', '.join(sorted(missing))}")
    for column in ("scheduled_departure", "scheduled_arrival", "actual_arrival"):
        frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
    frame["cancelled"] = frame["cancelled"].astype(str).str.lower().eq("true")
    frame = frame.dropna(
        subset=["scheduled_departure", "scheduled_arrival", "actual_arrival"]
    )
    frame = frame[~frame["cancelled"]].copy()
    frame["origin"] = frame["origin"].str.upper()
    frame["destination"] = frame["destination"].str.upper()
    frame["operator"] = frame["operator"].astype(str)
    frame["scheduled_duration_minutes"] = (
        (frame["scheduled_arrival"] - frame["scheduled_departure"]).dt.total_seconds()
        / 60
    ).round()
    frame = frame[frame["scheduled_duration_minutes"].between(1, 600)].copy()
    frame["late"] = (
        (frame["actual_arrival"] - frame["scheduled_arrival"]).dt.total_seconds() >= 600
    ).astype(int)
    if len(frame) < 100 or frame["late"].nunique() < 2:
        raise DatasetError(
            "need at least 100 completed services with both target classes"
        )
    return frame.sort_values("scheduled_departure").reset_index(drop=True)


def feature_frame(history: pd.DataFrame) -> pd.DataFrame:
    """Build only features that would have been known by each departure time."""
    frame = history.copy()
    local = frame["scheduled_departure"].dt.tz_convert("Europe/London")
    frame["departure_hour"] = local.dt.hour
    frame["weekday"] = local.dt.weekday
    frame["month"] = local.dt.month
    frame["route_key"] = frame["origin"] + "-" + frame["destination"]
    route_history: dict[str, list[int]] = {}
    operator_history: dict[str, list[int]] = {}
    route_rates: list[float | None] = []
    operator_rates: list[float | None] = []
    arrivals = frame.sort_values("actual_arrival").itertuples()
    next_arrival = next(arrivals, None)
    for row in frame.itertuples():
        while next_arrival and next_arrival.actual_arrival <= row.scheduled_departure:
            completed_route = f"{next_arrival.origin}-{next_arrival.destination}"
            route_history.setdefault(completed_route, []).append(next_arrival.late)
            operator_history.setdefault(next_arrival.operator, []).append(
                next_arrival.late
            )
            next_arrival = next(arrivals, None)
        route_values = route_history.get(row.route_key, [])[-30:]
        operator_values = operator_history.get(row.operator, [])[-60:]
        route_rates.append(
            sum(route_values) / len(route_values) if route_values else None
        )
        operator_rates.append(
            sum(operator_values) / len(operator_values) if operator_values else None
        )
    frame["route_late_rate"] = route_rates
    frame["operator_late_rate"] = operator_rates
    return frame


def _metrics(
    target: pd.Series, probability: list[float] | pd.Series
) -> dict[str, float]:
    predicted = pd.Series(probability).ge(0.5)
    return {
        "roc_auc": round(float(roc_auc_score(target, probability)), 3),
        "precision": round(
            float(precision_score(target, predicted, zero_division=0)), 3
        ),
        "recall": round(float(recall_score(target, predicted, zero_division=0)), 3),
        "brier_score": round(float(brier_score_loss(target, probability)), 3),
    }


def train(history_path: Path, artifact_path: Path) -> DelayModel:
    """Train 70/15/15 in time order and save a small local model artifact."""
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    frame = feature_frame(load_history(history_path))
    train_end, validation_end = int(len(frame) * 0.7), int(len(frame) * 0.85)
    training, validation, testing = (
        frame.iloc[:train_end],
        frame.iloc[train_end:validation_end],
        frame.iloc[validation_end:],
    )
    if any(
        partition["late"].nunique() < 2 for partition in (training, validation, testing)
    ):
        raise DatasetError(
            "each chronological split needs delayed and non-delayed services"
        )
    classifier = CatBoostClassifier(
        iterations=300,
        depth=6,
        learning_rate=0.05,
        loss_function="Logloss",
        verbose=False,
        random_seed=42,
        allow_writing_files=False,
    )
    classifier.fit(training[FEATURES], training["late"], cat_features=CATEGORICAL)
    validation_raw = classifier.predict_proba(validation[FEATURES])[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip").fit(
        validation_raw, validation["late"]
    )
    test_probability = calibrator.predict(
        classifier.predict_proba(testing[FEATURES])[:, 1]
    )
    default_rate = float(training["late"].mean())
    baseline = testing["route_late_rate"].fillna(default_rate)
    report = {
        "split": {
            "train": len(training),
            "validation": len(validation),
            "test": len(testing),
        },
        "historical_route_rate": _metrics(testing["late"], baseline),
        "calibrated_catboost": _metrics(testing["late"], test_probability),
    }
    _save_calibration_plot(testing["late"], test_probability, artifact_path.parent)
    reference = frame.iloc[:validation_end]
    route_rates = reference.groupby("route_key")["late"].mean().to_dict()
    operator_rates = reference.groupby("operator")["late"].mean().to_dict()
    route_hours = {
        route: sorted(values.astype(int).unique().tolist())
        for route, values in reference.groupby("route_key")["departure_hour"]
    }
    importance = pd.Series(classifier.feature_importances_, index=FEATURES)
    model = DelayModel(
        classifier=classifier,
        calibrator=calibrator,
        route_rates=route_rates,
        operator_rates=operator_rates,
        default_rate=default_rate,
        cutoff=str(reference["scheduled_departure"].max().date()),
        route_hours=route_hours,
        importances=importance.nlargest(3).index.tolist(),
        report=report,
    )
    joblib.dump(model, artifact_path)
    return model


def load_model(path: Path) -> DelayModel:
    """Load only the locally-created artifact selected by the application config."""
    return joblib.load(path)


def _inference_row(
    journey: Journey, route_rates: dict[str, float], operator_rates: dict[str, float]
) -> dict[str, Any]:
    local = journey.scheduled_departure.astimezone(ZoneInfo("Europe/London"))
    route = f"{journey.origin}-{journey.destination}"
    return {
        "origin": journey.origin,
        "destination": journey.destination,
        "operator": journey.operator,
        "departure_hour": local.hour,
        "weekday": local.weekday(),
        "month": local.month,
        "scheduled_duration_minutes": journey.scheduled_duration_minutes,
        "route_late_rate": route_rates.get(route),
        "operator_late_rate": operator_rates.get(journey.operator),
    }


def _factor_text(
    journey: Journey, row: dict[str, Any], importances: list[str]
) -> list[str]:
    labels = {
        "route_late_rate": (
            f"historical {journey.origin}-{journey.destination} reliability"
        ),
        "operator_late_rate": f"historical {journey.operator} reliability",
        "departure_hour": f"scheduled {row['departure_hour']:02d}:00 departure",
        "weekday": "weekday travel pattern",
        "month": "seasonal month pattern",
        "scheduled_duration_minutes": "scheduled journey duration",
        "origin": "origin station pattern",
        "destination": "destination station pattern",
        "operator": "operator pattern",
    }
    return [labels[item] for item in importances]


def _save_calibration_plot(
    target: pd.Series, probability: list[float], directory: Path
) -> None:
    observed, predicted = calibration_curve(
        target, probability, n_bins=8, strategy="quantile"
    )
    figure, axis = plt.subplots(figsize=(5, 4))
    axis.plot([0, 1], [0, 1], "--", color="grey", label="perfect calibration")
    axis.plot(predicted, observed, "o-", label="CatBoost")
    axis.set(
        xlabel="Mean predicted probability",
        ylabel="Observed late rate",
        title="Test calibration",
    )
    axis.legend()
    figure.tight_layout()
    figure.savefig(directory / "calibration.png", dpi=150)
    plt.close(figure)
