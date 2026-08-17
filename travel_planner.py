import os
import json
import argparse
from datetime import datetime
import requests
from dotenv import load_dotenv
from openai import OpenAI

# .env 환경변수 로드
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

errors_log = []

def normalize_recommendation_data(data):
    """LLM 응답을 현재 코드가 다루는 형식으로 정규화한다."""
    if not isinstance(data, dict):
        return {
            "recommended_city": "제주",
            "recommended_cities": ["제주"],
            "weather": "정보 불러오기 실패",
            "events": [],
            "reason": "기본 추천 데이터가 적용되었습니다."
        }

    raw_cities = data.get("recommended_cities")
    if isinstance(raw_cities, str):
        raw_cities = [raw_cities]
    elif raw_cities is None:
        raw_city = data.get("recommended_city")
        raw_cities = [raw_city] if raw_city else []

    city_list = [str(city).strip() for city in raw_cities if str(city).strip()]
    if not city_list:
        city_list = ["제주"]

    normalized = dict(data)
    normalized["recommended_cities"] = city_list
    normalized["recommended_city"] = city_list[0]
    normalized["events"] = data.get("events") if isinstance(data.get("events"), list) else []
    if not normalized["events"] and data.get("events"):
        normalized["events"] = [data.get("events")]
    return normalized

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

    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        print("  [주의] GROQ_API_KEY가 설정되지 않았습니다. 기본 테스트 데이터를 사용합니다.")
        return normalize_recommendation_data({
            "recommended_city": "제주",
            "recommended_cities": ["제주", "강릉", "속초"],
            "weather": "8월 중순 평균 28°C 내외, 다소 습하고 무더움",
            "events": ["제주 해변 축제", "야간 문화재 탐방"],
            "reason": "8월 중순은 제주의 해변과 물놀이를 즐기기 좋은 시기입니다."
        })

    client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
    prompt = f"""
    여행 날짜 '{date_str}'에 어울리는 국내 여행지 2~3곳을 추천해 주세요.
    응답은 반드시 아래 필드를 포함하는 JSON 형식이어야 합니다.

    - recommended_city: 대표 추천 도시 이름 (예: "제주")
    - recommended_cities: 추천 도시 목록 2~3개 (배열)
    - weather: 해당 시기의 일반적인 날씨 요약
    - events: 해당 시기 관련 행사/축제 후보 1~3개 (배열)
    - reason: 추천 이유 2~4문장
    """

    for attempt in range(2):
        try:
            response = client.responses.create(
                model=GROQ_MODEL,
                input=prompt,
                text={"format": {"type": "json_object"}}
            )
            data = normalize_recommendation_data(json.loads(response.output_text))
            print(f"  - recommended_cities: {', '.join(data.get('recommended_cities', []))}")
            return data
        except Exception as e:
            if attempt == 1:
                errors_log.append({"step": "llm_1st_recommendation", "type": "JSON_PARSE_ERROR", "message": str(e)})
                return normalize_recommendation_data({
                    "recommended_city": "강릉",
                    "recommended_cities": ["강릉", "속초", "전주"],
                    "weather": "정보 불러오기 실패",
                    "events": [],
                    "reason": "JSON 파싱 실패로 기본 추천 데이터가 적용되었습니다."
                })

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

def build_fallback_report(date_str, rec_data, places, error_message=None):
    """LLM 보고서 생성이 실패해도 저장 가능한 기본 Markdown 리포트를 만든다."""
    cities = rec_data.get('recommended_cities') or [rec_data.get('recommended_city')]
    city_text = ', '.join(cities)
    places_text = "\n".join(
        [f"- **{p['name']}**: {p['address']} ({p['url']})" for p in places]
    ) if places else "- 데이터 없음 (장소 검색 결과 0건)"
    error_text = f"\n\n## 참고\nLLM 보고서 생성 실패: {error_message}\n" if error_message else ""

    return f"""# {date_str} 국내 여행 추천 리포트

## 추천 지역
{city_text}

## 추천 이유
{rec_data.get('reason')}

## 날씨 요약
{rec_data.get('weather')}

## 행사/축제
{', '.join(rec_data.get('events', [])) if rec_data.get('events') else '없음'}

## 맛집 추천
{places_text}

## 1일 추천 일정
- **오전**: {city_text}의 주요 명소 산책 및 가벼운 아침 식사
- **오후**: 추천 맛집 방문 및 지역 대표 문화/자연 체험
- **저녁**: 지역 야경 감상 및 맛있는 저녁 식사 후 일과 마무리{error_text}
"""

