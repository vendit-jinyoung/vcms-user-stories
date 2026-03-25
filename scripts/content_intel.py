#!/usr/bin/env python3
"""
content_intel.py — Content Intelligence Pipeline
=================================================
VOC(1,415 use cases) + Slack(31,968 messages) + 발행된 MDX 콘텐츠를
통합 DB로 구축하고, 미발행 갭을 GitHub Issues로 등록한다.

Usage:
    python3 scripts/content_intel.py build      # DB 구축 (전체)
    python3 scripts/content_intel.py scan       # 갭 분석 리포트
    python3 scripts/content_intel.py issues     # GitHub Issues 생성
    python3 scripts/content_intel.py issues --dry-run  # 미리보기만
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from textwrap import dedent

# ── Paths ─────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "content_intel.db"
CATEGORIES_JSON = ROOT / "categories.json"
SLACK_DB = Path.home() / "data" / "slack_index.db"
KO_DIR = ROOT / "ko"

# ── MECE category → MDX content mapping ──────────────────────────
# Each category maps to keywords found in MDX filenames/content
CATEGORY_MDX_KEYWORDS: dict[str, list[str]] = {
    "pricing-management": [
        "rate", "pricing", "요금", "markup", "seasonal-rate", "dayuse-rate",
        "bulk-rate", "walk-in-special", "channel-rate", "promotion",
    ],
    "inventory-management": [
        "inventory", "재고", "stop-sell", "reopen", "auto-replenish",
        "max-inventory", "room-close", "walk-in-booking", "overbooking",
        "reservation-change", "manual-booking",
    ],
    "channel-management": [
        "channel-connect", "channel-sync", "multi-channel", "sales-period",
        "채널", "연동", "sync-failure",
    ],
    "reservation-management": [
        "reservation", "예약", "booking", "change-cancel", "multi-night",
        "group-booking",
    ],
    "room-product-config": [
        "room-type", "package-product", "mapping", "객실", "상품",
    ],
    "operations-automation": [
        "automation", "자동화", "night-unmanned", "야간",
    ],
    "dayuse-checkin-time": [
        "dayuse", "대실", "checkin", "checkout", "flexible",
    ],
    "promotions-special-offers": [
        "promotion", "프로모션", "특가", "seasonal-promotion", "special-deal",
    ],
    "manual-direct-booking": [
        "manual-booking", "walk-in", "수기", "직접",
    ],
    "onboarding-setup": [
        "onboarding", "setup", "초기", "repeater", "education",
    ],
    "specific-channel-ops": [
        "agoda", "yanolja", "yeogiottae", "naver", "tripdotcom",
        "onda", "ddnayo", "kkulstay", "tripbtoz",
    ],
    "overbooking-prevention": [
        "overbooking", "오버부킹",
    ],
    "multi-property-accounts": [
        "multi-property", "permission", "다지점", "권한",
    ],
    "customer-communication": [
        "message", "auto-message", "메시지", "커뮤니케이션",
    ],
    "pms-kiosk-hardware": [
        "pms", "kiosk", "키오스크", "하드웨어",
    ],
    "settlement-reports": [
        "settlement", "정산", "매출", "리포트",
    ],
}

# ── Slack channels relevant to VCMS content ──────────────────────
VCMS_SLACK_CHANNELS = (
    "lounge-vcms", "lounge-vcms-tf", "public-vcms",
    "public-cx", "system-vcms-noti",
    "알림-고객이슈", "알림-cms가아파요",
)

# Slack message → category keyword mapping
SLACK_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "pricing-management": ["요금", "가격", "단가", "할인", "수수료", "마크업", "전송가", "rate"],
    "inventory-management": ["재고", "마감", "판매중지", "방막기", "오픈", "블로킹", "stop sell"],
    "channel-management": ["연동", "채널", "동기화", "sync", "api", "연결"],
    "reservation-management": ["예약", "취소", "변경", "노쇼", "booking"],
    "room-product-config": ["객실", "상품", "패키지", "룸타입", "매핑"],
    "operations-automation": ["자동", "스케줄", "야간", "무인"],
    "dayuse-checkin-time": ["대실", "체크인", "체크아웃", "입실", "퇴실"],
    "promotions-special-offers": ["프로모션", "특가", "쿠폰", "할인", "이벤트"],
    "manual-direct-booking": ["수기", "워크인", "전화예약", "직접"],
    "onboarding-setup": ["교육", "세팅", "초기", "온보딩", "설치"],
    "specific-channel-ops": ["야놀자", "아고다", "여기어때", "네이버", "트립닷컴", "떠나요", "온다"],
    "overbooking-prevention": ["오버부킹", "초과예약", "중복예약"],
    "multi-property-accounts": ["다지점", "권한", "계정", "마스터"],
    "customer-communication": ["문자", "메시지", "알림톡", "sms", "카카오"],
    "pms-kiosk-hardware": ["pms", "키오스크", "도어락", "하드웨어"],
    "settlement-reports": ["정산", "매출", "리포트", "세금"],
}


# ══════════════════════════════════════════════════════════════════
# DB Schema
# ══════════════════════════════════════════════════════════════════

SCHEMA = """
-- VOC use cases (from categories.json)
CREATE TABLE IF NOT EXISTS voc_use_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_slug TEXT NOT NULL,
    category_name TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    hotel_context TEXT,
    benefit TEXT,
    source_file TEXT,
    published_in TEXT,          -- comma-separated MDX paths
    is_published INTEGER DEFAULT 0
);

