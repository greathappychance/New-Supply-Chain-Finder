from __future__ import annotations

import math
from collections.abc import Sequence

from .constants import NO_VALUE
from .models import Supplier
from .ranking import is_korean


def _is_number(value: float | int | None) -> bool:
    return value is not None and math.isfinite(value)


def format_text(value: str | None) -> str:
    return value.strip() if value and value.strip() else NO_VALUE


def format_integer(value: int | float | None) -> str:
    return str(round(value)) if _is_number(value) else NO_VALUE


def format_revenue(value: int | float | None) -> str:
    """매출액(억원): 천 단위 쉼표"""
    return f"{round(value):,}" if _is_number(value) else NO_VALUE


def format_ratio(value: float | None, estimated: bool) -> str:
    """매출비율: "45%", 추정치는 "45%*" """
    if not _is_number(value):
        return NO_VALUE
    rounded = round(value * 10) / 10
    text = str(int(rounded)) if rounded == int(rounded) else str(rounded)
    return f"{text}%{'*' if estimated else ''}"


def format_list(items: Sequence[str]) -> str:
    values = [v.strip() for v in items if v and v.strip()]
    return ", ".join(values) if values else NO_VALUE


def format_main_items(items: Sequence[str]) -> str:
    """주요 취급 품목: 항상 3칸, 빈 칸은 "-" """
    return ", ".join(format_text(items[i] if i < len(items) else None) for i in range(3))


def format_supplier_cell(supplier: Supplier, key: str) -> str:
    """결과 표 셀 문자열. 결측값은 모두 "-" (PRD §3.3.3)"""
    if key == "years_in_business":
        return format_integer(supplier.years_in_business)
    if key == "revenue_krw_100m":
        return format_revenue(supplier.revenue_krw_100m)
    if key == "item_revenue_ratio":
        return format_ratio(supplier.item_revenue_ratio, supplier.is_revenue_ratio_estimated)
    if key == "main_items":
        return format_main_items(supplier.main_items)
    if key in ("major_customers", "steel_customers", "source_urls"):
        return format_list(getattr(supplier, key))
    return format_text(getattr(supplier, key))


def summarize(suppliers: Sequence[Supplier]) -> tuple[int, int, int]:
    """(전체, 한국, 해외) 업체 수"""
    korean = sum(1 for s in suppliers if is_korean(s))
    return len(suppliers), korean, len(suppliers) - korean


def has_estimated_value(suppliers: Sequence[Supplier]) -> bool:
    return any(s.is_revenue_ratio_estimated and s.item_revenue_ratio is not None for s in suppliers)


def _final_consonant(word: str) -> int | None:
    """마지막 글자의 종성 번호 (0이면 받침 없음). 한글 음절이 아니면 None."""
    stripped = word.strip()
    if not stripped:
        return None
    code = ord(stripped[-1])
    if code < 0xAC00 or code > 0xD7A3:
        return None
    return (code - 0xAC00) % 28


def object_particle(word: str) -> str:
    """목적격 조사: 을/를. 한글이 아니면 "을(를)" """
    jong = _final_consonant(word)
    if jong is None:
        return "을(를)"
    return "를" if jong == 0 else "을"


def direction_particle(word: str) -> str:
    """방향 조사: 으로/로. 받침이 없거나 ㄹ 받침이면 "로". 한글이 아니면 "(으)로" """
    jong = _final_consonant(word)
    if jong is None:
        return "(으)로"
    return "로" if jong in (0, 8) else "으로"


def format_interpretation(item_name: str, interpreted_item: str) -> str:
    """"'부품'을 '산업용 베어링'으로 해석했습니다." (PRD E-03)"""
    return (
        f"'{item_name}'{object_particle(item_name)} "
        f"'{interpreted_item}'{direction_particle(interpreted_item)} 해석했습니다."
    )
