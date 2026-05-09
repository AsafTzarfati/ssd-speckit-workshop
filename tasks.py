"""Cross-platform task runner. Replaces the old Makefile so Windows students
don't need GNU Make / WSL just to run the workshop.

Usage:
    python tasks.py <command>
    python tasks.py --help

Commands match the former Makefile targets one-for-one.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _run(*cmd: str) -> int:
    """Run a subprocess and return its exit code (no exception on non-zero)."""
    return subprocess.run(cmd, cwd=ROOT).returncode


def cmd_install(_args: argparse.Namespace) -> int:
    return _run(sys.executable, "-m", "pip", "install", "-e", ".[dev]")


def cmd_sim(_args: argparse.Namespace) -> int:
    return _run(sys.executable, "-m", "sim")


def cmd_login(_args: argparse.Namespace) -> int:
    sys.path.insert(0, str(ROOT))
    from github_auth import CopilotAuth

    auth = CopilotAuth()
    if auth.is_logged_in():
        print(f"Already logged in as {auth.username}.")
    else:
        auth.login()
    return 0


def cmd_verify(_args: argparse.Namespace) -> int:
    return _run(sys.executable, str(ROOT / "scripts" / "verify_setup.py"))


def cmd_test(_args: argparse.Namespace) -> int:
    return _run(sys.executable, "-m", "pytest", "-q")


def cmd_clean(_args: argparse.Namespace) -> int:
    for pycache in ROOT.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)
    for path in [ROOT / ".pytest_cache", ROOT / "build", ROOT / "dist"]:
        shutil.rmtree(path, ignore_errors=True)
    for egg in ROOT.glob("*.egg-info"):
        shutil.rmtree(egg, ignore_errors=True)
    return 0


COMMANDS = {
    "install": (cmd_install, 'pip install -e ".[dev]"'),
    "sim":     (cmd_sim,     "Boot the drone simulator (Ctrl-C to stop)"),
    "login":   (cmd_login,   "One-time GitHub Copilot device-flow login"),
    "verify":  (cmd_verify,  "Pre-workshop sanity check"),
    "test":    (cmd_test,    "Run the pytest suite"),
    "clean":   (cmd_clean,   "Remove __pycache__/.pytest_cache/*.egg-info/build/dist"),
}


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python tasks.py",
        description="Workshop task runner. Replaces the old Makefile.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="COMMAND")
    for name, (handler, help_text) in COMMANDS.items():
        p = sub.add_parser(name, help=help_text)
        p.set_defaults(func=handler)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
