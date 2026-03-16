from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

REGIONS = [
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
    "경기",
    "강원",
    "충북",
    "충남",
    "경북",
    "경남",
    "전북",
    "전남",
    "제주",
]

CITY_TO_REGION: dict[str, str] = {
    "속초": "강원",
    "춘천": "강원",
    "원주": "강원",
    "강릉": "강원",
    "동해": "강원",
    "양양": "강원",
    "평창": "강원",
    "정선": "강원",
    "영월": "강원",
    "횡성": "강원",
    "수원": "경기",
    "성남": "경기",
    "고양": "경기",
    "용인": "경기",
    "안산": "경기",
    "의정부": "경기",
    "파주": "경기",
    "김포": "경기",
    "광명": "경기",
    "하남": "경기",
    "안양": "경기",
    "부천": "경기",
    "동두천": "경기",
    "구리": "경기",
    "남양주": "경기",
    "이천": "경기",
    "여주": "경기",
    "평택": "경기",
    "시흥": "경기",
    "고척": "경기",
    "월곶": "경기",
    "다산": "경기",
    "천안": "충남",
    "아산": "충남",
    "보령": "충남",
    "서산": "충남",
    "논산": "충남",
    "태안": "충남",
    "청주": "충북",
    "충주": "충북",
    "제천": "충북",
    "단양": "충북",
    "경주": "경북",
    "안동": "경북",
    "포항": "경북",
    "구미": "경북",
    "영주": "경북",
    "사천": "경남",
    "진주": "경남",
    "통영": "경남",
    "거제": "경남",
    "함양": "경남",
    "창원": "경남",
    "김해": "경남",
    "전주": "전북",
    "군산": "전북",
    "익산": "전북",
    "남원": "전북",
    "목포": "전남",
    "여수": "전남",
    "순천": "전남",
    "광양": "전남",
    "구례": "전남",
    "영광": "전남",
    "서귀포": "제주",
    "제주시": "제주",
    "중구": "서울",
    "종로": "서울",
    "광진구": "서울",
    "구로구": "서울",
    "강남": "서울",
    "수영구": "부산",
    "동구": "부산",
    "해운대": "부산",
    "구월동": "인천",
    "서구": "인천",
    "연수구": "인천",
    "광산구": "광주",
}

VENUE_TYPE_KEYWORDS = [
    "리조트",
    "리조텔",
    "게스트하우스",
    "펜션",
    "풀빌라",
    "스테이",
    "모텔",
    "호텔",
]

PHONE_PATTERN = re.compile(r"0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}")

PHONE_ONLY_FILENAME = re.compile(r"^0\d{9,10}$")

KOREAN_SURNAMES = (
    "김이박최정강조윤장임한오서신권황안송전홍류유고문양손배백허노남심하주"
    "우곽성차방공강현변함태탁염여추도석선설마길"
)

KOREAN_NAME_PATTERN = re.compile(
    r"(?<![가-힣])([" + KOREAN_SURNAMES + r"][가-힣]{1,2})(?![가-힣])"
)

MONETARY_PATTERN = re.compile(r"\d[\d,]*\s*(?:만\s*)?원")

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

ROLE_SUFFIXES = re.compile(
    r"(?:대표님?|매니저님?|사장님?|부장님?|과장님?|주임님?|지배인|직원|대리인?|담당자|프론트|따님|가족)"
)

KOREAN_PARTICLES = set(
    "가이을를은는에의와과도만나로며고서라야"
    "해할한히적성화된될합져"
    "게데요기일증면씩지락명트"
    "때쯤부터까죠자"
)

