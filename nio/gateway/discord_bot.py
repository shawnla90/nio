"""NIO Discord gateway.

Lightweight Discord bot that responds via Ollama with NIO middleware.
No Hermes dependency. Runs as a standalone process.
"""

from __future__ import annotations

import os

import discord

from nio.core.antislop import detect, score
from nio.core.soul import get_active_soul, resolve_soul_with_inheritance
from nio.gateway.ollama import chat


class NIOBot(discord.Client):
    def __init__(self, model: str, ollama_host: str, allowed_users: set | None = None):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

        self.model = model
        self.ollama_host = ollama_host
        self.allowed_users = allowed_users
        self.conversations: dict[int, list] = {}
        self.system_prompt = ""
        self.session_id = None
        self.turn_index = 0

    async def on_ready(self):
        print(f"[nio] Discord bot online: {self.user}")
        print(f"[nio] Model: {self.model} @ {self.ollama_host}")

        # Load soul prompt
        soul_ref = get_active_soul()
        if soul_ref:
            soul_id = soul_ref.split("@")[0]
            try:
                resolved = resolve_soul_with_inheritance(soul_id)
                self.system_prompt = resolved.get("body", "")
                print(f"[nio] Soul loaded: {soul_ref}")
            except Exception:
                print(f"[nio] Could not load soul: {soul_ref}")

        # Start NIO session
        try:
            from nio.claude_code.session_bridge import start_cc_session
            self.session_id = start_cc_session(
                soul_id=soul_ref.split("@")[0] if soul_ref else "",
                soul_version=soul_ref.split("@")[1] if soul_ref and "@" in soul_ref else "",
            )
            print(f"[nio] Session: {self.session_id[:8]}...")
        except Exception:
            pass

        print("[nio] Listening for messages...\n")

    async def on_message(self, message: discord.Message):
        # Ignore own messages
        if message.author == self.user:
            return

        # Check allowed users
        if self.allowed_users and str(message.author.id) not in self.allowed_users:
            return

        # Respond to DMs or mentions
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mention = self.user in message.mentions if self.user else False
        is_nio = message.content.lower().startswith("nio")

        if not (is_dm or is_mention or is_nio):
            return

        text = message.content
        # Strip mention/prefix
        if is_mention and self.user:
            text = text.replace(f"<@{self.user.id}>", "").strip()
        if is_nio:
            text = text[3:].strip()

        if not text:
            return

        channel_id = message.channel.id
        print(f"[nio] <- {message.author}: {text[:80]}")

        # Typing indicator
        async with message.channel.typing():
            # Build history
            history = self.conversations.get(channel_id, [])[-10:]

            # Call Ollama
            try:
                response = chat(
                    message=text,
                    system_prompt=self.system_prompt,
                    model=self.model,
                    host=self.ollama_host,
                    history=history,
                )
            except Exception as e:
                response = f"Error reaching model: {e}"
                print(f"[nio] ERROR: {e}")

            # Anti-slop
            slop_score = score(response)
            violations = detect(response)
            if violations:
                v_names = ", ".join(v["id"] for v in violations[:3])
                print(f"[nio] slop: {slop_score:.0f}/100 [{v_names}]")

            # Store history
            if channel_id not in self.conversations:
                self.conversations[channel_id] = []
            self.conversations[channel_id].append({"role": "user", "content": text})
            self.conversations[channel_id].append({"role": "assistant", "content": response})
            if len(self.conversations[channel_id]) > 20:
                self.conversations[channel_id] = self.conversations[channel_id][-20:]

            # Record turn
            self.turn_index += 1
            try:
                from nio.claude_code.session_bridge import record_cc_turn
                if self.session_id:
                    record_cc_turn(
                        session_id=self.session_id,
                        user_msg=text,
                        agent_msg=response,
                        turn_index=self.turn_index,
                    )
            except Exception:
                pass

        # Send response (split if over 2000 chars)
        print(f"[nio] -> ({slop_score:.0f}/100): {response[:80]}")
        for i in range(0, len(response), 2000):
            await message.reply(response[i:i + 2000], mention_author=False)


def start(
    model: str = "gemma2",
    ollama_host: str = "http://localhost:11434",
    token: str = "",
    allowed_users: str = "",
):
    """Start the NIO Discord bot."""
    if not token:
        token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        # Read from hermes .env
        env_path = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_path):
            for line in open(env_path):
                if line.strip().startswith("DISCORD_BOT_TOKEN"):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not token:
        print("[nio] ERROR: No Discord token. Set DISCORD_BOT_TOKEN or run nio setup platforms")
        return

    users = set(allowed_users.split(",")) if allowed_users else None
    bot = NIOBot(model=model, ollama_host=ollama_host, allowed_users=users)
    bot.run(token)
