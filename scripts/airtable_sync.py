#!/usr/bin/env python3
"""
airtable_sync.py — 에어테이블 콜db → content_intel.db 단방향 동기화
===================================================================
에어테이블 "CMS 확산 TF /growth" 베이스에서 콜db를 읽어
로컬 DB에 주간 스냅샷으로 쌓는다.

Usage:
    python3 scripts/airtable_sync.py sync       # 전체 동기화
    python3 scripts/airtable_sync.py stats      # 현재 DB 통계
    python3 scripts/airtable_sync.py weekly      # 주간 리포트
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "content_intel.db"

AIRTABLE_BASE_ID = "appNmAJVDnaqKCh8S"
AIRTABLE_TABLE_ID = "tbl0su6ZyoQ7qwVTU"

# 가져올 필드
FIELDS = [
    "Profile_ID",
    "성함 또는 업체명",
    "숙박업소명",
    "지역",
    "객실 수",
    "리드상태",
    "리드 종류",
    "문의항목",
    "사용하는 기능",
    "도어락",
    "키텍",
    "유입경로",
    "유입경로/문의내용",
    "콜담당자(DR)",
    "리드 유입 일시",
    "클로징 일자",
    "교육&설치 현황",
    "드롭원인",
    "Created",
]


def get_token() -> str:
    """환경변수 또는 .env에서 토큰 로드"""
    token = os.environ.get("AIRTABLE_PAT")
    if token:
        return token
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("AIRTABLE_PAT="):
                return line.split("=", 1)[1].strip()
    print("❌ AIRTABLE_PAT 환경변수가 없습니다. .env 파일을 확인하세요.")
    sys.exit(1)


def fetch_all_records(token: str) -> list[dict]:
    """에어테이블 API에서 전체 레코드를 페이징으로 가져온다."""
    records = []
    offset = None

    # 필드 파라미터 구성
    field_params = "&".join(
        f"fields%5B%5D={urllib.parse.quote(f)}" for f in FIELDS
    )

    while True:
        url = (
            f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"
            f"?pageSize=100&{field_params}"
        )
        if offset:
            url += f"&offset={offset}"

        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())

        batch = data.get("records", [])
        records.extend(batch)

        offset = data.get("offset")
        if not offset:
            break

        # 진행 표시
        print(f"  {len(records)}건 로드...", end="\r")

    print(f"  총 {len(records)}건 로드 완료")
    return records


def init_tables(conn: sqlite3.Connection):
    """에어테이블 관련 테이블 생성"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS airtable_leads (
            record_id TEXT PRIMARY KEY,
            profile_id TEXT,
            property_name TEXT,
            accommodation_name TEXT,
            region TEXT,
            room_count TEXT,
            lead_status TEXT,
            lead_type TEXT,
            inquiry_items TEXT,
            products_used TEXT,
            doorlock TEXT,
            keytech TEXT,
            source_channel TEXT,
            inquiry_detail TEXT,
            call_agent TEXT,
            lead_date TEXT,
            closing_date TEXT,
            onboarding_status TEXT,
            drop_reason TEXT,
            created_at TEXT,
            synced_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS airtable_sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            synced_at TEXT NOT NULL,
            total_records INTEGER,
            new_records INTEGER,
            updated_records INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_leads_status ON airtable_leads(lead_status);
        CREATE INDEX IF NOT EXISTS idx_leads_inquiry ON airtable_leads(inquiry_items);
        CREATE INDEX IF NOT EXISTS idx_leads_region ON airtable_leads(region);
        CREATE INDEX IF NOT EXISTS idx_leads_synced ON airtable_leads(synced_at);
    """)


def sync_records(conn: sqlite3.Connection, records: list[dict]):
    """레코드를 DB에 upsert"""
    now = datetime.now().isoformat(timespec="seconds")
    new_count = 0
    updated_count = 0

    for rec in records:
        f = rec.get("fields", {})

        # 사용하는 기능은 리스트 → 콤마 조인
        products = f.get("사용하는 기능", [])
        if isinstance(products, list):
            products = ", ".join(products)

        # 드롭원인도 리스트
        drop = f.get("드롭원인", [])
        if isinstance(drop, list):
            drop = ", ".join(drop)

        row = (
            rec["id"],
            f.get("Profile_ID"),
            f.get("성함 또는 업체명"),
            f.get("숙박업소명"),
            f.get("지역"),
            f.get("객실 수"),
            f.get("리드상태"),
            f.get("리드 종류"),
            f.get("문의항목"),
            products or None,
            f.get("도어락"),
            f.get("키텍"),
            f.get("유입경로"),
            f.get("유입경로/문의내용"),
            f.get("콜담당자(DR)"),
            f.get("리드 유입 일시"),
            f.get("클로징 일자"),
            f.get("교육&설치 현황"),
            drop or None,
            f.get("Created"),
            now,
        )

        # 기존 레코드 확인
        existing = conn.execute(
            "SELECT synced_at FROM airtable_leads WHERE record_id = ?",
            (rec["id"],),
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE airtable_leads SET
                    profile_id=?, property_name=?, accommodation_name=?,
                    region=?, room_count=?, lead_status=?, lead_type=?,
                    inquiry_items=?, products_used=?, doorlock=?, keytech=?,
                    source_channel=?, inquiry_detail=?, call_agent=?,
                    lead_date=?, closing_date=?, onboarding_status=?,
                    drop_reason=?, created_at=?, synced_at=?
                WHERE record_id=?""",
                row[1:] + (rec["id"],),
            )
            updated_count += 1
        else:
            conn.execute(
                """INSERT INTO airtable_leads VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                row,
            )
            new_count += 1

    # 동기화 로그
    conn.execute(
        "INSERT INTO airtable_sync_log (synced_at, total_records, new_records, updated_records) VALUES (?,?,?,?)",
        (now, len(records), new_count, updated_count),
    )
    conn.commit()

    print(f"\n✅ 동기화 완료: 신규 {new_count} / 업데이트 {updated_count} / 전체 {len(records)}")


def cmd_sync():
    """전체 동기화 실행"""
    token = get_token()
    conn = sqlite3.connect(DB_PATH)
    init_tables(conn)

    print("에어테이블에서 데이터 가져오는 중...")
    records = fetch_all_records(token)
    sync_records(conn, records)
    conn.close()


def cmd_stats():
    """현재 DB 통계"""
    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("SELECT 1 FROM airtable_leads LIMIT 1")
    except sqlite3.OperationalError:
        print("❌ 아직 동기화된 데이터가 없습니다. 먼저 sync를 실행하세요.")
        return

    total = conn.execute("SELECT COUNT(*) FROM airtable_leads").fetchone()[0]
    print(f"\n총 리드: {total}건")

    # 리드상태 분포
    print("\n📊 리드상태:")
    for row in conn.execute(
        "SELECT lead_status, COUNT(*) c FROM airtable_leads GROUP BY lead_status ORDER BY c DESC"
    ):
        print(f"  {row[0] or '(없음)':20s} {row[1]:>5d}")

    # 문의항목 분포
    print("\n📊 문의항목:")
    items: dict[str, int] = {}
    for (val,) in conn.execute(
        "SELECT inquiry_items FROM airtable_leads WHERE inquiry_items IS NOT NULL"
    ):
        for item in val.split(","):
            item = item.strip()
            if item:
                items[item] = items.get(item, 0) + 1
    for item, count in sorted(items.items(), key=lambda x: -x[1])[:15]:
        print(f"  {item:30s} {count:>5d}")

    # 지역 분포
    print("\n📊 지역 (상위 10):")
    for row in conn.execute(
        "SELECT region, COUNT(*) c FROM airtable_leads WHERE region IS NOT NULL GROUP BY region ORDER BY c DESC LIMIT 10"
    ):
        print(f"  {row[0]:20s} {row[1]:>5d}")

    # 동기화 이력
    print("\n📋 동기화 이력:")
    for row in conn.execute(
        "SELECT synced_at, total_records, new_records, updated_records FROM airtable_sync_log ORDER BY id DESC LIMIT 5"
    ):
        print(f"  {row[0]} | 전체 {row[1]} | 신규 {row[2]} | 업데이트 {row[3]}")

    conn.close()


def cmd_weekly():
    """주간 리포트 — 최근 7일 신규 리드 + 상태 변화"""
    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("SELECT 1 FROM airtable_leads LIMIT 1")
    except sqlite3.OperationalError:
        print("❌ 아직 동기화된 데이터가 없습니다.")
        return

    week_ago = (datetime.now() - timedelta(days=7)).isoformat()

    print(f"\n📅 주간 리포트 ({week_ago[:10]} ~ 오늘)")

    # 최근 7일 생성된 리드
    recent = conn.execute(
        "SELECT COUNT(*) FROM airtable_leads WHERE created_at >= ?",
        (week_ago,),
    ).fetchone()[0]
    print(f"\n신규 리드: {recent}건")

    # 최근 리드 중 문의항목 분포
    print("\n신규 리드 문의항목:")
    items: dict[str, int] = {}
    for (val,) in conn.execute(
        "SELECT inquiry_items FROM airtable_leads WHERE created_at >= ? AND inquiry_items IS NOT NULL",
        (week_ago,),
    ):
        for item in val.split(","):
            item = item.strip()
            if item:
                items[item] = items.get(item, 0) + 1
    for item, count in sorted(items.items(), key=lambda x: -x[1]):
        print(f"  {item}: {count}")

    # Closing 건
    closing = conn.execute(
        "SELECT COUNT(*) FROM airtable_leads WHERE closing_date >= ?",
        (week_ago,),
    ).fetchone()[0]
    print(f"\n이번 주 클로징: {closing}건")

    # 전체 파이프라인 현황
    print("\n전체 파이프라인:")
    for row in conn.execute(
        """SELECT lead_status, COUNT(*) c FROM airtable_leads
           WHERE lead_status NOT IN ('거절', 'Failed', 'Drop')
           GROUP BY lead_status ORDER BY c DESC"""
    ):
        print(f"  {row[0] or '(없음)':20s} {row[1]:>5d}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="에어테이블 → content_intel.db 동기화")
    parser.add_argument(
        "command",
        choices=["sync", "stats", "weekly"],
        help="sync: 전체 동기화 | stats: DB 통계 | weekly: 주간 리포트",
    )
    args = parser.parse_args()

    if args.command == "sync":
        cmd_sync()
    elif args.command == "stats":
        cmd_stats()
    elif args.command == "weekly":
        cmd_weekly()


if __name__ == "__main__":
    main()
