from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Supplier:
    """추천 결과 표의 한 행. 필드 순서는 PRD §3.3.3의 열 순서와 같다."""

    name: str
    country: str
    location: str
    years_in_business: int | None
    company_size: str | None
    revenue_krw_100m: int | None  # 지난해 매출액(억원). 해외 업체는 원화 환산값
    credit_grade: str  # 없으면 "-"
    main_items: tuple[str, str, str]
    item_revenue_ratio: float | None  # 해당품목 매출비율(%)
    major_customers: tuple[str, ...]
    steel_customers: tuple[str, ...]

    is_revenue_ratio_estimated: bool = False
    source: str = ""
    source_urls: tuple[str, ...] = ()
    as_of: str = ""


@dataclass(frozen=True)
class SupplierCandidate(Supplier):
    """provider가 반환하는 후보 업체. 화면에 보내기 전에 내부 필드를 제거한다."""

    status: str = "정상"  # 정상 / 휴업 / 폐업 / 회생절차
    is_service_provider: bool = False

    def to_supplier(self) -> Supplier:
        return Supplier(**{f.name: getattr(self, f.name) for f in fields(Supplier)})


@dataclass(frozen=True)
class RecommendRequest:
    purchase_type: str
    item_name: str


@dataclass(frozen=True)
class ProviderResult:
    candidates: list[SupplierCandidate]
    data_as_of: str
    is_sample_data: bool
    interpreted_item: str | None = None
    fx_as_of: str | None = None


@dataclass(frozen=True)
class RecommendResponse:
    suppliers: list[Supplier]
    data_as_of: str
    is_sample_data: bool
    interpreted_item: str | None = None  # 모호한 품목명을 해석한 결과 (PRD E-03)
    notice: str | None = None  # 결과 부족 안내 (PRD E-01)
    fx_as_of: str | None = None
