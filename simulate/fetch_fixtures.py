#!/usr/bin/env python
"""
Supabase에서 ingredient_master + recipe + recipe_ingredient를 추출해
simulate/fixtures/ 에 JSON으로 저장하는 1회성 스크립트.

사용: python simulate/fetch_fixtures.py
     (리포 루트에서 실행, .env.local 또는 .env 필요)
"""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(".env.local")
load_dotenv(".env")

import asyncpg  # noqa: E402

# DATABASE_URL 형식: postgresql+asyncpg://user:pass@host:port/db
# asyncpg.connect 에는 순수 postgresql:// DSN 사용
_RAW_DB_URL = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _bitstring_to_str(val) -> str:
    """asyncpg BitString 또는 str → 공백 없는 이진 문자열로 변환."""
    if hasattr(val, "as_string"):
        return val.as_string().replace(" ", "")
    return str(val).replace(" ", "")


def _parse_bit_id(val) -> int:
    """PostgreSQL BIT 컬럼 → bit_id 정수 변환 (LSB-0 기준).

    app/models/ingredient.py의 _BitToInt TypeDecorator와 동일한 로직:
        left_pos = bit_str.index("1")
        return len(bit_str) - 1 - left_pos
    """
    if isinstance(val, int):
        return val
    bit_str = _bitstring_to_str(val)
    if "1" not in bit_str:
        return 0
    left_pos = bit_str.index("1")
    return len(bit_str) - 1 - left_pos


def _parse_recipe_bit(val) -> int:
    """PostgreSQL BIT 컬럼 → recipe_bit 정수 변환 (표준 2진수 해석).

    app/models/recipe.py의 _BitMaskToInt TypeDecorator와 동일한 로직:
        return int(bit_str, 2)
    """
    if val is None:
        return 0
    if isinstance(val, int):
        return val
    bit_str = _bitstring_to_str(val)
    return int(bit_str, 2) if bit_str else 0


async def _fetch_all(conn: asyncpg.Connection, table: str) -> list[dict]:
    """전체 행을 dict 리스트로 반환."""
    rows = await conn.fetch(f"SELECT * FROM {table}")
    return [dict(row) for row in rows]


async def main_async() -> None:
    conn = await asyncpg.connect(_RAW_DB_URL)
    FIXTURES_DIR.mkdir(exist_ok=True)

    try:
        # ingredient_master
        ingredients = await _fetch_all(conn, "ingredient_master")
        for ing in ingredients:
            ing["bit_id"] = _parse_bit_id(ing["bit_id"])
            if ing.get("risk_factor") is not None:
                ing["risk_factor"] = float(ing["risk_factor"])
        (FIXTURES_DIR / "ingredient_master.json").write_text(
            json.dumps(ingredients, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"ingredient_master: {len(ingredients)}건 저장")

        # recipe
        recipes = await _fetch_all(conn, "recipe")
        for r in recipes:
            r["recipe_bit"] = _parse_recipe_bit(r.get("recipe_bit"))

        # recipe_ingredient (전체 fetch 후 recipe_id 기준으로 그룹핑)
        all_ri = await _fetch_all(conn, "recipe_ingredient")
        ri_by_recipe: dict[int, list[dict]] = {}
        for ri in all_ri:
            ri_by_recipe.setdefault(ri["recipe_id"], []).append(ri)

        for r in recipes:
            r["ingredients"] = ri_by_recipe.get(r["id"], [])

        (FIXTURES_DIR / "recipes.json").write_text(
            json.dumps(recipes, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"recipe: {len(recipes)}건, recipe_ingredient: {len(all_ri)}건 저장")

    finally:
        await conn.close()


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
