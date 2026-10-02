from __future__ import annotations

from .constants import MIN_RESULTS
from .filtering import filter_candidates
from .models import RecommendRequest, RecommendResponse
from .providers.base import SupplierProvider
from .ranking import is_korean, rank_suppliers
from .selection import select_suppliers


def recommend(request: RecommendRequest, provider: SupplierProvider) -> RecommendResponse:
    """후보 수집 → 필터링 → 정렬 → 구성 조정 (PRD §6)"""
    result = provider.search(request.purchase_type, request.item_name)

    selected = select_suppliers(rank_suppliers(filter_candidates(result.candidates, request.purchase_type)))
    suppliers = [c.to_supplier() for c in selected]

    count = len(suppliers)
    return RecommendResponse(
        suppliers=suppliers,
        data_as_of=result.data_as_of,
        is_sample_data=result.is_sample_data,
        interpreted_item=result.interpreted_item,
        notice=f"조건을 만족하는 업체가 {count}곳만 확인되었습니다." if 0 < count < MIN_RESULTS else None,
        fx_as_of=result.fx_as_of if any(not is_korean(s) for s in suppliers) else None,
    )
