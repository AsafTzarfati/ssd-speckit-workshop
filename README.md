# Spec-Driven Development Workshop

Welcome. In this 4-hour hands-on workshop, you'll build an AI Telemetry
Watchdog using GitHub SpecKit, GitHub Copilot's agent mode, and a drone
telemetry simulator that's already installed for you.

You'll spend most of the workshop writing specs, not code. The Copilot agent
writes the code. You review it, correct it, and merge it.

## Before the workshop

Please complete these steps **before** you arrive. If verification fails on
the day, you'll lose the first 30 minutes of the session.

### 1. Tools you need
- **Python 3.11 or newer** — check with `python --version`
- **Git**
- **VS Code or Cursor** with the GitHub Copilot extension installed
- **GitHub Copilot** subscription with **agent mode** enabled
- A working terminal — Linux or macOS

### 2. Clone and install
```bash
git clone https://github.com/AsafTzarfati/ssd-speckit-workshop.git
cd ssd-speckit-workshop
pip install -e ".[dev]"
```

This installs Microsoft's [agent-framework](https://github.com/microsoft/agent-framework)
(`pip install agent-framework`) as the runtime for your Watchdog. You'll define the
Watchdog as an `Agent` with `Tool`s for telemetry analysis, and orchestrate the
discovery of patterns via a `Workflow`. See the
[agent-framework docs](https://github.com/microsoft/agent-framework) for the
`Agent` / `Tool` / `Workflow` abstractions.

### 3. Log in to GitHub Copilot
The Watchdog you'll build calls the GitHub Copilot API directly. You need
to authorize this repo against your Copilot account **once**. The OAuth
token is saved locally to `.copilot_token.json` (gitignored) so you won't
be prompted again.

```bash
make login
```

You'll be shown a code and a URL. Open the URL in your browser, paste the
code, and approve. When you see `Logged in as <your-github-handle>` you're
done.

> Requires an active GitHub Copilot subscription (Individual, Business, or
> Enterprise). If you already have `GITHUB_TOKEN` set in your environment
> with `read:user` scope, that's used automatically and `make login` is a no-op.

### 4. Verify your setup
```bash
make verify
```

You should see:
```
✓ Python 3.11+
✓ Sim package installed
✓ Sim boots and emits valid telemetry
✓ Copilot auth module ready
✓ All checks passed — see you at the workshop
```

If any check fails, please ping the workshop channel before the day-of.

## Submission contract

Your Watchdog discovers up to 4 hidden patterns in the telemetry stream and
posts its findings to the workshop leaderboard. The submission body must
match [`specs/submission_schema.json`](specs/submission_schema.json) — every
team's agent emits the same shape so grading is fair across runs.

Each pattern gets its own object inside `answer.pattern_N`. Numeric/structural
fields (bounding box, lag in samples, etc.) are graded deterministically
with tolerance bands. Each pattern also takes a free-text `label`; the
leaderboard normalizes it and matches against an alias dictionary, so
descriptions like "Israeli flag", "Star of David", or "hexagram" all score
the same as long as your structural fields are correct.

> **Tip — Pattern 1 is a visual shape.** Plot lat vs lon over the full
> flight and look at the trace before you try to label it. The
> `components` field expects lowercase tokens for the sub-shapes you
> see (e.g. `stripes`, `hexagram`).

Partial credit is awarded per pattern — submit what you've solved, skip what
you haven't.

## During the workshop

You'll write the **Constitution**, **Spec**, **Plan**, and **Tasks** together
with the room. The Copilot agent will write the Watchdog code. You'll review
each diff before it's merged.

### Capturing telemetry

Each scenario in the sim is **finite** — the simulator emits a fixed
number of frames, then closes the websocket with `1001 going away`.
A naive read loop will crash on that. Use the helper we ship instead:

```bash
python scripts/capture.py --out telemetry.jsonl
```

`scripts/capture.py` reconnects forever — when the sim closes, it
restarts the subprocess and keeps appending frames to the JSONL file.
Hit `Ctrl-C` when you have enough data.

### Building the Watchdog with Microsoft agent-framework

The Watchdog is implemented as an **Agent** powered by Microsoft's
[agent-framework](https://github.com/microsoft/agent-framework). The chat
client is wired to the Copilot API (via the `github_auth.py` module), so
your `read:user` Copilot token is the only credential you need — no Azure
/ OpenAI key required.

A runnable starting point lives in
[`examples/watchdog_skeleton.py`](examples/watchdog_skeleton.py); copy it
into your repo and grow it under your spec/plan. The shape is:

```python
from agent_framework import tool, Agent
from github_auth import CopilotAuth

auth = CopilotAuth()  # already logged in via `make login`

# 1. Define Tools — pure analytical functions over the captured frames.
#    The `@tool` decorator wraps the function as a FunctionTool the agent
#    can call. Use `Annotated[..., "doc"]` to document parameters.
@tool(name="detect_geospatial_shape",
      description="Plot lat/lon, return bbox + components.")
def detect_geospatial_shape(frames: list[dict]) -> dict: ...

# 2. Two ways to call a tool:
#    a) directly (sync) — useful for tests / local analysis:
#       result = detect_geospatial_shape.func(frames=frames)
#    b) via the agent (async, with arguments=) — used at run time:
#       result = await detect_geospatial_shape.invoke(arguments={"frames": frames})

# 3. Wire the agent (full code in examples/watchdog_skeleton.py)
watchdog = Agent(
    name="DroneWatchdog",
    instructions="...",
    tools=[detect_geospatial_shape, ...],
)
```

Things the framework gives you for free that the spec should leverage:
**streaming**, **checkpointing** (so a long capture isn't lost on a crash),
and **human-in-the-loop** (confirm a borderline label before submitting).

## What NOT to do

- **Don't read the simulator's source code.** The sim is a black-box dependency.
  Part of the workshop's discipline is using analysis — not source-reading —
  to understand what the system is emitting.
- **Don't write Watchdog code by hand.** The agent writes it. You drive the
  spec and review the output. That's the muscle this workshop is building.
- **Don't pre-write your constitution or spec.** We do that together, live.

See you on the day.