COMMON_KOREAN_WORDS = {
    "정상",
    "정보",
    "정리",
    "정도",
    "정확",
    "정기",
    "정말",
    "정산",
    "정합",
    "정책",
    "정가",
    "정기",
    "오류",
    "오전",
    "오후",
    "오늘",
    "오는",
    "오래",
    "오픈",
    "강화",
    "강조",
    "강력",
    "전화",
    "전체",
    "전혀",
    "전용",
    "전달",
    "전략",
    "전환",
    "전에",
    "전문",
    "조건",
    "조치",
    "조금",
    "조정",
    "조절",
    "조식",
    "조회",
    "최대",
    "최소",
    "최근",
    "최초",
    "최적",
    "최종",
    "임시",
    "임대",
    "장치",
    "장소",
    "장기",
    "장애",
    "배송",
    "배정",
    "배치",
    "서비스",
    "신규",
    "신청",
    "신뢰",
    "신분",
    "황당",
    "안내",
    "안전",
    "안녕",
    "안정",
    "송금",
    "홍보",
    "유지",
    "유료",
    "유사",
    "유연",
    "유도",
    "유형",
    "유입",
    "유출",
    "고객",
    "고정",
    "고장",
    "고려",
    "고유",
    "문의",
    "문제",
    "문서",
    "문자",
    "문구",
    "양해",
    "양식",
    "손님",
    "손실",
    "손해",
    "심각",
    "하나",
    "하고",
    "하는",
    "하면",
    "하지",
    "하단",
    "하루",
    "노력",
    "노출",
    "노쇼",
    "허용",
    "성공",
    "성능",
    "성수",
    "성인",
    "차이",
    "차량",
    "차감",
    "차등",
    "차단",
    "방법",
    "방문",
    "방지",
    "방식",
    "공유",
    "공지",
    "공실",
    "공사",
    "공휴",
    "현재",
    "현금",
    "현장",
    "현황",
    "현실",
    "변경",
    "변동",
    "변수",
    "함께",
    "도움",
    "도입",
    "도보",
    "선택",
    "선불",
    "설정",
    "설명",
    "설치",
    "설날",
    "마감",
    "마련",
    "발생",
    "발견",
    "발급",
    "발송",
    "작동",
    "작성",
    "시스템",
    "서버",
    "이런",
    "이전",
    "이상",
    "이중",
    "이동",
    "이름",
    "이미",
    "이용",
    "이벤",
    "이후",
    "이력",
    "이탈",
    "여러",
    "여름",
    "여유",
    "여부",
    "권한",
    "주차",
    "주소",
    "주간",
    "주말",
    "주의",
    "주기",
    "추가",
    "추석",
    "추적",
    "우리",
    "우선",
    "이렇",
    "이에",
    "이나",
    "이라",
    "이벤",
    "성수",
    "공휴",
    "도어",
    "신분",
    "고객",
    "한눈",
    "한다",
    "하나",
    "하게",
    "선택",
    "유연",
    "정합",
    "정확",
    "최적",
    "손익",
    "주요",
    "주세",
    "주지",
    "마련",
    "이어",
    "고려",
    "여는",
    "방을",
    "방이",
    "하여",
    "하고",
    "하죠",
    "이벤",
    "정해",
}

NON_NAME_WORDS = {
    "담당자",
    "매니저",
    "대표자",
    "대표님",
    "사장님",
    "부장님",
    "과장님",
    "주임님",
    "프론트",
    "지배인",
    "업무폰",
    "미확인",
    "고객님",
    "대표번호",
}


class VenueRegistry:
    def __init__(self) -> None:
        self._venue_to_anon: dict[str, str] = {}
        self._region_initial_count: dict[str, dict[str, int]] = {}

    def reset(self) -> None:
        self._venue_to_anon.clear()
        self._region_initial_count.clear()

    def get_or_assign(self, venue_name: str, region: str, venue_type: str) -> str:
        if venue_name in self._venue_to_anon:
            return self._venue_to_anon[venue_name]

        initial = _extract_initial(venue_name)

        if region not in self._region_initial_count:
            self._region_initial_count[region] = {}

        counts = self._region_initial_count[region]
        if initial not in counts:
            counts[initial] = 0

        counts[initial] += 1
        count = counts[initial]

        if count == 1:
            anon = f"{region} {initial}{venue_type}"
        else:
            anon = f"{region} {initial}{venue_type}({count})"

            if count == 2:
                first_venue = None
                for v, a in self._venue_to_anon.items():
                    if a == f"{region} {initial}{venue_type}":
                        first_venue = v
                        break
                if first_venue:
                    self._venue_to_anon[first_venue] = (
                        f"{region} {initial}{venue_type}(1)"
                    )

        self._venue_to_anon[venue_name] = anon
        return anon

    def lookup(self, venue_name: str) -> Optional[str]:
        return self._venue_to_anon.get(venue_name)


_default_registry = VenueRegistry()


def get_default_registry() -> VenueRegistry:
    return _default_registry


def _extract_initial(venue_name: str) -> str:
    for ch in venue_name:
        if ch.isascii() and ch.isalpha():
            return ch.upper()
    for ch in venue_name:
        if "가" <= ch <= "힣":
            return ch
    return "X"


def _detect_venue_type(text: str) -> str:
    for vt in VENUE_TYPE_KEYWORDS:
        if vt in text:
            return vt
    return "호텔"


def _extract_region(text: str) -> Optional[str]:
    for region in REGIONS:
        if region in text:
            return region

    for city, region in CITY_TO_REGION.items():
        if city in text:
            return region

    return None


def _strip_filename(source_file_path: str) -> str:
    name = os.path.basename(source_file_path)

    name = re.sub(r"\.\w+$", "", name)

    name = re.sub(r"_\d{6}_\d{6}$", "", name)

    prefixes = ["통화 녹음 ", "통화_녹음_"]
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break

    name = name.lstrip("#")

    return name.strip()