-- Slack messages relevant to VCMS content
CREATE TABLE IF NOT EXISTS slack_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    date TEXT NOT NULL,
    channel TEXT NOT NULL,
    user_name TEXT,
    text_clean TEXT,
    category_slug TEXT,
    is_mapped INTEGER DEFAULT 0
);

-- Published MDX content inventory
CREATE TABLE IF NOT EXISTS published_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL UNIQUE,
    tab TEXT NOT NULL,           -- vcms-usage | channels | magazine
    title TEXT,
    description TEXT,
    category_slugs TEXT,        -- comma-separated matched categories
    word_count INTEGER DEFAULT 0
);

-- Content gap analysis results
CREATE TABLE IF NOT EXISTS content_gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_slug TEXT NOT NULL,
    category_name TEXT NOT NULL,
    total_use_cases INTEGER,
    published_use_cases INTEGER,
    unpublished_use_cases INTEGER,
    slack_signal_count INTEGER,
    coverage_pct REAL,
    priority TEXT,              -- high | medium | low
    suggested_title TEXT,
    suggested_tab TEXT,         -- vcms-usage | channels | magazine
    issue_number INTEGER        -- GitHub issue # once created
);

CREATE INDEX IF NOT EXISTS idx_voc_category ON voc_use_cases(category_slug);
CREATE INDEX IF NOT EXISTS idx_voc_published ON voc_use_cases(is_published);
CREATE INDEX IF NOT EXISTS idx_slack_category ON slack_signals(category_slug);
CREATE INDEX IF NOT EXISTS idx_gaps_priority ON content_gaps(priority);
"""


def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    return conn


# ══════════════════════════════════════════════════════════════════
# Phase 1: Ingest VOC use cases
# ══════════════════════════════════════════════════════════════════

def ingest_voc(conn: sqlite3.Connection) -> int:
    if not CATEGORIES_JSON.exists():
        print(f"  ERROR: {CATEGORIES_JSON} not found")
        return 0

    conn.execute("DELETE FROM voc_use_cases")
    data = json.loads(CATEGORIES_JSON.read_text(encoding="utf-8"))

    batch = []
    for cat in data:
        slug = cat["slug"]
        name = cat["category"]
        for uc in cat.get("use_cases", []):
            batch.append((
                slug, name,
                uc.get("title", ""),
                uc.get("description", ""),
                uc.get("hotel_context", ""),
                uc.get("benefit", ""),
                uc.get("source_file", ""),
            ))

    conn.executemany(
        "INSERT INTO voc_use_cases (category_slug, category_name, title, description, hotel_context, benefit, source_file) VALUES (?,?,?,?,?,?,?)",
        batch,
    )
    conn.commit()
    print(f"  VOC: {len(batch)} use cases ingested")
    return len(batch)


# ══════════════════════════════════════════════════════════════════
# Phase 2: Ingest Slack signals
# ══════════════════════════════════════════════════════════════════

def classify_slack_message(text_lower: str) -> str | None:
    """Classify a Slack message into a MECE category by keyword match."""
    scores: dict[str, int] = {}
    for slug, keywords in SLACK_CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[slug] = score
    if not scores:
        return None
    return max(scores, key=scores.get)


def ingest_slack(conn: sqlite3.Connection) -> int:
    if not SLACK_DB.exists():
        print(f"  WARN: {SLACK_DB} not found, skipping Slack ingest")
        return 0

    conn.execute("DELETE FROM slack_signals")

    slack_conn = sqlite3.connect(str(SLACK_DB))
    channels_placeholder = ",".join(f"'{c}'" for c in VCMS_SLACK_CHANNELS)
    rows = slack_conn.execute(
        f"SELECT ts, date, channel, user_name, text_clean FROM messages WHERE channel IN ({channels_placeholder})"
    ).fetchall()
    slack_conn.close()

    batch = []
    for ts, date, channel, user_name, text_clean in rows:
        if not text_clean or len(text_clean) < 10:
            continue
        category = classify_slack_message(text_clean.lower())
        batch.append((ts, date, channel, user_name, text_clean[:500], category, 1 if category else 0))

    conn.executemany(
        "INSERT INTO slack_signals (ts, date, channel, user_name, text_clean, category_slug, is_mapped) VALUES (?,?,?,?,?,?,?)",
        batch,
    )
    conn.commit()
    print(f"  Slack: {len(batch)} signals ingested ({sum(1 for b in batch if b[5])} categorized)")
    return len(batch)


# ══════════════════════════════════════════════════════════════════
# Phase 3: Scan published MDX content
# ══════════════════════════════════════════════════════════════════

def extract_frontmatter(mdx_path: Path) -> dict[str, str]:
    """Extract YAML frontmatter from MDX file."""
    text = mdx_path.read_text(encoding="utf-8")
    fm = {}
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            for line in text[3:end].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    fm[key.strip().strip('"')] = val.strip().strip('"')
    fm["_word_count"] = len(text.split())
    fm["_full_text"] = text[:2000].lower()
    return fm


def classify_mdx(file_path: str, full_text_lower: str) -> list[str]:
    """Match MDX file to its PRIMARY MECE category (best match only).
    Returns a list with 0 or 1 element to keep the interface stable."""
    combined = file_path.lower() + " " + full_text_lower
    best_slug = None
    best_score = 0
    for slug, keywords in CATEGORY_MDX_KEYWORDS.items():
        # Weight filename matches higher than body matches
        fname_score = sum(3 for kw in keywords if kw in file_path.lower())
        body_score = sum(1 for kw in keywords if kw in full_text_lower)
        score = fname_score + body_score
        if score > best_score:
            best_score = score
            best_slug = slug
    if best_slug and best_score >= 2:
        return [best_slug]
    return []


def determine_tab(rel_path: str) -> str:
    if "vcms-usage" in rel_path:
        return "vcms-usage"
    elif "channels" in rel_path:
        return "channels"
    elif "magazine" in rel_path:
        return "magazine"
    return "unknown"


def ingest_mdx(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM published_content")

    count = 0
    for mdx in sorted(KO_DIR.rglob("*.mdx")):
        rel = str(mdx.relative_to(ROOT))
        fm = extract_frontmatter(mdx)
        tab = determine_tab(rel)
        categories = classify_mdx(rel, fm.get("_full_text", ""))

        conn.execute(
            "INSERT INTO published_content (file_path, tab, title, description, category_slugs, word_count) VALUES (?,?,?,?,?,?)",
            (rel, tab, fm.get("title", ""), fm.get("description", ""),
             ",".join(categories), fm.get("_word_count", 0)),
        )
        count += 1

    conn.commit()
    print(f"  MDX: {count} files indexed")
    return count


# ══════════════════════════════════════════════════════════════════
# Phase 4: Map VOC → published content
# ══════════════════════════════════════════════════════════════════

def map_voc_to_content(conn: sqlite3.Connection):
    """Mark VOC use cases as published based on realistic per-page capacity.

    Rule: 1 MDX page ≈ 10 use cases covered (based on current avg page depth).
    A category with 361 use cases and 8 MDX pages → 80/361 = 22% covered.
    """
    USE_CASES_PER_PAGE = 10

    # Count MDX pages per primary category
    rows = conn.execute(
        "SELECT category_slugs FROM published_content WHERE category_slugs != ''"
    ).fetchall()
    coverage: dict[str, int] = defaultdict(int)
    for (slugs,) in rows:
        for s in slugs.split(","):
            coverage[s.strip()] += 1

    for slug, mdx_count in coverage.items():
        total_uc = conn.execute(
            "SELECT COUNT(*) FROM voc_use_cases WHERE category_slug = ?", (slug,)
        ).fetchone()[0]
        if total_uc == 0:
            continue

        covered_count = min(total_uc, mdx_count * USE_CASES_PER_PAGE)

        conn.execute("""
            UPDATE voc_use_cases SET is_published = 1
            WHERE category_slug = ? AND id IN (
                SELECT id FROM voc_use_cases WHERE category_slug = ?
                ORDER BY id LIMIT ?
            )
        """, (slug, slug, covered_count))

    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM voc_use_cases").fetchone()[0]
    published = conn.execute("SELECT COUNT(*) FROM voc_use_cases WHERE is_published = 1").fetchone()[0]
    pct = round(published / total * 100, 1) if total else 0
    print(f"  Mapping: {published}/{total} use cases covered ({pct}%)")


# ══════════════════════════════════════════════════════════════════
# Phase 5: Gap analysis
# ══════════════════════════════════════════════════════════════════

# Content policy exclusions
EXCLUDED_CATEGORIES = {"pms-kiosk-hardware", "settlement-reports"}

CATEGORY_TAB_MAP: dict[str, str] = {
    "pricing-management": "vcms-usage",
    "inventory-management": "vcms-usage",
    "channel-management": "vcms-usage",
    "reservation-management": "vcms-usage",
    "room-product-config": "vcms-usage",
    "operations-automation": "vcms-usage",
    "dayuse-checkin-time": "vcms-usage",
    "promotions-special-offers": "vcms-usage",
    "manual-direct-booking": "vcms-usage",
    "onboarding-setup": "vcms-usage",
    "specific-channel-ops": "channels",
    "overbooking-prevention": "vcms-usage",
    "multi-property-accounts": "vcms-usage",
    "customer-communication": "vcms-usage",
}

CATEGORY_TITLE_MAP: dict[str, str] = {
    "pricing-management": "요금 운영 심화 — 미발행 사례 기반",
    "inventory-management": "재고 운영 추가 시나리오",
    "channel-management": "채널 연동 트러블슈팅 가이드",
    "reservation-management": "예약 관리 실무 — 변경/취소/노쇼 대응",
    "room-product-config": "객실·상품 설정 추가 패턴",
    "operations-automation": "운영 자동화 확장 — 스케줄/야간/무인",
    "dayuse-checkin-time": "대실·입퇴실 시간 고급 운영",
    "promotions-special-offers": "프로모션 운영 실전 가이드",
    "manual-direct-booking": "수기 예약 관리 고도화",
    "onboarding-setup": "온보딩 교육 체크리스트 확장",
    "specific-channel-ops": "채널별 추가 운영 노트",
    "overbooking-prevention": "오버부킹 예방 고급 설정",
    "multi-property-accounts": "다지점·권한 관리 심화",
    "customer-communication": "고객 커뮤니케이션 자동화",
}


def run_gap_analysis(conn: sqlite3.Connection) -> list[dict]:
    conn.execute("DELETE FROM content_gaps")

    gaps = []
    categories = json.loads(CATEGORIES_JSON.read_text(encoding="utf-8"))

    for cat in categories:
        slug = cat["slug"]
        name = cat["category"]

        if slug in EXCLUDED_CATEGORIES:
            continue

        total = cat.get("count", len(cat.get("use_cases", [])))
        published = conn.execute(
            "SELECT COUNT(*) FROM voc_use_cases WHERE category_slug = ? AND is_published = 1",
            (slug,),
        ).fetchone()[0]
        unpublished = total - published

        slack_count = conn.execute(
            "SELECT COUNT(*) FROM slack_signals WHERE category_slug = ?", (slug,)
        ).fetchone()[0]

        coverage = (published / total * 100) if total > 0 else 0

        # Priority based on coverage gap + slack signal volume
        if coverage < 30 and slack_count > 100:
            priority = "high"
        elif coverage < 50 or (unpublished > 20 and slack_count > 50):
            priority = "high"
        elif coverage < 70:
            priority = "medium"
        else:
            priority = "low"

        gap = {
            "category_slug": slug,
            "category_name": name,
            "total": total,
            "published": published,
            "unpublished": unpublished,
            "slack_signals": slack_count,
            "coverage_pct": round(coverage, 1),
            "priority": priority,
            "suggested_title": CATEGORY_TITLE_MAP.get(slug, f"{name} 추가 콘텐츠"),
            "suggested_tab": CATEGORY_TAB_MAP.get(slug, "vcms-usage"),
        }
        gaps.append(gap)

        conn.execute(
            """INSERT INTO content_gaps
               (category_slug, category_name, total_use_cases, published_use_cases,
                unpublished_use_cases, slack_signal_count, coverage_pct, priority,
                suggested_title, suggested_tab)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (slug, name, total, published, unpublished, slack_count,
             coverage, priority, gap["suggested_title"], gap["suggested_tab"]),
        )

    conn.commit()

    # Sort by priority then unpublished count
    priority_order = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda g: (priority_order[g["priority"]], -g["unpublished"]))

    return gaps


