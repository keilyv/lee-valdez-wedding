#!/usr/bin/env python3
"""Connect your personal Telegram chat to the deployed RSVP Worker.

Bot tokens are entered privately and sent to Cloudflare as Worker secrets.
They are never written to a file or included in a shell command.
"""

import getpass
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent


def telegram(token, method, payload=None):
    address = f"https://api.telegram.org/bot{token}/{method}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(address, body, {"Content-Type": "application/json"} if body else {})
    try:
        with urlopen(request, timeout=15) as response:
            result = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Telegram could not be reached or the bot token was invalid") from exc
    if not result.get("ok"):
        raise RuntimeError("Telegram rejected the request; check the bot token")
    return result["result"]


def store_secret(name, value):
    result = subprocess.run(["npx", "wrangler", "secret", "put", name],
                            cwd=HERE, input=value + "\n", text=True,
                            capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"Could not save {name} to Cloudflare. Check Wrangler login and try again.")
    print(f"Saved {name} securely in Cloudflare.")


def main():
    if "TELEGRAM_BOT_TOKEN" not in (HERE / "worker.js").read_text():
        raise RuntimeError("First replace worker.js with the updated version provided for notifications.")
    print("In Telegram, create a bot with @BotFather, then open your new bot and tap Start.")
    token = getpass.getpass("Paste the bot token from BotFather (input hidden): ").strip()
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
        raise RuntimeError("That does not look like a Telegram bot token")
    updates = telegram(token, "getUpdates")
    chats = [(item.get("message") or {}).get("chat") for item in reversed(updates)]
    chat = next((item for item in chats if item and item.get("type") == "private"), None)
    if chat is None:
        raise RuntimeError("No private chat found. Open your new bot in Telegram, tap Start, then run this again.")
    label = " ".join(str(chat.get(part, "")) for part in ("first_name", "last_name")).strip()
    if chat.get("username"):
        label += f" (@{chat['username']})"
    print(f"Alerts will go to the Telegram chat for {label or 'your account'}.")
    if input("Is that your chat? Type yes to continue: ").strip().lower() != "yes":
        print("No changes made.")
        return
    telegram(token, "sendMessage", {
        "chat_id": chat["id"],
        "text": "Wedding RSVP alerts are ready. New and updated guest responses will appear here.",
    })
    print("Check Telegram for the test message.")
    store_secret("TELEGRAM_BOT_TOKEN", token)
    store_secret("TELEGRAM_CHAT_ID", str(chat["id"]))
    print("Publishing the updated RSVP Worker...")
    completed = subprocess.run(["npx", "wrangler", "deploy"], cwd=HERE, check=False)
    if completed.returncode:
        raise RuntimeError("Secrets were saved, but deployment failed. Run npx wrangler deploy from rsvp-setup.")
    print("Done. Submit a test RSVP again to confirm you receive an alert.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, KeyError) as exc:
        sys.exit(f"Setup stopped: {exc}")