def _clean_and_extract_tokens(text: str) -> list[str]:
    cleaned = re.sub(r"\d+객실\s*", "", text)
    cleaned = re.sub(r"\(.*?\)", "", cleaned)
    cleaned = PHONE_PATTERN.sub("", cleaned)

    for region in REGIONS:
        cleaned = cleaned.replace(region, " ")
    for city in CITY_TO_REGION:
        cleaned = cleaned.replace(city, " ")

    cleaned = re.sub(r"[시군구](?=\s|$)", "", cleaned)
    cleaned = ROLE_SUFFIXES.sub("", cleaned)
    for w in NON_NAME_WORDS:
        cleaned = cleaned.replace(w, " ")

    def _strip_names(t: str) -> str:
        return KOREAN_NAME_PATTERN.sub(
            lambda m: "" if _is_likely_name(m.group(1)) else m.group(0), t
        )

    cleaned = _strip_names(cleaned)

    tokens = [t.strip("_ ") for t in re.split(r"[\s_]+", cleaned) if t.strip("_ ")]
    return [t for t in tokens if len(t) >= 2 and not t.isdigit()]


def _extract_venue_name(stripped: str) -> Optional[str]:
    if PHONE_ONLY_FILENAME.match(stripped.replace(" ", "").replace("_", "")):
        return None

    bracket_match = re.search(r"\[\s*(.*?)\s*\]", stripped)
    if bracket_match:
        bracket_content = bracket_match.group(1)
        bracket_tokens = _clean_and_extract_tokens(bracket_content)
        if bracket_tokens:
            return bracket_tokens[0]

    no_brackets = re.sub(r"\[.*?\]", "", stripped)
    tokens = _clean_and_extract_tokens(no_brackets)

    if tokens:
        return tokens[0]
    return None


def anonymize_venue(
    source_file_path: str,
    registry: Optional[VenueRegistry] = None,
) -> str:
    if registry is None:
        registry = _default_registry

    stripped = _strip_filename(source_file_path)

    compact = stripped.replace("_", " ")
    if PHONE_ONLY_FILENAME.match(compact.replace(" ", "")):
        return "미확인 업장"

    region = _extract_region(stripped)
    if region is None:
        region = "미확인"

    venue_type = _detect_venue_type(stripped)
    venue_name = _extract_venue_name(stripped)

    if venue_name is None:
        return "미확인 업장"

    return registry.get_or_assign(venue_name, region, venue_type)


def anonymize_text(
    text: str,
    blacklist: Optional[list[str]] = None,
    registry: Optional[VenueRegistry] = None,
) -> str:
    if registry is None:
        registry = _default_registry

    result = text

    if blacklist:
        sorted_bl = sorted(blacklist, key=len, reverse=True)
        for venue in sorted_bl:
            anon = registry.lookup(venue)
            replacement = anon if anon else "[업장명]"
            result = result.replace(venue, replacement)

    result = PHONE_PATTERN.sub("", result)

    result = MONETARY_PATTERN.sub("", result)

    result = _replace_names(result)

    result = re.sub(r"\s{2,}", " ", result).strip()

    return result


def _is_likely_name(candidate: str) -> bool:
    if candidate in NON_NAME_WORDS or candidate in COMMON_KOREAN_WORDS:
        return False

    if len(candidate) == 3 and candidate[:2] in COMMON_KOREAN_WORDS:
        if candidate[2] in KOREAN_PARTICLES:
            return False

    return True


def _replace_names(text: str) -> str:
    def _sub_name(m: re.Match) -> str:
        name = m.group(1)
        if not _is_likely_name(name):
            return name
        return "담당자"

    return KOREAN_NAME_PATTERN.sub(_sub_name, text)


def pii_scan(
    text: str,
    blacklist: Optional[list[str]] = None,
) -> list[str]:
    violations: list[str] = []

    if blacklist:
        for venue in blacklist:
            if venue in text:
                violations.append(f"venue_name: '{venue}'")

    phones = PHONE_PATTERN.findall(text)
    for phone in phones:
        violations.append(f"phone: '{phone}'")

    emails = EMAIL_PATTERN.findall(text)
    for email in emails:
        violations.append(f"email: '{email}'")

    for m in KOREAN_NAME_PATTERN.finditer(text):
        name = m.group(1)
        if _is_likely_name(name):
            violations.append(f"personal_name: '{name}'")

    return violations


def build_blacklist(data_dir: str) -> list[str]:
    venue_names: set[str] = set()
    bulk_dir = Path(data_dir)

    if not bulk_dir.exists():
        return []

    for json_file in bulk_dir.glob("**/*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        meta = data.get("_extraction_metadata", {})
        source_file = meta.get("source_file", "")
        if not source_file:
            continue

        stripped = _strip_filename(source_file)
        venue = _extract_venue_name(stripped)
        if venue:
            venue_names.add(venue)

    return sorted(venue_names)
