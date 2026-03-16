#!/usr/bin/env python3
"""
categorize_use_cases.py
Extracts use_cases from VOC JSON files, deduplicates, and categorizes them
using keyword-based rules (NO external LLM API calls).

Phase A: Extract → _all_use_cases.json
Phase B: Categorize → categories.json
Phase C: Verify → prints QA report

Usage:
    python3 scripts/categorize_use_cases.py
"""

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "llm_extractions" / "bulk"
INTERMEDIATE_FILE = PROJECT_ROOT / "_all_use_cases.json"
OUTPUT_FILE = PROJECT_ROOT / "categories.json"

SKIP_FILES = {"_progress.json", "_progress.json.bak", "_batch_log.txt"}

# ── Category Definitions ───────────────────────────────────────
# Priority: lower number = checked first (specific before general)
# Each category has primary keywords (strong match) and secondary keywords
CATEGORIES = [
    {
        "category": "오버부킹 방지/처리",
        "slug": "overbooking-prevention",
        "description": "오버부킹(초과 예약) 감지, 방지, 해결 및 강제 객실 배정",
        "primary": [
            "오버부킹",
            "overbooking",
            "중복 예약",
            "초과 예약",
            "강제 배정",
            "forced allocation",
        ],
        "secondary": ["재배정"],
        "priority": 1,
    },
    {
        "category": "대실/입퇴실 시간 관리",
        "slug": "dayuse-checkin-time",
        "description": "대실(Day-Use) 운영, 얼리체크인/레이트체크아웃, 입퇴실 시간 유연 설정",
        "primary": [
            "대실",
            "day-use",
            "day use",
            "dayuse",
            "시간제",
            "얼리 체크인",
            "레이트 체크아웃",
            "레이트 체크인",
            "early check-in",
            "late check-out",
            "late check-in",
            "입퇴실 시간",
            "입/퇴실 시간",
            "체크인/체크아웃 시간",
            "체크인/아웃",
            "hourly stay",
        ],
        "secondary": [
            "체크인 시간",
            "체크아웃 시간",
            "입실 시간",
            "퇴실 시간",
            "시간 설정",
            "시간 조정",
            "늦은 입실",
            "늦은 체크인",
        ],
        "priority": 2,
    },
    {
        "category": "PMS/키오스크/하드웨어 연동",
        "slug": "pms-kiosk-hardware",
        "description": "PMS 연동, 키오스크 체크인, 도어락, 무인 운영 시스템",
        "primary": [
            "PMS",
            "키오스크",
            "kiosk",
            "도어락",
            "door lock",
            "무인 운영",
            "무인 체크인",
            "무인 키오스크",
            "카드키",
            "셀프 체크인",
            "self-service",
            "self-check",
            "K-MES",
            "벤디트 PMS",
            "VPMS",
            "벤디트 클라우드",
            "벤디트 미니",
        ],
        "secondary": [
            "객실 배정 시 문자",
            "자동 객실 배정",
            "객실 배정",
            "키 발급",
            "키패드",
        ],
        "priority": 3,
    },
    {
        "category": "프로모션/특가 운영",
        "slug": "promotions-special-offers",
        "description": "프로모션, 특가 상품, 쿠폰, 할인 이벤트, 도보특가 등 판매 촉진",
        "primary": [
            "프로모션",
            "특가",
            "핫딜",
            "쿠폰",
            "promotion",
            "도보특가",
            "도보 특가",
            "금일특가",
            "금일 특가",
            "오픈 특가",
            "오픈특가",
            "쇼킹 특가",
            "당일 할인",
            "할인 이벤트",
            "special offer",
        ],
        "secondary": [
            "당일 빈방",
            "판매 촉진",
            "광고",
            "마케팅",
            "인센티브",
            "할인 적용",
        ],
        "priority": 4,
    },
    {
        "category": "정산/매출 리포트",
        "slug": "settlement-reports",
        "description": "매출 데이터, 정산 내역, 세금 자료, 통계 및 리포트 관리",
        "primary": [
            "정산",
            "매출",
            "리포트",
            "통계",
            "회계",
            "세금",
            "데이터 추출",
            "데이터 취합",
            "엑셀 관리",
            "report",
            "revenue",
            "settlement",
            "성과 모니터링",
            "판매 완료 객실 수",
            "매출 성과",
        ],
        "secondary": [
            "과거 데이터",
            "일일 기록",
            "재무 데이터",
        ],
        "priority": 5,
    },
    {
        "category": "고객 커뮤니케이션",
        "slug": "customer-communication",
        "description": "고객 문자/SMS 발송, 자동 메시지, 예약 알림, 고객 관리",
        "primary": [
            "문자 발송",
            "SMS",
            "자동 문자",
            "메시지 발송",
            "고객 메시지",
            "알림 발송",
            "자동 메시지",
            "커뮤니케이션",
            "communication",
            "notification",
            "고객 응대",
            "고객 관리",
            "고객 로열티",
            "도도 포인트",
            "고객 커뮤니케이션",
        ],
        "secondary": [
            "문자",
            "알림",
            "메시지",
            "메시징",
        ],
        "priority": 6,
    },
    {
        "category": "다지점/사용자 관리",
        "slug": "multi-property-accounts",
        "description": "다지점 통합 관리, 사용자/직원 계정, 권한 관리, 마스터 계정",
        "primary": [
            "다지점",
            "다중 숙소",
            "다중 계정",
            "다중 사용자",
            "마스터 계정",
            "직원 관리",
            "사용자 계정",
            "권한 관리",
            "직원별 권한",
            "관리자 초대",
            "multi-property",
            "다수 업장",
            "계정 관리",
            "직원 교육",
            "직원 인센티브",
        ],
        "secondary": [
            "공동 관리자",
            "직원",
            "사용자",
            "계정",
            "직원 대상",
            "직원별",
            "직원용",
        ],
        "priority": 7,
    },
    {
        "category": "온보딩/시스템 설정",
        "slug": "onboarding-setup",
        "description": "초기 설정, 원격 지원, 시스템 도입, 모바일 접속, 계정 설정",
        "primary": [
            "초기 설정",
            "초기설정",
            "온보딩",
            "원격 지원",
            "원격 접속",
            "원격 설정",
            "AnyDesk",
            "원격지",
            "시스템 도입",
            "시스템 설정",
            "시스템 관리",
            "시스템 모니터링",
            "모바일 접속",
            "모바일 웹",
            "모바일 환경",
            "VCMS 계정",
            "로그인",
            "2단계 인증",
            "비밀번호",
            "베타 테스트",
            "유료 전환",
            "대행사에서 직접",
            "장기적인 시스템",
        ],
        "secondary": [
            "원격",
            "설정",
            "setup",
            "onboarding",
            "시스템 사용",
            "시스템 활용",
            "상시 운영",
            "착신전환",
            "대표번호",
        ],
        "priority": 8,
    },
    {
        "category": "수기/직접 예약 관리",
        "slug": "manual-direct-booking",
        "description": "수기 예약, 전화 예약, 워크인, 직접 예약 엔진, 자체 홈페이지 예약",
        "primary": [
            "수기 예약",
            "전화 예약",
            "워크인",
            "walk-in",
            "수동 예약",
            "manual booking",
            "직접 예약",
            "부킹 엔진",
            "booking engine",
            "자체 홈페이지",
            "자체 예약",
            "direct booking",
            "수기 관리",
            "네이버 플레이스",
            "꿀스테이",
            "인스타그램 및 전화",
        ],
        "secondary": [
            "수기",
            "수동 입력",
            "직접 채널",
        ],
        "priority": 9,
    },
    {
        "category": "객실 타입/상품 설정",
        "slug": "room-product-config",
        "description": "객실 타입 구성, 상품 매핑, 패키지 생성, 룸타입별 설정",
        "primary": [
            "객실 타입",
            "룸타입",
            "room type",
            "객실 유형",
            "상품 관리",
            "상품 구성",
            "상품 생성",
            "상품 매핑",
            "패키지",
            "package",
            "조식 패키지",
            "글램핑",
            "객실명",
            "객실 설정",
            "객실 구성",
            "어메니티",
            "간편 식품",
            "석식 및 와인",
            "반려견 동반",
            "흡연",
            "smoking",
        ],
        "secondary": [
            "상품",
            "타입 변경",
            "타입 관리",
            "유형 관리",
            "매핑",
            "product",
        ],
        "priority": 10,
    },
    {
        "category": "요금/가격 관리",
        "slug": "pricing-management",
        "description": "동적 가격, 시즌별/요일별 요금, 채널별 차등 가격, 일괄 변경, 인원별 요금",
        "primary": [
            "요금 관리",
            "가격 관리",
            "가격 설정",
            "가격 조정",
            "요금 설정",
            "요금 조정",
            "요금 변경",
            "가격 변경",
            "dynamic pricing",
            "다이내믹",
            "동적 가격",
            "시즌별 요금",
            "성수기 요금",
            "공휴일 요금",
            "요일별 요금",
            "기간별 요금",
            "인원별 요금",
            "가격 차등",
            "요금 차등",
            "차등 가격",
            "할인율",
            "수수료율",
            "가격 최적화",
            "일괄 가격",
            "일괄 요금",
            "요금 일괄",
            "가격 일괄",
            "최소 요금",
            "추가 인원 요금",
            "pricing",
            "rate adjustment",
            "price",
        ],
        "secondary": [
            "요금",
            "가격",
            "pricing",
            "rate",
            "할인",
            "할증",
            "수수료",
        ],
        "priority": 11,
    },
    {
        "category": "재고/객실 가용성 관리",
        "slug": "inventory-management",
        "description": "객실 재고 수량 관리, 방막기, 자동 보충, 블로킹, 판매 중지/오픈",
        "primary": [
            "재고 관리",
            "재고 연동",
            "재고 동기화",
            "재고 조정",
            "재고 보충",
            "자동 재고",
            "재고 노출",
            "재고 제한",
            "재고 표시",
            "재고 오픈",
            "재고 마감",
            "방막기",
            "방 막기",
            "판매 중지",
            "판매 마감",
            "객실 마감",
            "객실 오픈",
            "객실 블로킹",
            "블로킹",
            "blocking",
            "inventory management",
            "inventory control",
            "가용성",
            "availability",
            "auto-replenishment",
            "자동 마감",
            "만실",
            "잔여 수량",
            "재고 현황",
        ],
        "secondary": [
            "재고",
            "inventory",
            "stock",
            "마감",
        ],
        "priority": 12,
    },
    {
        "category": "예약 관리",
        "slug": "reservation-management",
        "description": "예약 조회/확인, 예약 변경/취소, 예약 동기화, 예약 현황 모니터링",
        "primary": [
            "예약 관리",
            "예약 연동",
            "예약 확인",
            "예약 현황",
            "예약 동기화",
            "예약 변경",
            "예약 취소",
            "예약 내역",
            "예약 데이터",
            "예약 목록",
            "예약 통합",
            "예약 수신",
            "예약 표시",
            "reservation",
            "booking management",
            "booking sync",
            "예약 검색",
        ],
        "secondary": [
            "예약",
            "booking",
            "reservation",
        ],
        "priority": 13,
    },
    {
        "category": "채널 통합 관리",
        "slug": "channel-management",
        "description": "OTA 채널 연동, 다중 채널 통합, 채널 매니저 설정, 채널별 전략",
        "primary": [
            "채널 관리",
            "채널 연동",
            "채널 통합",
            "채널 매니저",
            "채널 동기화",
            "채널 확장",
            "OTA 관리",
            "OTA 연동",
            "OTA 통합",
            "다중 OTA",
            "다중 채널",
            "다채널",
            "다수 OTA",
            "channel management",
            "multi-channel",
            "multi-OTA",
            "centralized",
            "중앙 집중",
            "중앙 관리",
            "중앙화",
            "채널별 관리",
            "통합 관리",
        ],
        "secondary": [
            "채널",
            "channel",
            "OTA",
        ],
        "priority": 14,
    },
    {
        "category": "특정 채널 운영",
        "slug": "specific-channel-ops",
        "description": "야놀자, 아고다, 에어비앤비, 네이버, 트립닷컴 등 개별 채널별 설정 및 운영",
        "primary": [
            "야놀자",
            "아고다",
            "에어비앤비",
            "Airbnb",
            "네이버",
            "Naver",
            "트립닷컴",
            "Trip.com",
            "부킹닷컴",
            "Booking.com",
            "익스피디아",
            "Expedia",
            "여기어때",
            "떠나요",
            "Agoda",
            "Onda",
            "TL Linkan",
            "TravelLine",
            "리피터",
            "고니랩",
        ],
        "secondary": [],
        "priority": 15,
    },
    {
        "category": "운영 자동화/효율화",
        "slug": "operations-automation",
        "description": "객실 청소 관리, 업무 자동화, 운영 효율화, 근무 시간 관리",
        "primary": [
            "자동화",
            "자동 배정",
            "자동 객실",
            "청소 관리",
            "청소 직원",
            "청소 요청",
            "청소 지시",
            "객실 상태",
            "객실 점검",
            "객실 관리 시스템",
            "업무 효율",
            "시간 단축",
            "근무 시간",
            "야간 관리",
            "일일 모니터링",
            "단축키",
            "automation",
        ],
        "secondary": [
            "효율",
            "자동",
            "운영",
        ],
        "priority": 16,
    },
]


