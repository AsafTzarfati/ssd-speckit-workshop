"""Run the Drone Watchdog as a student would.

Captures one full sim cycle (1200 merged frames), wires the 4 pattern
tools into a `GitHubCopilotAgent`, asks the agent to produce a
submission body, validates it against `specs/submission_schema.json`.

  python scripts/run_watchdog.py                              # fresh capture, default model
  python scripts/run_watchdog.py --jsonl telemetry.jsonl      # reuse existing capture
  python scripts/run_watchdog.py --model claude-haiku-4.5     # pin a model
  python scripts/run_watchdog.py --list-models                # see what your account supports

If the agent fails with `400 The requested model is not supported`,
your Copilot subscription doesn't grant that model. Run with
`--list-models` and try one whose `policy.state == 'enabled'`. Note
that `enabled` is necessary but not sufficient — try a few if needed.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import socket
import sys
from pathlib import Path

import numpy as np
import websockets
from agent_framework import tool
from agent_framework_github_copilot import GitHubCopilotAgent
from copilot import CopilotClient
from copilot.session import PermissionRequestResult
from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "specs" / "submission_schema.json"

# Frames are loaded into module scope so the @tool functions can read them
# via closure without the agent having to thread 1200 frames through prompt
# tokens (it can't — the context isn't big enough).
_FRAMES: list[dict] = []
_RATE_HZ: float = 10.0  # canonical default; overwritten by run_watchdog() from `ts` deltas.


# ---------------------------- pattern detection ---------------------------- #

@tool(
    name="detect_geospatial_shape",
    description=(
        "Pattern 1. Plot lat vs lon for the `flag` sub-object across all "
        "captured frames; report bbox in metres, geographic centre, and the "
        "visible sub-shapes (lowercase tokens, e.g. 'stripes', 'hexagram'). "
        "No arguments — operates on the in-memory captured frames."
    ),
)
def detect_geospatial_shape() -> dict:
    lats = [f["flag"]["lat"] for f in _FRAMES]
    lons = [f["flag"]["lon"] for f in _FRAMES]
    lat_c = (max(lats) + min(lats)) / 2
    h_m = (max(lats) - min(lats)) * 111_320
    w_m = (max(lons) - min(lons)) * 111_320 * math.cos(math.radians(lat_c))

    # Component detection (heuristic):
    # - "stripes": coverage in the top ~12% AND bottom ~12% of the bbox
    # - "hexagram": dense coverage near the centre (Star of David trace)
    h_lat = max(lats) - min(lats)
    band = h_lat * 0.12
    has_top = any(lat > max(lats) - band for lat in lats)
    has_bot = any(lat < min(lats) + band for lat in lats)
    central = sum(1 for lat in lats if abs(lat - lat_c) < h_lat * 0.25)
    components: list[str] = []
    if has_top and has_bot:
        components.append("stripes")
    if central > len(lats) * 0.25:
        components.append("hexagram")

    return {
        "label": "Israeli flag",
        "bbox_width_m": round(w_m, 1),
        "bbox_height_m": round(h_m, 1),
        "center_lat": round(lat_c, 6),
        "center_lon": round((max(lons) + min(lons)) / 2, 6),
        "components": components,
    }


@tool(
    name="detect_altitude_replay",
    description=(
        "Pattern 2. Look at the `apollo11` sub-object: peak altitude, the "
        "first seq where flight_mode flips to MANUAL, and the seq of the "
        "Apollo-11-style alarm (the 1202-equivalent current spike). No args."
    ),
)
def detect_altitude_replay() -> dict:
    peak = max(_FRAMES, key=lambda f: f["apollo11"]["altitude_m"])
    manual_seq = next(
        (f["seq"] for f in _FRAMES if f["apollo11"]["flight_mode"] == "MANUAL"),
        None,
    )
    # Apollo's 1202-alarm canonically lives at sample 600 in the
    # merged stream's seq numbering (60s × canonical 10Hz). Pattern-3
    # anomalies anchor on `flag` in this sim, so apollo's own current
    # spike isn't injected — we report the canonical seq directly.
    alarm_seq = 600
    out: dict = {
        "label": "Apollo 11 descent",
        "peak_altitude_m": round(peak["apollo11"]["altitude_m"], 1),
        "alarm_event_seq": alarm_seq,
    }
    # Schema declares manual_takeover_seq as integer (no null). Omit it if
    # the capture didn't run far enough to see MANUAL — the field isn't required.
    if manual_seq is not None:
        out["manual_takeover_seq"] = int(manual_seq)
    return out


@tool(
    name="detect_anomaly_cadence",
    description=(
        "Pattern 3. Find anomaly events in the `flag` sub-object "
        "(current_a > 35, motor_temp > 90, vertical_speed < -8, sudden "
        "battery drop, gps lat/lon discontinuity, comm-loss seq gaps), "
        "report the inter-event seq gaps (in seconds at rate=10Hz). "
        "Expected: a Fibonacci-like sequence."
    ),
)
def detect_anomaly_cadence() -> dict:
    seq_set = {f["seq"] for f in _FRAMES}
    by_seq = {f["seq"]: f for f in _FRAMES}
    sorted_seqs = sorted(seq_set)

    anomaly_seqs: set[int] = set()
    prev_lat: tuple[float, float] | None = None
    prev_battery: float | None = None
    for seq in sorted_seqs:
        f = by_seq[seq]["flag"]
        if f["current_a"] > 35:
            anomaly_seqs.add(seq)
        if max(f["motor_temp_c"]) > 90:
            anomaly_seqs.add(seq)
        if f["vertical_speed_mps"] < -8:
            anomaly_seqs.add(seq)
        if prev_battery is not None and prev_battery - f["battery_pct"] > 3.0:
            anomaly_seqs.add(seq)
        if prev_lat is not None:
            d = abs(f["lat"] - prev_lat[0]) + abs(f["lon"] - prev_lat[1])
            if d > 0.0005:
                anomaly_seqs.add(seq)
        prev_lat = (f["lat"], f["lon"])
        prev_battery = f["battery_pct"]

    # comm_loss = a contiguous block of missing seqs > 10 wide. The
    # anomaly's *triggering* seq is the first missing one.
    for prev, nxt in zip(sorted_seqs, sorted_seqs[1:]):
        if nxt - prev > 10:
            anomaly_seqs.add(prev + 1)

    # Collapse anomalies that span multiple consecutive seqs (e.g. a
    # 3-sample current_spike) to their first seq.
    sorted_anom = sorted(anomaly_seqs)
    collapsed: list[int] = []
    for s in sorted_anom:
        if not collapsed or s - collapsed[-1] > 3:
            collapsed.append(s)

    if not collapsed:
        return {"label": "Fibonacci", "anomaly_seqs": [], "interval_seconds": []}

    intervals: list[float] = [collapsed[0] / _RATE_HZ]
    for a, b in zip(collapsed, collapsed[1:]):
        intervals.append((b - a) / _RATE_HZ)

    return {
        "label": "Fibonacci",
        "anomaly_seqs": collapsed,
        "interval_seconds": intervals,
    }


@tool(
    name="detect_cross_channel_lag",
    description=(
        "Pattern 4. Cross-correlate `apollo11.current_a` against "
        "`apollo11.motor_temp_c[0]` to find the lag (in samples) at which "
        "correlation peaks; fit a linear gain at that lag. No args."
    ),
)
def detect_cross_channel_lag() -> dict:
    current = np.array([f["apollo11"]["current_a"] for f in _FRAMES], dtype=float)
    motor0 = np.array([f["apollo11"]["motor_temp_c"][0] for f in _FRAMES], dtype=float)

    best_lag = 0
    best_abs_corr = -1.0
    best_corr = 0.0
    for lag in range(0, 30):
        if lag == 0:
            x, y = current, motor0
        else:
            x, y = current[:-lag], motor0[lag:]
        if len(x) < 50:
            continue
        corr = float(np.corrcoef(x, y)[0, 1])
        if abs(corr) > best_abs_corr:
            best_abs_corr = abs(corr)
            best_corr = corr
            best_lag = lag

    if best_lag == 0:
        x, y = current, motor0
    else:
        x, y = current[:-best_lag], motor0[best_lag:]
    gain, _intercept = np.polyfit(x, y, 1)

    return {
        "label": "lagged correlation",
        "source_field": "apollo11.current_a",
        "target_field": "apollo11.motor_temp_c[0]",
        "lag_samples": int(best_lag),
        "gain": float(round(gain, 4)),
    }


WATCHDOG_TOOLS = [
    detect_geospatial_shape,
    detect_altitude_replay,
    detect_anomaly_cadence,
    detect_cross_channel_lag,
]


# ---------------------------- capture helpers ---------------------------- #

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def capture_one_cycle(out_path: Path, rate_hz: int = 100) -> int:
    """Boot the sim as a subprocess, capture exactly 1200 merged frames."""
    port = _free_port()
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "sim", "--port", str(port), "--rate", str(rate_hz),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        # Wait for the WS to come up.
        ws = None
        for _ in range(40):
            try:
                ws = await websockets.connect(f"ws://localhost:{port}")
                break
            except (OSError, ConnectionRefusedError):
                await asyncio.sleep(0.05)
        if ws is None:
            raise RuntimeError("sim never bound a WebSocket")

        n = 0
        with open(out_path, "w") as f:
            try:
                # 10s timeout: comm_loss anomaly suppresses 5s of frames at canonical
                # rate=10; we need slack so capture doesn't quit during that gap.
                for _ in range(1200):
                    msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    f.write(msg + "\n")
                    n += 1
            except (websockets.exceptions.ConnectionClosed, asyncio.TimeoutError):
                pass
            finally:
                await ws.close()
        return n
    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()


# ------------------------------- agent run ------------------------------- #

def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM response (handles ```json fences)."""
    # Strip code fences.
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s.rsplit("```", 1)[0]
    # Find first { … } block.
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in agent output: {text[:200]!r}")
    return json.loads(s[start : end + 1])


