from __future__ import annotations

from .constants import CREDIT_GRADE_ORDER, MIN_CREDIT_GRADE, MIN_RESULTS, NO_VALUE
from .models import SupplierCandidate
from .ranking import grade_rank


def meets_min_grade(grade: str, min_grade: str = MIN_CREDIT_GRADE) -> bool:
    """등급이 없으면("-") 제외하지 않는다. 알 수 없는 등급 문자열은 하한선 미달로 본다."""
    if grade.strip() == NO_VALUE:
        return True
    rank = grade_rank(grade)
    return rank < len(CREDIT_GRADE_ORDER) and rank <= grade_rank(min_grade)


def is_eligible(candidate: SupplierCandidate) -> bool:
    """"준수한 수준" 기준 (PRD §1.3): 정상 영업 중이고 신용등급 하한선 이상"""
    return candidate.status == "정상" and meets_min_grade(candidate.credit_grade)


def apply_service_preference(candidates: list[SupplierCandidate], purchase_type: str) -> list[SupplierCandidate]:
    """수리·용역은 서비스 업체를, 그 외 구매 유형은 제조·공급 업체를 우선한다.

    우선 대상만으로 최소 추천 수를 채울 수 없으면 전체 후보를 사용한다.
    """
    want_service = purchase_type in ("수리", "용역")
    preferred = [c for c in candidates if c.is_service_provider == want_service]
    return preferred if len(preferred) >= MIN_RESULTS else candidates


def filter_candidates(candidates: list[SupplierCandidate], purchase_type: str) -> list[SupplierCandidate]:
    return apply_service_preference([c for c in candidates if is_eligible(c)], purchase_type)
