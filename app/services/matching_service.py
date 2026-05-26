from rapidfuzz import process, fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ingredient import IngredientMaster
from app.schemas.ocr import OcrRawItem, OcrScanCandidate, OcrCandidate

_EXCLUDE_KEYWORDS = frozenset([
    "비닐봉투", "봉투", "쿠폰", "적립금", "할인", "부가세", "합계",
    "영수증", "카드", "현금", "거스름돈", "포인트", "영수", "합산",
])

_OVERRIDE: dict[str, str] = {
    "계란": "달걀",
    "란": "달걀",
}

_FUZZY_THRESHOLD = 70


async def match_items(db: AsyncSession, raw_items: list[OcrRawItem]) -> list[OcrScanCandidate]:
    if not raw_items:
        return []

    result = await db.execute(select(IngredientMaster))
    masters = result.scalars().all()
    name_to_id: dict[str, int] = {m.name: m.id for m in masters}
    names = list(name_to_id.keys())

    candidates: list[OcrScanCandidate] = []
    for item in raw_items:
        text = item.text

        if any(kw in text for kw in _EXCLUDE_KEYWORDS):
            candidates.append(OcrScanCandidate(
                raw_text=text, recommended_action="skip", candidates=[],
            ))
            continue

        normalized = _OVERRIDE.get(text, text)

        if normalized in name_to_id:
            candidates.append(OcrScanCandidate(
                raw_text=text,
                recommended_action="register",
                candidates=[OcrCandidate(
                    ingredient_master_id=name_to_id[normalized],
                    ingredient_name=normalized,
                    confidence=100.0,
                )],
            ))
            continue

        fuzzy_matches = process.extract(
            normalized, names, scorer=fuzz.partial_ratio, limit=3,
        )
        match_candidates = [
            OcrCandidate(
                ingredient_master_id=name_to_id[name],
                ingredient_name=name,
                confidence=float(score),
            )
            for name, score, _ in fuzzy_matches
        ]
        best = fuzzy_matches[0][1] if fuzzy_matches else 0
        candidates.append(OcrScanCandidate(
            raw_text=text,
            recommended_action="register" if best >= _FUZZY_THRESHOLD else "skip",
            candidates=match_candidates,
        ))

    return candidates
