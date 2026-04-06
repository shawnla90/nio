"""NIO Gateway runner.

Lightweight message loop: WhatsApp bridge -> Ollama -> NIO middleware -> reply.
No Hermes dependency. Runs as a standalone process.

Usage:
    nio gateway start
    nio gateway start --model gemma2:2b --ollama-host http://mac-mini:11434
"""

from __future__ import annotations

import signal
import sys
import time

_running = True


def _handle_signal(sig, frame):
    global _running
    _running = False
    print("\n[nio] Shutting down gateway...")


def start(
    model: str = "gemma2",
    ollama_host: str = "http://localhost:11434",
    bridge_url: str = "http://localhost:3000",
    poll_interval: float = 1.0,
):
    """Start the NIO gateway message loop.

    Polls WhatsApp bridge for messages, sends to Ollama with soul prompt,
    runs anti-slop scoring, sends response back.
    """
    from nio.core.antislop import detect, score
    from nio.core.soul import get_active_soul, resolve_soul_with_inheritance
    from nio.gateway.ollama import chat, check_health, list_models
    from nio.gateway.whatsapp import check_bridge, poll_messages, send_message, send_typing

    global _running
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    print("[nio] Gateway starting...")
    print(f"[nio] Model: {model} @ {ollama_host}")
    print(f"[nio] Bridge: {bridge_url}")

    # Check Ollama
    if not check_health(ollama_host):
        print(f"[nio] ERROR: Ollama not reachable at {ollama_host}")
        print("[nio] Run: ollama serve")
        sys.exit(1)

    models = list_models(ollama_host)
    if not any(model in m for m in models):
        print(f"[nio] WARNING: Model '{model}' not found. Available: {models}")
        print(f"[nio] Run: ollama pull {model}")
        sys.exit(1)

    print(f"[nio] Ollama OK. Models: {', '.join(models)}")

    # Check WhatsApp bridge
    if not check_bridge(bridge_url):
        print(f"[nio] WARNING: WhatsApp bridge not reachable at {bridge_url}")
        print("[nio] Messages will queue until bridge starts.")

    # Load soul prompt
    system_prompt = ""
    soul_ref = get_active_soul()
    if soul_ref:
        soul_id = soul_ref.split("@")[0]
        try:
            resolved = resolve_soul_with_inheritance(soul_id)
            system_prompt = resolved.get("body", "")
            print(f"[nio] Soul loaded: {soul_ref}")
        except Exception:
            print(f"[nio] Could not load soul: {soul_ref}")

    # Track conversations (chat_id -> message history)
    conversations: dict[str, list] = {}

    print("[nio] Listening for messages...\n")

    # Session tracking
    session_id = None
    try:
        from nio.claude_code.session_bridge import start_cc_session
        session_id = start_cc_session(
            soul_id=soul_ref.split("@")[0] if soul_ref else "",
            soul_version=soul_ref.split("@")[1] if soul_ref and "@" in soul_ref else "",
        )
        print(f"[nio] Session: {session_id[:8]}...")
    except Exception:
        pass

    turn_index = 0

    while _running:
        messages = poll_messages(bridge_url, timeout=10)

        for msg in messages:
            chat_id = msg.get("chatId", "")
            text = msg.get("text", "") or msg.get("message", "")
            sender = msg.get("sender", chat_id)

            if not text or not chat_id:
                continue

            print(f"[nio] <- {sender[:20]}: {text[:80]}")

            # Send typing indicator
            send_typing(chat_id, bridge_url)

            # Build conversation history
            if chat_id not in conversations:
                conversations[chat_id] = []

            history = conversations[chat_id][-10:]  # Keep last 10 turns

            # Call Ollama
            try:
                response = chat(
                    message=text,
                    system_prompt=system_prompt,
                    model=model,
                    host=ollama_host,
                    history=history,
                )
            except Exception as e:
                response = f"Sorry, I hit an error: {e}"
                print(f"[nio] ERROR: {e}")

            # Run anti-slop
            slop_score = score(response)
            violations = detect(response)
            if violations:
                v_names = ", ".join(v["id"] for v in violations[:3])
                print(f"[nio] slop: {slop_score:.0f}/100 [{v_names}]")

            # Store in conversation history
            conversations[chat_id].append({"role": "user", "content": text})
            conversations[chat_id].append({"role": "assistant", "content": response})

            # Trim history
            if len(conversations[chat_id]) > 20:
                conversations[chat_id] = conversations[chat_id][-20:]

            # Record turn in NIO
            turn_index += 1
            try:
                from nio.claude_code.session_bridge import record_cc_turn
                if session_id:
                    record_cc_turn(
                        session_id=session_id,
                        user_msg=text,
                        agent_msg=response,
                        turn_index=turn_index,
                    )
            except Exception:
                pass

            # Send response
            sent = send_message(chat_id, response, bridge_url)
            status = "sent" if sent else "FAILED"
            print(f"[nio] -> {status} ({slop_score:.0f}/100): {response[:80]}")

        if not messages:
            time.sleep(poll_interval)

    # End session
    if session_id:
        try:
            from nio.claude_code.session_bridge import end_cc_session
            end_cc_session(session_id)
        except Exception:
            pass

    print("[nio] Gateway stopped.")
