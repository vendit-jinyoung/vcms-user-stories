from __future__ import annotations

import json
import os
import tempfile

import pytest

from scripts.anonymize import (
    VenueRegistry,
    anonymize_text,
    anonymize_venue,
    build_blacklist,
    pii_scan,
)


@pytest.fixture(autouse=True)
def fresh_registry():
    from scripts.anonymize import _default_registry

    _default_registry.reset()
    yield _default_registry
    _default_registry.reset()


class TestAnonymizeVenue:
    def test_busan_elbon(self):
        result = anonymize_venue(
            "통화 녹음 #부산 엘본쓰 35객실 담당자_250819_181100.m4a"
        )
        assert "부산" in result
        assert "엘" in result or "E" in result.upper()
        assert "엘본쓰" not in result

    def test_gangwon_chuncheon_hotel77(self):
        result = anonymize_venue(
            "통화 녹음 20객실 강원 춘천시 호텔77 설희석_250702_161445.m4a"
        )
        assert "강원" in result
        assert "호텔" in result
        assert "호텔77" not in result
        assert "설희석" not in result

    def test_busan_moonbay(self):
        result = anonymize_venue(
            "통화 녹음 45객실 부산 수영구 문베이호텔 황지명_250702_184013.m4a"
        )
        assert "부산" in result
        assert "호텔" in result
        assert "문베이" not in result
        assert "황지명" not in result

    def test_phone_only_filename(self):
        result = anonymize_venue("통화 녹음 01022660140_250828_183551.m4a")
        assert result == "미확인 업장"

    def test_phone_only_with_underscore(self):
        result = anonymize_venue("통화 녹음 01085752980_250827_181310.m4a")
        assert result == "미확인 업장"

    def test_conflict_resolution_same_initial(self):
        registry = VenueRegistry()

        r1 = anonymize_venue(
            "통화 녹음 45객실 강원 속초시 호텔아마란스 어윤진_250814_165710.m4a",
            registry=registry,
        )
        assert "강원" in r1
        assert "호텔" in r1

        r2 = anonymize_venue(
            "통화 녹음 45객실 강원 속초시 호텔ABC 김철수_250814_165710.m4a",
            registry=registry,
        )
        assert "강원" in r2
        assert "호텔" in r2

        assert r1 != r2

    def test_consistent_across_calls(self):
        registry = VenueRegistry()
        r1 = anonymize_venue(
            "통화 녹음 #부산 엘본쓰 35객실 담당자_250819_181100.m4a",
            registry=registry,
        )
        r2 = anonymize_venue(
            "통화 녹음 #부산 엘본쓰 35객실 담당자대표자_260120_184052.m4a",
            registry=registry,
        )
        assert r1 == r2

    def test_region_detection_chungnam(self):
        result = anonymize_venue(
            "통화 녹음 충남 천안 파인 호텔 박상혁대표님_260224_164058.m4a"
        )
        assert "충남" in result

    def test_region_detection_from_city_name(self):
        result = anonymize_venue(
            "통화 녹음 동두천 글렌스테이 12객실 윤재형 대표님_250923_163711.m4a"
        )
        assert "경기" in result
        assert "스테이" in result

    def test_pension_type(self):
        result = anonymize_venue(
            "통화 녹음 7객실 충북 단양군 에뜨왈 펜션 에뜨왈 펜션_250723_151657.m4a"
        )
        assert "충북" in result
        assert "펜션" in result

    def test_resort_type(self):
        result = anonymize_venue(
            "통화 녹음 영광 힐링컨벤션 리조트 매니저님_251013_144926.m4a"
        )
        assert "리조트" in result

    def test_jeju_region(self):
        result = anonymize_venue(
            "통화 녹음 12객실 제주 제주시 길리리조트 한다온_260120_213836.m4a"
        )
        assert "제주" in result
        assert "리조트" in result

    def test_seoul_region_from_district(self):
        result = anonymize_venue(
            "통화 녹음 34객실 서울 중구 호텔레스 김경일_250916_202335.m4a"
        )
        assert "서울" in result
        assert "호텔" in result

    def test_ulsan_region(self):
        result = anonymize_venue(
            "통화 녹음 울산 호텔먹자닷컴 34객실 대표님_250912_182522.m4a"
        )
        assert "울산" in result


