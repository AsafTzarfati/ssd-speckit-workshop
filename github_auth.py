"""GitHub Copilot OAuth — drop-in auth module for the workshop.

Usage:
    from github_auth import CopilotAuth

    auth = CopilotAuth()          # loads saved token automatically
    if not auth.is_logged_in():
        auth.login()              # runs device flow (one-time)

    # Use this before every API call — it auto-refreshes the JWT
    jwt = auth.get_jwt()
    headers = auth.get_headers()  # ready-to-use headers dict
"""

import json
import os
import time
import webbrowser
from pathlib import Path

import requests

# Public Client ID used by Copilot editor plugins — no app registration needed.
CLIENT_ID = "Iv1.b507a08c87ecfe98"

COPILOT_CHAT_URL = "https://api.githubcopilot.com/chat/completions"

# These headers are required — the Copilot API checks them.
REQUIRED_HEADERS = {
    "User-Agent": "GithubCopilot/1.155.0",
    "Editor-Version": "Neovim/0.9.5",
    "Editor-Plugin-Version": "copilot.vim/1.16.0",
    "Copilot-Integration-Id": "vscode-chat",
    "Openai-Intent": "conversation-panel",
    "Openai-Organization": "github-copilot",
}

TOKEN_FILE = Path(__file__).parent / ".copilot_token.json"


class CopilotAuth:
    def __init__(self, token_file: Path = TOKEN_FILE):
        self._token_file = token_file
        self._oauth_token: str | None = None
        self._username: str | None = None
        self._jwt: str | None = None
        self._jwt_expires_at: float = 0
        self._chat_url: str = COPILOT_CHAT_URL

        self._load_saved_token()

    def is_logged_in(self) -> bool:
        return self._oauth_token is not None and self._username is not None

    def login(self) -> str:
        """Run the device flow. Returns the GitHub username.

        One-time interactive step. The OAuth token is then saved to disk.
        """
        resp = requests.post(
            "https://github.com/login/device/code",
            headers={"Accept": "application/json"},
            json={"client_id": CLIENT_ID, "scope": "read:user"},
        )
        resp.raise_for_status()
        data = resp.json()

        device_code = data["device_code"]
        user_code = data["user_code"]
        verification_uri = data["verification_uri"]
        interval = data["interval"]

        print(f"\n  Go to:  {verification_uri}")
        print(f"  Enter:  {user_code}\n")
        webbrowser.open(verification_uri)

        print("  Waiting for authorization...", end="", flush=True)
        self._oauth_token = self._poll_for_token(device_code, interval)

        self._username = self._validate_token(self._oauth_token)
        self._save_token()
        print(f"\n  Logged in as {self._username}\n")
        return self._username

    def logout(self):
        self._oauth_token = None
        self._username = None
        self._jwt = None
        self._jwt_expires_at = 0
        if self._token_file.exists():
            self._token_file.unlink()

    def get_jwt(self) -> str:
        """Get a valid Copilot JWT, refreshing if it's about to expire."""
        if not self._oauth_token:
            raise RuntimeError("Not logged in. Call login() first.")

        if time.time() > self._jwt_expires_at - 60:
            self._refresh_jwt()

        return self._jwt

    def get_headers(self) -> dict:
        """Complete headers for a Copilot API call."""
        return {
            "Authorization": f"Bearer {self.get_jwt()}",
            "Content-Type": "application/json",
            **REQUIRED_HEADERS,
        }

    @property
    def chat_url(self) -> str:
        return self._chat_url

    @property
    def username(self) -> str | None:
        return self._username

    def _save_token(self):
        self._token_file.write_text(
            json.dumps({"token": self._oauth_token, "user": self._username})
        )

    def _load_saved_token(self):
        env_token = os.environ.get("GITHUB_TOKEN")
        if env_token:
            username = self._validate_token(env_token)
            if username:
                self._oauth_token = env_token
                self._username = username
                return

        if not self._token_file.exists():
            return

        try:
            data = json.loads(self._token_file.read_text())
            token = data["token"]
        except (json.JSONDecodeError, KeyError):
            return

        username = self._validate_token(token)
        if username:
            self._oauth_token = token
            self._username = username

    def _poll_for_token(self, device_code: str, interval: int) -> str:
        poll_interval = interval
        deadline = time.time() + 900

        while time.time() < deadline:
            time.sleep(poll_interval)
            print(".", end="", flush=True)

            resp = requests.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                json={
                    "client_id": CLIENT_ID,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )
            data = resp.json()

            if "access_token" in data:
                return data["access_token"]

            error = data.get("error", "")
            if error == "authorization_pending":
                continue
            elif error == "slow_down":
                poll_interval += 5
            elif error == "expired_token":
                raise RuntimeError("Device code expired. Try again.")
            elif error == "access_denied":
                raise RuntimeError("User denied authorization.")
            else:
                raise RuntimeError(f"Unexpected: {data}")

        raise RuntimeError("Timed out waiting for authorization.")

    def _validate_token(self, token: str) -> str | None:
        resp = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/json",
                "User-Agent": "GithubCopilot/1.155.0",
            },
            timeout=10,
        )
        if not resp.ok:
            return None
        return resp.json().get("login")

    def _refresh_jwt(self):
        resp = requests.get(
            "https://api.github.com/copilot_internal/v2/token",
            headers={
                "Authorization": f"token {self._oauth_token}",
                "Accept": "application/json",
                "User-Agent": "GithubCopilot/1.155.0",
                "Editor-Version": "Neovim/0.9.5",
                "Editor-Plugin-Version": "copilot.vim/1.16.0",
            },
            timeout=10,
        )
        if not resp.ok:
            raise RuntimeError(
                f"Copilot token exchange failed: {resp.status_code}\n"
                "Make sure this GitHub account has an active Copilot subscription."
            )
        data = resp.json()
        self._jwt = data["token"]
        self._jwt_expires_at = float(data["expires_at"])
        api_base = data.get("endpoints", {}).get("api", "").rstrip("/")
        if api_base:
            self._chat_url = f"{api_base}/chat/completions"
