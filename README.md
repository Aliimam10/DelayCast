# DelayCast

DelayCast is a compact, local-only ML portfolio project. It estimates the
probability that a direct National Rail service will arrive **at least 10
minutes late**. It is intentionally small enough to understand end-to-end:
one CatBoost model, one chronological split, a FastAPI backend, and one Next.js
page.

It is not a travel-planning product. The model gives a historical risk estimate;
the separate Darwin card shows official live information where configured.

## Data-use policy

We use synthetic train records only as a smoke test to verify that the
end-to-end software pipeline works. Final DelayCast training, evaluation,
screenshots, metrics, and portfolio discussion use real historical National
Rail service data retrieved through the relevant National Rail data access,
normalised into DelayCast's documented input schema, and evaluated on a
chronologically held-out test period.

## Why this model and evaluation design?

CatBoost is the one final classifier because origin, destination, and operator
are categorical tabular features. A historical route-rate baseline provides a
simple comparison. Services are sorted by scheduled departure: the oldest 70%
train the classifier, the next 15% calibrate its probabilities, and the newest
15% are the one untouched test set. There is no random split.

The test report records ROC-AUC, precision, recall, and Brier score for both
the baseline and calibrated CatBoost. It also writes `calibration.png`, which
compares predicted probabilities to observed late rates.

## Data contract

Register with the Rail Data Marketplace and export completed HSP/Darwin
services into one CSV. The raw HSP response varies by subscription, so export
these seven documented columns once and keep the ML project easy to inspect:

```text
scheduled_departure,scheduled_arrival,actual_arrival,
origin,destination,operator,cancelled
```

- Times must be ISO 8601 with a timezone offset.
- `origin` and `destination` are uppercase three-letter CRS codes.
- `cancelled` is `true` or `false`; cancelled services are excluded because
  they are not an arrival-delay label.
- Do not commit downloaded data, Darwin credentials, or model artifacts.

Features are only origin, destination, operator, UK local departure hour,
weekday, month, scheduled duration, and previous completed route/operator late
rates. The rates only include services that had actually arrived before the
current service's scheduled departure, so they do not reveal its outcome.

## Run locally

1. Put a normalised historical CSV somewhere ignored, for example
   `delaycast/data/hsp_services.csv`.
   To verify the application without downloading data, create a deliberately
   fictional CSV instead:

   ```bash
   cd delaycast/backend
   uv run python -m delaycast.sample ../data/demo.csv
   ```

   Use `../data/demo.csv` in the training command below for that safe walkthrough.

2. Train the model and view the held-out report:

   ```bash
   cd delaycast/backend
   uv sync --dev
   uv run python -m delaycast.train ../data/hsp_services.csv
   ```

   This creates ignored `delaycast/artifacts/delaycast.joblib` and
   `calibration.png`. A minimum of 100 completed services is required; aim for
   several months across the routes you want to demonstrate.
3. Start the backend:

   ```bash
   uv run uvicorn delaycast.app:app --reload
   ```
4. In another terminal, start the frontend:

   ```bash
   cd delaycast/web
   npm install
   npm run dev
   ```

   Open `http://localhost:3000`.

## Optional Darwin card

Copy `backend/.env.example` to `backend/.env`, add the username/password issued
by National Rail, and load those variables before starting FastAPI. The backend
calls the documented JSON Live Departure Board endpoint only when the frontend
requests a status. If credentials are absent, the card clearly says so while
the local ML prediction remains available.

National Rail requires registration and attribution for Darwin use. See the
[official Darwin feed information](https://www.nationalrail.co.uk/developers/darwin-data-feeds/)
and [LDBWS JSON documentation](https://realtime.nationalrail.co.uk/LDBWS/docs/documentation.html).

## Deliberately future work

Weather, a model zoo, prediction-minute regression, historical live-Darwin
snapshots, deployment, accounts, databases, and richer route search are all
out of scope. They would distract from the core time-aware classification
project.
