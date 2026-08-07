import os
import json
import argparse
from datetime import datetime
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

# .env 환경변수 로드
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")

errors_log = []

def validate_date(date_str):
    """YYYY-MM-DD 날짜 형식 검증 함수"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        print("\n[오류] 올바른 날짜 형식이 아닙니다.")
        print("사용법: python travel_planner.py -date \"YYYY-MM-DD\" (예: 2026-08-15)")
        exit(1)

def get_llm_recommendation(date_str):
    """LLM을 이용해 입력 날짜 기반 여행지/날씨/행사 추천 (JSON 반환)"""
    print("\n[1/3] 1차 추천 생성 중(LLM)...")

    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        print("  [주의] GEMINI_API_KEY가 설정되지 않았습니다. 기본 테스트 데이터를 사용합니다.")
        return {
            "recommended_city": "제주",
            "weather": "8월 중순 평균 28°C 내외, 다소 습하고 무더움",
            "events": ["제주 해변 축제", "야간 문화재 탐방"],
            "reason": "8월 중순은 제주의 해변과 물놀이를 즐기기 좋은 시기입니다."
        }

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
    여행 날짜 '{date_str}'에 어울리는 국내 여행지 1곳을 추천해 주세요.
    응답은 반드시 아래 필드를 포함하는 JSON 형식이어야 합니다.

    - recommended_city: 추천 도시 이름 (예: "제주", "강릉")
    - weather: 해당 시기의 일반적인 날씨 요약
    - events: 해당 시기 관련 행사/축제 후보 1~3개 (배열)
    - reason: 추천 이유 2~4문장
    """

    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            data = json.loads(response.text)
            print(f"  - recommended_city: \"{data.get('recommended_city')}\"")
            return data
        except Exception as e:
            if attempt == 1:
                errors_log.append({"step": "llm_1st_recommendation", "type": "JSON_PARSE_ERROR", "message": str(e)})
                return {
                    "recommended_city": "강릉",
                    "weather": "정보 불러오기 실패",
                    "events": [],
                    "reason": "JSON 파싱 실패로 기본 추천 데이터가 적용되었습니다."
                }

def search_places(city):
    """지도/장소 API를 사용하여 추천 도시 맛집 N곳 검색 (실패 시에도 에러 기록 후 빈 리스트 반환)"""
    print("\n[2/3] 맛집 검색 중(지도/장소 API)...")

    if not KAKAO_REST_API_KEY or KAKAO_REST_API_KEY == "your_kakao_api_key_here":
        print("  [주의] KAKAO_REST_API_KEY가 설정되지 않았습니다. 맛집 섹션은 '데이터 없음' 처리됩니다.")
        errors_log.append({"step": "place_search", "type": "NO_API_KEY", "message": "Kakao REST API Key is missing"})
        return []

    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {"query": f"{city} 맛집", "size": 5}

    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        if res.status_code != 200:
            errors_log.append({"step": "place_search", "type": f"HTTP_{res.status_code}", "message": res.text})
            print(f"  - 지도 API 오류 발생 (HTTP {res.status_code}). '데이터 없음'으로 진행합니다.")
            return []

        documents = res.json().get("documents", [])
        if not documents:
            errors_log.append({"step": "place_search", "type": "EMPTY_RESULT", "message": f"0 results for query={city} 맛집"})
            print("  - 검색 결과가 0건입니다.")
            return []

        places = []
        for doc in documents:
            places.append({
                "name": doc.get("place_name"),
                "address": doc.get("road_address_name") or doc.get("address_name"),
                "category": doc.get("category_name"),
                "url": doc.get("place_url"),
                "x": doc.get("x"),
                "y": doc.get("y")
            })
        print(f"  - 맛집 {len(places)}곳 검색 완료")
        return places
    except Exception as e:
        errors_log.append({"step": "place_search", "type": "NETWORK_ERROR", "message": str(e)})
        print("  - 네트워크/요청 오류로 맛집 검색 실패. 계속 진행합니다.")
        return []

def main():
    parser = argparse.ArgumentParser(description="AI 여행 플래너 CLI")
    parser.add_argument("-date", required=True, help="여행 날짜 (YYYY-MM-DD)")

    args = parser.parse_args()
    target_date = validate_date(args.date)

    # 1단계: 1차 추천
    rec_data = get_llm_recommendation(target_date)

    # 2단계: 맛집 검색
    places = search_places(rec_data.get("recommended_city", ""))

if __name__ == "__main__":
    main()