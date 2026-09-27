"""Small typed contracts shared by the HTTP and model boundaries."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class Journey(BaseModel):
    """One direct journey to score before it departs."""

    origin: str = Field(min_length=3, max_length=3)
    destination: str = Field(min_length=3, max_length=3)
    operator: str = Field(min_length=2, max_length=80)
    scheduled_departure: datetime
    scheduled_duration_minutes: int = Field(ge=1, le=600)

    @field_validator("origin", "destination")
    @classmethod
    def uppercase_crs(cls, value: str) -> str:
        """Use the National Rail three-letter station convention."""
        return value.upper()

    @field_validator("scheduled_departure")
    @classmethod
    def aware_departure(cls, value: datetime) -> datetime:
        """Avoid silently treating a UK wall-clock time as UTC."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scheduled_departure must include a timezone offset")
        return value


class Score(BaseModel):
    """A calibrated probability and minimal explanatory context."""

    probability: float = Field(ge=0, le=1)
    risk: str
    factors: list[str]
    data_cutoff: str


class PredictionResponse(BaseModel):
    """The main journey score plus timetable-shaped alternatives."""

    score: Score
    alternatives: list[AlternativeScore]


class AlternativeScore(BaseModel):
    """A typical scheduled-time alternative, not a live timetable guarantee."""

    scheduled_departure: str
    score: Score


class LiveStatus(BaseModel):
    """A compact public projection of Darwin's official departure board."""

    available: bool
    message: str
    scheduled_departure: str | None = None
    expected_departure: str | None = None
    platform: str | None = None
    cancelled: bool | None = None
    operator: str | None = None
