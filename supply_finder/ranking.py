from __future__ import annotations

from functools import cmp_to_key
from typing import TypeVar

from .constants import CREDIT_GRADE_ORDER, KOREA
from .models import Supplier

T = TypeVar("T", bound=Supplier)


def is_korean(supplier: Supplier) -> bool:
    return supplier.country == KOREA


def grade_rank(grade: str) -> int:
    """등급이 높을수록 작은 값. "-"나 알 수 없는 등급은 가장 낮게 취급한다."""
    normalized = grade.strip().upper()
    return CREDIT_GRADE_ORDER.index(normalized) if normalized in CREDIT_GRADE_ORDER else len(CREDIT_GRADE_ORDER)


def compare_suppliers(a: Supplier, b: Supplier) -> int:
    """추천 순서 비교 (PRD §3.3.2)

    1. 한국 업체 우선  2. 해당품목 매출비율 높은 순(None은 뒤)  3. 신용평가등급 높은 순("-"는 뒤)
    모두 같으면 결과가 매번 같도록 업체명 순.
    """
    by_country = int(not is_korean(a)) - int(not is_korean(b))
    if by_country:
        return by_country

    ra, rb = a.item_revenue_ratio, b.item_revenue_ratio
    if ra != rb:
        if ra is None:
            return 1
        if rb is None:
            return -1
        return -1 if ra > rb else 1

    by_grade = grade_rank(a.credit_grade) - grade_rank(b.credit_grade)
    if by_grade:
        return by_grade

    return (a.name > b.name) - (a.name < b.name)


def rank_suppliers(suppliers: list[T]) -> list[T]:
    return sorted(suppliers, key=cmp_to_key(compare_suppliers))
