from __future__ import annotations

from dataclasses import replace
from itertools import count

from supply_finder.models import SupplierCandidate

_seq = count(1)


def make_candidate(**overrides) -> SupplierCandidate:
    """테스트용 후보 업체. 지정하지 않은 필드는 한국·정상·BBB 기본값"""
    base = SupplierCandidate(
        name=f"테스트업체{next(_seq):03d}",
        country="대한민국",
        location="서울 중구",
        years_in_business=10,
        company_size="중소기업",
        revenue_krw_100m=100,
        credit_grade="BBB",
        main_items=("품목A", "품목B", "품목C"),
        item_revenue_ratio=50,
        major_customers=("고객사A",),
        steel_customers=(),
        source="테스트",
        as_of="2026-09-30",
    )
    return replace(base, **overrides)


def make_many(n: int, **overrides) -> list[SupplierCandidate]:
    return [make_candidate(**overrides) for _ in range(n)]
