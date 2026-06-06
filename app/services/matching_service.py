import re
from rapidfuzz import process, fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ingredient import IngredientMaster
from app.schemas.ocr import OcrRawItem, OcrScanCandidate, OcrCandidate
from app.core.unit_mapping import INGREDIENT_UNITS, CATEGORY_UNITS

_EXCLUDE_KEYWORDS = frozenset([
    "비닐봉투", "봉투", "쿠폰", "적립금", "할인", "부가세", "합계",
    "영수증", "카드", "현금", "거스름돈", "포인트", "영수", "합산",
    "소계", "결제금액", "신용카드", "체크카드",
])

_BRAND_WORDS = frozenset([
    "풀무원", "이마트", "롯데마트", "홈플러스", "GS25", "CU",
    "하림", "동원", "서울우유", "남양", "CJ", "비비고", "오뚜기",
    "청정원", "농심", "빙그레", "샘표", "대상", "해태", "롯데",
    "삼양", "오리온", "사조", "한성", "농협", "본가", "사계절",
    "한우리", "신선설농탕",
])

_ORIGIN_WORDS = frozenset([
    "제주", "국산", "수입산", "노르웨이", "미국산", "호주산", "칠레산",
    "국내산", "외국산", "유기농", "친환경", "무농약", "자연산",
])

# 식재료 자체가 아닌 처리 방법·포장 형태
_DESCRIPTOR_WORDS = frozenset([
    "슬라이스", "필레", "냉동", "냉장", "훈제", "신선", "캔", "통조림",
    "분말", "가루", "즙", "추출물", "구이용", "볶음용", "찌개용",
    "국물용", "망",
])

# OCR 텍스트의 표현 → ingredient_master 표준명 매핑
_OVERRIDE: dict[str, str] = {
    "계란": "달걀",
    "왕란": "달걀",
    "특란": "달걀",
    "대란": "달걀",
    "감귤": "귤",
}

_QTY_RE = re.compile(
    r"\d+(\.\d+)?\s*(g|kg|ml|L|l|개|입|봉|팩|마리|단|알|인분|구|통|병|포|박스|세트|x)"
    r"(\s*\d+)?",
    re.IGNORECASE,
)
_PAREN_RE = re.compile(r"\([^)]*\)")

_REGISTER_THRESHOLD = 90
_REVIEW_THRESHOLD = 60


def _get_default_unit(name: str, category: str) -> str:
    if name in INGREDIENT_UNITS:
        return INGREDIENT_UNITS[name]
    units = CATEGORY_UNITS.get(category)
    return units[0] if units else "개"


def _extract_keyword(text: str) -> str:
    text = _PAREN_RE.sub(" ", text)
    text = _QTY_RE.sub(" ", text)
    tokens = [
        t for t in text.split()
        if t not in _BRAND_WORDS
        and t not in _ORIGIN_WORDS
        and t not in _DESCRIPTOR_WORDS
        and not (len(t) == 1 and t.isascii())  # 단위 잔여 문자("x","L") 제거
    ]
    return " ".join(tokens).strip()


def _normalize(keyword: str) -> str:
    tokens = keyword.split()
    overridden = list(dict.fromkeys(_OVERRIDE.get(t, t) for t in tokens))
    joined = " ".join(overridden)
    return _OVERRIDE.get(joined, joined)


async def match_items(db: AsyncSession, raw_items: list[OcrRawItem]) -> list[OcrScanCandidate]:
    if not raw_items:
        return []

    result = await db.execute(select(IngredientMaster))
    masters = result.scalars().all()
    name_to_master: dict[str, IngredientMaster] = {m.name: m for m in masters}
    names = list(name_to_master.keys())

    candidates: list[OcrScanCandidate] = []
    for item in raw_items:
        text = item.text

        if any(kw in text for kw in _EXCLUDE_KEYWORDS):
            candidates.append(OcrScanCandidate(
                raw_text=text, recommended_action="skip", candidates=[],
            ))
            continue

        keyword = _extract_keyword(text) or text
        normalized = _normalize(keyword)

        # 정확히 일치하면 바로 register
        if normalized in name_to_master:
            m = name_to_master[normalized]
            candidates.append(OcrScanCandidate(
                raw_text=text,
                recommended_action="register",
                candidates=[OcrCandidate(
                    ingredient_master_id=m.id,
                    ingredient_name=normalized,
                    confidence=100.0,
                    default_shelf_days=m.default_shelf_days,
                    default_unit=_get_default_unit(normalized, m.category),
                )],
            ))
            continue

        fuzzy_matches = process.extract(
            normalized, names, scorer=fuzz.WRatio, limit=3,
        )
        match_candidates = [
            OcrCandidate(
                ingredient_master_id=name_to_master[name].id,
                ingredient_name=name,
                confidence=float(score),
                default_shelf_days=name_to_master[name].default_shelf_days,
                default_unit=_get_default_unit(name, name_to_master[name].category),
            )
            for name, score, _ in fuzzy_matches
        ]
        best = fuzzy_matches[0][1] if fuzzy_matches else 0

        if best >= _REGISTER_THRESHOLD:
            action = "register"
        elif best >= _REVIEW_THRESHOLD:
            action = "review"
        else:
            action = "skip"

        candidates.append(OcrScanCandidate(
            raw_text=text,
            recommended_action=action,
            candidates=match_candidates,
        ))

    return candidates
