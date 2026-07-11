"""CLI와 API가 공유하는 조회 로직."""
from __future__ import annotations

import core.dart_api as dc
from core.report import compute_ratios, extract_key_accounts


def collect_company_data(api_key: str, corp_code: str, corp_name: str, years: list[int]) -> dict:
    """회사 1곳의 연도별 데이터를 build_workbook이 기대하는 구조로 반환."""
    years_data = {}
    for year in years:
        rows, fs_div = dc.fetch_main_accounts(api_key, corp_code, year)
        if not rows:
            continue
        accounts = extract_key_accounts(rows)
        ratios = compute_ratios(accounts)
        years_data[year] = {"accounts": accounts, "ratios": ratios, "fs_div": fs_div}
    return {"name": corp_name, "years": years_data}