# ── Helpers ─────────────────────────────────────────────────────


def parse_venue_from_source(source_file: str) -> str:
    """Strip '통화 녹음 ' prefix and '_YYMMDD_HHMMSS.m4a' suffix."""
    name = source_file
    name = re.sub(r"^통화 녹음 ", "", name)
    name = re.sub(r"_\d{6}_\d{6}\.m4a$", "", name)
    return name.strip()


def load_all_use_cases(data_dir: Path) -> list[dict]:
    """Read all JSON files and extract use_cases with source metadata."""
    use_cases = []
    json_files = sorted(data_dir.glob("*.json"))
    skipped = 0

    for fpath in json_files:
        if fpath.name in SKIP_FILES:
            continue
        try:
            with open(fpath) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  WARN: Skipping {fpath.name}: {e}")
            skipped += 1
            continue

        ucs = data.get("use_cases", [])
        if not ucs:
            continue

        source_file = data.get("_extraction_metadata", {}).get(
            "source_file", fpath.name
        )
        venue = parse_venue_from_source(source_file)

        for uc in ucs:
            title = uc.get("title", "").strip()
            if not title:
                continue
            use_cases.append(
                {
                    "title": title,
                    "description": uc.get("description", ""),
                    "hotel_context": uc.get("hotel_context", ""),
                    "benefit": uc.get("benefit", ""),
                    "source_file": source_file,
                    "venue": venue,
                }
            )

    if skipped:
        print(f"  WARN: {skipped} files skipped due to errors")
    return use_cases


