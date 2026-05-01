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
