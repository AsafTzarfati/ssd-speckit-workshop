import asyncio
import json
import sys

import pytest
import websockets


async def test_sim_emits_valid_telemetry():
    """Boot the sim as a subprocess, connect, read 10 samples, validate."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "sim", "--port", "8766", "--rate", "1000",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.sleep(0.5)

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
