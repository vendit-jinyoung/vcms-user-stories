#!/usr/bin/env python3
"""
Generate anonymized use-case draft inputs from categorized VOC data.

Usage:
    python scripts/generate_use_case_drafts.py                 # full pipeline
    python scripts/generate_use_case_drafts.py --verify-only   # PII scan only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

# ── project imports ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from anonymize import (
    VenueRegistry,
    anonymize_text,
    anonymize_venue,
    build_blacklist,
    pii_scan,
)

# ── paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
CATEGORIES_JSON = ROOT / "categories.json"
DRAFT_INPUTS_JSON = ROOT / "_draft_inputs.json"
DRAFTS_DIR = ROOT / "drafts"
DATA_DIR = ROOT / "data" / "llm_extractions" / "bulk"
EVIDENCE_DIR = ROOT / ".sisyphus" / "evidence"

# ── clustering config ────────────────────────────────────────────────────────
TITLE_SIMILARITY_THRESHOLD = 0.45
MIN_CLUSTER_SIZE = 2

# ── draft topic plan ─────────────────────────────────────────────────────────
# Pre-planned topics per category to ensure quality and coherence.
# Each entry: (page_slug, page_title, keyword_patterns)
DRAFT_PLAN: dict[str, list[tuple[str, str, list[str]]]] = {
    "pms-kiosk-hardware": [
        (
            "unmanned-checkin-system",
            "무인 체크인/체크아웃 시스템 구축",
            ["무인", "체크인", "키오스크", "셀프"],
        ),
        (
            "pms-room-management",
            "PMS 연동으로 객실 관리 효율화",
            ["PMS", "객실 관리", "배정", "대시보드"],
        ),
    ],
    "room-product-config": [
        (
            "room-type-pricing-strategy",
            "객실 타입별 요금 전략 설정",
            ["객실 타입", "요금", "가격", "트윈", "더블"],
        ),
        (
            "package-product-management",
            "패키지 상품 구성 및 관리",
            ["패키지", "상품", "바베큐", "생맥주", "애프터눈"],
        ),
    ],
    "customer-communication": [
        (
            "auto-message-system",
            "예약 확인/안내 자동 메시지 설정",
            ["문자", "SMS", "메시지", "알림", "발송"],
        ),
    ],
    "multi-property-accounts": [
        (
            "multi-property-management",
            "다지점 숙소 통합 관리",
            ["다지점", "직원", "권한", "계정", "관리"],
        ),
    ],
    "dayuse-checkin-time": [
        (
            "dayuse-optimization",
            "대실 상품 운영 최적화",
            ["대실", "Day-Use", "피크닉", "시간"],
        ),
        (
            "flexible-checkin-checkout",
            "입퇴실 시간 유연 설정",
            ["체크인", "체크아웃", "입실", "퇴실", "시간"],
        ),
    ],
    "manual-direct-booking": [
        (
            "manual-booking-inventory-sync",
            "전화/현장 예약 등록 및 재고 연동",
            ["수기", "전화", "직접", "워크인", "현장"],
        ),
    ],
    "reservation-management": [
        (
            "reservation-change-cancel",
            "예약 변경 및 취소 처리",
            ["변경", "취소", "수정", "노쇼"],
        ),
        (
            "multi-night-group-booking",
            "연박/단체 예약 관리",
            ["연박", "단체", "장기", "그룹"],
        ),
    ],
    "overbooking-prevention": [
        (
            "overbooking-prevention-setup",
            "오버부킹 방지 설정",
            ["오버부킹", "중복", "재고", "마감"],
        ),
    ],
    "onboarding-setup": [
        (
            "vcms-initial-setup",
            "VCMS 초기 세팅 가이드",
            ["세팅", "설정", "온보딩", "초기", "연동"],
        ),
    ],
    "pricing-management": [
        (
            "seasonal-pricing",
            "기간별/시즌별 요금 설정",
            ["기간", "시즌", "성수기", "비수기", "공휴일"],
        ),
        (
            "channel-commission-pricing",
            "채널별 수수료 반영 판매가 관리",
            ["수수료", "채널", "판매가", "정산"],
        ),
        (
            "bulk-rate-adjustment",
            "요금 일괄 조정 및 동기화",
            ["일괄", "동기화", "변경", "조정"],
        ),
    ],
    "operations-automation": [
        (
            "night-unmanned-operations",
            "야간 무인 운영 자동화",
            ["야간", "무인", "자동", "새벽"],
        ),
        (
            "staff-task-automation",
            "직원 업무 자동화",
            ["직원", "청소", "점검", "공지", "배정"],
        ),
    ],
    "inventory-management": [
        (
            "channel-inventory-sync",
            "채널별 재고 연동 관리",
            ["재고", "연동", "동기화", "수량"],
        ),
        (
            "room-close-open-automation",
            "객실 마감/오픈 자동화",
            ["마감", "오픈", "만실", "차단"],
        ),
    ],
    "settlement-reports": [
        (
            "channel-settlement-reports",
            "채널별 정산 리포트 활용",
            ["정산", "리포트", "매출", "통계"],
        ),
    ],
    "channel-management": [
        (
            "multi-channel-integration",
            "다채널 통합 연동 설정",
            ["통합", "연동", "채널", "OTA"],
        ),
        (
            "channel-product-visibility",
            "채널별 상품 노출 관리",
            ["노출", "숨김", "판매", "중지"],
        ),
    ],
    "specific-channel-ops": [
        (
            "naver-yanolja-tips",
            "네이버/야놀자/여기어때 채널 운영 팁",
            ["네이버", "야놀자", "여기어때", "아고다"],
        ),
    ],
    "promotions-special-offers": [
        (
            "seasonal-promotion-ops",
            "시즌 프로모션 운영",
            ["프로모션", "특가", "이벤트", "할인"],
        ),
        (
            "walk-in-special-deals",
            "도보특가/오픈특가 운영",
            ["도보특가", "오픈특가", "특가", "랜덤"],
        ),
    ],
}


# ── helpers ──────────────────────────────────────────────────────────────────


def title_similarity(a: str, b: str) -> float:
    """Compute normalized similarity between two Korean/English titles."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def matches_keywords(text: str, keywords: list[str]) -> int:
    """Count how many keywords appear in the text (case-insensitive)."""
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw.lower() in text_lower)


