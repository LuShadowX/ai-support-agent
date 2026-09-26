"""Telegram channel - same agent, same knowledge base.  Run:  uv run python -m app.telegram_bot

Get a token from @BotFather on Telegram and put it in .env as TELEGRAM_BOT_TOKEN.
"""

import logging
import time

import httpx

from app.agent import build_agent
from app.config import get_settings

log = logging.getLogger("telegram")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env first.")

    agent, _, _ = build_agent(settings)
    api = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    offset = None
    log.info("Bot running. Press Ctrl+C to stop.")

    with httpx.Client(timeout=40) as http:
        while True:
            try:
                updates = http.get(f"{api}/getUpdates", params={"timeout": 30, "offset": offset}).json()
            except httpx.HTTPError as exc:
                log.warning("Polling failed (%s), retrying in 5s", exc)
                time.sleep(5)
                continue

            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message") or {}
                text = (message.get("text") or "").strip()
                chat_id = message.get("chat", {}).get("id")
                if not text or chat_id is None:
                    continue

                if text == "/start":
                    reply = settings.greeting
                else:
                    http.post(f"{api}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
                    reply = agent.reply(f"tg-{chat_id}", text[: settings.max_message_chars]).text

                try:
                    http.post(f"{api}/sendMessage", json={"chat_id": chat_id, "text": reply})
                except httpx.HTTPError:
                    log.exception("Failed to send reply to %s", chat_id)


if __name__ == "__main__":
    main()
