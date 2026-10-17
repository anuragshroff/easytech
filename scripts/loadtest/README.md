# Voice-call load test

Ramps real concurrent calls against a EasyTech deployment and reports the concurrency where
the event loop saturates — the number that drives `autoscaling.web.keda.callsPerPod`.

```bash
export EASYTECH_DEVOPS_SECRET=...      # gates /health/active-calls
export TWILIO_ACCOUNT_SID=... TWILIO_AUTH_TOKEN=...

venv/bin/python scripts/loadtest/ramp_calls.py \
  --base-url https://staging.example.com \
  --steps 25,50,100,150,200,250 --hold-seconds 60 \
  --from-number "+1..." --to-number "+1..."

# offline analysis check (no network):
venv/bin/python scripts/loadtest/ramp_calls.py --self-check
```

Output is a per-step table of `active_calls`, `loop_lag_p95_ms`, `loop_lag_max_ms`, the
knee, and a suggested `callsPerPod` (80% of the last step under threshold, so a pod can
absorb a burst before KEDA reacts). The ramp stops early once the knee is crossed.

## Why this and not a synthetic generator

A synthetic in-process "call" does no per-call CPU work, so its loop lag never climbs and
any knee it reports is fiction. A real capacity number needs real media (STT/LLM/TTS +
transport). There is no free, faithful, reusable generator in the repo, so this harness
places real calls. Cost = the sum of `--steps` × `--hold-seconds` of call minutes.

## Prerequisites

- **Target one worker/pod.** `loop_lag` and `active_calls` are per-process. On
  multi-worker/multi-pod deploys calls spread out and you measure per-worker headroom, not
  one pod's. Port-forward a single pod or run single-process uvicorn.
- **A destination that answers and holds.** Calls to `--to-number` get `HOLD_TWIML`
  (`<Pause length="600"/>`), so a Twilio number with a Voice URL (or the `Twiml` param
  path used here) will keep the line up. If you prefer the call to run a workflow, dial
  the app's own inbound number instead.
- **Twilio concurrency.** Raise the account's concurrent outbound-call limit above your
  max step, or Twilio queues the surplus and `active_calls` under-reports.
- `ENABLE_PROMETHEUS_METRICS=true` is not required by this harness (it reads the health
  endpoint), but the same run populates `easytech_active_calls` in Grafana if set.

## Files

- `ramp_calls.py` — harness + `analyze()` and its `--self-check`.