def match_use_cases_to_plan(
    use_cases: list[dict[str, Any]],
    plan_entries: list[tuple[str, str, list[str]]],
) -> dict[str, list[dict[str, Any]]]:
    """Assign use_cases to planned draft topics by keyword matching."""
    assignments: dict[str, list[dict[str, Any]]] = {
        slug: [] for slug, _, _ in plan_entries
    }
    assigned_indices: set[int] = set()

    # Score each use_case against each plan entry
    for idx, uc in enumerate(use_cases):
        search_text = f"{uc['title']} {uc['description']} {uc.get('hotel_context', '')} {uc.get('benefit', '')}"
        best_slug = None
        best_score = 0

        for slug, _title, keywords in plan_entries:
            score = matches_keywords(search_text, keywords)
            if score > best_score:
                best_score = score
                best_slug = slug

        if best_slug and best_score >= 1:
            assignments[best_slug].append(uc)
            assigned_indices.add(idx)

    return assignments


def extract_key_points(
    use_cases: list[dict[str, Any]], max_points: int = 5
) -> list[str]:
    """Extract key pain points/needs from a cluster of use_cases."""
    points: list[str] = []
    seen: set[str] = set()

    for uc in use_cases:
        # Extract from description
        desc = uc.get("description", "")
        benefit = uc.get("benefit", "")

        for text in [desc, benefit]:
            # Simple extraction: sentences mentioning problems or needs
            for sentence in re.split(r"[.。]", text):
                sentence = sentence.strip()
                if len(sentence) < 10 or len(sentence) > 80:
                    continue
                # Check for pain point indicators
                if any(
                    kw in sentence
                    for kw in [
                        "어려",
                        "문제",
                        "불편",
                        "부담",
                        "오류",
                        "불일치",
                        "수동",
                        "비효율",
                        "복잡",
                    ]
                ):
                    normalized = sentence[:30]
                    if normalized not in seen:
                        seen.add(normalized)
                        points.append(sentence)

        if len(points) >= max_points:
            break

    return points[:max_points]


