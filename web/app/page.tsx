"use client";

import { FormEvent, useState } from "react";
import { AlertCircle, Clock3, RadioTower, TrainFront } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const routes = [
  {
    label: "London Euston → Manchester Piccadilly",
    origin: "EUS",
    destination: "MAN",
    operator: "Avanti West Coast",
    duration: 126,
  },
  {
    label: "London Euston → Birmingham New Street",
    origin: "EUS",
    destination: "BHM",
    operator: "Avanti West Coast",
    duration: 84,
  },
  {
    label: "London King's Cross → Leeds",
    origin: "KGX",
    destination: "LDS",
    operator: "LNER",
    duration: 133,
  },
  {
    label: "London Paddington → Bristol Temple Meads",
    origin: "PAD",
    destination: "BRI",
    operator: "Great Western Railway",
    duration: 94,
  },
];

type Score = {
  probability: number;
  risk: string;
  factors: string[];
  data_cutoff: string;
};

type Result = {
  score: Score;
  alternatives: { scheduled_departure: string; score: Score }[];
};

type Live = {
  available: boolean;
  message: string;
  scheduled_departure?: string;
  expected_departure?: string;
  platform?: string;
  cancelled?: boolean;
  operator?: string;
};

function percent(value: number) {
  return new Intl.NumberFormat("en-GB", {
    style: "percent",
    maximumFractionDigits: 0,
  }).format(value);
}

