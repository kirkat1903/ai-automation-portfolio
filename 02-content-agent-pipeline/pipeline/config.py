"""Настройки из переменных окружения (.env). Секреты в код не кладём."""
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


_load_dotenv()


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    feeds: list[str]
    anthropic_key: str | None
    anthropic_model: str
    tg_token: str | None
    tg_channel: str | None
    comfy_url: str | None
    tg_api_id: str | None
    tg_api_hash: str | None
    db_path: Path = ROOT / "data" / "pipeline.sqlite3"

    def require(self, *names: str) -> None:
        missing = [n for n in names if not getattr(self, n)]
        if missing:
            raise ConfigError("Не заданы переменные окружения для: " + ", ".join(missing))


def load() -> Config:
    return Config(
        feeds=[f for f in os.getenv("FEEDS", "").split(",") if f.strip()],
        anthropic_key=os.getenv("ANTHROPIC_API_KEY"),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        tg_token=os.getenv("TG_BOT_TOKEN"),
        tg_channel=os.getenv("TG_CHANNEL"),          # @channel или -100...
        comfy_url=os.getenv("COMFY_URL"),            # http://127.0.0.1:8188
        tg_api_id=os.getenv("TG_API_ID"),            # для статистики (Telethon)
        tg_api_hash=os.getenv("TG_API_HASH"),
    )