def print_scan_report(gaps: list[dict]):
    print("\n" + "=" * 70)
    print("  CONTENT GAP ANALYSIS REPORT")
    print("=" * 70)

    for g in gaps:
        bar_len = int(g["coverage_pct"] / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        pri_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}[g["priority"]]

        print(f"\n{pri_icon} [{g['priority'].upper():6s}] {g['category_name']}")
        print(f"   VOC: {g['published']}/{g['total']} covered  |  Slack: {g['slack_signals']} signals")
        print(f"   {bar} {g['coverage_pct']}%")
        print(f"   → {g['suggested_title']} ({g['suggested_tab']})")

    print("\n" + "-" * 70)
    total_uc = sum(g["total"] for g in gaps)
    total_pub = sum(g["published"] for g in gaps)
    total_unpub = sum(g["unpublished"] for g in gaps)
    total_slack = sum(g["slack_signals"] for g in gaps)
    print(f"  Total: {total_pub}/{total_uc} use cases covered ({total_unpub} gaps)")
    print(f"  Slack signals: {total_slack}")
    print(f"  High priority: {sum(1 for g in gaps if g['priority'] == 'high')}")
    print(f"  Medium priority: {sum(1 for g in gaps if g['priority'] == 'medium')}")
    print("=" * 70)