def build_anonymized_contexts(
    use_cases: list[dict[str, Any]],
    blacklist: list[str],
    registry: VenueRegistry,
    max_contexts: int = 5,
) -> list[str]:
    """Build anonymized context snippets from use_cases."""
    contexts: list[str] = []

    for uc in use_cases[:max_contexts]:
        source_file = uc.get("source_file", "")
        venue = anonymize_venue(source_file, registry=registry)
        hotel_ctx = uc.get("hotel_context", "")
        anon_ctx = anonymize_text(hotel_ctx, blacklist=blacklist, registry=registry)

        if venue != "미확인 업장" and anon_ctx:
            contexts.append(f"{venue}에서 {anon_ctx}")
        elif anon_ctx:
            contexts.append(anon_ctx)

    return contexts


# ── main pipeline ────────────────────────────────────────────────────────────


def prepare_draft_inputs() -> list[dict[str, Any]]:
    """Read categories.json, cluster use_cases, anonymize, produce draft inputs."""
    # Load categories
    with open(CATEGORIES_JSON, "r", encoding="utf-8") as f:
        categories = json.load(f)

    # Build blacklist from extraction data
    blacklist = build_blacklist(str(DATA_DIR))
    print(f"[INFO] Blacklist: {len(blacklist)} venue names")

    # Also add venue names found in categories.json source_files
    extra_venues: set[str] = set()
    for cat in categories:
        for uc in cat["use_cases"]:
            sf = uc.get("source_file", "")
            if sf:
                from anonymize import _strip_filename, _extract_venue_name

                stripped = _strip_filename(sf)
                vn = _extract_venue_name(stripped)
                if vn:
                    extra_venues.add(vn)
    blacklist = sorted(set(blacklist) | extra_venues)
    print(f"[INFO] Extended blacklist: {len(blacklist)} venue names")

    # Create registry for consistent anonymization
    registry = VenueRegistry()

    # Pre-register all venues
    for cat in categories:
        for uc in cat["use_cases"]:
            sf = uc.get("source_file", "")
            if sf:
                anonymize_venue(sf, registry=registry)

    draft_inputs: list[dict[str, Any]] = []

    for cat in categories:
        slug = cat["slug"]
        category_name = cat["category"]
        use_cases = cat["use_cases"]

        if slug not in DRAFT_PLAN:
            print(f"[WARN] No plan for category: {slug}, skipping")
            continue

        plan_entries = DRAFT_PLAN[slug]
        assignments = match_use_cases_to_plan(use_cases, plan_entries)

        for page_slug, page_title, keywords in plan_entries:
            matched = assignments[page_slug]

            if len(matched) < MIN_CLUSTER_SIZE:
                # Try to pad with unassigned use_cases
                remaining = [uc for uc in use_cases if uc not in matched]
                for uc in remaining:
                    if len(matched) >= MIN_CLUSTER_SIZE:
                        break
                    search_text = f"{uc['title']} {uc['description']}"
                    if (
                        matches_keywords(search_text, keywords) >= 1
                        or len(matched) < MIN_CLUSTER_SIZE
                    ):
                        matched.append(uc)

            if len(matched) < MIN_CLUSTER_SIZE:
                # Last resort: just take first N from category
                for uc in use_cases:
                    if uc not in matched:
                        matched.append(uc)
                    if len(matched) >= MIN_CLUSTER_SIZE:
                        break

            # Build anonymized contexts
            anon_contexts = build_anonymized_contexts(
                matched, blacklist, registry, max_contexts=5
            )

            # Extract key points
            key_points = extract_key_points(matched)

            draft_inputs.append(
                {
                    "category": category_name,
                    "category_slug": slug,
                    "page_slug": page_slug,
                    "page_title": page_title,
                    "source_count": len(matched),
                    "anonymized_contexts": anon_contexts,
                    "key_points": key_points,
                }
            )

    return draft_inputs


