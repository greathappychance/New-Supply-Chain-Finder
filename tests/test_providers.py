"""표시 형식, 샘플 데이터 추천 흐름, OpenAI 응답 정규화"""

import pytest

from supply_finder.formatting import format_interpretation, format_ratio, format_revenue, format_supplier_cell
from supply_finder.models import ProviderResult, RecommendRequest
from supply_finder.providers.base import ProviderConfigError
from supply_finder.providers.mock import MockSupplierProvider, match_categories
from supply_finder.providers.openai_provider import (
    AI_SOURCE_LABEL,
    AiSupplier,
    OpenAISupplierProvider,
    Revenue,
    normalize_grade,
    to_candidate,
)
from supply_finder.ranking import is_korean
from supply_finder.recommend import recommend
from tests.helpers import make_candidate

# ---------- 표시 형식 ----------

def test_formats():
    assert format_revenue(1250) == "1,250"
    assert format_revenue(None) == "-"
    assert format_ratio(45, False) == "45%"
    assert format_ratio(45, True) == "45%*"
    assert format_ratio(12.34, False) == "12.3%"
    assert format_ratio(None, True) == "-"


def test_missing_values_render_as_dash():
    s = make_candidate(location="", years_in_business=None, company_size=None, revenue_krw_100m=None,
                       credit_grade="", item_revenue_ratio=None, major_customers=(), steel_customers=())
    for key in ["location", "years_in_business", "company_size", "revenue_krw_100m", "credit_grade",
                "item_revenue_ratio", "major_customers", "steel_customers"]:
        assert format_supplier_cell(s, key) == "-"
    assert format_supplier_cell(make_candidate(main_items=("A", "", "")), "main_items") == "A, -, -"


def test_interpretation_particles():
    assert format_interpretation("부품", "산업용 베어링") == "'부품'을 '산업용 베어링'으로 해석했습니다."
    assert format_interpretation("기계", "감속기") == "'기계'를 '감속기'로 해석했습니다."
    assert format_interpretation("자재", "산업용 윤활유") == "'자재'를 '산업용 윤활유'로 해석했습니다."
    assert format_interpretation("part", "베어링") == "'part'을(를) '베어링'으로 해석했습니다."


# ---------- 샘플 데이터 추천 흐름 ----------

def run(purchase_type, item):
    return recommend(RecommendRequest(purchase_type, item), MockSupplierProvider())


def test_match_categories():
    assert match_categories("내화 벽돌")[0] == ["refractory"]
    assert match_categories("Gear Box")[0] == ["reducer"]
    assert match_categories("부품") == (["bearing"], "산업용 베어링")
    assert match_categories("설비")[0] == ["reducer"]
    assert match_categories("우주선")[0] == []


def test_refractory_full_result():
    res = run("자재구매", "내화물")
    names = [s.name for s in res.suppliers]
    assert len(names) == 10 and sum(map(is_korean, res.suppliers)) == 8
    assert names[0] == "다솜내화공업(주)" and names[7] == "(주)라온내화"
    assert "(주)단미세라믹스" not in names and "(주)청암내화" not in names
    assert names.index("(주)누리세라텍") < names.index("(주)새길세라믹")
    assert res.fx_as_of == "2026-09-30" and res.is_sample_data
    demo = next(s for s in res.suppliers if s.name == "Demo Refractory Co., Ltd.")
    assert demo.revenue_krw_100m == 7980
    assert not hasattr(res.suppliers[0], "status")


def test_shortage_notices():
    crane = run("설비구매", "크레인")
    assert len(crane.suppliers) == 3 and all(map(is_korean, crane.suppliers))
    assert crane.notice == "조건을 만족하는 업체가 3곳만 확인되었습니다."
    assert run("원료구매", "철광석").notice == "조건을 만족하는 업체가 1곳만 확인되었습니다."
    empty = run("자재구매", "우주선")
    assert empty.suppliers == [] and empty.notice is None


def test_other_scenarios():
    assert len(run("설비구매", "감속기").suppliers) == 7
    lub = run("자재구매", "윤활유")
    assert len(lub.suppliers) == 5 and lub.fx_as_of is None
    assert run("자재구매", "부품").interpreted_item == "산업용 베어링"


