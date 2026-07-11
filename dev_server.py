"""로컬 프리뷰 전용 개발 서버. Vercel의 정적파일+/api 라우팅을 임시로 흉내낸다.
배포에는 사용하지 않음 (Vercel은 vercel.json/파일 구조로 자동 라우팅).
"""
from __future__ import annotations

import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from api.compare import handler as CompareHandler

ROOT = Path(__file__).parent


class DevHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        if self.path.startswith("/api/compare"):
            CompareHandler.do_POST(self)
        else:
            self.send_error(404)


if __name__ == "__main__":
    port = 5173
    print(f"http://127.0.0.1:{port}")
    HTTPServer(("127.0.0.1", port), DevHandler).serve_forever()
