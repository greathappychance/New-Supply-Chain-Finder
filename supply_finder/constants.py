APP_TITLE = "New Supply Chain Finder"

PURCHASE_TYPES: tuple[str, ...] = ("원료구매", "설비구매", "자재구매", "수리", "용역")

COMPANY_SIZES: tuple[str, ...] = ("대기업", "중견기업", "중소기업")

BUSINESS_STATUSES: tuple[str, ...] = ("정상", "휴업", "폐업", "회생절차")

# 결과 표 열 정의. 순서는 PRD §3.3.3에 고정되어 있으므로 바꾸지 않는다.
RESULT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("name", "업체명"),
    ("country", "국가"),
    ("location", "소재지"),
    ("years_in_business", "업력(년)"),
    ("company_size", "기업규모분류"),
    ("revenue_krw_100m", "지난해 매출액(억원)"),
    ("credit_grade", "신용평가등급"),
    ("main_items", "주요 취급 품목 3가지"),
    ("item_revenue_ratio", "해당품목 매출비율"),
    ("major_customers", "주요 거래처"),
    ("steel_customers", "철강 산업군 고객사"),
)

# 신용평가등급, 높은 순. "-"(등급 없음)는 목록에 없으며 가장 낮게 취급한다.
CREDIT_GRADE_ORDER: tuple[str, ...] = (
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
    "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
    "B+", "B", "B-", "CCC", "CC", "C", "D",
)

NO_VALUE = "-"
KOREA = "대한민국"

ITEM_NAME_MIN_LENGTH = 2
ITEM_NAME_MAX_LENGTH = 200

# 신용평가등급 하한선. 이보다 낮은 등급의 업체는 추천에서 제외한다 ("-"는 제외하지 않음).
MIN_CREDIT_GRADE = "BBB-"

MIN_RESULTS = 5
MAX_RESULTS = 10
# 추천 결과 중 한국 업체 최소 비율
MIN_KOREAN_SHARE = 0.8
