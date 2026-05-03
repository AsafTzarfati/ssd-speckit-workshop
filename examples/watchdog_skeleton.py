"""Watchdog skeleton — copy this into your repo and grow it under your spec.

Demonstrates the two things students will get wrong without a starting point:

1. The decorator is `@tool` (NOT `@ai_function` or `@Tool`).
2. There are two ways to call a FunctionTool:
   - direct/sync   — `result = my_tool.func(frames=frames)`
   - via the agent — `await my_tool.invoke(arguments={"frames": frames})`
   The first is what your unit tests should use; the second is what runs
   when the agent decides to call the tool.

Run end-to-end after producing telemetry.jsonl with scripts/capture.py:

    python scripts/capture.py --out telemetry.jsonl   # Ctrl-C after a while
    python examples/watchdog_skeleton.py telemetry.jsonl
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Annotated

from agent_framework import tool
from agent_framework_github_copilot import GitHubCopilotAgent


def load(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f]


@tool(
    name="detect_geospatial_shape",
    description="Plot lat vs lon, return bbox in metres + visible components.",
)
def detect_geospatial_shape(
    frames: Annotated[list[dict], "Captured telemetry frames."],
) -> dict:
    lats = [f["lat"] for f in frames]
    lons = [f["lon"] for f in frames]
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
    description="Find peak altitude and the seq at which flight_mode flips to MANUAL.",
)
def detect_altitude_replay(frames: list[dict]) -> dict:
    peak = max(frames, key=lambda f: f["altitude_m"])
    manual_seq = next(
        (f["seq"] for f in frames if f["flight_mode"] == "MANUAL"), None
    )
    return {
        "label": "TODO",
        "peak_altitude_m": round(peak["altitude_m"], 1),
        "manual_takeover_seq": manual_seq,
        "alarm_event_seq": None,
        "modes_seen": dict(Counter(f["flight_mode"] for f in frames)),
    }


@tool(
    name="detect_anomaly_cadence",
    description="Find anomalies and report the inter-anomaly seq gaps.",
)
def detect_anomaly_cadence(frames: list[dict]) -> dict:
    return {"label": "TODO", "anomaly_seqs": [], "interval_seconds": []}


@tool(
    name="detect_cross_channel_lag",
    description="Find lag where one channel becomes a scaled echo of another.",
)
def detect_cross_channel_lag(frames: list[dict]) -> dict:
    return {
        "label": "TODO",
        "source_field": "current_a",
        "target_field": "motor_temp_c[0]",
        "lag_samples": 0,
        "gain": 0.0,
    }


WATCHDOG_TOOLS = [
    detect_geospatial_shape,
    detect_altitude_replay,
    detect_anomaly_cadence,
    detect_cross_channel_lag,
]


def make_agent() -> GitHubCopilotAgent:
    """Construct the Copilot-backed agent with the tools attached.

    GitHubCopilotAgent picks up auth from the Copilot SDK environment.
    See `github_auth.CopilotAuth` for the device-flow login the workshop
    uses to populate that environment.
    """
    return GitHubCopilotAgent(
        name="DroneWatchdog",
        instructions=(
            "You are the Drone Watchdog. Given captured drone telemetry, "
            "call each pattern-detection tool and assemble an `answer` "
            "object matching specs/submission_schema.json."
        ),
        tools=WATCHDOG_TOOLS,
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
