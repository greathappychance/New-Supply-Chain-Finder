# New Supply Chain Finder (Streamlit)

기업 구매담당자를 위한 신규 공급선 탐색 앱. 구매 유형과 품목명을 입력하면 OpenAI 모델(기본 `gpt-6-astra`)이
웹 검색으로 **실제 공급 업체**를 조사하고, PRD 규칙에 따라 5~10곳을 추천한다.

- 추천 순서: 한국 업체 우선 → 해당품목 매출비율 높은 순 → 신용평가등급 높은 순
- 한국 업체 비율 80% 이상, 휴·폐업·회생절차 업체와 신용등급 BBB- 미만 업체 제외
- 검색 1회에 보통 1~2분, OpenAI API 비용이 든다. 같은 검색어는 24시간 캐시된다.
- 신용등급·매출 정보는 AI가 찾은 공개 정보라 틀릴 수 있다. 화면의 "업체별 출처 보기"로 확인할 것.

## 로컬 실행

Python 3.11 이상.

```bash
cd streamlit_app
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env  → OPENAI_API_KEY 입력
streamlit run app.py              # http://localhost:8501
pytest                            # 테스트
```

## 설정

| 이름 | 설명 | 기본값 |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API 키 (필수) | 없음 |
| `OPENAI_MODEL` | 업체 검색 모델 | `gpt-6-astra` |
| `SUPPLIER_PROVIDER` | `ai`(실제 업체) / `mock`(가상 샘플, 개발·테스트용) | `ai` |

로컬은 `.env`, Streamlit Community Cloud는 Secrets, Docker 호스팅은 환경변수로 넣는다.
`.env`와 `.streamlit/secrets.toml`은 `.gitignore`에 들어 있어 git에 올라가지 않는다.

## 배포

### A. Streamlit Community Cloud (무료, 가장 간단)

1. 이 `streamlit_app` 폴더 내용을 GitHub 저장소에 올린다 (`.env`는 자동으로 제외됨).
2. https://share.streamlit.io 에서 **Create app** → 저장소·브랜치 선택, Main file path에 `app.py`
   (저장소 루트가 아니라 하위 폴더라면 `streamlit_app/app.py`).
3. **Advanced settings**에서 Python 버전(3.12 권장)을 고르고, **Secrets**에 붙여넣는다:
   ```toml
   OPENAI_API_KEY = "sk-..."
   OPENAI_MODEL = "gpt-6-astra"
   ```
4. **Deploy**. 공개 URL이 생기면 누구나 검색할 수 있고 비용은 키 소유자에게 청구되므로,
   필요하면 앱 Settings > Sharing에서 접근할 수 있는 사람을 제한한다.

### B. Docker (Render, Railway, Cloud Run 등)

```bash
docker build -t supply-finder .
docker run -p 8501:8501 -e OPENAI_API_KEY=sk-... supply-finder
```

호스팅 서비스가 `PORT` 환경변수를 주면 그 포트로 실행된다.

## 구조

```
app.py                      Streamlit 화면 (검색 폼, 결과 표, 안내·오류)
supply_finder/
  recommend.py              추천 흐름: 후보 수집 → 필터링 → 정렬 → 구성 조정
  filtering.py              휴·폐업 / 신용등급 하한선 / 서비스 업체 우선
  ranking.py                정렬 규칙
  selection.py              5~10개 선정, 한국 업체 80% 이상
  validation.py             입력 검증
  formatting.py             표시 형식 (쉼표, %, 추정치 *, 결측값 "-")
  config.py                 .env / st.secrets 읽기
  providers/openai_provider.py   OpenAI Responses API + 웹 검색
  providers/mock.py         가상 샘플 데이터 (테스트용)
data/                       샘플 데이터, 품목 분류, 고정 참고 환율
tests/                      pytest
```

해외 업체 매출액은 `data/fx-rates.json`의 고정 참고 환율로 원화 환산한다. 실시간 시세가 아니므로 주기적으로 갱신한다.
