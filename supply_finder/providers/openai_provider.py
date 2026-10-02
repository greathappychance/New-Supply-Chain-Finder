"""OpenAI(Responses API + 웹 검색)로 실제 공급 업체를 조사하는 provider."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from ..config import get_setting
from ..constants import CREDIT_GRADE_ORDER, KOREA, NO_VALUE
from ..models import ProviderResult, SupplierCandidate
from .base import ProviderConfigError
from .mock import fx_as_of, krw_per_unit

DEFAULT_MODEL = "gpt-6-astra"
AI_SOURCE_LABEL = "AI 웹 검색"
REQUEST_TIMEOUT_SECONDS = 170


class Revenue(BaseModel):
    currency: str = Field(description="ISO 통화 코드 (KRW, USD, EUR, JPY, CNY 등)")
    millions: float = Field(description="직전 회계연도 매출액, 해당 통화 백만 단위")


class AiSupplier(BaseModel):
    name: str = Field(description="정식 법인명. 한국 업체는 한글 상호(예: (주)○○)")
    country: str = Field(description="본사 국가의 한국어 이름 (예: 대한민국, 독일, 일본)")
    location: str = Field(description="본사 소재지. 한국은 '경북 포항시'처럼 시·도 + 시·군·구")
    founded_year: int | None = Field(description="설립연도. 확인 못 하면 null")
    # enum 대신 문자열로 받고 코드에서 정규화한다 (값이 조금 달라도 응답 전체가 실패하지 않도록).
    company_size: str | None = Field(description="대기업 / 중견기업 / 중소기업 중 하나. 모르면 null")
    revenue: Revenue | None
    credit_grade: str = Field(
        description="S&P 표기 신용등급(AAA~D, +/-). 국내는 회사채 또는 기업신용평가 등급. 확인 못 하면 '-'"
    )
    main_items: list[str] = Field(description="주요 취급 품목 3가지, 매출 비중 큰 순")
    item_revenue_ratio: float | None = Field(description="검색 품목의 매출 비중(%). 근거가 전혀 없으면 null")
    is_ratio_estimated: bool = Field(description="매출 비중이 공시 수치가 아니라 추정치이면 true")
    major_customers: list[str] = Field(description="주요 거래처 최대 5곳")
    steel_customers: list[str] = Field(description="주요 거래처 중 철강 제조·가공 업체. 없으면 빈 배열")
    is_service_provider: bool = Field(description="수리·정비·점검 등 서비스 제공 업체이면 true")
    status: str = Field(description="정상 / 휴업 / 폐업 / 회생절차 중 하나")
    source_urls: list[str] = Field(description="이 업체 정보를 확인한 웹 페이지 URL")


class AiResult(BaseModel):
    interpreted_item: str | None = Field(
        description="품목명이 모호해서 구체적인 품목으로 해석했다면 그 품목명, 아니면 null"
    )
    suppliers: list[AiSupplier]


SYSTEM_PROMPT = """당신은 한국 기업 구매담당자를 돕는 공급선 조사 전문가입니다.
주어진 구매 유형과 품목명에 대해 그 품목을 실제로 생산·공급(수리·용역이면 서비스 제공)하는 업체를 웹 검색으로 조사합니다.

