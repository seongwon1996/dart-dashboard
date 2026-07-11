"""Vercel 서버리스 함수: 회사 목록 + 연도를 받아 DART에서 재무데이터를 조회해 JSON으로 반환한다.

POST /api/compare
body: { "companies": [{"corp_code": "...", "corp_name": "..."}, ...], "years": [2025, 2024, 2023] }
응답: { "companies": [{"name": str, "years": {year: {"accounts": {...}, "ratios": {...}, "fs_div": str}}}] }
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import core.dart_api as dc
from core.service import collect_company_data

MIN_COMPANIES = 2
MAX_COMPANIES = 5
MAX_YEARS = 5


def _send_json(req: BaseHTTPRequestHandler, status: int, data: dict) -> None:
    """모듈 함수로 둔다 — 로컬 dev_server.py가 다른 handler 클래스 인스턴스에서
    이 로직을 위임 호출해도(self가 이 클래스가 아니어도) 그대로 동작하도록."""
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req.send_response(status)
    req.send_header("Content-Type", "application/json; charset=utf-8")
    # Content-Length가 없으면 keep-alive 연결에서 클라이언트가 응답 끝을 알 수 없어 멈춘다.
    req.send_header("Content-Length", str(len(body)))
    req.end_headers()
    req.wfile.write(body)


def _send_error(req: BaseHTTPRequestHandler, status: int, message: str) -> None:
    _send_json(req, status, {"error": message})


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
                return _send_error(self, 400, f"회사는 {MIN_COMPANIES}~{MAX_COMPANIES}개 선택해주세요.")
            if not isinstance(years_in, list) or not years_in or len(years_in) > MAX_YEARS:
                return _send_error(self, 400, f"연도는 1~{MAX_YEARS}개 선택해주세요.")

            years = sorted({int(y) for y in years_in}, reverse=True)
            api_key = dc.get_api_key()

            company_data = []
            for c in companies_in:
                corp_code = str(c.get("corp_code", "")).strip()
                corp_name = str(c.get("corp_name", "")).strip()
                if not corp_code or not corp_name:
                    return _send_error(self, 400, "회사 정보(corp_code, corp_name)가 올바르지 않습니다.")
                company_data.append(collect_company_data(api_key, corp_code, corp_name, years))

            if not any(cd["years"] for cd in company_data):
                return _send_error(self, 404, "조회된 재무데이터가 없습니다.")

            _send_json(self, 200, {"companies": company_data, "years": years})

        except dc.DartApiError as e:
            _send_error(self, 502, str(e))
        except Exception as e:  # noqa: BLE001 - 서버리스 함수 최상단, 모든 예외를 JSON 오류로 변환
            _send_error(self, 500, f"서버 오류: {e}")
