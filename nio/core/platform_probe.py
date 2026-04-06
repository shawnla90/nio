"""Platform detection and requirement checks.

Probes Hermes configuration to determine which platforms are configured,
connected, or available to set up.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

HERMES_HOME = Path.home() / ".hermes"
HERMES_ENV = HERMES_HOME / ".env"

PLATFORMS = {
    "discord": {
        "env_key": "DISCORD_BOT_TOKEN",
        "display": "Discord",
        "requires": "discord.py",
        "setup_url": "https://discord.com/developers/applications",
        "help": "Create a bot at discord.com/developers, copy the bot token.",
    },
    "telegram": {
        "env_key": "TELEGRAM_BOT_TOKEN",
        "display": "Telegram",
        "requires": "python-telegram-bot",
        "setup_url": "https://t.me/BotFather",
        "help": "Message @BotFather on Telegram, create a bot, copy the token.",
    },
    "whatsapp": {
        "env_key": "WHATSAPP_ENABLED",
        "display": "WhatsApp",
        "requires": "Node.js + Baileys",
        "setup_url": None,
        "help": "Requires Node.js. NIO will display a QR code to scan with your phone.",
    },
    "slack": {
        "env_key": "SLACK_BOT_TOKEN",
        "display": "Slack",
        "requires": "slack-bolt",
        "setup_url": "https://api.slack.com/apps",
        "help": "Create a Slack app, enable Socket Mode, copy the bot token.",
    },
    "signal": {
        "env_key": "SIGNAL_ACCOUNT",
        "display": "Signal",
        "requires": "signal-cli",
        "setup_url": None,
        "help": "Requires signal-cli binary. Link as a secondary device via QR code.",
    },
}


def _read_env() -> dict[str, str]:
    """Read key=value pairs from ~/.hermes/.env."""
    env = {}
    if not HERMES_ENV.exists():
        return env
    for line in HERMES_ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _write_env(key: str, value: str):
    """Write or update a key in ~/.hermes/.env."""
    HERMES_ENV.parent.mkdir(parents=True, exist_ok=True)
    env_lines = []
    replaced = False

    if HERMES_ENV.exists():
        for line in HERMES_ENV.read_text().splitlines():
            if line.strip().startswith(f"{key}="):
                env_lines.append(f'{key}="{value}"')
                replaced = True
            else:
                env_lines.append(line)

    if not replaced:
        env_lines.append(f'{key}="{value}"')

    HERMES_ENV.write_text("\n".join(env_lines) + "\n")


def probe_platform(platform: str) -> dict:
    """Check if a platform is configured.

    Returns: {"configured": bool, "token_set": bool, "display": str, "help": str}
    """
    info = PLATFORMS.get(platform, {})
    env = _read_env()
    env_key = info.get("env_key", "")
    token = env.get(env_key, "")

    return {
        "platform": platform,
        "display": info.get("display", platform),
        "configured": bool(token),
        "token_set": bool(token),
        "token_preview": f"{token[:6]}...{token[-4:]}" if len(token) > 10 else ("set" if token else ""),
        "requires": info.get("requires", ""),
        "setup_url": info.get("setup_url"),
        "help": info.get("help", ""),
    }


def probe_all() -> list[dict]:
    """Probe all platforms."""
    return [probe_platform(p) for p in PLATFORMS]


def configure_platform(platform: str, token: str):
    """Write a platform token to ~/.hermes/.env."""
    info = PLATFORMS.get(platform, {})
    env_key = info.get("env_key")
    if env_key:
        _write_env(env_key, token)


def check_hermes_installed() -> bool:
    """Check if Hermes is installed and gateway is available."""
    return HERMES_HOME.exists()


def check_whatsapp_bridge() -> Optional[Path]:
    """Check if the WhatsApp Baileys bridge is installed."""
    candidates = [
        Path.home() / "hermes-agent" / "scripts" / "whatsapp-bridge",
        HERMES_HOME / "whatsapp-bridge",
    ]
    for p in candidates:
        if (p / "bridge.js").exists() or (p / "package.json").exists():
            return p
    return None
