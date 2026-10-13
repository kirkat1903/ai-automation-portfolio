"""Шаг 5. Статистика постов.

Bot API не отдаёт просмотры постов в канале, поэтому используем пользовательский
клиент Telethon (MTProto). Нужны TG_API_ID / TG_API_HASH с my.telegram.org;
при первом запуске Telethon попросит войти по номеру телефона.
"""
import asyncio


async def _fetch(api_id, api_hash, channel, message_ids):
    from telethon import TelegramClient  # pip install telethon
    async with TelegramClient("stats_session", int(api_id), api_hash) as client:
        msgs = await client.get_messages(channel, ids=message_ids)
        result = []
        for m in msgs:
            if m is None:
                continue
            reactions = sum(r.count for r in m.reactions.results) if m.reactions else 0
            result.append({"message_id": m.id, "views": m.views or 0,
                           "forwards": m.forwards or 0, "reactions": reactions})
        return result


def collect(con, api_id, api_hash, channel) -> list[dict]:
    ids = [r["message_id"] for r in con.execute(
        "SELECT message_id FROM posts WHERE message_id IS NOT NULL")]
    if not ids:
        return []
    rows = asyncio.run(_fetch(api_id, api_hash, channel, ids))
    con.executemany("INSERT INTO stats(message_id, views, forwards, reactions) "
                    "VALUES (:message_id, :views, :forwards, :reactions)", rows)
    con.commit()
    return rows