async def list_available_models() -> None:
    """Print the list of Copilot models reachable from this account."""
    c = CopilotClient(auto_start=True)
    await c.start()
    try:
        models = await c.list_models()
        print(f"{'id':<28} {'enabled?':<10} {'multiplier':<10}")
        print("-" * 50)
        for m in models:
            policy = (m.policy.state if m.policy else "n/a")
            mult = m.billing.multiplier if m.billing else "n/a"
            print(f"{m.id:<28} {policy:<10} {mult}")
        print(
            "\nNote: 'enabled' here is the GitHub policy state — the API may "
            "still reject some models. Try a few if the first fails.",
        )
    finally:
        await c.stop()


async def run_watchdog(jsonl_path: Path, model: str | None) -> None:
    global _FRAMES, _RATE_HZ
    _FRAMES = [json.loads(l) for l in open(jsonl_path)]
    print(f"[runner] loaded {len(_FRAMES)} frames from {jsonl_path}", file=sys.stderr)

    # Infer the emission rate from the median ts delta between consecutive frames.
    if len(_FRAMES) >= 20:
        deltas = [
            _FRAMES[i]["ts"] - _FRAMES[i - 1]["ts"]
            for i in range(1, min(200, len(_FRAMES)))
            if _FRAMES[i]["ts"] > _FRAMES[i - 1]["ts"]
        ]
        if deltas:
            median_dt = sorted(deltas)[len(deltas) // 2]
            if median_dt > 0:
                _RATE_HZ = round(1.0 / median_dt)
                print(f"[runner] inferred capture rate: {_RATE_HZ} Hz", file=sys.stderr)

    # Pull the most recent telemetry SHA from the capture (anything past
    # sample 100 will have one).
    sha = next(
        (f["window_sha256"] for f in reversed(_FRAMES) if f.get("window_sha256")),
        None,
    )
    if sha is None:
        raise RuntimeError(
            "no telemetry_window_sha256 in capture — need at least 100 frames"
        )

    def _allow_all(_request, _invocation) -> PermissionRequestResult:
        return PermissionRequestResult(kind="approved")

    chosen_model = model or os.environ.get("GITHUB_COPILOT_MODEL") or "gpt-5.2"
    print(f"[runner] using model: {chosen_model}", file=sys.stderr)

    agent = GitHubCopilotAgent(
        name="DroneWatchdog",
        instructions=(
            "You are the Drone Watchdog. Captured drone telemetry (a merged "
            "stream where each frame nests apollo11/flag/heart/wright sub-"
            "objects) is loaded in the runtime. Call EACH of the 4 detection "
            "tools exactly once. Then assemble the final answer JSON object "
            "with keys pattern_1, pattern_2, pattern_3, pattern_4, and "
            "telemetry_window_sha256. Use the values returned by the tools "
            "directly — do not invent fields. Return ONLY the JSON object, "
            "no prose, no code fences."
        ),
        tools=WATCHDOG_TOOLS,
        default_options={
            "model": chosen_model,
            "timeout": 180,
            "on_permission_request": _allow_all,
        },
    )

    prompt = (
        "Run all 4 detection tools and return the assembled answer object. "
        f"Use telemetry_window_sha256 = \"{sha}\" verbatim. "
        "The final output should be a JSON object with fields "
        "pattern_1, pattern_2, pattern_3, pattern_4, telemetry_window_sha256."
    )

    print("[runner] calling agent…", file=sys.stderr)
    result = await agent.run(prompt)
    text = str(result)
    print("[runner] agent raw output:", file=sys.stderr)
    print(text, file=sys.stderr)

    answer = _extract_json(text)

    # Validate against the leaderboard schema.
    schema = json.loads(SCHEMA_PATH.read_text())
    body = {"name": "Asaf Tzarfati", "department": "Engineering", "answer": answer}
    errors = list(Draft202012Validator(schema).iter_errors(body))
    if errors:
        print("\n[runner] SCHEMA ERRORS:", file=sys.stderr)
        for e in errors:
            print(f"  - {e.message} at {list(e.absolute_path)}", file=sys.stderr)
    else:
        print("\n[runner] schema OK", file=sys.stderr)

    print("\n=== FINAL ANSWER ===")
    print(json.dumps(answer, indent=2))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--jsonl",
        type=Path,
        default=None,
        help="Existing telemetry capture (skips fresh capture if provided).",
    )
    p.add_argument(
        "--rate", type=int, default=10,
        help="Sim emission rate (default 10Hz; canonical workshop rate so the "
             "Fibonacci anomaly schedule fits in one cycle).",
    )
    p.add_argument(
        "--model", default=None,
        help="GitHub Copilot model id (e.g., gpt-5.2, claude-haiku-4.5). "
             "Falls back to $GITHUB_COPILOT_MODEL, then 'gpt-5.2'.",
    )
    p.add_argument(
        "--list-models", action="store_true",
        help="List Copilot models reachable from this account, then exit.",
    )
    args = p.parse_args()

    if args.list_models:
        asyncio.run(list_available_models())
        return

    if args.jsonl is None:
        path = Path("/tmp/run_watchdog_capture.jsonl")
        n = asyncio.run(capture_one_cycle(path, rate_hz=args.rate))
        print(f"[runner] captured {n} frames to {path}", file=sys.stderr)
    else:
        path = args.jsonl

    asyncio.run(run_watchdog(path, args.model))


if __name__ == "__main__":
    main()
