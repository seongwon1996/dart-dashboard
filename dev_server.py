"""로컬 프리뷰 전용 개발 서버. Vercel의 정적파일+/api 라우팅을 임시로 흉내낸다.
배포에는 사용하지 않음 (Vercel은 vercel.json/파일 구조로 자동 라우팅).

/api/<name> 요청은 api/<name>.py 모듈의 handler.do_POST로 그대로 위임한다.
"""
from __future__ import annotations

import importlib
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

ROOT = Path(__file__).parent
API_DIR = ROOT / "api"


class DevHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        if not self.path.startswith("/api/"):
            return self.send_error(404)

        name = self.path[len("/api/"):].split("?")[0].strip("/")
        module_path = API_DIR / f"{name}.py"
        if not module_path.exists():
            return self.send_error(404)

        module = importlib.import_module(f"api.{name}")
        module.handler.do_POST(self)


if __name__ == "__main__":
    port = 5173
    print(f"http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), DevHandler).serve_forever()
