"""Tiny adapter for National Rail's public JSON Live Departure Board."""

from __future__ import annotations

import os

import httpx

from delaycast.contracts import LiveStatus

_BASE_URL = "https://realtime.nationalrail.co.uk/LDBWS/api/20220120"


async def status(origin: str, destination: str) -> LiveStatus:
    """Fetch the next official departure, or explain why live data is unavailable."""
    username = os.getenv("DARWIN_USERNAME")
    password = os.getenv("DARWIN_PASSWORD")
    if not username or not password:
        return LiveStatus(
            available=False,
            message="Add Darwin credentials to backend/.env to enable live status.",
        )
    try:
        async with httpx.AsyncClient(auth=(username, password), timeout=8) as client:
            response = await client.get(
                f"{_BASE_URL}/GetDepartureBoard/{origin}",
                params={"numRows": 1, "filterCrs": destination, "filterType": "to"},
            )
            response.raise_for_status()
    except httpx.HTTPError:
        return LiveStatus(available=False, message="Darwin is unavailable right now.")
    services = response.json().get("trainServices", [])
    if not services:
        return LiveStatus(
            available=False, message="No matching live departure was found."
        )
    service = services[0]
    return LiveStatus(
        available=True,
        message="Official National Rail Darwin status.",
        scheduled_departure=service.get("std"),
        expected_departure=service.get("etd"),
        platform=service.get("platform"),
        cancelled=service.get("isCancelled"),
        operator=service.get("operator"),
    )
