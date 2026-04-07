"""Cloudflare tunnel detection and management.

Probes cloudflared installation, login state, existing tunnels,
and manages access configuration in ~/.nio/config.yaml.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

NIO_HOME = Path.home() / ".nio"
CONFIG_PATH = NIO_HOME / "config.yaml"


def check_cloudflared_installed() -> Optional[str]:
    """Return path to cloudflared if installed, else None."""
    return shutil.which("cloudflared")


def check_cloudflared_logged_in() -> bool:
    """Return True if cloudflared is authenticated (can list tunnels)."""
    try:
        result = subprocess.run(
            ["cloudflared", "tunnel", "list"],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def list_tunnels() -> list[dict]:
    """Parse `cloudflared tunnel list` into [{"name": str, "id": str}]."""
    try:
        result = subprocess.run(
            ["cloudflared", "tunnel", "list", "--output", "json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
        import json
        tunnels = json.loads(result.stdout)
        return [{"name": t.get("name", ""), "id": t.get("id", "")} for t in tunnels]
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return []


def create_tunnel(name: str) -> bool:
    """Create a new Cloudflare tunnel. Returns True on success."""
    try:
        result = subprocess.run(
            ["cloudflared", "tunnel", "create", name],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_access_config() -> dict:
    """Read access config from ~/.nio/config.yaml. Defaults to local."""
    import yaml

    if not CONFIG_PATH.exists():
        return {"mode": "local"}
    try:
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f) or {}
        return config.get("access", {"mode": "local"})
    except Exception:
        return {"mode": "local"}


def write_access_config(
    mode: str, tunnel_name: str = "", tunnel_url: str = "",
) -> None:
    """Merge access config into ~/.nio/config.yaml, preserving other keys."""
    import yaml

    config = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            config = {}

    access = {"mode": mode}
    if tunnel_name:
        access["tunnel_name"] = tunnel_name
    if tunnel_url:
        access["tunnel_url"] = tunnel_url

    config["access"] = access

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def test_tunnel_reachable(url: str, timeout: int = 5) -> bool:
    """Hit https://{url}/health and return True if 200."""
    import urllib.request

    try:
        req = urllib.request.Request(f"https://{url}/health")
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status == 200
    except Exception:
        return False


def start_tunnel(
    tunnel_name: str = "", quick: bool = False,
) -> subprocess.Popen:
    """Start a Cloudflare tunnel as a background process."""
    if quick:
        cmd = ["cloudflared", "tunnel", "--url", "http://localhost:4242"]
    else:
        cmd = ["cloudflared", "tunnel", "run", tunnel_name]

    return subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def is_tunnel_running() -> bool:
    """Return True if a cloudflared process is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "cloudflared"],
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def stop_tunnel() -> None:
    """Kill all cloudflared processes."""
    subprocess.run(["pkill", "-f", "cloudflared"], capture_output=True)
