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
- IDE with the GitHub Copilot extension installed
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
fields are graded deterministically with tolerance bands. Each pattern also
takes a free-text `label`; the leaderboard normalizes it and matches against
an alias dictionary, so a few different phrasings all score the same as long
as your structural fields are correct.

Partial credit is awarded per pattern — submit what you've solved, skip what
you haven't.

## During the workshop

You'll write the **Constitution**, **Spec**, **Plan**, and **Tasks** together
with the room. The Copilot agent will write the Watchdog code. You'll review
each diff before it's merged.

### Capturing telemetry

The sim emits a **merged telemetry stream** — each WebSocket frame is a
JSON object with top-level metadata (`drone_id`, `seq`, `ts`,
`window_sha256`) plus several nested sub-objects, each carrying its own
per-tick telemetry (lat/lon, altitude, flight_mode, currents, motor temps,
…). Inspect a frame to learn the exact keys.

Figuring out which sub-object hosts each pattern is part of the workshop —
not every sub-object is meaningful. The stream is **finite** and the
simulator closes the websocket with `1001 going away` at the end. A naive
read loop will crash on that. Use the helper we ship instead:

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

A minimal starting point — just the wiring (auth, agent construction,
permission handler) without any pattern-specific code — lives in
[`examples/watchdog_skeleton.py`](examples/watchdog_skeleton.py). Copy it
into your repo and grow the tools under your own spec/plan. The shape is:

```python
from agent_framework import tool, Agent
from github_auth import CopilotAuth

auth = CopilotAuth()  # already logged in via `make login`

# 1. Define Tools — pure analytical functions over the captured frames.
#    The `@tool` decorator wraps the function as a FunctionTool the agent
#    can call. Use `Annotated[..., "doc"]` to document parameters.
@tool(name="my_pattern_detector",
      description="Inspect captured frames and return the structured findings your spec calls for.")
def my_pattern_detector(frames: list[dict]) -> dict: ...

# 2. Two ways to call a tool:
#    a) directly (sync) — useful for tests / local analysis:
#       result = my_pattern_detector.func(frames=frames)
#    b) via the agent (async, with arguments=) — used at run time:
#       result = await my_pattern_detector.invoke(arguments={"frames": frames})

# 3. Wire the agent
watchdog = Agent(
    name="DroneWatchdog",
    instructions="...",
    tools=[my_pattern_detector, ...],
)
```

Things the framework gives you for free that the spec should leverage:
**streaming**, **checkpointing** (so a long capture isn't lost on a crash),
and **human-in-the-loop** (confirm a borderline label before submitting).

To list the models your Copilot account can call from the agent:

```bash
python -c "from github_auth import CopilotAuth; \
  [print(m.id) for m in CopilotAuth().chat_client().list_models() \
    if getattr(m, 'capabilities', None) and m.capabilities.type == 'chat']"
```

### Common errors

Four ways the agent will silently misbehave if you're not paying attention:

1. **`400 The requested model is not supported`** — your Copilot
   subscription doesn't grant the model you asked for. The default in
   the skeleton is `gpt-5.2`. Override with `--model …` or
   `GITHUB_COPILOT_MODEL=…`. Note that `client.list_models()` shows
   `policy.state == 'enabled'` for models the API may still reject;
   `enabled` is necessary but not sufficient. Try a few.
2. **Tool returns `Permission denied and could not request permission
   from user`** — the SDK's default `on_permission_request` denies
   every request. The skeleton ships an `_allow_all` handler; if you
   strip it or write your own, remember to return
   `PermissionRequestResult(kind="approved")` for the calls you want
   to permit.
3. **Capture ends after ~120 frames at rate=10** — the `comm_loss`
   anomaly suppresses 5 seconds of frames. If your read-loop's recv
   timeout is `<= 5s` it'll quit mid-cycle. `scripts/capture.py` uses
   10s; if you write your own loop, do at least the same.
4. **Schema rejects a `null` on a nullable integer field** — some
   fields are typed `integer | null`. If you build the JSON by hand
   make sure not to emit a stray Python `None` that serializes to a
   different shape (e.g. JS `undefined` from a TypeScript port).
   Omitting the key entirely is also valid for optional fields.

## What NOT to do

- **Don't read the simulator's source code.** The sim is a black-box dependency.
  Part of the workshop's discipline is using analysis — not source-reading —
  to understand what the system is emitting.
- **Don't write Watchdog code by hand.** The agent writes it. You drive the
  spec and review the output. That's the muscle this workshop is building.
- **Don't pre-write your constitution or spec.** We do that together, live.

See you on the day.
