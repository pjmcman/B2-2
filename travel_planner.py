import argparse
from datetime import datetime

def validate_date(date_str):
    """YYYY-MM-DD 날짜 형식 검증 함수"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        print("\n[오류] 올바른 날짜 형식이 아닙니다.")
        print("사용법: python travel_planner.py -date \"YYYY-MM-DD\" (예: 2026-08-15)")
        exit(1)

def main():
    parser = argparse.ArgumentParser(description="AI 여행 플래너 CLI")
    parser.add_argument("-date", required=True, help="여행 날짜 (YYYY-MM-DD)")

    args = parser.parse_args()
    target_date = validate_date(args.date)

    print(f"\n[입력 완료] 여행 설정 날짜: {target_date}")

if __name__ == "__main__":
    main()