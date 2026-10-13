# AI & Automation Portfolio — Екатерина Рукосуева

Три проекта под задачи «AI-креатора / Automation Engineer»: автоматизация проектирования,
контент-пайплайн на AI-агентах и производство рекламы.

| # | Проект | Стек | Что показывает |
|---|---|---|---|
| 01 | [CAD-автоматизация](01-cad-automation) | Python, ezdxf, Revit API (pyRevit) | JSON → DXF-план со стенами, дверьми, размерами, мебелью и экспликацией; Revit-кнопка нумерации и марок |
| 02 | [AI-агент для Telegram-канала](02-content-agent-pipeline) | Python, Claude API, ComfyUI API, Telegram Bot API, Telethon, SQLite | Цепочка «собрать → сгенерировать → опубликовать → собрать статистику» |
| 03 | [Фабрика креативов](03-ad-creative-factory) | Python, Pillow, pandas, SciPy | Пакетная сборка баннеров под 4 формата + анализ кампании и перераспределение бюджета |

## Быстрый старт

```bash
cd 01-cad-automation && pip install -r requirements.txt && python dxf_plan_generator.py examples/apartment.json -o output/
cd ../02-content-agent-pipeline && pip install -r requirements.txt && python -m pipeline.run --dry-run
cd ../03-ad-creative-factory && pip install -r requirements.txt && python banner_factory.py data/products.csv -o output/
```

## Общие принципы

- Ошибки входных данных и внешних сервисов сообщаются явно, без тихих «заглушек».
- Секреты — только в `.env`.
- Что проверено, а что нет, написано прямо: Revit-скрипт написан по документации и не запускался в Revit;
  данные рекламной кампании — синтетические.

## Контакты

- GitHub: [kirkat1903](https://github.com/kirkat1903)
- Почта: rukosuevakatya@gmail.com
- Telegram: [@Kirkat1_9](https://t.me/Kirkat1_9)