# ---------- OpenAI 응답 정규화 ----------

def ai_supplier(**overrides) -> AiSupplier:
    data = dict(
        name="(주)테스트", country="대한민국", location="경기 화성시", founded_year=2000, company_size="중소기업",
        revenue=Revenue(currency="KRW", millions=50000), credit_grade="BBB+", main_items=["볼트", "너트", "와셔"],
        item_revenue_ratio=60, is_ratio_estimated=False, major_customers=["고객사"], steel_customers=[],
        is_service_provider=False, status="정상", source_urls=["https://example.com/a"],
    )
    data.update(overrides)
    return AiSupplier(**data)


@pytest.mark.parametrize("raw,expected", [
    ("A+", "A+"), ("a-", "A-"), ("A0", "A"), ("BBB0", "BBB"), (" BBB-(안정적) ", "BBB-"),
    ("AA+ (Stable)", "AA+"), ("-", "-"), ("", "-"), ("Baa1", "-"), ("없음", "-"),
])
def test_normalize_grade(raw, expected):
    assert normalize_grade(raw) == expected


def test_to_candidate_basics():
    c = to_candidate(ai_supplier(), "2026-10-02")
    assert (c.years_in_business, c.revenue_krw_100m, c.source) == (26, 500, AI_SOURCE_LABEL)
    assert to_candidate(ai_supplier(revenue=Revenue(currency="usd", millions=100)), "2026-10-02").revenue_krw_100m == 1380
    assert to_candidate(ai_supplier(revenue=Revenue(currency="XYZ", millions=1)), "2026-10-02").revenue_krw_100m is None
    for country in ["한국", "South Korea", "KR"]:
        assert to_candidate(ai_supplier(country=country), "2026-10-02").country == "대한민국"
    assert to_candidate(ai_supplier(main_items=["A"]), "2026-10-02").main_items == ("A", "", "")
    bad = to_candidate(ai_supplier(item_revenue_ratio=150, founded_year=2030), "2026-10-02")
    assert bad.item_revenue_ratio is None and bad.years_in_business is None
    urls = to_candidate(ai_supplier(source_urls=["https://a.com", "javascript:alert(1)"]), "2026-10-02").source_urls
    assert urls == ("https://a.com",)


@pytest.mark.parametrize("raw,expected", [("중견", "중견기업"), ("대기업 (상호출자제한)", "대기업"), ("모름", None), (None, None)])
def test_normalize_size(raw, expected):
    assert to_candidate(ai_supplier(company_size=raw), "2026-10-02").company_size == expected


@pytest.mark.parametrize("raw,expected", [("폐업(2024)", "폐업"), ("기업회생 절차 진행", "회생절차"), ("법정관리", "회생절차"), ("영업중", "정상")])
def test_normalize_status(raw, expected):
    assert to_candidate(ai_supplier(status=raw), "2026-10-02").status == expected


def test_ai_results_go_through_same_rules():
    raw = [ai_supplier(name=f"국내{i}", item_revenue_ratio=10 + i) for i in range(9)]
    raw += [ai_supplier(name="폐업사", status="폐업", item_revenue_ratio=99),
            ai_supplier(name="등급미달", credit_grade="BB", item_revenue_ratio=98)]
    raw += [ai_supplier(name=f"해외{i}", country=c, credit_grade="-", item_revenue_ratio=90)
            for i, c in enumerate(["독일", "일본", "미국"])]

    class FakeProvider:
        def search(self, purchase_type, item_name):
            return ProviderResult([to_candidate(s, "2026-10-02") for s in raw], "2026-10-02", False, None, "2026-09-30")

    names = [s.name for s in recommend(RecommendRequest("자재구매", "볼트"), FakeProvider()).suppliers]
    assert len(names) == 10
    assert names[:8] == [f"국내{i}" for i in range(8, 0, -1)]
    assert "폐업사" not in names and "등급미달" not in names


def test_missing_or_wrong_key_raises_config_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    with pytest.raises(ProviderConfigError):
        OpenAISupplierProvider().search("자재구매", "볼트")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-ant-wrong-service")
    with pytest.raises(ProviderConfigError):
        OpenAISupplierProvider().search("자재구매", "볼트")
