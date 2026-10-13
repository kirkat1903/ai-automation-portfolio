"""
Campaign Analyzer — анализ эффективности креативов и перераспределение бюджета.

Вход:  CSV с выгрузкой статистики (день, креатив, показы, клики, конверсии, расход).
Выход: отчёт в Markdown + график; рекомендованные доли бюджета на следующий период.

Методика:
  * CTR, CR (конверсия из клика), CPA по каждому креативу;
  * z-тест двух долей: значимо ли креатив отличается по CR от лидера;
  * перераспределение бюджета по Thompson sampling: для каждого креатива
    апостериорное Beta-распределение конверсии на показ, доля бюджета ∝ вероятности
    быть лучшим по «конверсиям на рубль». Слабые креативы получают минимум (explore),
    а не ноль — чтобы не отключить креатив по случайному провалу.

    python campaign_analyzer.py data/campaign_stats.csv -o output/
    python campaign_analyzer.py --make-demo data/campaign_stats.csv   # синтетика для примера
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

REQUIRED = {"date", "creative", "impressions", "clicks", "conversions", "spend"}


def make_demo(path: Path, seed: int = 7) -> None:
    """СИНТЕТИЧЕСКИЕ данные для демонстрации — не реальная кампания."""
    rng = np.random.default_rng(seed)
    truth = {  # «истинные» CTR и CR, которые анализатор должен вскрыть
        "sofa_promo_square": (0.018, 0.045),
        "sofa_promo_story": (0.024, 0.030),
        "lamp_launch_square": (0.012, 0.060),
        "studio_consult_story": (0.020, 0.052),
    }
    rows = []
    for day in pd.date_range("2026-09-01", periods=14):
        for name, (ctr, cr) in truth.items():
            imps = int(rng.normal(9000, 1200))
            clicks = rng.binomial(imps, ctr)
            conv = rng.binomial(clicks, cr)
            rows.append({"date": day.date(), "creative": name, "impressions": imps,
                         "clicks": clicks, "conversions": conv,
                         "spend": round(imps / 1000 * rng.normal(180, 15), 2)})
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    print(f"Синтетические данные записаны в {path}")


def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = REQUIRED - set(df.columns)
    if missing:
        raise SystemExit(f"В {path} нет столбцов: {sorted(missing)}")
    bad = df[(df.clicks > df.impressions) | (df.conversions > df.clicks)]
    if not bad.empty:
        raise SystemExit(f"Некорректные строки (кликов больше показов или конверсий больше кликов):\n{bad}")
    return df


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    s = df.groupby("creative")[["impressions", "clicks", "conversions", "spend"]].sum()
    s["CTR_%"] = s.clicks / s.impressions * 100
    s["CR_%"] = s.conversions / s.clicks.replace(0, np.nan) * 100
    s["CPA"] = s.spend / s.conversions.replace(0, np.nan)
    s["CPM"] = s.spend / s.impressions * 1000
    return s.sort_values("CPA")


def z_test_vs_leader(s: pd.DataFrame) -> pd.Series:
    """p-value двустороннего z-теста CR каждого креатива против лидера по CPA."""
    leader = s.index[0]
    c1, n1 = s.loc[leader, "conversions"], s.loc[leader, "clicks"]
    out = {}
    for name, row in s.iterrows():
        if name == leader:
            out[name] = np.nan
            continue
        c2, n2 = row.conversions, row.clicks
        p = (c1 + c2) / (n1 + n2)
        se = np.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
        z = (c1 / n1 - c2 / n2) / se if se > 0 else 0
        out[name] = 2 * (1 - norm.cdf(abs(z)))
    return pd.Series(out)


def thompson_allocation(s: pd.DataFrame, draws: int = 20000, floor: float = 0.05, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    cpm = s.CPM.to_numpy()
    samples = np.column_stack([
        rng.beta(1 + row.conversions, 1 + row.impressions - row.conversions, draws)
        for _, row in s.iterrows()
    ])
    conv_per_ruble = samples / (cpm / 1000)            # конверсий на 1 ₽
    p_best = np.bincount(conv_per_ruble.argmax(axis=1), minlength=len(s)) / draws
    share = np.maximum(p_best, floor)                  # минимум на «разведку»
    return pd.Series(share / share.sum(), index=s.index)


def plot(df: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    daily = df.assign(cpa=df.spend / df.conversions.replace(0, np.nan)) \
              .pivot_table(index="date", columns="creative", values="cpa")
    ax = daily.rolling(3, min_periods=1).mean().plot(figsize=(10, 5), linewidth=2)
    ax.set_title("CPA по дням (скользящее среднее, 3 дня)")
    ax.set_ylabel("₽ за конверсию")
    ax.set_xlabel("")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=130)
    plt.close()


def report(s, pvals, alloc, out_dir: Path, src: Path) -> Path:
    t = s.copy()
    t["p_vs_leader"] = pvals
    t["budget_share_%"] = alloc * 100
    cols = ["impressions", "clicks", "conversions", "spend", "CTR_%", "CR_%", "CPA", "p_vs_leader", "budget_share_%"]
    lines = [f"# Отчёт по кампании\n\nИсточник: `{src.name}`\n",
             t[cols].round(3).to_markdown(), "\n## Выводы\n"]
    leader = s.index[0]
    lines.append(f"- Лидер по CPA: **{leader}** — {s.loc[leader, 'CPA']:.0f} ₽ за конверсию.")
    for name, p in pvals.dropna().items():
        if p < 0.05:
            verdict = "конверсия из клика **значимо ниже** (p < 0.05) — проблема в оффере или посадочной"
        elif s.loc[name, "CTR_%"] < 0.8 * s.loc[leader, "CTR_%"]:
            verdict = ("конверсия на уровне лидера, но CTR заметно ниже — "
                       "переделывать визуал и заголовок, а не оффер")
        else:
            verdict = "отличие по конверсии пока **не значимо** — нужно больше данных"
        lines.append(f"- {name}: {verdict} (p = {p:.3f}).")
    top_ctr = s["CTR_%"].idxmax()
    if top_ctr != leader:
        lines.append(f"- {top_ctr} лучше всех по CTR, но не по CPA: креатив привлекает клики, "
                     "а не покупателей — проверить соответствие обещания на баннере и посадочной.")
    lines.append("\n## Бюджет на следующий период\n")
    for name, share in alloc.sort_values(ascending=False).items():
        lines.append(f"- {name}: {share * 100:.0f}%")
    lines.append("\n![CPA по дням](cpa_by_day.png)\n")
    path = out_dir / "campaign_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("output"))
    ap.add_argument("--make-demo", action="store_true", help="сгенерировать синтетический CSV и выйти")
    args = ap.parse_args()
    if args.make_demo:
        make_demo(args.csv)
        return 0
    df = load(args.csv)
    s = summarize(df)
    pvals = z_test_vs_leader(s)
    alloc = thompson_allocation(s)
    args.out.mkdir(parents=True, exist_ok=True)
    plot(df, args.out / "cpa_by_day.png")
    path = report(s, pvals, alloc, args.out, args.csv)
    print(path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
