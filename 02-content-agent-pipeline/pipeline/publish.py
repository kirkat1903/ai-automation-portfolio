"""Шаг 4. Публикация в Telegram-канал через Bot API (бот — админ канала)."""
from pathlib import Path

import requests

CAPTION_LIMIT = 1024  # лимит подписи к фото в Telegram


class PublishError(RuntimeError):
    pass


def publish(token: str, channel: str, text: str, image: Path | None = None) -> int:
    base = f"https://api.telegram.org/bot{token}"
    if image and len(text) <= CAPTION_LIMIT:
        with image.open("rb") as f:
            r = requests.post(f"{base}/sendPhoto", timeout=60, files={"photo": f},
                              data={"chat_id": channel, "caption": text, "parse_mode": "HTML"})
    else:
        if image:  # длинный текст: сначала фото, потом текст отдельным сообщением
            with image.open("rb") as f:
                requests.post(f"{base}/sendPhoto", timeout=60, files={"photo": f},
                              data={"chat_id": channel}).raise_for_status()
        r = requests.post(f"{base}/sendMessage", timeout=30, data={
            "chat_id": channel, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})
    body = r.json()
    if not body.get("ok"):
        raise PublishError(f"Telegram: {body.get('description', r.text[:200])}")
    return body["result"]["message_id"]