# ══════════════════════════════════════════════════════════════════
# Phase 6: GitHub Issues
# ══════════════════════════════════════════════════════════════════

def get_unpublished_examples(conn: sqlite3.Connection, slug: str, limit: int = 5) -> list[str]:
    """Get example unpublished use case titles for an issue body."""
    rows = conn.execute(
        "SELECT title FROM voc_use_cases WHERE category_slug = ? AND is_published = 0 LIMIT ?",
        (slug, limit),
    ).fetchall()
    return [r[0] for r in rows]


def create_github_issues(conn: sqlite3.Connection, gaps: list[dict], dry_run: bool = False):
    # Only create issues for medium+ priority
    actionable = [g for g in gaps if g["priority"] in ("high", "medium")]

    if not actionable:
        print("  No actionable gaps found.")
        return

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Creating {len(actionable)} GitHub Issues...\n")

    for g in actionable:
        examples = get_unpublished_examples(conn, g["category_slug"])
        examples_md = "\n".join(f"  - {e}" for e in examples)

        pri_label = {"high": "priority: high", "medium": "priority: medium"}[g["priority"]]

        title = f"[content] {g['suggested_title']}"
        body = dedent(f"""\
        ## Content Gap: {g['category_name']}

        | Metric | Value |
        |--------|-------|
        | VOC use cases | {g['total']} |
        | Currently covered | {g['published']} ({g['coverage_pct']}%) |
        | Uncovered | {g['unpublished']} |
        | Slack signals | {g['slack_signals']} |
        | Priority | **{g['priority'].upper()}** |
        | Target tab | `{g['suggested_tab']}` |

        ## Unpublished Use Case Examples
        {examples_md}

        ## Action
        - [ ] Draft MDX content based on uncovered VOC use cases
        - [ ] Review against content-policy-vcms.md
        - [ ] Add to docs.json navigation
        - [ ] PR & publish

        ---
        *Auto-generated by `content_intel.py scan`*
        *Category: `{g['category_slug']}` | {g['total']} total use cases*
        """)

        if dry_run:
            print(f"  {'🔴' if g['priority'] == 'high' else '🟡'} {title}")
            print(f"     {g['unpublished']} uncovered use cases, {g['slack_signals']} slack signals")
        else:
            try:
                result = subprocess.run(
                    ["gh", "issue", "create",
                     "--title", title,
                     "--body", body,
                     "--label", f"content,{pri_label}"],
                    capture_output=True, text=True, cwd=str(ROOT),
                )
                if result.returncode == 0:
                    issue_url = result.stdout.strip()
                    issue_num = int(issue_url.rstrip("/").split("/")[-1])
                    conn.execute(
                        "UPDATE content_gaps SET issue_number = ? WHERE category_slug = ?",
                        (issue_num, g["category_slug"]),
                    )
                    print(f"  ✓ {title} → {issue_url}")
                else:
                    print(f"  ✗ {title}: {result.stderr.strip()}")
            except FileNotFoundError:
                print("  ERROR: `gh` CLI not found. Install GitHub CLI first.")
                return

    conn.commit()
    if dry_run:
        print(f"\n  Run without --dry-run to create these {len(actionable)} issues.")


