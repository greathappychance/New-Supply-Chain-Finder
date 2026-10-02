"""가상 업체 샘플 데이터 provider (개발·테스트용). SUPPLIER_PROVIDER=mock 일 때만 쓴다."""

from __future__ import annotations

import json
import re
from functools import cache

from ..config import APP_DIR
from ..models import ProviderResult, SupplierCandidate

DATA_DIR = APP_DIR / "data"


@cache
def _load(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def krw_per_unit() -> dict[str, float]:
    return _load("fx-rates.json")["krwPerUnit"]


def fx_as_of() -> str:
    return _load("fx-rates.json")["asOf"]


def normalize_item_name(value: str) -> str:
    return re.sub(r"[\s()·\-_/.,]", "", value.lower())


def match_categories(item_name: str) -> tuple[list[str], str | None]:
    """품목명을 품목 분류로 해석한다. 모호한 일반명사는 대표 분류로 해석한다 (PRD E-03)."""
    data = _load("item-categories.json")
    query = normalize_item_name(item_name)

    ambiguous_id = data["ambiguousTerms"].get(query)
    if ambiguous_id:
        category = next((c for c in data["categories"] if c["id"] == ambiguous_id), None)
        return [ambiguous_id], category["name"] if category else None

    ids = [
        c["id"]
        for c in data["categories"]
        if any(normalize_item_name(s) in query or query in normalize_item_name(s) for s in c["synonyms"])
    ]
    return ids, None


def _to_krw_100m(revenue: dict | None) -> int | None:
    """백만 단위 외화 매출액을 억원으로 환산한다. 환율이 없는 통화는 None."""
    if not revenue:
        return None
    rate = krw_per_unit().get(revenue["currency"])
    return None if rate is None else round(revenue["millions"] * rate / 100)


def _to_candidate(record: dict, category_ids: list[str], source: str, as_of: str) -> SupplierCandidate | None:
    matched = [c for c in record["categories"] if c["id"] in category_ids]
    if not matched:
        return None
    # 여러 분류가 매칭되면 매출비율이 가장 큰 분류를 해당 품목으로 본다.
    best = max(matched, key=lambda c: -1 if c["ratio"] is None else c["ratio"])
    base_year = int(as_of[:4])
    return SupplierCandidate(
        name=record["name"],
        country=record["country"],
        location=record["location"],
        years_in_business=None if record["foundedYear"] is None else base_year - record["foundedYear"],
        company_size=record["companySize"],
        revenue_krw_100m=_to_krw_100m(record["revenue"]),
        credit_grade=record["creditGrade"],
        main_items=tuple(record["mainItems"]),
        item_revenue_ratio=best["ratio"],
        major_customers=tuple(record["majorCustomers"]),
        steel_customers=tuple(record["steelCustomers"]),
        is_revenue_ratio_estimated=best.get("estimated", False),
        source=source,
        as_of=as_of,
        status=record["status"],
        is_service_provider=record["isServiceProvider"],
    )


class MockSupplierProvider:
    def search(self, purchase_type: str, item_name: str) -> ProviderResult:
        data = _load("mock-suppliers.json")
        ids, interpreted = match_categories(item_name)
        candidates = [
            c
            for r in data["suppliers"]
            if (c := _to_candidate(r, ids, data["source"], data["asOf"])) is not None
        ]
        return ProviderResult(
            candidates=candidates,
            data_as_of=data["asOf"],
            is_sample_data=True,
            interpreted_item=interpreted,
            fx_as_of=fx_as_of(),
        )
