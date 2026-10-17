#!/usr/bin/env python3
"""Ramp concurrent voice calls against a EasyTech deployment and report the knee.

The app already exposes everything this needs:

* ``GET /api/v1/health/active-calls`` -> ``{active_calls, loop_lag_p95_ms, loop_lag_max_ms}``
  (per-worker; header ``X-EasyTech-Devops-Secret``). ``loop_lag.py`` exists precisely so a
  load test can find the concurrency where the event-loop lag climbs, which is the
  number that drives KEDA ``callsPerPod``.
* ``POST /api/v1/telephony/initiate-call`` places a real outbound call; this harness
  instead hits Twilio directly so it can also hang calls up on demand.

A meaningful capacity number requires *real* media (real STT/LLM/TTS/transport) -- a
synthetic in-process call does no per-call CPU work, so its loop lag never rises and any
"knee" it reports is fiction. This harness therefore places real calls. There is no free
free-fidelity generator; see README for the trade-off.

Target ONE worker/pod (port-forward or a single-process uvicorn). ``loop_lag`` is
per-process, so calls spread across workers/pods measure per-worker capacity, not one pod's.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import math
import os
import sys
import time

import httpx

DEVOPS_SECRET_HEADER = "X-EasyTech-Devops-Secret"
HOLD_TWIML = '<Response><Pause length="600"/></Response>'
TWILIO_CALLS_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json"
TWILIO_CALL_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls/{call_sid}.json"


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, math.ceil(pct / 100 * len(ordered)) - 1))
    return ordered[idx]


def analyze(samples: list[dict], lag_threshold_ms: float) -> dict:
    """Given per-step samples, find the saturation knee and a safe callsPerPod.

    Each sample: {"target", "active_calls", "lag_p95", "lag_max"}. The knee is the first
    step where steady-state p95 loop lag crosses the threshold; the max sustainable
    concurrency is the last step below it. ``suggested_calls_per_pod`` keeps a 20% margin
    under the sustainable step (a pod must absorb a burst before KEDA reacts).
    """
    knee = next((s["target"] for s in samples if s["lag_p95"] >= lag_threshold_ms), None)
    passing = [s["target"] for s in samples if s["lag_p95"] < lag_threshold_ms]
    max_sustainable = passing[-1] if passing else 0
    suggested = max(1, int(max_sustainable * 0.8)) if max_sustainable else 0
    return {
        "knee": knee,
        "max_sustainable": max_sustainable,
        "suggested_calls_per_pod": suggested,
        "saturated": knee is not None,
    }


def render_report(samples: list[dict], verdict: dict, threshold: float) -> str:
    lines = [
        f"{'target':>7} {'active':>7} {'lag_p95(ms)':>12} {'lag_max(ms)':>12}",
        "-" * 42,
    ]
    for s in samples:
        mark = "  <= knee" if s["lag_p95"] >= threshold else ""
        lines.append(
            f"{s['target']:>7} {s['active_calls']:>7} "
            f"{s['lag_p95']:>12.1f} {s['lag_max']:>12.1f}{mark}"
        )
    lines.append("-" * 42)
    if not samples:
        lines.append("No samples collected.")
    elif verdict["saturated"]:
        lines.append(
            f"Knee at {verdict['knee']} concurrent calls "
            f"(lag_p95 >= {threshold:.0f}ms)."
        )
        lines.append(
            f"Max sustainable: {verdict['max_sustainable']}. "
            f"Suggested autoscaling.web.keda.callsPerPod: "
            f"{verdict['suggested_calls_per_pod']}."
        )
    else:
        lines.append(
            f"No knee up to {samples[-1]['target']} calls -- you have headroom. "
            "Raise --steps to push further."
        )
    return "\n".join(lines)


async def _sample_health(client: httpx.AsyncClient, base_url: str, headers: dict) -> dict:
    resp = await client.get(f"{base_url}/api/v1/health/active-calls", headers=headers)
    resp.raise_for_status()
    body = resp.json()
    return {
        "active_calls": body["active_calls"],
        "lag_p95": body["loop_lag_p95_ms"],
        "lag_max": body["loop_lag_max_ms"],
    }


async def _monitor_hold(
    client: httpx.AsyncClient, base_url: str, headers: dict, hold_seconds: float,
    interval: float = 1.0,
) -> dict:
    """Sample health for hold_seconds; return a steady-state aggregate for the step."""
    active: list[int] = []
    p95: list[float] = []
    mx: list[float] = []
    deadline = time.monotonic() + hold_seconds
    while time.monotonic() < deadline:
        try:
            s = await _sample_health(client, base_url, headers)
            active.append(s["active_calls"])
            p95.append(s["lag_p95"])
            mx.append(s["lag_max"])
        except httpx.HTTPError as exc:
            print(f"  ! health sample failed: {exc}", file=sys.stderr)
        await asyncio.sleep(interval)
    return {
        "active_calls": round(sum(active) / len(active)) if active else 0,
        "lag_p95": percentile(p95, 95),
        "lag_max": max(mx) if mx else 0.0,
    }


# ponytail: Twilio REST via httpx; swap for the app's /telephony/initiate-call later if
# you want the call to run a workflow instead of holding.
def _twilio_auth(sid: str, token: str) -> str:
    raw = base64.b64encode(f"{sid}:{token}".encode()).decode()
    return f"Basic {raw}"


async def _place_call(client: httpx.AsyncClient, sid: str, auth: str, frm: str, to: str) -> str | None:
    resp = await client.post(
        TWILIO_CALLS_URL.format(sid=sid),
        headers={"Authorization": auth},
        data={
            "From": frm,
            "To": to,
            "Twiml": HOLD_TWIML,
            "Timeout": "30",
        },
    )
    if resp.status_code >= 300:
        print(f"  ! place call failed {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        return None
    return resp.json().get("sid")


async def _hangup(client: httpx.AsyncClient, sid: str, auth: str, call_sid: str) -> None:
    await client.post(
        TWILIO_CALL_URL.format(sid=sid, call_sid=call_sid),
        headers={"Authorization": auth},
        data={"Status": "completed"},
    )


async def run_live(args: argparse.Namespace) -> int:
    if not args.twilio_sid or not args.twilio_token or not args.from_number or not args.to_number:
        print(
            "live mode needs --twilio-sid --twilio-token --from-number --to-number",
            file=sys.stderr,
        )
        return 2
    headers = {DEVOPS_SECRET_HEADER: args.devops_secret} if args.devops_secret else {}
    samples: list[dict] = []
    async with httpx.AsyncClient(timeout=30) as client:
        for target in args.steps:
            print(f"-> ramping to {target} concurrent calls ...", file=sys.stderr)
            auth = _twilio_auth(args.twilio_sid, args.twilio_token)
            sids = await asyncio.gather(
                *(_place_call(client, args.twilio_sid, auth, args.from_number, args.to_number)
                  for _ in range(target))
            )
            placed = [s for s in sids if s]
            step = await _monitor_hold(client, args.base_url, headers, args.hold_seconds)
            step["target"] = target
            samples.append(step)
            await asyncio.gather(
                *(_hangup(client, args.twilio_sid, auth, s) for s in placed)
            )
            if step["lag_p95"] >= args.lag_threshold_ms:
                print(f"   knee reached at {target}; stopping ramp.", file=sys.stderr)
                break
    verdict = analyze(samples, args.lag_threshold_ms)
    print(render_report(samples, verdict, args.lag_threshold_ms))
    return 0


def _demo() -> None:
    """Self-check for the analysis: flat lag then a knee, and no-knee headroom."""
    rising = [
        {"target": 25, "active_calls": 25, "lag_p95": 12, "lag_max": 20},
        {"target": 100, "active_calls": 100, "lag_p95": 40, "lag_max": 70},
        {"target": 200, "active_calls": 200, "lag_p95": 90, "lag_max": 140},
        {"target": 250, "active_calls": 250, "lag_p95": 220, "lag_max": 400},
    ]
    v = analyze(rising, 150)
    assert v["knee"] == 250, v
    assert v["max_sustainable"] == 200, v
    assert v["suggested_calls_per_pod"] == 160, v  # 200 * 0.8

    flat = [{"target": n, "active_calls": n, "lag_p95": 20, "lag_max": 30} for n in (25, 250)]
    assert analyze(flat, 150)["knee"] is None

    assert percentile([10, 20, 30, 40], 95) == 40
    assert percentile([], 95) == 0.0
    assert analyze([], 150)["saturated"] is False

    report = render_report(rising, analyze(rising, 150), 150)
    assert "Suggested autoscaling.web.keda.callsPerPod: 160" in report
    print("self-check ok")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--devops-secret", default=os.environ.get("EASYTECH_DEVOPS_SECRET", ""))
    parser.add_argument("--steps", type=lambda s: [int(x) for x in s.split(",")],
                        default=[25, 50, 100, 150, 200, 250])
    parser.add_argument("--hold-seconds", type=float, default=60.0)
    parser.add_argument("--lag-threshold-ms", type=float, default=150.0)
    parser.add_argument("--twilio-sid", default=os.environ.get("TWILIO_ACCOUNT_SID", ""))
    parser.add_argument("--twilio-token", default=os.environ.get("TWILIO_AUTH_TOKEN", ""))
    parser.add_argument("--from-number", default="")
    parser.add_argument("--to-number", default="")
    parser.add_argument("--self-check", action="store_true", help="run offline analysis self-check")
    args = parser.parse_args(argv)

    if args.self_check:
        _demo()
        return 0
    return asyncio.run(run_live(args))


if __name__ == "__main__":
    raise SystemExit(main())