class TestAnonymizeText:
    def test_phone_removal(self):
        text = "담당자에게 010-1234-5678로 연락주세요."
        result = anonymize_text(text)
        assert "010-1234-5678" not in result
        assert "연락주세요" in result

    def test_phone_removal_landline(self):
        text = "사무실 번호는 02-123-4567입니다."
        result = anonymize_text(text)
        assert "02-123-4567" not in result

    def test_phone_removal_no_hyphen(self):
        text = "전화번호 01012345678 입니다."
        result = anonymize_text(text)
        assert "01012345678" not in result

    def test_personal_name_removal(self):
        text = "김철수 매니저가 확인했습니다."
        result = anonymize_text(text)
        assert "김철수" not in result
        assert "담당자" in result

    def test_personal_name_three_char(self):
        text = "황지명 프론트에게 문의하세요."
        result = anonymize_text(text)
        assert "황지명" not in result

    def test_monetary_removal(self):
        text = "객실 가격이 5만원에서 8만원으로 올랐습니다."
        result = anonymize_text(text)
        assert "5만원" not in result
        assert "8만원" not in result
        assert "올랐습니다" in result

    def test_monetary_with_comma(self):
        text = "결제 금액은 150,000원입니다."
        result = anonymize_text(text)
        assert "150,000원" not in result

    def test_monetary_plain(self):
        text = "50000원 결제 완료."
        result = anonymize_text(text)
        assert "50000원" not in result

    def test_venue_blacklist_replacement(self):
        registry = VenueRegistry()
        registry.get_or_assign("엘본쓰", "부산", "호텔")

        text = "엘본쓰에서 문제가 발생했습니다."
        result = anonymize_text(text, blacklist=["엘본쓰"], registry=registry)
        assert "엘본쓰" not in result
        assert "부산" in result

    def test_keeps_normal_text(self):
        text = "객실 예약 시스템이 정상 작동합니다."
        result = anonymize_text(text)
        assert result == text

    def test_combined_anonymization(self):
        text = "김철수 매니저가 010-1234-5678로 엘본쓰 예약 5만원을 확인했습니다."
        registry = VenueRegistry()
        registry.get_or_assign("엘본쓰", "부산", "호텔")

        result = anonymize_text(text, blacklist=["엘본쓰"], registry=registry)
        assert "김철수" not in result
        assert "010-1234-5678" not in result
        assert "엘본쓰" not in result
        assert "5만원" not in result
        assert "확인했습니다" in result

    def test_preserves_role_words(self):
        text = "담당자가 확인 중입니다."
        result = anonymize_text(text)
        assert "담당자" in result


class TestPiiScan:
    def test_clean_text_passes(self):
        text = "부산 E호텔에서 시스템 오류가 발생했습니다."
        violations = pii_scan(text)
        assert len(violations) == 0

    def test_detects_venue_name(self):
        text = "엘본쓰에서 문제가 생겼습니다."
        violations = pii_scan(text, blacklist=["엘본쓰"])
        assert any("엘본쓰" in v for v in violations)

    def test_detects_phone(self):
        text = "연락처: 010-1234-5678"
        violations = pii_scan(text)
        assert any("phone" in v for v in violations)

    def test_detects_phone_no_hyphen(self):
        text = "전화 01012345678 입니다."
        violations = pii_scan(text)
        assert any("phone" in v for v in violations)

    def test_detects_email(self):
        text = "메일은 test@example.com 입니다."
        violations = pii_scan(text)
        assert any("email" in v for v in violations)

    def test_detects_personal_name(self):
        text = "박상혁 대표가 확인했습니다."
        violations = pii_scan(text)
        assert any("personal_name" in v for v in violations)

    def test_multiple_violations(self):
        text = "김철수가 010-9876-5432로 엘본쓰에 test@hotel.com 메일을 보냈습니다."
        violations = pii_scan(text, blacklist=["엘본쓰"])
        assert len(violations) >= 3

    def test_no_false_positive_role_words(self):
        text = "담당자가 매니저에게 연락했습니다."
        violations = pii_scan(text)
        name_violations = [v for v in violations if "personal_name" in v]
        assert len(name_violations) == 0