def deduplicate_use_cases(use_cases: list[dict]) -> list[dict]:
    """Deduplicate by normalized title. Keep first occurrence (richer context)."""
    seen: dict[str, int] = {}
    result = []

    for uc in use_cases:
        # Normalize: lowercase, strip whitespace/punctuation, collapse spaces
        norm = re.sub(r"[\s\-_/()（）]", "", uc["title"].lower()).strip()
        # Also normalize common English/Korean variants
        norm = norm.replace("&", "and")

        if norm not in seen:
            seen[norm] = len(result)
            result.append(uc)

    return result


def categorize_use_case(title: str, description: str = "") -> tuple[str, str]:
    """Assign a single use_case to a category using keyword matching.

    Returns (category_name, slug).
    Strategy: Score based on keyword matches with title weighted 3x over description.
    Primary keywords → strong match, Secondary → weak match.
    Highest score wins; ties broken by priority (lower = higher priority).
    """
    title_lower = title.lower()
    desc_lower = description.lower()

    best_cat: str = "운영 자동화/효율화"
    best_slug: str = "operations-automation"
    best_score = 0
    best_priority = 999

    for cat_def in CATEGORIES:
        score = 0

        for kw in cat_def["primary"]:
            kw_l = kw.lower()
            if kw_l in title_lower:
                score += 5  # Strong signal from title
            elif kw_l in desc_lower:
                score += 1  # Weak signal from description

        for kw in cat_def["secondary"]:
            kw_l = kw.lower()
            if kw_l in title_lower:
                score += 2  # Moderate from title
            # Ignore secondary in description (too noisy)

        if score > best_score or (
            score == best_score and cat_def["priority"] < best_priority
        ):
            best_score = score
            best_cat = cat_def["category"]
            best_slug = cat_def["slug"]
            best_priority = cat_def["priority"]

    # Fallback: if no match at all, try broader heuristics on TITLE only
    if best_score == 0:
        if any(k in title_lower for k in ["vcms", "v클라우드", "vcloud"]):
            return "채널 통합 관리", "channel-management"
        if any(k in title_lower for k in ["요금", "가격", "pricing", "rate"]):
            return "요금/가격 관리", "pricing-management"
        if any(k in title_lower for k in ["재고", "inventory"]):
            return "재고/객실 가용성 관리", "inventory-management"
        if any(k in title_lower for k in ["예약", "booking", "reservation"]):
            return "예약 관리", "reservation-management"
        if any(k in title_lower for k in ["채널", "channel", "ota"]):
            return "채널 통합 관리", "channel-management"
        if any(k in title_lower for k in ["객실", "room"]):
            return "객실 타입/상품 설정", "room-product-config"
        # True fallback
        return "운영 자동화/효율화", "operations-automation"

    return best_cat, best_slug


