"""DART 전체 기업코드 목록에서 상장사만 추려 data/corp_codes.json으로 저장한다.

프런트엔드 자동완성용 정적 데이터. 상장/폐지 등으로 목록이 바뀌면 다시 실행해 커밋한다.

사용법: python scripts/refresh_corp_codes.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import core.dart_api as dc

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "corp_codes.json"


def main():
    api_key = dc.get_api_key()
    print("DART corpCode 목록 다운로드 중...")
    corp_list = dc.load_corp_codes(api_key, force_refresh=True)

    listed = [c for c in corp_list if c["stock_code"]]
    listed.sort(key=lambda c: c["corp_name"])

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(listed, ensure_ascii=False), encoding="utf-8")
    print(f"상장사 {len(listed)}개 -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
