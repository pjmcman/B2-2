# 🗺️ AI 여행 플래너 CLI (Travel Planner)

LLM API(Groq)와 지도/장소 API(Kakao Local)를 조합하여 여행 날짜 기반 맞춤형 여행 리포트와 맛집 목록을 자동 생성하는 파이썬 CLI 프로그램입니다.

---

## 📌 주요 기능
1. **CLI 날짜 입력 및 검증**: `-date "YYYY-MM-DD"` 형식의 날짜 인자를 받아 유효성을 검증합니다.
2. **LLM 기반 1차 추천**: Groq를 사용해 입력 날짜의 시기적 특성에 맞는 국내 여행지, 날씨 요약, 축제/행사 데이터를 JSON 구조로 생성합니다.
3. **지도/장소 API 연동 맛집 검색**: 추천 도시를 기반으로 카카오 로컬 API를 호출하여 맛집 5곳의 정보(상호명, 주소, 카테고리, URL 등)를 수집합니다.
4. **최종 Markdown 리포트 출력**: 수집된 추천 정보 및 맛집 데이터를 조합하여 가독성 높은 Markdown 리포트를 작성합니다.
5. **결과 자동 저장 및 예외 처리**: `results/` 폴더에 원본 JSON 데이터와 Markdown 리포트를 자동 저장하며, API 오류 및 JSON 파싱 실패 시에도 안전하게 대체 동작을 수행합니다.

---

## 🚀 실행 방법

### 1. 환경변수(.env) 설정
프로젝트 루트 경로에 `.env` 파일을 생성하고 발급받은 API 키를 설정합니다.
```env
GROQ_API_KEY="your_groq_api_key"
GROQ_MODEL="llama-3.3-70b-versatile"
GROQ_BASE_URL="https://api.groq.com/openai/v1"
KAKAO_REST_API_KEY="your_kakao_api_key"
```

### 2. 실행 예시
```bash
python travel_planner.py -date 2026-08-15
```

### 3. 결과물 위치
- JSON 원본: `results/YYYY-MM-DD_raw.json`
- Markdown 보고서: `results/YYYY-MM-DD_travel_plan.md`