class TestBuildBlacklist:
    def test_extracts_from_json_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {
                "_extraction_metadata": {
                    "source_file": "통화 녹음 45객실 부산 수영구 문베이호텔 황지명_250702_184013.m4a"
                }
            }
            filepath = os.path.join(tmpdir, "test_insights.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

            result = build_blacklist(tmpdir)
            assert len(result) > 0
            assert any("문베이" in v for v in result)

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = build_blacklist(tmpdir)
            assert result == []

    def test_nonexistent_dir(self):
        result = build_blacklist("/nonexistent/path/xyz")
        assert result == []

    def test_deduplication(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                data = {
                    "_extraction_metadata": {
                        "source_file": "통화 녹음 45객실 부산 수영구 문베이호텔 황지명_250702_184013.m4a"
                    }
                }
                filepath = os.path.join(tmpdir, f"test_{i}_insights.json")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)

            result = build_blacklist(tmpdir)
            assert len(result) == len(set(result))

    def test_skips_phone_only_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = {
                "_extraction_metadata": {
                    "source_file": "통화 녹음 01022660140_250828_183551.m4a"
                }
            }
            filepath = os.path.join(tmpdir, "phone_insights.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

            result = build_blacklist(tmpdir)
            assert "01022660140" not in result


class TestRegistryConflictDetail:
    def test_numbering_on_second_conflict(self):
        registry = VenueRegistry()
        r1 = registry.get_or_assign("호텔A첫번째", "강원", "호텔")
        r2 = registry.get_or_assign("호텔A두번째", "강원", "호텔")

        assert "(1)" in registry.lookup("호텔A첫번째")
        assert "(2)" in r2

    def test_different_regions_no_conflict(self):
        registry = VenueRegistry()
        r1 = registry.get_or_assign("호텔Alpha", "부산", "호텔")
        r2 = registry.get_or_assign("호텔Alpha클론", "서울", "호텔")

        assert "(1)" not in r1
        assert "(2)" not in r2
        assert "부산" in r1
        assert "서울" in r2


class TestEdgeCases:
    def test_hash_prefix_in_filename(self):
        result = anonymize_venue(
            "통화 녹음 #부산 엘본쓰 35객실 담당자대표자_260120_184052.m4a"
        )
        assert "부산" in result
        assert "#" not in result

    def test_bracket_notation_in_filename(self):
        result = anonymize_venue(
            "통화 녹음 호텔반월 구월동점 [호텔반월] 프론트_251014_163940.m4a"
        )
        assert result != "미확인 업장"

    def test_complex_filename_with_parentheses(self):
        result = anonymize_venue(
            "통화 녹음 정다영 대표 (고객) [ 서울 광진구  호텔 리오 (구 강변모텔) (서울정다영) ]_251030_172307.m4a"
        )
        assert "서울" in result

    def test_empty_venue_graceful(self):
        result = anonymize_venue("통화 녹음 _250828_183551.m4a")
        assert isinstance(result, str)

    def test_underscore_format_filename(self):
        result = anonymize_venue(
            "통화_녹음_45객실_부산_수영구_문베이호텔_황지명_250801_141755.m4a"
        )
        assert "부산" in result
