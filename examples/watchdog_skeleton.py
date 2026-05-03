"""Watchdog skeleton — copy this into your repo and grow it under your spec.

The sim emits a *merged* telemetry stream: every frame carries all 4
scenarios at once, nested under per-scenario keys. Each sub-object holds
its own altitude, lat/lon, current, motor temps, flight_mode etc.

  frame = {
      "drone_id": "uav-01", "seq": 137, "ts": 1714.7,
      "apollo11": { "altitude_m": ..., "lat": ..., "flight_mode": ..., ... },
      "flag":     { "altitude_m": ..., "lat": ..., "flight_mode": ..., ... },
      "heart":    { ... },
      "wright":   { ... },
      "window_sha256": "..."
  }

Pattern → sub-object map (your job to verify, not blindly trust):
  - Pattern 1 (geospatial shape):     f["flag"]["lat"], f["flag"]["lon"]
  - Pattern 2 (Apollo descent):       f["apollo11"]["altitude_m"], ["flight_mode"], ["current_a"]
  - Pattern 3 (Fibonacci anomalies):  anomaly markers under f["flag"]
  - Pattern 4 (cross-channel lag):    f["apollo11"]["current_a"] → f["apollo11"]["motor_temp_c"][0]
  - heart, wright: decoys — present every frame, never the answer.

Demonstrates the things students will get wrong without a starting point:

1. The decorator is `@tool` (NOT `@ai_function` or `@Tool`).
2. There are two ways to call a FunctionTool:
   - direct/sync   — `result = my_tool.func(frames=frames)`
   - via the agent — `await my_tool.invoke(arguments={"frames": frames})`
   The first is what your unit tests should use; the second is what runs
   when the agent decides to call the tool.
3. The default `on_permission_request` denies every tool call silently.
   You MUST pass an approving handler — see `make_agent()` below.
4. The default model may not be enabled on your Copilot subscription. Pass
   `--model gpt-5.2` (or whichever `client.list_models()` shows) to choose.

Run end-to-end after producing telemetry.jsonl with scripts/capture.py:

    python scripts/capture.py --out telemetry.jsonl   # Ctrl-C after a while
    python examples/watchdog_skeleton.py telemetry.jsonl
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Annotated

from agent_framework import tool
from agent_framework_github_copilot import GitHubCopilotAgent
from copilot.session import PermissionRequestResult


def load(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f]


@tool(
    name="detect_geospatial_shape",
    description="Plot lat vs lon (from the flag sub-object), return bbox in metres + visible components.",
)
def detect_geospatial_shape(
    frames: Annotated[list[dict], "Captured merged-stream telemetry frames."],
) -> dict:
    lats = [f["flag"]["lat"] for f in frames]
    lons = [f["flag"]["lon"] for f in frames]
    lat_c = (max(lats) + min(lats)) / 2
    h = (max(lats) - min(lats)) * 111_320
    w = (max(lons) - min(lons)) * 111_320 * math.cos(math.radians(lat_c))
    # Plot the path (matplotlib / asciichart) and label what you see.
    return {
        "label": "TODO: plot the path and label it",
        "bbox_width_m": round(w, 1),
        "bbox_height_m": round(h, 1),
        "center_lat": round(lat_c, 6),
        "center_lon": round((max(lons) + min(lons)) / 2, 6),
        "components": [],
    }


@tool(
    name="detect_altitude_replay",
    description="Find peak altitude and the seq at which apollo11.flight_mode flips to MANUAL.",
)
def detect_altitude_replay(frames: list[dict]) -> dict:
    peak = max(frames, key=lambda f: f["apollo11"]["altitude_m"])
    manual_seq = next(
        (f["seq"] for f in frames if f["apollo11"]["flight_mode"] == "MANUAL"), None
    )
    return {
        "label": "TODO",
        "peak_altitude_m": round(peak["apollo11"]["altitude_m"], 1),
        "manual_takeover_seq": manual_seq,
        "alarm_event_seq": None,
        "modes_seen": dict(Counter(f["apollo11"]["flight_mode"] for f in frames)),
    }


@tool(
    name="detect_anomaly_cadence",
    description="Find anomalies (in the flag sub-object) and report the inter-anomaly seq gaps.",
)
def detect_anomaly_cadence(frames: list[dict]) -> dict:
    return {"label": "TODO", "anomaly_seqs": [], "interval_seconds": []}


@tool(
    name="detect_cross_channel_lag",
    description="Find lag where apollo11.motor_temp_c[0] is a scaled echo of apollo11.current_a.",
)
def detect_cross_channel_lag(frames: list[dict]) -> dict:
    return {
        "label": "TODO",
        "source_field": "apollo11.current_a",
        "target_field": "apollo11.motor_temp_c[0]",
        "lag_samples": 0,
        "gain": 0.0,
    }


WATCHDOG_TOOLS = [
    detect_geospatial_shape,
    detect_altitude_replay,
    detect_anomaly_cadence,
    detect_cross_channel_lag,
]


def _allow_all(_request, _invocation) -> PermissionRequestResult:
    """Approve every tool-call permission request.

    The Copilot SDK defaults to denying every request silently — tool
    results come back as 'Permission denied and could not request
    permission from user'. Workshop tools are pure read-only analysis,
    so allow-all is safe here. If you add tools that touch the
    filesystem or network, narrow this handler accordingly.
    """
    return PermissionRequestResult(kind="approved")


def make_agent(model: str | None = None) -> GitHubCopilotAgent:
    """Construct the Copilot-backed agent with the tools attached.

    GitHubCopilotAgent picks up auth from the Copilot SDK environment.
    See `github_auth.CopilotAuth` for the device-flow login the workshop
    uses to populate that environment.

    Pass `model` to pin a specific Copilot model. Falls back to the
    GITHUB_COPILOT_MODEL environment variable, then to "gpt-5.2" (a
    sensible default that's enabled on most subscriptions).

    Use `copilot.CopilotClient.list_models()` to see what's available
    on your account — note that `policy.state == 'enabled'` does NOT
    guarantee the model is reachable, so try a few if one fails.
    """
    chosen_model = model or os.environ.get("GITHUB_COPILOT_MODEL") or "gpt-5.2"
    return GitHubCopilotAgent(
        name="DroneWatchdog",
        instructions=(
            "You are the Drone Watchdog. Given captured drone telemetry "
            "(merged stream — each frame nests apollo11/flag/heart/wright "
            "sub-objects), call each pattern-detection tool and assemble an "
            "`answer` object matching specs/submission_schema.json."
        ),
        tools=WATCHDOG_TOOLS,
        default_options={
            "model": chosen_model,
            "timeout": 180,
            "on_permission_request": _allow_all,
        },
    )


def run_local_analysis(frames: list[dict]) -> dict:
    """Run each tool directly (sync) — this is the path your tests use."""
    return {
        "pattern_1": detect_geospatial_shape.func(frames=frames),
        "pattern_2": detect_altitude_replay.func(frames=frames),
        "pattern_3": detect_anomaly_cadence.func(frames=frames),
        "pattern_4": detect_cross_channel_lag.func(frames=frames),
    }


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python examples/watchdog_skeleton.py telemetry.jsonl",
              file=sys.stderr)
        sys.exit(2)
    path = Path(sys.argv[1])
    frames = load(str(path))
    print(json.dumps(run_local_analysis(frames), indent=2, default=str))


if __name__ == "__main__":
    main()