def generate_final_report(date_str, rec_data, places):
    """LLM을 연동해 최종 Markdown 여행 리포트 생성"""
    print("\n[3/3] 최종 리포트 생성 중(LLM)...")

    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        print("  - [안내] API 키 미설정 모드로 기본 템플릿 리포트를 생성합니다.")
        return build_fallback_report(date_str, rec_data, places)

    client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
    cities = rec_data.get('recommended_cities') or [rec_data.get('recommended_city')]
    prompt = f"""
    아래 정보를 바탕으로 깔끔하고 가독성 뛰어난 Markdown 형식의 국내 여행 추천 리포트를 작성해 주세요.

    - 여행 날짜: {date_str}
    - 추천 지역: {', '.join(cities)}
    - 날씨: {rec_data.get('weather')}
    - 행사/축제: {', '.join(rec_data.get('events', []))}
    - 추천 이유: {rec_data.get('reason')}
    - 맛집 목록: {json.dumps(places, ensure_ascii=False) if places else "데이터 없음"}

    [필수 목차]
    # {date_str} 국내 여행 추천 리포트
    ## 추천 지역
    ## 추천 이유
    ## 날씨 요약
    ## 행사/축제
    ## 맛집 추천 (데이터가 없으면 '데이터 없음'으로 표기)
    ## 1일 일정 제안 (오전/오후/저녁)
    """

    try:
        response = client.responses.create(
            model=GROQ_MODEL,
            input=prompt
        )
        return response.output_text
    except Exception as e:
        errors_log.append({"step": "report_generation", "type": "LLM_ERROR", "message": str(e)})
        return build_fallback_report(date_str, rec_data, places, str(e))

def merge_unique_places(places):
    """중복 맛집 정보를 제거한다."""
    seen = set()
    merged = []
    for place in places:
        key = (place.get("name"), place.get("address"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(place)
    return merged


def search_places_for_cities(cities):
    """여러 도시의 맛집을 한 번에 검색해 하나의 리스트로 합친다."""
    all_places = []
    for city in cities:
        all_places.extend(search_places(city))
    return merge_unique_places(all_places)


def load_cached_result(target_date):
    """기존 결과 JSON이 있으면 재사용한다. 형태는 {recommendation, places, errors, cache_meta}."""
    raw_json_path = f"results/{target_date}_raw.json"
    if not os.path.exists(raw_json_path):
        return None

    try:
        with open(raw_json_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        if isinstance(cached, dict) and cached.get("recommendation") and "places" in cached:
            cached.setdefault("cache_meta", {
                "date": target_date,
                "source": "local_cache",
                "version": "1.0"
            })
            return cached
    except Exception:
        return None
    return None


def main():
    parser = argparse.ArgumentParser(description="AI 여행 플래너 CLI")
    parser.add_argument("-date", required=True, help="여행 날짜 (YYYY-MM-DD)")

    args = parser.parse_args()
    target_date = validate_date(args.date)

    os.makedirs("results", exist_ok=True)
    raw_json_path = f"results/{target_date}_raw.json"

    cached = load_cached_result(target_date)
    if cached:
        rec_data = normalize_recommendation_data(cached.get("recommendation", {}))
        places = cached.get("places", [])
        errors_log.extend(cached.get("errors", []))
        print(f"\n[캐시 로드] {raw_json_path} 에서 기존 결과를 불러왔습니다.")
    else:
        # 1단계: 1차 추천
        rec_data = get_llm_recommendation(target_date)

        # 2단계: 맛집 검색
        cities = rec_data.get("recommended_cities") or [rec_data.get("recommended_city")]
        places = search_places_for_cities(cities)

    # 3단계: 최종 리포트 생성
    report_md = generate_final_report(target_date, rec_data, places)

    raw_data = {
        "recommendation": rec_data,
        "places": places,
        "errors": errors_log,
        "cache_meta": {
            "date": target_date,
            "source": "local_cache" if cached else "fresh_generation",
            "version": "1.0"
        }
    }
    with open(raw_json_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)

    report_path = f"results/{target_date}_travel_plan.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"\n완료! {report_path} 를 확인하세요.")

if __name__ == "__main__":
    main()
