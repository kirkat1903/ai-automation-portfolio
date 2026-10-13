"""Шаг 1. Сбор материала из RSS/Atom-лент (без сторонних библиотек)."""
import re
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape

ATOM = "{http://www.w3.org/2005/Atom}"


def _clean(text: str | None, limit: int = 1200) -> str:
    text = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def parse_feed(xml_bytes: bytes, source: str) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items = []
    for it in root.iter("item"):                       # RSS 2.0
        items.append({"title": _clean(it.findtext("title"), 300),
                      "link": (it.findtext("link") or "").strip(),
                      "summary": _clean(it.findtext("description")),
                      "source": source})
    for it in root.iter(f"{ATOM}entry"):               # Atom
        link_el = it.find(f"{ATOM}link")
        items.append({"title": _clean(it.findtext(f"{ATOM}title"), 300),
                      "link": link_el.get("href", "") if link_el is not None else "",
                      "summary": _clean(it.findtext(f"{ATOM}summary") or it.findtext(f"{ATOM}content")),
                      "source": source})
    return [i for i in items if i["link"] and i["title"]]


def fetch(url: str, timeout: int = 20) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "content-pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return parse_feed(resp.read(), source=url)