def run_pii_scan_on_drafts(blacklist: list[str]) -> tuple[int, list[str]]:
    """Scan all draft markdown files for PII violations."""
    total_violations = 0
    report_lines: list[str] = []

    if not DRAFTS_DIR.exists():
        report_lines.append("No drafts directory found.")
        return 0, report_lines

    md_files = sorted(DRAFTS_DIR.rglob("*.md"))
    report_lines.append(f"Scanning {len(md_files)} draft files...\n")

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        violations = pii_scan(content, blacklist=blacklist)

        rel_path = md_file.relative_to(ROOT)
        if violations:
            total_violations += len(violations)
            report_lines.append(f"FAIL  {rel_path}: {len(violations)} violation(s)")
            for v in violations:
                report_lines.append(f"  - {v}")
        else:
            report_lines.append(f"PASS  {rel_path}")

    report_lines.append(f"\n{'=' * 60}")
    report_lines.append(f"Total files scanned: {len(md_files)}")
    report_lines.append(f"Total PII violations: {total_violations}")
    report_lines.append(f"Result: {'PASS ✅' if total_violations == 0 else 'FAIL ❌'}")

    return total_violations, report_lines


def main():
    parser = argparse.ArgumentParser(description="Generate use-case draft inputs")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only run PII scan on existing drafts",
    )
    args = parser.parse_args()

    # Build blacklist
    blacklist = build_blacklist(str(DATA_DIR))
    # Extend with category source files
    if CATEGORIES_JSON.exists():
        with open(CATEGORIES_JSON, "r", encoding="utf-8") as f:
            categories = json.load(f)
        from anonymize import _strip_filename, _extract_venue_name

        for cat in categories:
            for uc in cat["use_cases"]:
                sf = uc.get("source_file", "")
                if sf:
                    stripped = _strip_filename(sf)
                    vn = _extract_venue_name(stripped)
                    if vn:
                        blacklist.append(vn)
        blacklist = sorted(set(blacklist))

    # Filter out generic venue type keywords and company name from blacklist
    # These are common words used in docs context, not PII
    BLACKLIST_EXCLUDE = {
        "호텔",
        "모텔",
        "리조트",
        "리조텔",
        "게스트하우스",
        "펜션",
        "풀빌라",
        "스테이",
        "벤디트",
        "VCMS",
        "vcms",
    }
    blacklist = [v for v in blacklist if v not in BLACKLIST_EXCLUDE]

    if args.verify_only:
        print("[MODE] Verify-only: scanning existing drafts for PII...")
        total_violations, report = run_pii_scan_on_drafts(blacklist)
        for line in report:
            print(line)

        # Save evidence
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        evidence_file = EVIDENCE_DIR / "task-4-pii-clean.txt"
        evidence_file.write_text("\n".join(report), encoding="utf-8")
        print(f"\n[SAVED] Evidence → {evidence_file}")

        sys.exit(1 if total_violations > 0 else 0)

    # Full pipeline
    print("[STEP 1] Preparing draft inputs...")
    draft_inputs = prepare_draft_inputs()

    # Save draft inputs
    with open(DRAFT_INPUTS_JSON, "w", encoding="utf-8") as f:
        json.dump(draft_inputs, f, ensure_ascii=False, indent=2)
    print(f"[SAVED] {len(draft_inputs)} draft inputs → {DRAFT_INPUTS_JSON}")

    # Create drafts directory structure
    for di in draft_inputs:
        cat_dir = DRAFTS_DIR / di["category_slug"]
        cat_dir.mkdir(parents=True, exist_ok=True)

    print(f"[STEP 2] Created directory structure under {DRAFTS_DIR}/")
    print(
        f"\n[DONE] Ready for content generation. Run with --verify-only after writing drafts."
    )

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Draft plan summary:")
    for di in draft_inputs:
        print(
            f"  {di['category_slug']}/{di['page_slug']}.md — {di['source_count']} sources"
        )
    print(f"Total drafts planned: {len(draft_inputs)}")


if __name__ == "__main__":
    main()