def resolve_channel_overlap(title: str, assigned_cat: str) -> str:
    """For titles assigned to '특정 채널 운영', check if they belong better elsewhere.

    E.g., '야놀자 요금 관리' → '요금/가격 관리' (specific channel is context, not core topic)
    But '야놀자 채널 관리' → '특정 채널 운영' (channel IS the topic)
    """
    if assigned_cat != "특정 채널 운영":
        return assigned_cat

    text = title.lower()

    # If the title is primarily about pricing
    pricing_kw = ["요금", "가격", "pricing", "rate", "할인", "수수료"]
    if any(k in text for k in pricing_kw) and not any(
        k in text for k in ["채널 관리", "채널 연동", "채널 매니저"]
    ):
        return "요금/가격 관리"

    # If primarily about inventory
    inv_kw = ["재고", "inventory", "방막기", "판매 중지", "마감"]
    if any(k in text for k in inv_kw) and not any(
        k in text for k in ["채널 관리", "채널 연동"]
    ):
        return "재고/객실 가용성 관리"

    # If primarily about reservations
    res_kw = ["예약 관리", "예약 연동", "예약 확인", "예약 현황"]
    if any(k in text for k in res_kw):
        return "예약 관리"

    # If primarily about room types/products
    room_kw = ["객실 타입", "룸타입", "상품 매핑", "room type"]
    if any(k in text for k in room_kw):
        return "객실 타입/상품 설정"

    return assigned_cat