export default function Home() {
  const [routeIndex, setRouteIndex] = useState(0);
  const [date, setDate] = useState("2026-10-02");
  const [time, setTime] = useState("18:20");
  const [result, setResult] = useState<Result | null>(null);
  const [live, setLive] = useState<Live | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const route = routes[routeIndex];

  async function predict(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    setLive(null);

    // The browser converts the chosen local journey time to an offset-aware
    // timestamp, which the API requires rather than guessing a timezone.
    const scheduledDeparture = new Date(`${date}T${time}:00`).toISOString();
    const journey = {
      origin: route.origin,
      destination: route.destination,
      operator: route.operator,
      scheduled_departure: scheduledDeparture,
      scheduled_duration_minutes: route.duration,
    };

    try {
      const [prediction, liveStatus] = await Promise.all([
        fetch(`${API}/predict`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(journey),
        }),
        fetch(
          `${API}/live-status?origin=${route.origin}&destination=${route.destination}`
        ),
      ]);
      if (!prediction.ok) {
        throw new Error(
          (await prediction.json()).detail ?? "Prediction is unavailable."
        );
      }
      setResult(await prediction.json());
      setLive(await liveStatus.json());
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not contact the local API."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-5 py-10 sm:py-16">
      <header className="mb-10">
        <div className="mb-3 flex items-center gap-2 text-sky-400">
          <TrainFront size={22} />
          <span className="font-semibold">DELAYCAST</span>
        </div>
        <h1 className="max-w-2xl text-4xl font-bold tracking-tight text-white sm:text-5xl">
          Will your train arrive 10 minutes late?
        </h1>
        <p className="mt-4 max-w-2xl text-slate-400">
          A compact National Rail ML portfolio project. The model estimates risk;
          Darwin remains the official source for live times.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <h2 className="mb-5 text-lg font-semibold text-white">
            Choose a journey
          </h2>
          <form className="space-y-4" onSubmit={predict}>
            <div>
              <label htmlFor="route">Route</label>
              <select
                id="route"
                value={routeIndex}
                onChange={(event) => setRouteIndex(Number(event.target.value))}
              >
                {routes.map((item, index) => (
                  <option key={item.label} value={index}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="date">Departure date</label>
                <input
                  id="date"
                  type="date"
                  value={date}
                  onChange={(event) => setDate(event.target.value)}
                  required
                />
              </div>
              <div>
                <label htmlFor="time">Departure time</label>
                <input
                  id="time"
                  type="time"
                  value={time}
                  onChange={(event) => setTime(event.target.value)}
                  required
                />
              </div>
            </div>
            <Button className="w-full" disabled={loading}>
              {loading ? "Calculating…" : "Predict delay risk"}
            </Button>
          </form>
        </Card>

        <div className="space-y-6">
          {error && (
            <Card className="border-rose-900">
              <div className="flex gap-3 text-rose-300">
                <AlertCircle />
                <p>{error}</p>
              </div>
            </Card>
          )}
          {result ? <Prediction result={result} /> : <EmptyResult />}
          {live && <LiveStatus live={live} />}
        </div>
      </div>

      <p className="mt-8 text-xs leading-5 text-slate-500">
        Trained only on completed historical services. Data cutoff and explanatory
        factors are shown with each result. Live-status data © National Rail /
        Darwin, subject to its terms.
      </p>
    </main>
  );
}

function EmptyResult() {
  return (
    <Card className="min-h-64">
      <Clock3 className="mb-4 text-slate-500" />
      <h2 className="text-lg font-semibold text-white">
        Your delay-risk result will appear here.
      </h2>
      <p className="mt-2 text-sm text-slate-400">
        Select a journey, then compare the model&apos;s calibrated probability with
        official live running information.
      </p>
    </Card>
  );
}

function Prediction({ result }: { result: Result }) {
  return (
    <Card>
      <p className="text-sm text-slate-400">Chance of arriving ≥10 min late</p>
      <div className="mt-2 flex items-end justify-between">
        <strong className="text-5xl text-white">
          {percent(result.score.probability)}
        </strong>
        <span className="rounded-full bg-sky-400/15 px-3 py-1 text-sm font-semibold text-sky-300">
          {result.score.risk} risk
        </span>
      </div>
      <p className="mt-6 text-sm font-medium text-slate-300">
        What the model relies on most
      </p>
      <ul className="mt-2 space-y-2 text-sm text-slate-400">
        {result.score.factors.map((factor) => (
          <li key={factor}>• {factor}</li>
        ))}
      </ul>
      <p className="mt-5 text-xs text-slate-500">
        Historical data through {result.score.data_cutoff}
      </p>
      {result.alternatives.length > 0 && <Alternatives result={result} />}
    </Card>
  );
}

function Alternatives({ result }: { result: Result }) {
  return (
    <>
      <p className="mt-6 text-sm font-medium text-slate-300">
        Typical timetable alternatives
      </p>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {result.alternatives.map((item) => (
          <div
            className="rounded-lg bg-slate-800 p-3 text-sm"
            key={item.scheduled_departure}
          >
            <span className="text-slate-400">
              {new Date(item.scheduled_departure).toLocaleTimeString("en-GB", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
            <strong className="float-right text-white">
              {percent(item.score.probability)}
            </strong>
          </div>
        ))}
      </div>
    </>
  );
}

function LiveStatus({ live }: { live: Live }) {
  return (
    <Card className="border-sky-900/80">
      <div className="flex items-center gap-2">
        <RadioTower size={18} className="text-sky-400" />
        <h2 className="font-semibold text-white">Official live status</h2>
      </div>
      {live.available ? (
        <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
          <StatusItem label="Scheduled" value={live.scheduled_departure} />
          <StatusItem
            label="Expected"
            value={live.cancelled ? "Cancelled" : live.expected_departure}
          />
          <StatusItem label="Platform" value={live.platform ?? "—"} />
          <StatusItem label="Operator" value={live.operator} />
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-400">{live.message}</p>
      )}
      <p className="mt-4 text-xs text-slate-500">
        {live.available
          ? live.message
          : "The ML prediction remains available without Darwin credentials."}
      </p>
    </Card>
  );
}

function StatusItem({ label, value }: { label: string; value?: string }) {
  return (
    <div>
      <p className="text-slate-500">{label}</p>
      <p className="font-medium text-white">{value ?? "—"}</p>
    </div>
  );
}
