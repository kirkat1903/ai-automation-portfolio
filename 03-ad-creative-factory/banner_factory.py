"""
Banner Factory — пакетная сборка рекламных креативов под все форматы соцсетей.

Вход:  products.csv (заголовок, подзаголовок, CTA, цена, цвета, картинка)
       + папка с изображениями (например, сгенерированными в Midjourney / ComfyUI).
Выход: по креативу на каждый формат + контакт-лист для быстрого ревью.

    python banner_factory.py data/products.csv --images data/images -o output/

Форматы: квадрат ленты 1080×1080, портрет ленты 1080×1350, сторис/рилс 1080×1920,
широкий баннер 1200×628. Текст автоматически уменьшается, пока не влезет в отведённую зону,
и переносится по словам — без обрезанных строк.
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

import matplotlib

# DejaVu (с кириллицей) поставляется вместе с matplotlib — одинаково на Windows, Linux и macOS
_FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
FONT_BOLD = str(_FONT_DIR / "DejaVuSans-Bold.ttf")
FONT_REG = str(_FONT_DIR / "DejaVuSans.ttf")

FORMATS = {
    "square_1080": (1080, 1080),
    "portrait_1080x1350": (1080, 1350),
    "story_1080x1920": (1080, 1920),
    "wide_1200x628": (1200, 628),
}


@dataclass
class Creative:
    id: str
    headline: str
    subline: str
    cta: str
    price: str
    bg: str
    accent: str
    text_color: str
    image: str


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError as e:
        raise SystemExit(f"Не найден шрифт {path}: укажите путь к TTF с кириллицей") from e


def wrap(draw, text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit_text(draw, text, font_path, max_w, max_h, start, min_size=18, spacing=1.15):
    """Подбирает максимальный кегль, при котором текст влезает в рамку."""
    size = start
    while size >= min_size:
        font = load_font(font_path, size)
        lines = wrap(draw, text, font, max_w)
        too_wide = any(draw.textlength(l, font=font) > max_w for l in lines)
        if not too_wide and len(lines) * size * spacing <= max_h:
            return font, lines, int(size * spacing)
        size -= 2
    raise ValueError(f"Текст не помещается даже кеглем {min_size}: «{text[:40]}…» — сократите его")


def cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(img.convert("RGB"), size, method=Image.LANCZOS, centering=(0.5, 0.45))


def render(c: Creative, fmt: str, images_dir: Path | None) -> Image.Image:
    W, H = FORMATS[fmt]
    bg, accent, fg = hex_rgb(c.bg), hex_rgb(c.accent), hex_rgb(c.text_color)
    canvas = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(canvas)
    pad = int(min(W, H) * 0.07)
    wide = W / H > 1.5

    # Зона изображения: справа у широкого баннера, сверху у остальных
    img_box = (W // 2, 0, W, H) if wide else (0, 0, W, int(H * (0.45 if H / W < 1.1 else 0.52)))
    if c.image and images_dir:
        path = images_dir / c.image
        if not path.exists():
            raise FileNotFoundError(f"Креатив {c.id}: нет изображения {path}")
        box_size = (img_box[2] - img_box[0], img_box[3] - img_box[1])
        canvas.paste(cover(Image.open(path), box_size), img_box[:2])
    else:
        # Без картинки — геометрический фон в акцентном цвете (явно, не «битая» картинка)
        d.rectangle(img_box, fill=accent)
        cx, cy = (img_box[0] + img_box[2]) // 2, (img_box[1] + img_box[3]) // 2
        r = int(min(img_box[2] - img_box[0], img_box[3] - img_box[1]) * 0.32)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=bg)

    # Текстовая зона
    tx0 = pad
    tx1 = (W // 2 - pad) if wide else (W - pad)
    ty0 = (pad if wide else img_box[3] + pad)
    ty1 = H - pad
    if H / W > 1.6:  # сторис: нижние ~18% перекрывает интерфейс (поле ответа, кнопки)
        ty1 = int(H * 0.82)
    text_w = tx1 - tx0
    # Сначала резервируем нижнюю полосу под цену и кнопку, остальное — под текст
    btn_font = load_font(FONT_BOLD, int(min(W, H) * 0.04))
    bh = int(btn_font.size * 2.2)
    reserved = bh + (int(min(W, H) * 0.09) if wide and c.price else 0) + pad // 2
    zone_h = ty1 - ty0 - reserved

    head_font, head_lines, head_lh = fit_text(d, c.headline, FONT_BOLD, text_w, zone_h * 0.62,
                                              start=int(min(W, H) * (0.1 if H / W > 1.6 else 0.085)))
    sub_font, sub_lines, sub_lh = fit_text(d, c.subline, FONT_REG, text_w, zone_h * 0.30,
                                           start=int(min(W, H) * (0.05 if H / W > 1.6 else 0.042)))
    y = ty0
    for line in head_lines:
        d.text((tx0, y), line, font=head_font, fill=fg)
        y += head_lh
    y += int(head_lh * 0.35)
    for line in sub_lines:
        d.text((tx0, y), line, font=sub_font, fill=fg)
        y += sub_lh

    # Нижняя строка: цена слева, кнопка CTA справа (у широкого — в столбик)
    bw = int(d.textlength(c.cta, font=btn_font)) + pad
    bx1, by1 = tx1, ty1
    bx0, by0 = bx1 - bw, by1 - bh
    if wide:
        bx0, bx1 = tx0, tx0 + bw
    d.rounded_rectangle((bx0, by0, bx1, by1), radius=bh // 2, fill=accent)
    d.text(((bx0 + bx1) // 2, (by0 + by1) // 2), c.cta, font=btn_font, fill=bg, anchor="mm")

    if c.price:
        price_font = load_font(FONT_BOLD, int(min(W, H) * 0.06))
        if wide:
            d.text((tx0, by0 - int(price_font.size * 0.4)), c.price, font=price_font, fill=fg, anchor="ls")
        else:
            d.text((tx0, (by0 + by1) // 2), c.price, font=price_font, fill=fg, anchor="lm")

    if y > by0 - pad // 3:
        raise ValueError(f"Креатив {c.id} / {fmt}: текст наезжает на кнопку — сократите подзаголовок")
    return canvas


def contact_sheet(paths: list[Path], out: Path, thumb_h: int = 360) -> None:
    thumbs = []
    for p in paths:
        im = Image.open(p)
        thumbs.append(im.resize((int(im.width * thumb_h / im.height), thumb_h)))
    gap = 24
    W = sum(t.width for t in thumbs) + gap * (len(thumbs) + 1)
    sheet = Image.new("RGB", (W, thumb_h + 2 * gap), (235, 235, 235))
    x = gap
    for t in thumbs:
        sheet.paste(t, (x, gap))
        x += t.width + gap
    sheet.save(out, quality=90)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--images", type=Path, default=None)
    ap.add_argument("-o", "--out", type=Path, default=Path("output"))
    ap.add_argument("--formats", nargs="*", default=list(FORMATS))
    args = ap.parse_args()

    with args.csv.open(encoding="utf-8-sig") as f:
        creatives = []
        for n, row in enumerate(csv.DictReader(f), start=2):
            if None in row:  # лишние поля: запятая внутри текста без кавычек
                raise SystemExit(f"{args.csv}:{n}: лишние столбцы — возьмите текст с запятыми в кавычки")
            creatives.append(Creative(**row))

    errors = 0
    for c in creatives:
        made = []
        for fmt in args.formats:
            try:
                img = render(c, fmt, args.images)
            except (ValueError, FileNotFoundError) as e:
                print(f"✗ {e}", file=sys.stderr)
                errors += 1
                continue
            path = args.out / c.id / f"{c.id}_{fmt}.jpg"
            path.parent.mkdir(parents=True, exist_ok=True)
            img.save(path, quality=92)
            made.append(path)
        if made:
            contact_sheet(made, args.out / c.id / f"{c.id}_contact_sheet.jpg")
            print(f"✓ {c.id}: {len(made)} форматов")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