# ── Main Pipeline ──────────────────────────────────────────────


def main():
    print(f"\n{'=' * 60}")
    print("  Use Case Extraction & Categorization (No LLM API)")
    print(f"{'=' * 60}")

    # ── Phase A: Extract ───────────────────────────────────────
    print(f"\n[Phase A] Extracting use_cases from {DATA_DIR.name}/...")
    all_use_cases = load_all_use_cases(DATA_DIR)
    print(f"  Total extracted: {len(all_use_cases)}")

    if not all_use_cases:
        print("ERROR: No use_cases found!")
        return 1

    # Deduplicate
    unique_use_cases = deduplicate_use_cases(all_use_cases)
    dup_count = len(all_use_cases) - len(unique_use_cases)
    print(f"  After dedup: {len(unique_use_cases)} (removed {dup_count} duplicates)")

    # Save intermediate
    with open(INTERMEDIATE_FILE, "w") as f:
        json.dump(
            {
                "metadata": {
                    "total_raw": len(all_use_cases),
                    "total_unique": len(unique_use_cases),
                    "duplicates_removed": dup_count,
                    "extracted_at": datetime.now().isoformat(),
                },
                "use_cases": unique_use_cases,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"  Saved intermediate: {INTERMEDIATE_FILE.name}")

    # ── Phase B: Categorize ────────────────────────────────────
    print(f"\n[Phase B] Categorizing {len(unique_use_cases)} use_cases...")

    # Assign categories
    categorized = []
    for uc in unique_use_cases:
        cat_name, cat_slug = categorize_use_case(uc["title"], uc.get("description", ""))
        # Apply channel overlap resolution
        cat_name = resolve_channel_overlap(uc["title"], cat_name)
        # Look up slug after resolution
        slug_map = {c["category"]: c["slug"] for c in CATEGORIES}
        cat_slug = slug_map.get(cat_name, cat_slug)

        categorized.append({**uc, "_category": cat_name, "_slug": cat_slug})

    # Group by category
    cat_groups: dict[str, list[dict]] = {}
    for uc in categorized:
        cat_name = uc["_category"]
        cat_groups.setdefault(cat_name, []).append(uc)

    # Build output
    cat_meta = {c["category"]: c for c in CATEGORIES}
    output = []
    for cat_name in sorted(cat_groups.keys()):
        ucs = cat_groups[cat_name]
        meta = cat_meta.get(cat_name, {})
        output.append(
            {
                "category": cat_name,
                "slug": meta.get("slug", cat_name.lower().replace("/", "-")),
                "description": meta.get("description", ""),
                "count": len(ucs),
                "use_cases": [
                    {
                        "title": u["title"],
                        "description": u["description"],
                        "hotel_context": u["hotel_context"],
                        "benefit": u["benefit"],
                        "source_file": u["source_file"],
                    }
                    for u in ucs
                ],
            }
        )

    # Remove empty categories (shouldn't happen but safety check)
    output = [g for g in output if g["count"] > 0]

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {OUTPUT_FILE.name}")

    # ── Phase C: Verify ────────────────────────────────────────
    print(f"\n[Phase C] Verification")
    print(f"{'─' * 50}")

    total_in_cats = sum(g["count"] for g in output)
    num_cats = len(output)
    empty_cats = [g["category"] for g in output if g["count"] == 0]

    ok_cats = 5 <= num_cats <= 20
    ok_count = total_in_cats >= 1400
    ok_empty = len(empty_cats) == 0
    ok_all_assigned = total_in_cats == len(unique_use_cases)

    print(f"  Categories:      {num_cats} (5-20)  {'OK' if ok_cats else 'FAIL'}")
    print(
        f"  Total in cats:   {total_in_cats} (>= 1400)  {'OK' if ok_count else 'FAIL'}"
    )
    print(
        f"  All assigned:    {total_in_cats}/{len(unique_use_cases)}  {'OK' if ok_all_assigned else 'FAIL'}"
    )
    print(f"  Empty cats:      {len(empty_cats)}  {'OK' if ok_empty else 'FAIL'}")

    print(f"\n  Category breakdown:")
    for g in sorted(output, key=lambda x: -x["count"]):
        pct = g["count"] / total_in_cats * 100
        print(f"    {g['category']:30s}  {g['count']:4d}  ({pct:5.1f}%)")

    all_passed = ok_cats and ok_count and ok_empty and ok_all_assigned
    print(f"\n  {'ALL CHECKS PASSED' if all_passed else 'SOME CHECKS FAILED'}")
    print(f"{'=' * 60}\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
