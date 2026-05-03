"""Capture telemetry to a JSONL file. Reconnects forever — Ctrl-C to stop.

The sim is finite: each scenario emits a fixed number of frames then closes
the websocket with `1001 going away`. We treat that as "scenario over",
restart the sim subprocess, reconnect, and keep appending frames.

Usage:
    python scripts/capture.py --out telemetry.jsonl
    python scripts/capture.py --out telemetry.jsonl --port 8770 --rate 50
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import signal
import sys
from pathlib import Path

import websockets
from websockets.exceptions import ConnectionClosed

# Reuse the same retry helper used by verify_setup.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_setup import connect_with_retry  # noqa: E402


async def _spawn_sim(port: int, rate: str) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        sys.executable, "-m", "sim", "--port", str(port), "--rate", rate,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )


async def _kill(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=2.0)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()


async def capture(out_path: Path, port: int, rate: str) -> None:
    total = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"capturing to {out_path} (Ctrl-C to stop)", file=sys.stderr)

    with open(out_path, "w") as f:
        while True:
            proc = await _spawn_sim(port, rate)
            try:
                ws = await connect_with_retry(f"ws://localhost:{port}")
                this_run = 0
                try:
                    while True:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        except ConnectionClosed:
                            break
                        f.write(msg + "\n")
                        f.flush()
                        this_run += 1
                        total += 1
                finally:
                    await ws.close()
                print(
                    f"scenario ended ({this_run} frames; total={total}) "
                    f"— restarting sim",
                    file=sys.stderr,
                )
            finally:
                await _kill(proc)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path("telemetry.jsonl"))
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--rate", default="10")
    args = p.parse_args()

    loop = asyncio.new_event_loop()
    task = loop.create_task(capture(args.out, args.port, args.rate))

    def _stop(*_):
        task.cancel()

    loop.add_signal_handler(signal.SIGINT, _stop)
    loop.add_signal_handler(signal.SIGTERM, _stop)

    with contextlib.suppress(asyncio.CancelledError, KeyboardInterrupt):
        loop.run_until_complete(task)
    loop.close()
    print("\nstopped", file=sys.stderr)


if __name__ == "__main__":
    main()
