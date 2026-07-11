"""Vercel 서버리스 함수: 회사 목록 + 연도를 받아 재무제표 비교 엑셀을 생성해 반환한다.

POST /api/compare
body: { "companies": [{"corp_code": "...", "corp_name": "..."}, ...], "years": [2025, 2024, 2023] }
응답: .xlsx 파일 (다운로드)
"""
from __future__ import annotations

import io
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent.parent))

import core.dart_api as dc
from core.report import build_workbook, compute_ratios, extract_key_accounts

MIN_COMPANIES = 2
MAX_COMPANIES = 5
MAX_YEARS = 5


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b"{}"
            payload = json.loads(body or b"{}")

            companies_in = payload.get("companies", [])
            years_in = payload.get("years", [])

            if not isinstance(companies_in, list) or not (
                MIN_COMPANIES <= len(companies_in) <= MAX_COMPANIES
            ):
                return self._error(400, f"회사는 {MIN_COMPANIES}~{MAX_COMPANIES}개 선택해주세요.")
            if not isinstance(years_in, list) or not years_in or len(years_in) > MAX_YEARS:
                return self._error(400, f"연도는 1~{MAX_YEARS}개 선택해주세요.")

            years = sorted({int(y) for y in years_in}, reverse=True)
            api_key = dc.get_api_key()

            company_data = []
            for c in companies_in:
                corp_code = str(c.get("corp_code", "")).strip()
                corp_name = str(c.get("corp_name", "")).strip()
                if not corp_code or not corp_name:
                    return self._error(400, "회사 정보(corp_code, corp_name)가 올바르지 않습니다.")

                years_data = {}
                for year in years:
                    rows, fs_div = dc.fetch_main_accounts(api_key, corp_code, year)
                    if not rows:
                        continue
                    accounts = extract_key_accounts(rows)
                    ratios = compute_ratios(accounts)
                    years_data[year] = {"accounts": accounts, "ratios": ratios, "fs_div": fs_div}
                company_data.append({"name": corp_name, "years": years_data})

            if not any(cd["years"] for cd in company_data):
                return self._error(404, "조회된 재무데이터가 없습니다.")

            wb = build_workbook(company_data, years)
            buf = io.BytesIO()
            wb.save(buf)
            content = buf.getvalue()

            filename = f"financial_comparison_{'_'.join(c['name'] for c in company_data)}.xlsx"

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            self.send_header(
                "Content-Disposition",
                f"attachment; filename=\"financial_comparison.xlsx\"; "
                f"filename*=UTF-8''{quote(filename)}",
            )
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        except dc.DartApiError as e:
            self._error(502, str(e))
        except Exception as e:  # noqa: BLE001 - 서버리스 함수 최상단, 모든 예외를 JSON 오류로 변환
            self._error(500, f"서버 오류: {e}")

    def _error(self, status: int, message: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}, ensure_ascii=False).encode("utf-8"))
