"""SQLite: что уже собрано, что опубликовано, какая статистика."""
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    link        TEXT PRIMARY KEY,
    title       TEXT,
    summary     TEXT,
    source      TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
    status      TEXT DEFAULT 'new'          -- new | published | failed
);
CREATE TABLE IF NOT EXISTS posts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    link        TEXT REFERENCES items(link),
    text        TEXT,
    image_path  TEXT,
    message_id  INTEGER,
    published_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS stats (
    message_id  INTEGER,
    views       INTEGER,
    forwards    INTEGER,
    reactions   INTEGER,
    checked_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def add_items(con, items: list[dict]) -> int:
    cur = con.executemany(
        "INSERT OR IGNORE INTO items(link, title, summary, source) VALUES (:link, :title, :summary, :source)",
        items)
    con.commit()
    return cur.rowcount


def next_new(con, limit: int):
    return con.execute(
        "SELECT * FROM items WHERE status='new' ORDER BY collected_at LIMIT ?", (limit,)).fetchall()


def mark(con, link: str, status: str) -> None:
    con.execute("UPDATE items SET status=? WHERE link=?", (status, link))
    con.commit()


def save_post(con, link, text, image_path, message_id) -> None:
    con.execute("INSERT INTO posts(link, text, image_path, message_id) VALUES (?,?,?,?)",
                (link, text, image_path, message_id))
    con.commit()
