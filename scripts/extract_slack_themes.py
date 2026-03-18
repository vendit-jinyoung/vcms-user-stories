#!/usr/bin/env python3
"""
Extract themes from Slack messages in local SQLite DB.

Queries system-vcms-noti and public-vcms channels, clusters messages
by keyword groups (연동/교육/장애/채널별), and outputs structured JSON.

Usage:
    python scripts/extract_slack_themes.py              # full run
    python scripts/extract_slack_themes.py --dry-run    # preview only
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────────
DB_PATH = Path("/Users/vendit/data/slack_index.db")
ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "_slack_themes.json"

# ── target channels ──────────────────────────────────────────────────────────
TARGET_CHANNELS = ("system-vcms-noti", "public-vcms")

# ── keyword groups ───────────────────────────────────────────────────────────
KEYWORD_GROUPS: dict[str, list[str]] = {
    "연동": ["연동", "동기화", "매핑"],
    "교육": ["교육", "세팅", "설치", "온보딩"],
    "장애": ["장애", "오류", "에러", "아파요"],
    "채널별": [
        "야놀자",
        "여기어때",
        "네이버",
        "아고다",
        "트립닷컴",
        "떠나요",
        "리피터",
    ],
}

# ── suggested category + slug defaults ───────────────────────────────────────
# For 채널별, sub-themes are created per channel keyword
CATEGORY_SLUG_MAP: dict[str, tuple[str, str]] = {
    "연동": ("channel-management", "channel-sync-setup"),
    "교육": ("onboarding-setup", "onboarding-education-guide"),
    "장애": ("channel-management", "channel-sync-failure-response"),
}

CHANNEL_KEYWORD_SLUGS: dict[str, tuple[str, str]] = {
    "야놀자": ("specific-channel-ops", "yanolja-integration-tips"),
    "네이버": ("specific-channel-ops", "naver-integration-tips"),
    "트립닷컴": ("specific-channel-ops", "tripdotcom-agoda-mapping"),
    "아고다": ("specific-channel-ops", "agoda-integration-tips"),
    "떠나요": ("specific-channel-ops", "ddnayo-repeater-guide"),
    "리피터": ("specific-channel-ops", "ddnayo-repeater-guide"),
    "여기어때": ("specific-channel-ops", "yogiotte-integration-tips"),
}

# ── theme name mapping ───────────────────────────────────────────────────────
GROUP_THEME_NAMES: dict[str, str] = {
    "연동": "채널 연동 및 동기화 설정",
    "교육": "온보딩 및 교육 안내",
    "장애": "채널 동기화 장애 대응",
}

CHANNEL_THEME_NAMES: dict[str, str] = {
    "야놀자": "야놀자 연동 운영 사례",
    "여기어때": "여기어때 연동 운영 사례",
    "네이버": "네이버 연동 운영 사례",
    "아고다": "아고다 연동 운영 사례",
    "트립닷컴": "트립닷컴 매핑 및 운영",
    "떠나요": "떠나요·리피터 연동 안내",
    "리피터": "떠나요·리피터 연동 안내",
}

MAX_REPRESENTATIVE = 8
MAX_THEMES = 10


def _build_fts_query(keywords: list[str]) -> str:
    """Build FTS5 MATCH query string from keyword list."""
    quoted = [f'"{kw}"' for kw in keywords]
    return " OR ".join(quoted)


def _query_keyword_group(
    cursor: sqlite3.Cursor,
    keywords: list[str],
    limit: int = 200,
) -> list[dict]:
    """Query messages matching keyword group via FTS5."""
    fts_query = _build_fts_query(keywords)
    cursor.execute(
        """
        SELECT m.date, m.channel, m.text_clean
        FROM messages m
        JOIN messages_fts fts ON m.rowid = fts.rowid
        WHERE fts.text_clean MATCH ?
        AND m.channel IN (?, ?)
        AND m.text_clean NOT LIKE 'New submission%'
        ORDER BY m.ts DESC
        LIMIT ?
        """,
        (fts_query, TARGET_CHANNELS[0], TARGET_CHANNELS[1], limit),
    )
    rows = cursor.fetchall()
    return [{"date": r[0], "channel": r[1], "text": r[2]} for r in rows]


def _get_total_messages(cursor: sqlite3.Cursor) -> int:
    """Count total messages in target channels."""
    cursor.execute(
        """
        SELECT COUNT(*) FROM messages
        WHERE channel IN (?, ?)
        AND text_clean NOT LIKE 'New submission%'
        """,
        TARGET_CHANNELS,
    )
    return cursor.fetchone()[0]


def _build_theme(
    group_name: str,
    keyword_label: str,
    messages: list[dict],
    theme_id: str,
    theme_name: str,
    suggested_category: str,
    suggested_slug: str,
) -> dict:
    """Build a single theme dict from matched messages."""
    channel_counts: dict[str, int] = defaultdict(int)
    dates: list[str] = []

    for msg in messages:
        channel_counts[msg["channel"]] += 1
        if msg["date"]:
            dates.append(msg["date"])

    dates_sorted = sorted(dates) if dates else []
    date_range = (
        [dates_sorted[0], dates_sorted[-1]] if len(dates_sorted) >= 2 else dates_sorted
    )

    representative = []
    for msg in messages[:MAX_REPRESENTATIVE]:
        representative.append(
            {
                "date": msg["date"],
                "channel": msg["channel"],
                "text": (msg["text"][:200] + "…")
                if len(msg["text"]) > 200
                else msg["text"],
            }
        )

    return {
        "theme_id": theme_id,
        "theme_name": theme_name,
        "keyword_group": group_name,
        "message_count": len(messages),
        "channels": dict(channel_counts),
        "date_range": date_range,
        "representative_messages": representative,
        "suggested_category": suggested_category,
        "suggested_draft_slug": suggested_slug,
    }


def _extract_themes(cursor: sqlite3.Cursor) -> list[dict]:
    """Extract all themes from DB, respecting MAX_THEMES."""
    themes: list[dict] = []

    # Process non-채널별 groups first
    for group_name in ["연동", "교육", "장애"]:
        keywords = KEYWORD_GROUPS[group_name]
        messages = _query_keyword_group(cursor, keywords)
        if not messages:
            continue

        cat, slug = CATEGORY_SLUG_MAP[group_name]
        theme_id = slug
        theme_name = GROUP_THEME_NAMES[group_name]

        themes.append(
            _build_theme(
                group_name, group_name, messages, theme_id, theme_name, cat, slug
            )
        )

    # Process 채널별 group — split into sub-themes per channel keyword
    channel_keywords = KEYWORD_GROUPS["채널별"]
    # Group 떠나요 + 리피터 together
    merged_keywords: dict[str, list[str]] = {}
    for kw in channel_keywords:
        if kw in ("떠나요", "리피터"):
            merged_keywords.setdefault("떠나요+리피터", []).append(kw)
        else:
            merged_keywords[kw] = [kw]

    for label, kws in merged_keywords.items():
        messages = _query_keyword_group(cursor, kws)
        if not messages:
            continue

        first_kw = kws[0]
        cat, slug = CHANNEL_KEYWORD_SLUGS.get(
            first_kw, ("specific-channel-ops", f"{first_kw}-tips")
        )
        theme_name = CHANNEL_THEME_NAMES.get(first_kw, f"{label} 연동 운영 사례")
        theme_id = slug

        themes.append(
            _build_theme("채널별", label, messages, theme_id, theme_name, cat, slug)
        )

    themes.sort(key=lambda t: t["message_count"], reverse=True)

    if len(themes) > MAX_THEMES:
        # Merge smallest themes into an "기타" theme
        keep = themes[: MAX_THEMES - 1]
        overflow = themes[MAX_THEMES - 1 :]

        merged_messages_count = sum(t["message_count"] for t in overflow)
        merged_channels: dict[str, int] = defaultdict(int)
        merged_dates: list[str] = []
        merged_representatives: list[dict] = []

        for t in overflow:
            for ch, cnt in t["channels"].items():
                merged_channels[ch] += cnt
            merged_dates.extend(t.get("date_range", []))
            merged_representatives.extend(t["representative_messages"])

        merged_dates_sorted = sorted(set(merged_dates)) if merged_dates else []
        merged_date_range = (
            [merged_dates_sorted[0], merged_dates_sorted[-1]]
            if len(merged_dates_sorted) >= 2
            else merged_dates_sorted
        )

        merged_theme = {
            "theme_id": "misc-combined",
            "theme_name": "기타 통합 주제",
            "keyword_group": "기타",
            "message_count": merged_messages_count,
            "channels": dict(merged_channels),
            "date_range": merged_date_range,
            "representative_messages": merged_representatives[:MAX_REPRESENTATIVE],
            "suggested_category": "general",
            "suggested_draft_slug": "misc-combined-topics",
        }

        keep.append(merged_theme)
        themes = keep

    return themes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract themes from Slack messages in local SQLite DB."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview keyword group counts without writing output file.",
    )
    args = parser.parse_args()

    # ── DB existence check ───────────────────────────────────────────────
    if not DB_PATH.exists():
        print(f"Error: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    # ── Connect read-only ────────────────────────────────────────────────
    db_uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    cursor = conn.cursor()

    try:
        total_messages = _get_total_messages(cursor)

        if args.dry_run:
            print("=== Dry Run: Keyword Group Counts ===")
            print(f"Total messages in target channels: {total_messages}")
            print()
            for group_name, keywords in KEYWORD_GROUPS.items():
                messages = _query_keyword_group(cursor, keywords)
                print(
                    f"  {group_name}: {len(messages)} messages (keywords: {', '.join(keywords)})"
                )
            print()
            print("No output file written (--dry-run).")
            return

        # ── Full run ─────────────────────────────────────────────────────
        themes = _extract_themes(cursor)

        output = {
            "metadata": {
                "extracted_at": datetime.now().isoformat(timespec="seconds"),
                "db_path": str(DB_PATH),
                "channels": list(TARGET_CHANNELS),
                "total_messages_scanned": total_messages,
                "themes_extracted": len(themes),
            },
            "themes": themes,
        }

        OUTPUT_PATH.write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print(f"Extracted {len(themes)} themes from {total_messages} messages.")
        print(f"Output: {OUTPUT_PATH}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
