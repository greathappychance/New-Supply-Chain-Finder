"""New Supply Chain Finder — Streamlit 화면.

실행: streamlit run app.py
"""

from __future__ import annotations

import logging
import re

import pandas as pd
import streamlit as st

from supply_finder.config import get_setting
from supply_finder.constants import APP_TITLE, MIN_CREDIT_GRADE, PURCHASE_TYPES, RESULT_COLUMNS
from supply_finder.formatting import (
    format_interpretation,
    format_supplier_cell,
    has_estimated_value,
    summarize,
)
from supply_finder.models import RecommendRequest, RecommendResponse
from supply_finder.providers import ProviderConfigError, get_supplier_provider
from supply_finder.providers.mock import normalize_item_name
from supply_finder.providers.openai_provider import DEFAULT_MODEL
from supply_finder.recommend import recommend
from supply_finder.validation import validate_recommend_input

logger = logging.getLogger(__name__)

st.set_page_config(page_title=APP_TITLE, page_icon="🏭", layout="wide")

NUMERIC_COLUMNS = {"업력(년)", "지난해 매출액(억원)", "해당품목 매출비율"}
SEARCHING_MESSAGE = "공급 업체를 찾는 중입니다... (AI가 웹을 검색하므로 보통 1분 남짓 걸립니다)"
GENERIC_ERROR = "추천 결과를 불러오지 못했습니다. 잠시 후 다시 시도해주세요."


