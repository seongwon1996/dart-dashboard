"""회사명으로 검색해 3개 회사의 최근 3개년 재무제표를 비교하고 엑셀로 저장한다.

사용 예:
    python main.py 삼성전자 SK하이닉스 LG에너지솔루션
    python main.py 삼성전자 SK하이닉스 LG에너지솔루션 --years 2025 2024 2023
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import core.dart_api as dc
from core.report import build_workbook, compute_ratios, extract_key_accounts

OUTPUT_DIR = Path(__file__).parent / "output"


def default_years() -> list[int]:
    today = dt.date.today()
    # 사업보고서는 통상 익년 3월 말까지 제출되므로, 4월 이전이면 최신 완결 연도가 하나 더 과거임
    latest = today.year - 1 if today.month >= 4 else today.year - 2
    return [latest, latest - 1, latest - 2]


def resolve_company(name: str, corp_list: list[dict]) -> dc.CompanyMatch:
    matches = dc.search_company(name, corp_list)
    if not matches:
        raise SystemExit(f"'{name}'에 해당하는 회사를 찾을 수 없습니다.")
    if len(matches) == 1:
        return matches[0]

    exact = [m for m in matches if m.corp_name == name]
    if len(exact) == 1:
        return exact[0]

    print(f"\n'{name}'에 대해 여러 후보가 검색되었습니다. 더 정확한 이름을 입력해주세요:")
    for m in matches[:15]:
        print(f"  - {m.corp_name} (종목코드: {m.stock_code or '비상장'})")
    raise SystemExit(1)


def collect_company_data(api_key: str, company: dc.CompanyMatch, years: list[int]) -> dict:
    """회사 1곳의 연도별 데이터를 build_workbook이 기대하는 구조로 반환."""
    years_data = {}
    for year in years:
        rows, fs_div = dc.fetch_main_accounts(api_key, company.corp_code, year)
        if not rows:
            print(f"  [경고] {company.corp_name} {year}년 재무데이터 없음")
            continue
        accounts = extract_key_accounts(rows)
        ratios = compute_ratios(accounts)
        years_data[year] = {"accounts": accounts, "ratios": ratios, "fs_div": fs_div}
    return {"name": company.corp_name, "years": years_data}


def main():
    parser = argparse.ArgumentParser(description="DART 기반 회사 재무제표 비교 도구")
    parser.add_argument("companies", nargs="*", help="비교할 회사명 (예: 삼성전자 SK하이닉스 LG에너지솔루션)")
    parser.add_argument("--years", nargs="+", type=int, help="비교할 연도 (기본: 최근 완결 3개년)")
    parser.add_argument("--output", type=str, help="저장할 엑셀 파일명")
    parser.add_argument("--api-key", type=str, help="DART API 키 (미지정 시 환경변수/파일 사용)")
    args = parser.parse_args()

    companies_input = args.companies
    if not companies_input:
        print("비교할 회사명 3개를 입력하세요 (Enter로 구분):")
        companies_input = [input(f"  회사 {i+1}: ").strip() for i in range(3)]

    api_key = dc.get_api_key(args.api_key)
    years = sorted(args.years or default_years(), reverse=True)

    print(f"\n대상 연도: {years}")
    print("기업 코드 목록 로딩 중...")
    corp_list = dc.load_corp_codes(api_key)

    companies = []
    for name in companies_input:
        company = resolve_company(name, corp_list)
        companies.append(company)
        print(f"  '{name}' -> {company.corp_name} (corp_code={company.corp_code})")

    company_data = []
    for company in companies:
        print(f"\n{company.corp_name} 재무데이터 조회 중...")
        company_data.append(collect_company_data(api_key, company, years))

    if not any(cd["years"] for cd in company_data):
        raise SystemExit("조회된 재무데이터가 없습니다.")

    wb = build_workbook(company_data, years)

    if args.output:
        output_path = Path(args.output)
    else:
        names_part = "_".join(c.corp_name for c in companies)
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"재무비교_{names_part}_{timestamp}.xlsx"

    output_path.parent.mkdir(exist_ok=True)
    wb.save(output_path)
    print(f"\n완료: {output_path.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except dc.DartApiError as e:
        print(f"\n[오류] {e}", file=sys.stderr)
        sys.exit(1)
