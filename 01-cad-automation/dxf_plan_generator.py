"""
DXF Plan Generator — генерация обмерного плана квартиры из JSON-описания.

Вход:  JSON со списком помещений (прямоугольники в метрах), дверей и мебели.
Выход: DXF-чертёж (открывается в AutoCAD / nanoCAD / BricsCAD) + PNG-превью
       + CSV-экспликация помещений (номер, название, площадь).

Что делает автоматически:
  * стены заданной толщины по контуру каждого помещения (слой WALLS);
  * дверные проёмы с дугой открывания (слой DOORS);
  * подпись помещения: номер, название, площадь в м² (слой TEXT);
  * размерные цепочки по внешнему контуру (слой DIMS);
  * мебель из библиотеки блоков (слой FURNITURE);
  * штамп с названием проекта и датой.

Запуск:
    python dxf_plan_generator.py examples/apartment.json -o output/
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment

MM = 1000  # чертим в миллиметрах, вход — в метрах

# dimlfac=1: стиль EZDXF по умолчанию масштабирует размер ×100 (рассчитан на метры)
DIM_OVERRIDE = {"dimtxt": 200, "dimasz": 120, "dimlfac": 1, "dimdec": 0}

LAYERS = {
    "WALLS": 7,      # белый/чёрный
    "DOORS": 3,      # зелёный
    "TEXT": 2,       # жёлтый
    "DIMS": 4,       # голубой
    "FURNITURE": 8,  # серый
    "FRAME": 7,
}


@dataclass
class Room:
    number: str
    name: str
    x: float
    y: float
    w: float
    h: float
    label_dx: float = 0.0   # смещение подписи, м (для тесных помещений)
    label_dy: float = 0.0

    @property
    def area(self) -> float:
        return round(self.w * self.h, 2)

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x + self.w / 2 + self.label_dx) * MM,
                (self.y + self.h / 2 + self.label_dy) * MM)


class PlanSpecError(ValueError):
    """Ошибка во входном JSON — сообщаем явно, а не рисуем «как получится»."""


def load_spec(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    for key in ("project", "wall_thickness", "rooms"):
        if key not in spec:
            raise PlanSpecError(f"В спецификации нет обязательного поля '{key}'")
    numbers = [r["number"] for r in spec["rooms"]]
    if len(numbers) != len(set(numbers)):
        raise PlanSpecError("Номера помещений должны быть уникальными")
    for r in spec["rooms"]:
        if r["w"] <= 0 or r["h"] <= 0:
            raise PlanSpecError(f"Помещение {r['number']}: размеры должны быть > 0")
    return spec


def make_doc() -> ezdxf.document.Drawing:
    doc = ezdxf.new("R2018", setup=True)
    doc.units = ezdxf.units.MM
    for name, color in LAYERS.items():
        doc.layers.add(name, color=color)
    _define_furniture_blocks(doc)
    return doc


def _define_furniture_blocks(doc) -> None:
    """Простая библиотека мебели. Размеры — типовые, в мм."""
    bed = doc.blocks.new("BED_DOUBLE")
    bed.add_lwpolyline([(0, 0), (1600, 0), (1600, 2000), (0, 2000)], close=True)
    bed.add_lwpolyline([(100, 1650), (750, 1650), (750, 1950), (100, 1950)], close=True)
    bed.add_lwpolyline([(850, 1650), (1500, 1650), (1500, 1950), (850, 1950)], close=True)

    sofa = doc.blocks.new("SOFA")
    sofa.add_lwpolyline([(0, 0), (2200, 0), (2200, 900), (0, 900)], close=True)
    sofa.add_lwpolyline([(150, 0), (2050, 0), (2050, 650), (150, 650)], close=True)

    table = doc.blocks.new("TABLE_ROUND")
    table.add_circle((0, 0), 500)

    wc = doc.blocks.new("WC")
    wc.add_lwpolyline([(0, 0), (400, 0), (400, 200), (0, 200)], close=True)
    wc.add_ellipse((200, 450), major_axis=(0, 250), ratio=0.75)

    bath = doc.blocks.new("BATH")
    bath.add_lwpolyline([(0, 0), (1700, 0), (1700, 750), (0, 750)], close=True)
    bath.add_lwpolyline([(80, 80), (1620, 80), (1620, 670), (80, 670)], close=True)

    kitchen = doc.blocks.new("KITCHEN_ROW")
    kitchen.add_lwpolyline([(0, 0), (2400, 0), (2400, 600), (0, 600)], close=True)
    kitchen.add_circle((1800, 300), 220)  # мойка
    for cx in (300, 700):
        kitchen.add_circle((cx, 200), 90)   # конфорки
        kitchen.add_circle((cx, 420), 90)


def draw_room(msp, room: Room, wall: float) -> None:
    x0, y0 = room.x * MM, room.y * MM
    x1, y1 = (room.x + room.w) * MM, (room.y + room.h) * MM
    t = wall * MM / 2
    # внутренний и внешний контур стены (полутолщина на каждую сторону)
    msp.add_lwpolyline([(x0 + t, y0 + t), (x1 - t, y0 + t), (x1 - t, y1 - t), (x0 + t, y1 - t)],
                       close=True, dxfattribs={"layer": "WALLS"})
    msp.add_lwpolyline([(x0 - t, y0 - t), (x1 + t, y0 - t), (x1 + t, y1 + t), (x0 - t, y1 + t)],
                       close=True, dxfattribs={"layer": "WALLS", "const_width": 0})

    cx, cy = room.center
    h = 180
    msp.add_text(room.number, height=h * 1.4, dxfattribs={"layer": "TEXT"}
                 ).set_placement((cx, cy + h * 1.6), align=TextEntityAlignment.MIDDLE_CENTER)
    msp.add_text(room.name, height=h, dxfattribs={"layer": "TEXT"}
                 ).set_placement((cx, cy), align=TextEntityAlignment.MIDDLE_CENTER)
    msp.add_text(f"{room.area:.2f} м²", height=h, dxfattribs={"layer": "TEXT"}
                 ).set_placement((cx, cy - h * 1.6), align=TextEntityAlignment.MIDDLE_CENTER)


def draw_door(msp, door: dict) -> None:
    """Дверь: проём (разрыв помечаем линией полотна) + дуга открывания."""
    x, y = door["x"] * MM, door["y"] * MM
    width = door.get("width", 0.8) * MM
    angle = door.get("angle", 0)  # направление полотна, градусы
    from math import cos, radians, sin
    a = radians(angle)
    leaf_end = (x + width * cos(a), y + width * sin(a))
    msp.add_line((x, y), leaf_end, dxfattribs={"layer": "DOORS"})
    msp.add_arc((x, y), width, angle - 90, angle, dxfattribs={"layer": "DOORS"})


def draw_furniture(msp, item: dict) -> None:
    if item["block"] not in msp.doc.blocks:
        raise PlanSpecError(f"Неизвестный блок мебели: {item['block']}")
    msp.add_blockref(item["block"], (item["x"] * MM, item["y"] * MM),
                     dxfattribs={"layer": "FURNITURE", "rotation": item.get("rotation", 0)})


def draw_dimensions(msp, rooms: list[Room]) -> None:
    """Габаритные размеры всего плана снизу и слева."""
    min_x = min(r.x for r in rooms) * MM
    max_x = max(r.x + r.w for r in rooms) * MM
    min_y = min(r.y for r in rooms) * MM
    max_y = max(r.y + r.h for r in rooms) * MM
    off = 900
    # цепочка по низу: разбиваем по границам помещений, касающихся нижней грани
    xs = sorted({r.x * MM for r in rooms if r.y * MM == min_y} |
                {(r.x + r.w) * MM for r in rooms if r.y * MM == min_y})
    for a, b in zip(xs, xs[1:]):
        msp.add_linear_dim(base=(a, min_y - off), p1=(a, min_y), p2=(b, min_y),
                           dimstyle="EZDXF", dxfattribs={"layer": "DIMS"},
                           override=DIM_OVERRIDE).render()
    msp.add_linear_dim(base=(min_x, min_y - off * 1.8), p1=(min_x, min_y), p2=(max_x, min_y),
                       dimstyle="EZDXF", dxfattribs={"layer": "DIMS"},
                       override=DIM_OVERRIDE).render()
    msp.add_linear_dim(base=(min_x - off, min_y), p1=(min_x, min_y), p2=(min_x, max_y),
                       angle=90, dimstyle="EZDXF", dxfattribs={"layer": "DIMS"},
                       override=DIM_OVERRIDE).render()


def draw_stamp(msp, rooms: list[Room], project: str) -> None:
    max_x = max(r.x + r.w for r in rooms) * MM
    min_y = min(r.y for r in rooms) * MM
    x0, y0 = max_x - 7500, min_y - 4200
    msp.add_lwpolyline([(x0, y0), (x0 + 7500, y0), (x0 + 7500, y0 + 1500), (x0, y0 + 1500)],
                       close=True, dxfattribs={"layer": "FRAME"})
    total = sum(r.area for r in rooms)
    msp.add_text(project, height=250, dxfattribs={"layer": "TEXT"}).set_placement((x0 + 200, y0 + 1050))
    msp.add_text(f"Общая площадь: {total:.2f} м²", height=200,
                 dxfattribs={"layer": "TEXT"}).set_placement((x0 + 200, y0 + 600))
    msp.add_text(f"Сгенерировано {date.today():%d.%m.%Y}", height=160,
                 dxfattribs={"layer": "TEXT"}).set_placement((x0 + 200, y0 + 200))


def write_schedule(rooms: list[Room], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig — корректно открывается в Excel
        w = csv.writer(f, delimiter=";")
        w.writerow(["№", "Наименование", "Ширина, м", "Длина, м", "Площадь, м²"])
        for r in sorted(rooms, key=lambda r: r.number):
            w.writerow([r.number, r.name, r.w, r.h, f"{r.area:.2f}".replace(".", ",")])
        w.writerow(["", "ИТОГО", "", "", f"{sum(r.area for r in rooms):.2f}".replace(".", ",")])


def render_png(doc, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy, ColorPolicy
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_axes([0, 0, 1, 1])
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE,
                        color_policy=ColorPolicy.BLACK)
    Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(doc.modelspace())
    fig.savefig(path, dpi=150)
    plt.close(fig)


def generate(spec_path: Path, out_dir: Path) -> dict[str, Path]:
    spec = load_spec(spec_path)
    rooms = [Room(**r) for r in spec["rooms"]]
    doc = make_doc()
    msp = doc.modelspace()

    for room in rooms:
        draw_room(msp, room, spec["wall_thickness"])
    for door in spec.get("doors", []):
        draw_door(msp, door)
    for item in spec.get("furniture", []):
        draw_furniture(msp, item)
    draw_dimensions(msp, rooms)
    draw_stamp(msp, rooms, spec["project"])

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = spec_path.stem
    paths = {
        "dxf": out_dir / f"{stem}.dxf",
        "png": out_dir / f"{stem}.png",
        "csv": out_dir / f"{stem}_explication.csv",
    }
    doc.saveas(paths["dxf"])
    write_schedule(rooms, paths["csv"])
    render_png(doc, paths["png"])
    return paths


def main() -> int:
    p = argparse.ArgumentParser(description="JSON → DXF план помещений")
    p.add_argument("spec", type=Path)
    p.add_argument("-o", "--out", type=Path, default=Path("output"))
    args = p.parse_args()
    try:
        paths = generate(args.spec, args.out)
    except PlanSpecError as e:
        print(f"Ошибка спецификации: {e}", file=sys.stderr)
        return 2
    for kind, path in paths.items():
        print(f"{kind.upper():4} → {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
