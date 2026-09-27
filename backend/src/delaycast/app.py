"""Minimal FastAPI edge: one prediction endpoint and one live-status endpoint."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from delaycast.contracts import (
    AlternativeScore,
    Journey,
    LiveStatus,
    PredictionResponse,
)
from delaycast.darwin import status
from delaycast.model import DelayModel, load_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load a local artifact once; training remains an explicit CLI action."""
    path = Path(os.getenv("MODEL_PATH", "../artifacts/delaycast.joblib"))
    app.state.model = load_model(path) if path.exists() else None
    yield


app = FastAPI(title="DelayCast", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _model() -> DelayModel:
    model = app.state.model
    if model is None:
        raise HTTPException(
            status_code=503, detail="Train the local model before predicting."
        )
    return model


@app.get("/health")
def health() -> dict[str, bool]:
    """Tell the frontend whether inference is ready."""
    return {"model_ready": app.state.model is not None}


@app.get("/options")
def options() -> list[dict[str, object]]:
    """Expose trained route choices without adding a database or timetable service."""
    model = _model()
    return [
        {
            "origin": route.split("-")[0],
            "destination": route.split("-")[1],
            "hours": hours,
        }
        for route, hours in model.route_hours.items()
    ]


@app.post("/predict", response_model=PredictionResponse)
def predict(journey: Journey) -> PredictionResponse:
    """Score a direct service and two nearby timetable-pattern alternatives."""
    model = _model()
    score = model.score(journey)
    route_hours = model.route_hours.get(f"{journey.origin}-{journey.destination}", [])
    current_hour = journey.scheduled_departure.astimezone(
        ZoneInfo("Europe/London")
    ).hour
    future_hours = [hour for hour in route_hours if hour > current_hour][:2]
    alternatives = [
        AlternativeScore(
            scheduled_departure=journey.scheduled_departure.replace(
                hour=hour
            ).isoformat(),
            score=model.score(
                journey.model_copy(
                    update={
                        "scheduled_departure": journey.scheduled_departure.replace(
                            hour=hour
                        )
                    }
                )
            ),
        )
        for hour in future_hours
    ]
    return PredictionResponse(score=score, alternatives=alternatives)


@app.get("/live-status", response_model=LiveStatus)
async def live_status(origin: str, destination: str) -> LiveStatus:
    """Keep official Darwin times visibly separate from the ML probability."""
    return await status(origin.upper(), destination.upper())
