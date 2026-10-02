"""정렬·선정·필터링·검증 규칙 (PRD §1.3, §3.2, §3.3)"""

import pytest

from supply_finder.filtering import apply_service_preference, filter_candidates, meets_min_grade
from supply_finder.ranking import grade_rank, is_korean, rank_suppliers
from supply_finder.selection import min_korean_count, select_suppliers
from supply_finder.validation import validate_recommend_input
from tests.helpers import make_candidate, make_many


def names(items):
    return [s.name for s in items]


# ---------- 정렬 ----------

def test_grade_rank_order():
    assert grade_rank("AAA") < grade_rank("AA+") < grade_rank("A-") < grade_rank("BBB+")
    assert grade_rank("-") > grade_rank("D")
    assert grade_rank(" bbb+ ") == grade_rank("BBB+")


def test_korean_always_above_foreign():
    foreign = make_candidate(name="F", country="독일", item_revenue_ratio=99, credit_grade="AAA")
    korean = make_candidate(name="K", item_revenue_ratio=1, credit_grade="-")
    assert names(rank_suppliers([foreign, korean])) == ["K", "F"]


def test_ratio_desc_and_none_last_within_country():
    unknown = make_candidate(name="null", item_revenue_ratio=None, credit_grade="AAA")
    low = make_candidate(name="low", item_revenue_ratio=1)
    high = make_candidate(name="high", item_revenue_ratio=80)
    foreign = make_candidate(name="foreign", country="미국", item_revenue_ratio=90)
    assert names(rank_suppliers([unknown, foreign, low, high])) == ["high", "low", "null", "foreign"]


def test_grade_breaks_ratio_ties_and_dash_last():
    items = [make_candidate(name=g, item_revenue_ratio=40, credit_grade=g) for g in ["BBB", "-", "A+", "BBB+"]]
    assert names(rank_suppliers(items)) == ["A+", "BBB+", "BBB", "-"]


def test_name_tiebreak_is_deterministic():
    a = make_candidate(name="(주)이음", item_revenue_ratio=40)
    b = make_candidate(name="(주)버금", item_revenue_ratio=40)
    assert names(rank_suppliers([a, b])) == names(rank_suppliers([b, a])) == ["(주)버금", "(주)이음"]


# ---------- 선정 (5~10개, 한국 80% 이상) ----------

@pytest.mark.parametrize("total,expected", [(5, 4), (6, 5), (7, 6), (8, 7), (9, 8), (10, 8)])
def test_min_korean_count_matches_prd_table(total, expected):
    assert min_korean_count(total) == expected


def pool(k, f):
    return rank_suppliers(make_many(k) + make_many(f, country="일본"))


def counts(items):
    k = sum(1 for s in items if is_korean(s))
    return len(items), k, len(items) - k


@pytest.mark.parametrize(
    "k,f,expected",
    [(20, 5, (10, 8, 2)), (12, 0, (10, 10, 0)), (5, 1, (6, 5, 1)), (6, 3, (7, 6, 1)), (4, 3, (5, 4, 1)),
     (3, 1, (3, 3, 0)), (1, 4, (1, 1, 0)), (0, 5, (0, 0, 0))],
)
def test_select_counts(k, f, expected):
    assert counts(select_suppliers(pool(k, f))) == expected


def test_select_always_within_rules():
    for k in range(13):
        for f in range(7):
            total, korean, _ = counts(select_suppliers(pool(k, f)))
            assert total <= 10
            if total:
                assert korean / total >= 0.8


# ---------- 필터링 ----------

@pytest.mark.parametrize("grade,ok", [("AAA", True), ("BBB-", True), ("BB+", False), ("D", False), ("-", True), ("ZZ", False)])
def test_meets_min_grade(grade, ok):
    assert meets_min_grade(grade) is ok


def test_filter_excludes_closed_and_low_grade():
    items = [
        make_candidate(name="ok"),
        make_candidate(status="휴업"),
        make_candidate(status="폐업"),
        make_candidate(status="회생절차"),
        make_candidate(credit_grade="BB+"),
        make_candidate(name="foreign", country="독일", credit_grade="-"),
    ]
    assert names(filter_candidates(items, "자재구매")) == ["ok", "foreign"]


def test_service_preference():
    service_heavy = make_many(5, is_service_provider=True) + make_many(3)
    assert all(c.is_service_provider for c in apply_service_preference(service_heavy, "수리"))
    service_light = make_many(2, is_service_provider=True) + make_many(6)
    assert len(apply_service_preference(service_light, "수리")) == 8
    goods = make_many(5) + make_many(3, is_service_provider=True)
    assert not any(c.is_service_provider for c in apply_service_preference(goods, "설비구매"))


# ---------- 입력 검증 ----------

@pytest.mark.parametrize("value,error", [
    ("", "품목명을 입력해주세요."),
    ("   ", "품목명을 입력해주세요."),
    ("가", "품목명은 2자 이상 입력해주세요."),
    ("가나", None),
    ("가" * 200, None),
    ("가" * 201, "품목명은 200자 이하로 입력해주세요."),
    ("🔧" * 200, None),
])
def test_item_name_validation(value, error):
    assert validate_recommend_input("수리", value).item_name == error


def test_purchase_type_validation():
    assert validate_recommend_input("", "감속기").purchase_type == "구매 유형을 선택해주세요."
    assert validate_recommend_input("임대", "감속기").purchase_type == "올바른 구매 유형이 아닙니다."
    for t in ["원료구매", "설비구매", "자재구매", "수리", "용역"]:
        assert validate_recommend_input(t, "감속기").purchase_type is None