# ══════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════

def cmd_build():
    print("Building content intelligence DB...")
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = init_db()
    ingest_voc(conn)
    ingest_slack(conn)
    ingest_mdx(conn)
    map_voc_to_content(conn)
    print(f"\n  DB: {DB_PATH} ({DB_PATH.stat().st_size / 1024:.0f} KB)")
    conn.close()


def cmd_scan():
    if not DB_PATH.exists():
        print("DB not found, building first...")
        cmd_build()
    conn = init_db()
    gaps = run_gap_analysis(conn)
    print_scan_report(gaps)
    conn.close()


def cmd_issues(dry_run: bool = False):
    if not DB_PATH.exists():
        cmd_build()
    conn = init_db()
    gaps = run_gap_analysis(conn)
    print_scan_report(gaps)
    create_github_issues(conn, gaps, dry_run=dry_run)
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Content Intelligence Pipeline")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("build", help="Build unified DB from all sources")
    sub.add_parser("scan", help="Run gap analysis and print report")

    issues_parser = sub.add_parser("issues", help="Create GitHub Issues for gaps")
    issues_parser.add_argument("--dry-run", action="store_true", help="Preview only")

    args = parser.parse_args()

    if args.command == "build":
        cmd_build()
    elif args.command == "scan":
        cmd_scan()
    elif args.command == "issues":
        cmd_issues(dry_run=args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
