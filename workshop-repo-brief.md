# Build Brief — Workshop SpecKit Repo

> **For Claude Code.** This is the public repo students clone for the Spec-Driven Development workshop. It is intentionally **almost empty** — the whole point of the workshop is that students populate it during the live session, driving GitHub Copilot's agent via SpecKit. Read end-to-end before writing any code.

---

## 1. Mission

Build a tiny scaffolding repo that:

1. Pulls in the `sim-drone` simulator as a pinned dependency
2. Initializes a `.specify/` directory so SpecKit commands work out of the box
3. Provides a Makefile students use during the workshop (`make sim`, `make watchdog`, `make verify`)
4. Ships a participant-facing README that walks them through pre-workshop setup
5. Has a smoke test that proves the sim is reachable and emitting valid telemetry

It must NOT:

- Contain any Watchdog implementation
- Pre-write the constitution, spec, plan, or task list
- Hint at the hidden patterns in the sim
- Suggest a Watchdog architecture in code, comments, or docs
- Vendor the sim source into this repo

This repo is **scaffolding**. Students fill it during the workshop. If you find yourself writing more than ~30 lines of Python total, you're over-building.

---

## 2. Hard Constraints

| | |
|---|---|
| Python version | 3.11+ |
| Build tool | Standard `pyproject.toml` (PEP 621), `pip install -e .` |
| SpecKit version | Current GitHub SpecKit (https://github.com/github/spec-kit), pinned by commit SHA — never track main |
| Sim dependency | `sim-drone` pinned to `v1.0.0` by git tag |
| Test framework | `pytest` + `pytest-asyncio`. Nothing else. |
| OS support | Linux + macOS. Windows-specific path handling not required. |

DO NOT:
- Pre-populate `.specify/memory/constitution.md`
- Pre-populate `specs/` with any spec
- Implement any part of the Watchdog
- Add a "starter" `main.py` or `__main__.py` to the watchdog package
- Add CI complexity beyond a single verify job
- Add pre-commit hooks, linters, or formatters (workshop participants don't need them in their way)

---

## 3. Layout

```
workshop-speckit/
├── pyproject.toml
├── Makefile
├── README.md                    # participant-facing — primary deliverable
├── .gitignore
├── .specify/                    # SpecKit-initialized, content empty
│   └── memory/
│       └── .gitkeep             # constitution.md authored during workshop
├── specs/                       # populated during workshop via /speckit.specify
│   └── .gitkeep
├── watchdog/                    # empty package; agent populates during workshop
│   └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_smoke.py            # the one integration test that proves setup works
├── scripts/
│   └── verify_setup.py          # called by `make verify`, prettier output
└── .github/
    └── workflows/
        └── verify.yml
```

Use a flat package layout (no `src/`). The repo is small enough that `src/` adds friction without benefit.

---

## 4. Dependencies

`pyproject.toml`:

```toml
[project]
name = "workshop-speckit"
version = "0.1.0"
description = "Spec-Driven Development workshop — student scaffolding"
requires-python = ">=3.11"
dependencies = [
    "sim-drone @ git+https://github.com/<REPLACE_ME_OWNER>/sim-drone.git@v1.0.0",
    "websockets>=12.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["watchdog*"]
```

Replace `<REPLACE_ME_OWNER>` with the actual GitHub owner before the first commit. Leave the placeholder as a literal string in your draft so the human can search-replace it once.

---

## 5. Makefile

```make
.PHONY: install sim watchdog verify test clean

install:
	pip install -e ".[dev]"

# Boot the simulator on its default port (Ctrl-C to stop)
sim:
	python -m sim

# Run the Watchdog. Will fail until students build it during the workshop —
# that is expected and intentional.
watchdog:
	python -m watchdog

# Pre-workshop sanity check. Students run this BEFORE arriving.
verify:
	@python scripts/verify_setup.py

test:
	pytest -q

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache *.egg-info build dist
```

No targets beyond these. Keep it readable for participants who'll glance at it on the day.

---

## 6. README.md — The Most Important File

This is what every participant reads. Most won't read anything else.

It must do exactly four things, in order:

1. Welcome them in one paragraph
2. List pre-workshop setup steps (numbered, copy-pasteable)
3. Tell them how to run `make verify` and what success looks like
4. Tell them what NOT to do, and why

Tone: friendly, direct, no fluff. English by default; the instructor can swap to Hebrew.

Required structure (use this verbatim, just adjust the placeholder URLs):

```markdown
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
git clone <THIS_REPO_URL>
cd workshop-speckit
pip install -e ".[dev]"
```

### 3. Verify your setup
```bash
make verify
```

You should see:
```
✓ Python 3.11+
✓ Sim package installed
✓ Sim boots and emits valid telemetry
✓ All checks passed — see you at the workshop
```

If any check fails, please ping the workshop channel before the day-of.

## During the workshop

You'll write the **Constitution**, **Spec**, **Plan**, and **Tasks** together
with the room. The Copilot agent will write the Watchdog code. You'll review
each diff before it's merged.

## What NOT to do

- **Don't read the simulator's source code.** The sim is a black-box dependency.
  Part of the workshop's discipline is using analysis — not source-reading —
  to understand what the system is emitting.
- **Don't write Watchdog code by hand.** The agent writes it. You drive the
  spec and review the output. That's the muscle this workshop is building.
- **Don't pre-write your constitution or spec.** We do that together, live.

See you on the day.
```

Every word is intentional. Don't editorialize. Don't add sections. Don't add badges. Don't add a contributors guide.

---

## 7. SpecKit Initialization

After the basic skeleton is in place, run SpecKit's init in this directory:

```bash
uvx --from git+https://github.com/github/spec-kit.git@<PINNED_SHA> specify init --here
```

(Replace `<PINNED_SHA>` with the current head of github/spec-kit at the time of build. Pin it. Workshop reproducibility depends on this.)

After init:

1. **Delete or empty** any seeded constitution / template files SpecKit creates in `.specify/memory/`. Students write the constitution from scratch during Phase 1 of the workshop.
2. Keep the directory structure SpecKit created.
3. Add `.gitkeep` files where needed so the empty directories survive `git add`.
4. Commit the result.

Verify by running `specify --help` — it should recognize the directory as initialized.

---

## 8. The `watchdog/` Package

Single file: `watchdog/__init__.py`, containing only one line:

```python
"""Watchdog package — populated during the workshop via SpecKit + Copilot agent."""
```

Do NOT add `main.py`, `__main__.py`, type stubs, abstract base classes, protocol definitions, or **any** structural hint about how the Watchdog should be built. The architecture emerges from the spec the room writes — that is the central pedagogical bet of the workshop.

`make watchdog` will fail with `ModuleNotFoundError` until students populate the package. That's correct. That's the point.

---

## 9. The Smoke Test

`tests/test_smoke.py`:

```python
import asyncio
import json
import pytest
import websockets


@pytest.mark.asyncio
async def test_sim_emits_valid_telemetry():
    """Boot the sim as a subprocess, connect, read 10 samples, validate."""
    proc = await asyncio.create_subprocess_exec(
        "python", "-m", "sim", "--port", "8766", "--rate", "1000",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.sleep(0.5)  # let the WS server bind

        async with websockets.connect("ws://localhost:8766") as ws:
            samples = []
            for _ in range(10):
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                samples.append(json.loads(msg))

        assert len(samples) == 10
        required_keys = {"drone_id", "seq", "ts", "altitude_m", "battery_pct", "motor_temp_c"}
        for s in samples:
            assert required_keys <= s.keys(), f"missing keys: {required_keys - s.keys()}"
            assert isinstance(s["motor_temp_c"], list)
            assert len(s["motor_temp_c"]) == 4

        seqs = [s["seq"] for s in samples]
        assert seqs == list(range(seqs[0], seqs[0] + 10)), f"non-contiguous seqs: {seqs}"

    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
```

`tests/conftest.py` adds `pytest-asyncio` strict mode:

```python
import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        if "asyncio" in item.keywords:
            continue
```

(Or use `pytest-asyncio`'s `mode = "auto"` in `pyproject.toml` — your call. Pick one and be consistent.)

---

## 10. The Verify Script

`scripts/verify_setup.py` — a friendly CLI for participants. Output should look exactly like the README claims:

```
✓ Python 3.11+
✓ Sim package installed
✓ Sim boots and emits valid telemetry
✓ All checks passed — see you at the workshop
```

Implementation:

1. Check `sys.version_info >= (3, 11)` → ✓ or ✗
2. `import sim` → ✓ or ✗
3. Boot sim as subprocess on a random free port, connect via WS, read 5 samples → ✓ or ✗
4. Print final status

On any ✗, exit non-zero with a one-line hint about what to do (`Please install Python 3.11+`, `Run pip install -e ".[dev]"`, etc.).

Keep it under 80 lines.

---

## 11. CI

`.github/workflows/verify.yml`:

```yaml
name: verify

on:
  push:
  pull_request:

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: pytest -q
      - run: python scripts/verify_setup.py
```

This is your tripwire for "did a sim release break the workshop repo?" — must always be green when you tag a workshop-ready version.

---

## 12. Acceptance Tests

The following must all pass from a fresh `git clone`:

```bash
git clone <repo>
cd workshop-speckit
pip install -e ".[dev]"
make verify       # exits 0, prints all ✓
make test         # exits 0
make sim &        # streams JSON
sleep 1
# manually verify with: wscat -c ws://localhost:8765
kill %1
```

Plus, by inspection:

| Check | Pass |
|---|---|
| `.specify/` exists and is initialized | yes |
| `.specify/memory/constitution.md` does NOT exist | yes |
| `specs/` is empty (just `.gitkeep`) | yes |
| `watchdog/__init__.py` is exactly one docstring | yes |
| README is participant-friendly | yes (subjective; ask a friend) |
| CI is green on `main` | yes |

---

## 13. Build Order

1. `pyproject.toml`, `.gitignore`, `Makefile`
2. `pip install -e ".[dev]"` from a fresh venv — verify the sim wheel pulls correctly from `git+https`. **If this step fails, stop. Do not proceed until the sim is publishable.**
3. Write `tests/test_smoke.py` and `tests/conftest.py` — make `pytest` pass
4. Write `scripts/verify_setup.py` — make `make verify` print all ✓
5. Run SpecKit init, scrub seeded content, commit
6. Create `watchdog/__init__.py`
7. Write the README
8. Add CI workflow
9. Final acceptance tests from a fresh clone — must all pass

---

## 14. Out of Scope

- Any Watchdog code (it's the workshop's deliverable, not yours)
- Architecture diagrams, design docs, or prose about how the Watchdog "should" work
- Pre-written constitution, spec, plan, or task list
- A reference Watchdog solution (lives in a separate repo or branch — different brief, different session)
- Workshop slides, talking points, or instructor notes
- Slack bots, registration tools, or participant communication
- Multi-language i18n for the README (instructor can fork and translate)

---

## 15. Done When

- A fresh `git clone` followed by `pip install -e ".[dev]" && make verify` exits 0 with all ✓
- `make sim` produces a working WebSocket stream a `wscat` client can read
- README is something a mid-level Python dev could follow without help
- CI is green on `main`
- No Watchdog code exists in this repo
- No constitution, spec, or plan files exist in this repo

When all that's true, you're done. The workshop will fill the rest.
