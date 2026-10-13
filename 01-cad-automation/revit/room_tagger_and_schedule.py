# -*- coding: utf-8 -*-
"""
pyRevit-скрипт: нумерация, маркировка и экспликация помещений.

Что делает (в активном плане этажа):
  1. Собирает все размещённые помещения (Rooms) уровня текущего вида.
  2. Перенумеровывает их слева направо, сверху вниз: 101, 102, ... (префикс = номер этажа).
  3. Ставит марку помещения в центр каждой комнаты, у которой марки ещё нет.
  4. Выгружает экспликацию (номер, имя, площадь м², периметр м) в CSV рядом с проектом.

Установка: положить в папку кнопки pyRevit
  <MyExtension>.extension/<Tab>.tab/<Panel>.panel/RoomTagger.pushbutton/script.py

Совместимость: Revit 2022+ (используется UnitTypeId). Запуск — IronPython 2.7 или CPython 3 в pyRevit.

Важно: скрипт написан по документации Revit API, но в учебном окружении
без Revit не запускался — перед использованием на рабочем проекте
проверить на копии модели.
"""
import io
import os

from Autodesk.Revit.DB import (
    BuiltInCategory, BuiltInParameter, FilteredElementCollector,
    LinkElementId, SpatialElementBoundaryOptions, Transaction, UnitTypeId,
    UnitUtils, UV, ViewPlan,
)
from pyrevit import forms, revit

doc = revit.doc
view = doc.ActiveView

if not isinstance(view, ViewPlan):
    forms.alert(u"Откройте план этажа и запустите скрипт снова.", exitscript=True)

level_id = view.GenLevel.Id
floor_prefix = forms.ask_for_string(
    default="1", prompt=u"Номер этажа (префикс для нумерации):", title=u"Нумерация помещений")
if not floor_prefix:
    forms.alert(u"Номер этажа не указан — скрипт остановлен.", exitscript=True)

rooms = [
    r for r in FilteredElementCollector(doc)
    .OfCategory(BuiltInCategory.OST_Rooms)
    .WhereElementIsNotElementType()
    if r.LevelId == level_id and r.Area > 0 and r.Location is not None  # только размещённые
]
if not rooms:
    forms.alert(u"На уровне текущего вида нет размещённых помещений.", exitscript=True)

# Сортировка: сверху вниз (по Y, с допуском ~1 м, чтобы один «ряд» считался одной строкой),
# затем слева направо по X. Внутренние единицы Revit — футы.
ROW_TOL_FT = UnitUtils.ConvertToInternalUnits(1.0, UnitTypeId.Meters)


def sort_key(room):
    p = room.Location.Point
    return (-round(p.Y / ROW_TOL_FT), p.X)


rooms.sort(key=sort_key)

already_tagged = {
    tag.Room.Id.IntegerValue
    for tag in FilteredElementCollector(doc, view.Id)
    .OfCategory(BuiltInCategory.OST_RoomTags)
    .WhereElementIsNotElementType()
    if tag.Room is not None
}

boundary_opts = SpatialElementBoundaryOptions()
rows = []
tagged = 0

t = Transaction(doc, u"Нумерация и маркировка помещений")
t.Start()
try:
    # Двухпроходная нумерация: сначала временные номера, чтобы не словить
    # конфликт «номер уже занят» при перестановке.
    for i, room in enumerate(rooms):
        room.Number = u"tmp_{}".format(i)
    for i, room in enumerate(rooms, start=1):
        room.Number = u"{}{:02d}".format(floor_prefix, i)

        if room.Id.IntegerValue not in already_tagged:
            p = room.Location.Point
            doc.Create.NewRoomTag(LinkElementId(room.Id), UV(p.X, p.Y), view.Id)
            tagged += 1

        perimeter_ft = sum(
            seg.GetCurve().Length
            for loop in room.GetBoundarySegments(boundary_opts)
            for seg in loop
        )
        rows.append([
            room.Number,
            room.get_Parameter(BuiltInParameter.ROOM_NAME).AsString() or u"",
            round(UnitUtils.ConvertFromInternalUnits(room.Area, UnitTypeId.SquareMeters), 2),
            round(UnitUtils.ConvertFromInternalUnits(perimeter_ft, UnitTypeId.Meters), 2),
        ])
    t.Commit()
except Exception as e:
    t.RollBack()
    forms.alert(u"Ошибка, изменения отменены:\n{}".format(e), exitscript=True)

# Экспликация в CSV рядом с файлом проекта (или в папке пользователя, если проект не сохранён)
folder = os.path.dirname(doc.PathName) or os.path.expanduser("~")
out_path = os.path.join(folder, u"explication_{}.csv".format(view.Name.replace(" ", "_")))
# csv-модуль в IronPython 2.7 плохо дружит с unicode, поэтому пишем строки вручную
def _line(cells):
    return u";".join(u"{}".format(c).replace(u".", u",") if isinstance(c, float)
                     else u"{}".format(c) for c in cells) + u"\r\n"


with io.open(out_path, "w", encoding="utf-8-sig") as f:
    f.write(_line([u"№", u"Наименование", u"Площадь, м²", u"Периметр, м"]))
    for row in rows:
        f.write(_line(row))
    f.write(_line([u"", u"ИТОГО", round(sum(r[2] for r in rows), 2), u""]))

forms.alert(
    u"Помещений: {}\nНовых марок: {}\nЭкспликация: {}".format(len(rooms), tagged, out_path),
    title=u"Готово")
