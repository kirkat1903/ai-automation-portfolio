"""
Оркестратор агента: собрать → сгенерировать → (картинка) → опубликовать → статистика.

    python -m pipeline.run --dry-run          # локально, без ключей и сети
    python -m pipeline.run --limit 3          # боевой режим
    python -m pipeline.run --stats            # только обновить статистику

Каждый шаг падает с понятной ошибкой, а не подменяет результат «заглушкой».
Режим --dry-run включается только явно и помечает все артефакты как тестовые.
"""
import argparse
import hashlib
import logging
import sys
from pathlib import Path

from . import collect, config, generate, image, publish, stats, storage

ROOT = config.ROOT
log = logging.getLogger("pipeline")


def dry_post(item: dict) -> dict:
    """Детерминированный «пост» для проверки пайплайна без LLM. Не для публикации."""
    return {"title": f"[DRY-RUN] {item['title']}",
            "text": item["summary"][:400],
            "hashtags": ["тест", "dryrun"],
            "image_prompt": f"interior photo, {item['title']}"}


def step_collect(cfg, con, dry: bool) -> None:
    if dry:
        items = collect.parse_feed((ROOT / "data" / "sample_feed.xml").read_bytes(), "sample_feed.xml")
    else:
        if not cfg.feeds:
            raise config.ConfigError("FEEDS пуст: укажите RSS-ленты через запятую")
        items = []
        for url in cfg.feeds:
            try:
                items += collect.fetch(url)
            except Exception as e:  # одна упавшая лента не должна ронять остальные — но сообщаем
                log.error("Лента %s недоступна: %s", url, e)
    log.info("Собрано %d материалов, новых: %d", len(items), storage.add_items(con, items))


def step_publish(cfg, con, limit: int, dry: bool) -> None:
    if not dry:
        cfg.require("anthropic_key", "tg_token", "tg_channel")
    outbox = ROOT / "data" / "outbox"
    for row in storage.next_new(con, limit):
        item = dict(row)
        try:
            post = dry_post(item) if dry else generate.make_post(item, cfg.anthropic_key, cfg.anthropic_model)
            text = generate.format_post(post, item["link"])

            img_path = None
            if cfg.comfy_url and not dry:
                img_path = image.generate(cfg.comfy_url, ROOT / "workflows" / "sdxl_interior_api.json",
                                          post["image_prompt"], ROOT / "data" / "images")

            if dry:
                outbox.mkdir(parents=True, exist_ok=True)
                out = outbox / f"post_{hashlib.md5(item['link'].encode()).hexdigest()[:8]}.html"
                out.write_text(text, encoding="utf-8")
                message_id = None
                log.info("[DRY-RUN] пост сохранён в %s", out.relative_to(ROOT))
            else:
                message_id = publish.publish(cfg.tg_token, cfg.tg_channel, text, img_path)
                log.info("Опубликовано: message_id=%s", message_id)

            storage.save_post(con, item["link"], text, str(img_path) if img_path else None, message_id)
            storage.mark(con, item["link"], "published")
        except (generate.GenerationError, image.ImageError, publish.PublishError) as e:
            storage.mark(con, item["link"], "failed")
            log.error("Материал %s пропущен: %s", item["link"], e)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="без сети и ключей, посты в data/outbox/")
    p.add_argument("--limit", type=int, default=3, help="сколько постов за запуск")
    p.add_argument("--stats", action="store_true", help="только собрать статистику")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cfg = config.load()
    db = ROOT / "data" / ("dryrun.sqlite3" if args.dry_run else "pipeline.sqlite3")
    con = storage.connect(db)
    try:
        if args.stats:
            cfg.require("tg_api_id", "tg_api_hash", "tg_channel")
            for r in stats.collect(con, cfg.tg_api_id, cfg.tg_api_hash, cfg.tg_channel):
                log.info("msg %(message_id)s: 👁 %(views)s, ↗ %(forwards)s, ♥ %(reactions)s", r)
            return 0
        step_collect(cfg, con, args.dry_run)
        step_publish(cfg, con, args.limit, args.dry_run)
    except config.ConfigError as e:
        log.error("%s", e)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
