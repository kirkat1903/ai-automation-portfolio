"""Шаг 2. Генерация поста через Claude API: текст + промпт для картинки."""
import json
import requests

API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM = """Ты — редактор Telegram-канала студии дизайна интерьеров.
Из новости делаешь короткий пост: цепляющий заголовок, 3–5 предложений по делу,
практический вывод для читателя, 2–3 хэштега. Без воды и канцелярита, без выдуманных фактов:
используй только то, что есть в исходнике.
Отвечай ТОЛЬКО JSON без markdown-обёртки:
{"title": str, "text": str, "hashtags": [str], "image_prompt": str}
image_prompt — на английском, для Stable Diffusion: интерьерная фотография по теме поста."""

REQUIRED = {"title", "text", "hashtags", "image_prompt"}


class GenerationError(RuntimeError):
    pass


def parse_reply(raw: str) -> dict:
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise GenerationError(f"Модель вернула не JSON: {raw[:200]!r}") from e
    missing = REQUIRED - data.keys()
    if missing:
        raise GenerationError(f"В ответе модели нет полей: {sorted(missing)}")
    return data


def make_post(item: dict, api_key: str, model: str) -> dict:
    user = f"Источник: {item['source']}\nЗаголовок: {item['title']}\nТекст: {item['summary']}\nСсылка: {item['link']}"
    resp = requests.post(
        API_URL,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": model, "max_tokens": 800, "system": SYSTEM,
              "messages": [{"role": "user", "content": user}]},
        timeout=60,
    )
    if resp.status_code != 200:
        raise GenerationError(f"Claude API {resp.status_code}: {resp.text[:300]}")
    text = "".join(b.get("text", "") for b in resp.json()["content"] if b["type"] == "text")
    return parse_reply(text)


def format_post(post: dict, link: str) -> str:
    tags = " ".join("#" + t.lstrip("#") for t in post["hashtags"])
    return f"<b>{post['title']}</b>\n\n{post['text']}\n\n<a href=\"{link}\">Источник</a>\n{tags}"
