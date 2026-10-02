from __future__ import annotations

import math
from typing import TypeVar

from .constants import MAX_RESULTS, MIN_KOREAN_SHARE
from .models import Supplier
from .ranking import is_korean

T = TypeVar("T", bound=Supplier)


def min_korean_count(total: int) -> int:
    """n개 추천 시 필요한 한국 업체 최소 수. 5~9개 → 해외 최대 1, 10개 → 해외 최대 2 (PRD §3.3.1)"""
    # 0.8 * 6 = 4.800000000000001 같은 부동소수점 오차를 흡수한다.
    return math.ceil(total * MIN_KOREAN_SHARE - 1e-9)


def select_suppliers(ranked: list[T]) -> list[T]:
    """정렬된 후보에서 최대 10개를 고르되 한국 업체 비율 80% 이상을 지킨다.

    비율을 맞출 수 없으면 해외 업체를 줄이고, 그래도 안 되면 총 개수를 줄인다 (PRD E-02).
    결과는 한국 업체 → 해외 업체 순서를 유지한다.
    """
    korean = [s for s in ranked if is_korean(s)]
    foreign = [s for s in ranked if not is_korean(s)]

    for total in range(min(MAX_RESULTS, len(ranked)), 0, -1):
        korean_count = max(min_korean_count(total), total - len(foreign))
        if korean_count <= len(korean):
            return korean[:korean_count] + foreign[: total - korean_count]
    return []
