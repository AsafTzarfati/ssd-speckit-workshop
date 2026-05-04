"""Watchdog skeleton — copy this into your repo and grow it under your spec.

This file is intentionally minimal. It shows ONLY the wiring (auth, agent
construction, permission handler, one example tool) so you can run the
agent end-to-end. The pattern-detection tools are your job — write them
under your spec/plan, not by reading hints here.

The sim emits a *merged* telemetry stream: every frame is a JSON object
with top-level metadata (`drone_id`, `seq`, `ts`, `window_sha256`) and
several nested sub-objects, each carrying its own per-tick telemetry
(altitude, lat/lon, flight_mode, current, motor temps, …). Inspect a
frame to learn the exact keys — figuring out which sub-object hosts
each pattern is part of the workshop.

Things students will get wrong without a starting point:

1. The decorator is `@tool` (NOT `@ai_function` or `@Tool`).
2. There are two ways to call a FunctionTool:
   - direct/sync   — `result = my_tool.func(frames=frames)`
   - via the agent — `await my_tool.invoke(arguments={"frames": frames})`
   The first is what your unit tests should use; the second is what runs
   when the agent decides to call the tool.
3. The default `on_permission_request` denies every tool call silently.
   You MUST pass an approving handler — see `make_agent()` below.
4. The default model may not be enabled on your Copilot subscription.
   Pass `--model …` (or set `GITHUB_COPILOT_MODEL`) to choose one
   `client.list_models()` shows as enabled.

Run end-to-end after producing telemetry.jsonl with scripts/capture.py:

    python scripts/capture.py --out telemetry.jsonl   # Ctrl-C after a while
    python examples/watchdog_skeleton.py telemetry.jsonl
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Annotated

from agent_framework import tool
from agent_framework_github_copilot import GitHubCopilotAgent
from copilot.session import PermissionRequestResult


def load(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f]


@tool(
    name="summarize_frames",
    description="Return basic structural facts about the captured telemetry — frame count, seq range, the keys present on each frame. Use this to orient yourself before writing real detectors.",
)
def summarize_frames(
    frames: Annotated[list[dict], "Captured merged-stream telemetry frames."],
) -> dict:
    if not frames:
        return {"frame_count": 0}
    seqs = [f.get("seq") for f in frames if "seq" in f]
    top_keys = sorted({k for f in frames for k in f.keys()})
    sub_keys: dict[str, list[str]] = {}
    for k in top_keys:
        first_val = next((f[k] for f in frames if isinstance(f.get(k), dict)), None)
        if first_val is not None:
            sub_keys[k] = sorted(first_val.keys())
    return {
        "frame_count": len(frames),
        "seq_min": min(seqs) if seqs else None,
        "seq_max": max(seqs) if seqs else None,
        "top_level_keys": top_keys,
        "nested_sub_object_keys": sub_keys,
    }


# Add your own pattern-detection tools here. Each tool should:
#   - take `frames: list[dict]` (the captured merged-stream telemetry)
#   - return a dict matching the corresponding `answer.pattern_N` shape
#     in specs/submission_schema.json.
WATCHDOG_TOOLS = [
    summarize_frames,
    # detect_pattern_1, ...
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
            "(merged stream), call your detection tools and assemble an "
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
    return {tool.name: tool.func(frames=frames) for tool in WATCHDOG_TOOLS}


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
