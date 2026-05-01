"""Pre-workshop sanity check. Students run this BEFORE arriving."""
import asyncio
import importlib.util
import json
import socket
import sys


def fail(msg: str, hint: str) -> None:
    print(f"✗ {msg}")
    print(f"  → {hint}")
    sys.exit(1)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


async def connect_with_retry(uri: str, attempts: int = 20):
    import websockets

    last_err: Exception | None = None
    for _ in range(attempts):
        try:
            return await websockets.connect(uri)
        except (OSError, ConnectionError) as e:
            last_err = e
            await asyncio.sleep(0.25)
    raise last_err if last_err else RuntimeError("could not connect")


async def boot_and_read(port: int) -> None:
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "sim", "--port", str(port), "--rate", "1000",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        ws = await connect_with_retry(f"ws://localhost:{port}")
        try:
            for _ in range(5):
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                json.loads(msg)
        finally:
            await ws.close()
    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()


def main() -> None:
    if sys.version_info < (3, 11):
        fail("Python 3.11+", "Please install Python 3.11 or newer.")
    print("✓ Python 3.11+")

    if importlib.util.find_spec("sim") is None:
        fail("Sim package installed", 'Run: pip install -e ".[dev]"')
    print("✓ Sim package installed")

    try:
        asyncio.run(boot_and_read(free_port()))
    except Exception as e:
        fail("Sim boots and emits valid telemetry", f"Sim probe failed: {e}")
    print("✓ Sim boots and emits valid telemetry")

    if importlib.util.find_spec("requests") is None:
        fail("Copilot auth module ready", 'Run: pip install -e ".[dev]"')
    try:
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from github_auth import CopilotAuth  # noqa: F401
    except Exception as e:
        fail("Copilot auth module ready", f"Could not import github_auth: {e}")
    print("✓ Copilot auth module ready")

    print("✓ All checks passed — see you at the workshop")


if __name__ == "__main__":
    main()
