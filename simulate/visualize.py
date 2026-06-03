from __future__ import annotations
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm


def _set_korean_font() -> None:
    for font in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
        if fm.findfont(font, fallback_to_default=False):
            plt.rcParams["font.family"] = font
            return


def plot_all(metrics: dict, show: bool = True, save_path: str | None = None) -> None:
    _set_korean_font()
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(
        f"폐기량 절감 시뮬레이션  |  절감률 {metrics['waste_reduction_rate']:.1f}%",
        fontsize=14,
    )

    # ── Chart 1: 총 폐기량 막대 ────────────────────────────────────────────────
    ax1 = axes[0]
    labels = ["무작위", "α-스코어"]
    values = [metrics["total_waste_random"], metrics["total_waste_alpha"]]
    colors = ["#ff6b6b", "#51cf66"]
    bars = ax1.bar(labels, values, color=colors, width=0.5)
    ax1.set_title("총 폐기량 비교")
    ax1.set_ylabel("폐기량 (g)")
    for bar, val in zip(bars, values):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            val * 1.01,
            f"{val:,.0f} g",
            ha="center", va="bottom", fontsize=9,
        )

    # ── Chart 2: 일별 폐기량 추이 꺾은선 ─────────────────────────────────────
    ax2 = axes[1]
    days = list(range(1, len(metrics["waste_by_day_alpha"]) + 1))
    ax2.plot(days, metrics["waste_by_day_alpha"], label="α-스코어", color="#51cf66", linewidth=2)
    ax2.plot(
        days, metrics["waste_by_day_random"],
        label="무작위", color="#ff6b6b", linewidth=2, linestyle="--",
    )
    ax2.set_title("일별 평균 폐기량 추이")
    ax2.set_xlabel("시뮬레이션 일차")
    ax2.set_ylabel("평균 폐기량 (g / 명)")
    ax2.legend()

    # ── Chart 3: 카테고리별 묶음 막대 ────────────────────────────────────────
    ax3 = axes[2]
    cat_alpha = metrics.get("waste_by_category_alpha", {})
    cat_random = metrics.get("waste_by_category_random", {})
    all_cats = sorted(set(cat_alpha) | set(cat_random))

    if all_cats:
        x = list(range(len(all_cats)))
        w = 0.35
        ax3.bar(
            [xi - w / 2 for xi in x],
            [cat_alpha.get(c, 0) for c in all_cats],
            w, label="α-스코어", color="#51cf66",
        )
        ax3.bar(
            [xi + w / 2 for xi in x],
            [cat_random.get(c, 0) for c in all_cats],
            w, label="무작위", color="#ff6b6b",
        )
        ax3.set_xticks(x)
        ax3.set_xticklabels(all_cats, rotation=40, ha="right", fontsize=8)
        ax3.set_title("카테고리별 총 폐기량")
        ax3.set_ylabel("폐기량 (g)")
        ax3.legend()
    else:
        ax3.text(0.5, 0.5, "카테고리 데이터 없음", ha="center", va="center",
                 transform=ax3.transAxes)
        ax3.set_title("카테고리별 총 폐기량")

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"차트 저장 완료: {save_path}")
    if show:
        plt.show()
    plt.close(fig)