def md_escape(text: str) -> str:
    """업체명 등에 들어 있는 마크다운 기호가 서식으로 해석되지 않도록 한다."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|>~])", r"\\\1", text)


# 같은 검색어를 반복 조회할 때 비용과 대기 시간을 줄이기 위해 24시간 캐시한다.
# 실패(예외)는 캐시되지 않으므로 다시 시도할 수 있다.
@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_recommend(purchase_type: str, item_key: str, provider_name: str, _item_name: str) -> RecommendResponse:
    return recommend(RecommendRequest(purchase_type, _item_name), get_supplier_provider())


def friendly_error(error: Exception) -> str:
    """오류를 사용자에게 보여줄 한국어 메시지로 바꾼다."""
    if isinstance(error, ProviderConfigError):
        return str(error)
    try:
        import openai
    except ImportError:  # pragma: no cover
        return GENERIC_ERROR
    model = get_setting("OPENAI_MODEL", DEFAULT_MODEL)
    if isinstance(error, openai.AuthenticationError):
        return "OpenAI API 키가 올바르지 않습니다. .env(배포 환경은 Secrets)의 OPENAI_API_KEY를 확인해주세요."
    if isinstance(error, openai.NotFoundError):
        return f"모델 '{model}'을(를) 사용할 수 없습니다. OPENAI_MODEL 설정과 계정 권한을 확인해주세요."
    if isinstance(error, openai.RateLimitError):
        return "OpenAI 요청 한도를 초과했거나 크레딧이 부족합니다. 잠시 후 다시 시도하거나 결제 정보를 확인해주세요."
    if isinstance(error, openai.APITimeoutError):
        return "응답이 2분 30초 안에 오지 않았습니다. 잠시 후 다시 시도해주세요."
    if isinstance(error, openai.APIConnectionError):
        return "OpenAI 서버에 연결할 수 없습니다. 네트워크 상태를 확인한 뒤 다시 시도해주세요."
    return GENERIC_ERROR


def run_search(request: RecommendRequest) -> None:
    st.session_state.request = request
    st.session_state.result = None
    st.session_state.error = None
    provider_name = get_setting("SUPPLIER_PROVIDER") or "ai"
    with st.spinner(SEARCHING_MESSAGE):
        try:
            st.session_state.result = cached_recommend(
                request.purchase_type, normalize_item_name(request.item_name), provider_name, request.item_name
            )
        except Exception as e:  # noqa: BLE001 — 화면에는 정리된 메시지만 보여주고 원인은 로그로 남긴다
            logger.exception("추천 처리 실패")
            st.session_state.error = friendly_error(e)


def render_header() -> None:
    st.title(APP_TITLE)
    st.caption("구매 유형과 품목명을 입력하면 검증된 공급 업체를 추천합니다.")


def render_search_form() -> None:
    with st.form("search", border=True):
        col_type, col_item, col_button = st.columns([2, 5, 1.3], vertical_alignment="bottom")
        purchase_type = col_type.selectbox("구매 유형", PURCHASE_TYPES, index=None, placeholder="선택하세요")
        item_name = col_item.text_input("품목명", placeholder="예: 산업용 감속기, 집진기 필터백")
        submitted = col_button.form_submit_button("검색", type="primary", icon=":material/search:", width="stretch")

    if not submitted:
        return
    errors = validate_recommend_input(purchase_type or "", item_name)
    if errors.has_errors:
        for message in (errors.purchase_type, errors.item_name):
            if message:
                st.error(message, icon=":material/error:")
        return
    run_search(RecommendRequest(purchase_type, item_name.strip()))


def render_initial_guide() -> None:
    with st.container(border=True):
        st.markdown("#### 이렇게 사용하세요")
        steps = st.columns(3)
        steps[0].markdown("**1. 구매 유형 선택**  \n원료구매·설비구매·자재구매·수리·용역 중에서 고릅니다.")
        steps[1].markdown("**2. 품목명 입력**  \n찾는 품목을 구체적으로 적을수록 정확합니다. 예: 산업용 감속기")
        steps[2].markdown("**3. 추천 결과 확인**  \n조건을 갖춘 공급 업체 5~10곳을 순위대로 보여줍니다.")
        st.caption(
            f"추천 기준: 정상 영업 중이고 신용평가등급이 투자적격({MIN_CREDIT_GRADE} 이상)인 업체를 추천합니다. "
            "한국 업체를 우선하며(80% 이상), 해당 품목 매출비율과 신용평가등급이 높은 순으로 정렬합니다."
        )


def results_dataframe(result: RecommendResponse) -> pd.DataFrame:
    rows = []
    for rank, supplier in enumerate(result.suppliers, start=1):
        row = {"순위": rank}
        row.update({label: format_supplier_cell(supplier, key) for key, label in RESULT_COLUMNS})
        rows.append(row)
    return pd.DataFrame(rows, columns=["순위", *[label for _, label in RESULT_COLUMNS]])


def render_results(request: RecommendRequest, result: RecommendResponse) -> None:
    if result.is_sample_data:
        st.warning("샘플 데이터: 표시되는 업체는 모두 가상의 업체이며 실제 정보가 아닙니다.", icon=":material/warning:")
    if result.interpreted_item:
        st.info(format_interpretation(request.item_name, result.interpreted_item), icon=":material/info:")
    if result.notice:
        st.warning(result.notice, icon=":material/warning:")

    total, korean, foreign = summarize(result.suppliers)
    if total == 0:
        st.info(
            f"'{request.item_name}'에 맞는 공급 업체를 찾지 못했습니다.  \n"
            "품목명을 더 일반적인 표현으로 바꾸거나 다른 구매 유형으로 다시 검색해 보세요.",
            icon=":material/search_off:",
        )
        return

    st.subheader(f"추천 공급 업체 ({total}곳 · 한국 {korean} / 해외 {foreign})")
    column_config = {
        "순위": st.column_config.NumberColumn("순위", width="small", pinned=True),
        "업체명": st.column_config.TextColumn("업체명", pinned=True),
        **{
            label: st.column_config.TextColumn(label, alignment="right")
            for _, label in RESULT_COLUMNS
            if label in NUMERIC_COLUMNS
        },
    }
    st.dataframe(
        results_dataframe(result),
        hide_index=True,
        width="stretch",
        height=(total + 1) * 35 + 3,  # 모든 행이 스크롤 없이 보이도록
        column_config=column_config,
    )

    notes = ["정렬 기준: 한국 업체 우선 → 해당품목 매출비율 높은 순 → 신용평가등급 높은 순"]
    if has_estimated_value(result.suppliers):
        notes.append("\\* 표시는 추정치입니다.")
    dates = f"데이터 기준일: {result.data_as_of}"
    if result.fx_as_of:
        dates += f" · 환율 기준일: {result.fx_as_of} (해외 업체 매출액은 고정 참고 환율로 원화 환산)"
    notes.append(dates)
    sources = sorted({s.source for s in result.suppliers if s.source})
    notes.append(f"출처: {', '.join(sources) or '-'}")
    st.caption("  \n".join(notes))
    if not result.is_sample_data:
        st.caption(":orange[AI가 공개 웹 정보를 조사한 결과로, 신용등급·매출 정보가 틀릴 수 있으니 거래 전 반드시 확인하세요.]")

    if any(s.source_urls for s in result.suppliers):
        with st.expander("업체별 출처 보기"):
            for s in result.suppliers:
                links = ", ".join(f"[{md_escape(u)}]({u})" for u in s.source_urls) or "-"
                st.markdown(f"- **{md_escape(s.name)}**: {links}")


def main() -> None:
    for key in ("request", "result", "error"):
        st.session_state.setdefault(key, None)

    render_header()
    render_search_form()

    request: RecommendRequest | None = st.session_state.request
    if st.session_state.error:
        st.error(st.session_state.error, icon=":material/error:")
        if request and st.button("다시 시도", icon=":material/refresh:"):
            run_search(request)
            st.rerun()
    elif st.session_state.result is not None and request is not None:
        render_results(request, st.session_state.result)
    else:
        render_initial_guide()

    st.divider()
    st.caption("추천 결과는 참고용이며, 거래 전 업체 정보를 직접 확인하세요.")


main()
