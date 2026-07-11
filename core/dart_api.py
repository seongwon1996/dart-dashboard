"""DART(전자공시시스템) Open API 클라이언트. pandas 없이 순수 Python으로 동작.

- 회사명으로 고유 corp_code 검색
- 연도별 주요 재무계정(재무상태표/손익계산서) 조회
"""
from __future__ import annotations

import io
import json
import os
import time
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests

BASE_URL = "https://opendart.fss.or.kr/api"
CACHE_DIR = Path(__file__).parent.parent / ".cache"
CORP_CODE_CACHE = CACHE_DIR / "corp_codes.json"
CORP_CODE_MAX_AGE_SECONDS = 7 * 24 * 3600  # 1주일

REPRT_CODE_ANNUAL = "11011"


class DartApiError(RuntimeError):
    pass


@dataclass
class CompanyMatch:
    corp_code: str
    corp_name: str
    stock_code: str


def get_api_key(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    env_key = os.environ.get("DART_API_KEY")
    if env_key:
        return env_key
    key_file = Path(__file__).parent.parent / "dart_api_key.txt"
    if key_file.exists():
        key = key_file.read_text(encoding="utf-8").strip()
        if key:
            return key
    raise DartApiError(
        "DART API 키를 찾을 수 없습니다. 환경변수 DART_API_KEY를 설정하거나, "
        "dart-dashboard 폴더에 dart_api_key.txt 파일을 만들고 키를 넣어주세요."
    )


def _download_corp_codes(api_key: str) -> list[dict]:
    resp = requests.get(f"{BASE_URL}/corpCode.xml", params={"crtfc_key": api_key}, timeout=30)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xml_bytes = zf.read("CORPCODE.xml")

    root = ET.fromstring(xml_bytes)
    rows = []
    for node in root.findall("list"):
        corp_code = (node.findtext("corp_code") or "").strip()
        corp_name = (node.findtext("corp_name") or "").strip()
        stock_code = (node.findtext("stock_code") or "").strip()
        rows.append({"corp_code": corp_code, "corp_name": corp_name, "stock_code": stock_code})

    if not rows:
        raise DartApiError("DART corpCode 목록을 받아오지 못했습니다. API 키를 확인해주세요.")

    CACHE_DIR.mkdir(exist_ok=True)
    CORP_CODE_CACHE.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def load_corp_codes(api_key: str, force_refresh: bool = False) -> list[dict]:
    if not force_refresh and CORP_CODE_CACHE.exists():
        age = time.time() - CORP_CODE_CACHE.stat().st_mtime
        if age < CORP_CODE_MAX_AGE_SECONDS:
            return json.loads(CORP_CODE_CACHE.read_text(encoding="utf-8"))
    return _download_corp_codes(api_key)


def search_company(name: str, corp_list: list[dict]) -> list[CompanyMatch]:
    """회사명으로 후보를 찾는다. 상장사(종목코드 있음)를 우선한다."""
    name = name.strip()
    listed = [c for c in corp_list if c["stock_code"]]

    exact = [c for c in listed if c["corp_name"] == name]
    if exact:
        return [CompanyMatch(**c) for c in exact]

    contains = [c for c in listed if name in c["corp_name"]]
    if contains:
        return [CompanyMatch(**c) for c in contains]

    # 상장사 중에 없으면 비상장 포함 전체에서 재검색
    exact_all = [c for c in corp_list if c["corp_name"] == name]
    if exact_all:
        return [CompanyMatch(**c) for c in exact_all]

    contains_all = [c for c in corp_list if name in c["corp_name"]]
    return [CompanyMatch(**c) for c in contains_all]


def fetch_main_accounts(
    api_key: str,
    corp_code: str,
    year: int,
    reprt_code: str = REPRT_CODE_ANNUAL,
) -> tuple[list[dict], str]:
    """단일회사 주요계정(fnlttSinglAcnt) 조회. 연결(CFS) 우선, 없으면 별도(OFS).

    반환값: (계정 리스트, 사용된 fs_div)
    """
    for fs_div in ("CFS", "OFS"):
        params = {
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": reprt_code,
            "fs_div": fs_div,
        }
        resp = requests.get(f"{BASE_URL}/fnlttSinglAcnt.json", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status == "000":
            rows = data["list"]
            # DART가 fs_div 파라미터와 무관하게 CFS/OFS를 함께 내려주는 경우가 있어 명시적으로 필터링
            filtered = [r for r in rows if r.get("fs_div") == fs_div]
            return (filtered or rows), fs_div
        if status == "013":  # 조회된 데이터 없음 -> 다음 fs_div 시도
            continue
        raise DartApiError(f"DART API 오류 (status={status}): {data.get('message')}")

    return [], "N/A"
