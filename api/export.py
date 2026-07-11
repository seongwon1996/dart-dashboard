"""Vercel 서버리스 함수: 이미 조회된 재무데이터(JSON)를 받아 엑셀로 변환해 반환한다.
DART를 다시 호출하지 않는다 — /api/compare 응답을 그대로 재사용.

POST /api/export
body: { "companies": [{"name": str, "years": {year: {"accounts": {...}, "ratios": {...}, "fs_div": str}}}], "years": [2025, 2024, 2023] }
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

from core.report import build_workbook

MIN_COMPANIES = 2
MAX_COMPANIES = 5
MAX_YEARS = 5


def _send_error(req: BaseHTTPRequestHandler, status: int, message: str) -> None:
    """모듈 함수로 둔다 — 로컬 dev_server.py가 다른 handler 클래스 인스턴스에서
    이 로직을 위임 호출해도(self가 이 클래스가 아니어도) 그대로 동작하도록."""
    body = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
    req.send_response(status)
    req.send_header("Content-Type", "application/json; charset=utf-8")
    # Content-Length가 없으면 keep-alive 연결에서 클라이언트가 응답 끝을 알 수 없어 멈춘다.
    req.send_header("Content-Length", str(len(body)))
    req.end_headers()
    req.wfile.write(body)


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

            company_data = []
            for c in companies_in:
                name = str(c.get("name", "")).strip()
                years_data = c.get("years", {})
                if not name or not isinstance(years_data, dict):
                    return _send_error(self, 400, "회사 데이터 형식이 올바르지 않습니다.")
                # JSON 키는 문자열이므로 연도를 int로 되돌린다
                normalized = {int(y): v for y, v in years_data.items()}
                company_data.append({"name": name, "years": normalized})

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

        except Exception as e:  # noqa: BLE001 - 서버리스 함수 최상단, 모든 예외를 JSON 오류로 변환
            _send_error(self, 500, f"서버 오류: {e}")