조사 결과는 별도 프로그램이 필터링·정렬해서 구매담당자에게 표로 보여줍니다. 그러므로:
- 후보는 12~15곳을 찾고, 그중 한국 업체를 최대한 많이(가능하면 12곳 이상) 포함하세요. 결과 표의 80% 이상이 한국 업체여야 하기 때문입니다.
- 웹 검색으로 실존과 해당 품목 취급을 확인한 업체만 넣으세요. 업체를 지어내거나 확인하지 않은 정보를 채우면 구매 결정을 잘못 이끌 수 있습니다.
- 확인하지 못한 값은 추측하지 말고 null(신용등급은 "-")로 두세요.
- 단, 해당품목 매출비율(item_revenue_ratio)은 추천 순서를 정하는 핵심 기준입니다. 공시 수치가 없으면 홈페이지 제품 목록, 업종, 주력 제품 구성을 근거로 추정치(예: 볼트 전문 제조사 80~100%, 여러 제품 중 하나 20~40%)를 적고 is_ratio_estimated를 true로 표시하세요. 판단할 근거가 전혀 없을 때만 null로 두세요.
- 신용등급은 국내 업체는 한국기업평가·한국신용평가·NICE신용평가 회사채 등급이나 기업신용평가 등급, 해외 업체는 S&P·Moody's·Fitch 등급을 S&P 표기(AAA~D, +/-)로 적습니다.
- 기업규모분류는 국내는 공정거래위원회 대기업집단·중견기업법·중소기업기본법 기준, 해외 업체는 매출·종업원 규모로 준용합니다.
- 휴업·폐업·회생절차 중인 업체를 알게 되면 status에 그대로 표시하세요 (프로그램이 제외합니다).
- 품목명이 "부품", "자재"처럼 너무 일반적이면 구매 유형에 맞는 대표 품목으로 해석해 조사하고 interpreted_item에 적으세요.
- 텍스트 값은 한국어로 쓰되, 해외 업체명은 원어 표기를 유지하세요."""


def normalize_country(country: str) -> str:
    c = country.strip()
    return KOREA if re.fullmatch(r"(대한민국|한국|south korea|korea|republic of korea|kr)", c, re.I) else c


def normalize_grade(grade: str) -> str:
    """"A0", "BBB-(안정적)", "a+" 같은 표기를 등급표의 값으로 맞춘다. 알 수 없으면 "-"."""
    # 뒤에 영문·숫자가 이어지면(예: Moody's "Baa1") 등급표 표기가 아니므로 인정하지 않는다. "A0"의 0은 허용.
    match = re.match(r"^(AAA|AA|A|BBB|BB|B|CCC|CC|C|D)([+-]|0)?(?![A-Z0-9])", grade.strip().upper())
    if not match:
        return NO_VALUE
    sign = match.group(2) or ""
    normalized = match.group(1) + ("" if sign == "0" else sign)
    return normalized if normalized in CREDIT_GRADE_ORDER else NO_VALUE


def normalize_company_size(size: str | None) -> str | None:
    s = re.sub(r"\s", "", size or "")
    if s.startswith("대기업"):
        return "대기업"
    if s.startswith("중견"):
        return "중견기업"
    if s.startswith("중소") or s.startswith("소기업"):
        return "중소기업"
    return None


def normalize_status(status: str) -> str:
    if "폐업" in status:
        return "폐업"
    if "휴업" in status:
        return "휴업"
    if "회생" in status or "법정관리" in status:
        return "회생절차"
    return "정상"


def to_krw_100m(revenue: Revenue | None) -> int | None:
    if revenue is None:
        return None
    rate = krw_per_unit().get(revenue.currency.strip().upper())
    return None if rate is None else round(revenue.millions * rate / 100)


def to_candidate(s: AiSupplier, as_of: str) -> SupplierCandidate:
    base_year = int(as_of[:4])
    items = [v.strip() for v in s.main_items if v.strip()]
    items += [""] * (3 - len(items))
    ratio = s.item_revenue_ratio
    return SupplierCandidate(
        name=s.name.strip(),
        country=normalize_country(s.country),
        location=s.location.strip(),
        years_in_business=(
            base_year - s.founded_year if s.founded_year is not None and s.founded_year <= base_year else None
        ),
        company_size=normalize_company_size(s.company_size),
        revenue_krw_100m=to_krw_100m(s.revenue),
        credit_grade=normalize_grade(s.credit_grade),
        main_items=(items[0], items[1], items[2]),
        item_revenue_ratio=ratio if ratio is not None and 0 <= ratio <= 100 else None,
        major_customers=tuple(s.major_customers),
        steel_customers=tuple(s.steel_customers),
        is_revenue_ratio_estimated=s.is_ratio_estimated,
        source=AI_SOURCE_LABEL,
        source_urls=tuple(u for u in s.source_urls if re.match(r"^https?://", u)),
        as_of=as_of,
        status=normalize_status(s.status),
        is_service_provider=s.is_service_provider,
    )


def today_in_korea() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")


class OpenAISupplierProvider:
    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        api_key = get_setting("OPENAI_API_KEY")
        if not api_key:
            raise ProviderConfigError(
                "AI 검색에 필요한 OpenAI API 키가 설정되지 않았습니다. "
                ".env 파일(배포 환경은 Secrets)에 OPENAI_API_KEY를 입력해주세요."
            )
        # 다른 서비스의 키(예: Anthropic "sk-ant-")를 OpenAI 서버로 보내지 않는다.
        if api_key.startswith("sk-ant-"):
            raise ProviderConfigError("OPENAI_API_KEY에 Anthropic 키가 들어 있습니다. OpenAI API 키를 입력해주세요.")
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=1)
        return self._client

    def search(self, purchase_type: str, item_name: str) -> ProviderResult:
        client = self._get_client()
        model = get_setting("OPENAI_MODEL", DEFAULT_MODEL)
        as_of = today_in_korea()

        response = client.responses.parse(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=f"구매 유형: {purchase_type}\n품목명: {item_name}\n기준일: {as_of}",
            tools=[
                {
                    "type": "web_search",
                    "user_location": {"type": "approximate", "country": "KR", "timezone": "Asia/Seoul"},
                }
            ],
            text_format=AiResult,
        )

        if response.status == "incomplete":
            reason = response.incomplete_details.reason if response.incomplete_details else "unknown"
            raise RuntimeError(f"AI 응답이 완료되지 않았습니다 (reason: {reason})")
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError(f"AI 응답을 해석하지 못했습니다 (status: {response.status})")

        return ProviderResult(
            candidates=[to_candidate(s, as_of) for s in parsed.suppliers],
            data_as_of=as_of,
            is_sample_data=False,
            interpreted_item=parsed.interpreted_item,
            fx_as_of=fx_as_of(),
        )
