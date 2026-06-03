#!/usr/bin/env python
"""
폐기량 절감 시뮬레이션 메인 실행기.

사용:
    python simulate/run.py                # 차트 팝업
    python simulate/run.py --no-show      # 차트 저장만 (simulate/result.png)
    python simulate/run.py --users 100    # 빠른 테스트용 (100명)
"""
from __future__ import annotations
import argparse
import json
import random
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

import tqdm

from simulate.data_gen import generate_user
from simulate.engine import step
from simulate.metrics import aggregate
from simulate.strategies import pick_alpha_score, pick_random
from simulate.visualize import plot_all

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SIM_DAYS = 30
SEED = 42


def _load_fixtures() -> tuple[list[dict], list[dict]]:
    ing_path = FIXTURES_DIR / "ingredient_master.json"
    rec_path = FIXTURES_DIR / "recipes.json"
    if not ing_path.exists() or not rec_path.exists():
        raise FileNotFoundError(
            "픽스처 없음. 먼저 실행: python simulate/fetch_fixtures.py"
        )
    ingredient_master = json.loads(ing_path.read_text(encoding="utf-8"))
    recipes = json.loads(rec_path.read_text(encoding="utf-8"))
    return ingredient_master, recipes


def run_simulation(n_users: int, show: bool = True) -> None:
    ingredient_master, recipes = _load_fixtures()

    results_alpha: list = []
    results_random: list = []

    print(f"Simulating {n_users:,} users × {SIM_DAYS} days...")
    for uid in tqdm.tqdm(range(n_users)):
        user_rng = random.Random(SEED + uid)
        state_a = generate_user(uid, ingredient_master, user_rng)
        state_b = deepcopy(state_a)
        rng_a = random.Random(SEED + uid * 10_000)
        rng_b = random.Random(SEED + uid * 10_000)

        for day_offset in range(SIM_DAYS):
            sim_date = date.today() + timedelta(days=day_offset)
            step(state_a, recipes, sim_date, day_offset, ingredient_master, pick_alpha_score, rng_a)
            step(state_b, recipes, sim_date, day_offset, ingredient_master, pick_random, rng_b)

        results_alpha.append(state_a)
        results_random.append(state_b)

    m = aggregate(results_alpha, results_random)

    print(f"\n=== 시뮬레이션 결과 ({SIM_DAYS}일, {n_users:,}명) ===")
    print(f"α-스코어 전략 총 폐기량: {m['total_waste_alpha']:>12,.1f} g")
    print(f"무작위    전략 총 폐기량: {m['total_waste_random']:>12,.1f} g")
    print(f"폐기량 절감률:            {m['waste_reduction_rate']:>10.1f} %")

    save_path = str(Path(__file__).parent / "result.png") if not show else None
    plot_all(m, show=show, save_path=save_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="폐기량 절감 시뮬레이션")
    parser.add_argument("--users", type=int, default=1000, help="시뮬레이션 사용자 수 (기본 1000)")
    parser.add_argument("--no-show", action="store_true", help="차트 팝업 대신 result.png 저장")
    args = parser.parse_args()
    run_simulation(n_users=args.users, show=not args.no_show)


if __name__ == "__main__":
    main()
