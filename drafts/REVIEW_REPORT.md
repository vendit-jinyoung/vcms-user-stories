# 활용 사례 콘텐츠 검토 리포트

> **생성일**: 2026-03-16
> **검토자**: Dean
> **총 초안**: 30개 (16개 카테고리)
> **추가 소스**: Slack 운영 데이터 (system-vcms-noti + public-vcms)
> **데이터 소스**: VOC 통화녹음 1,414건 → use_case 1,415개 (중복 제거 후)

---

## 카테고리별 초안 목록

각 초안에 대해 `[x]` 승인 / `[ ]` 미검토 / `[R]` 수정 요청 / `[D]` 거절 표시해주세요.

### 요금/가격 관리 (361건 기반, 3개 초안)
- [ ] [기간별/시즌별 요금 설정](pricing-management/seasonal-pricing.md) — 성수기/비수기/공휴일 요금 관리
- [ ] [채널별 수수료 반영 판매가 관리](pricing-management/channel-commission-pricing.md) — OTA 수수료 고려한 판매가 설정
- [ ] [요금 일괄 조정 및 동기화](pricing-management/bulk-rate-adjustment.md) — 여러 객실 요금 한 번에 변경

### 재고/객실 가용성 관리 (206건 기반, 2개 초안)
- [ ] [채널별 재고 연동 관리](inventory-management/channel-inventory-sync.md) — 실시간 재고 동기화
- [ ] [객실 마감/오픈 자동화](inventory-management/room-close-open-automation.md) — 만실/수리 시 자동 마감

### 채널 통합 관리 (193건 기반, 2개 초안)
- [ ] [다채널 통합 연동 설정](channel-management/multi-channel-integration.md) — OTA 채널 통합 관리
- [ ] [채널별 상품 노출 관리](channel-management/channel-product-visibility.md) — 채널별 선택적 상품 판매

### 예약 관리 (132건 기반, 2개 초안)
- [ ] [예약 변경 및 취소 처리](reservation-management/reservation-change-cancel.md) — 변경/취소/노쇼 처리
- [ ] [연박/단체 예약 관리](reservation-management/multi-night-group-booking.md) — 연박·단체 재고 관리

### 객실 타입/상품 설정 (97건 기반, 2개 초안)
- [ ] [객실 타입별 요금 전략 설정](room-product-config/room-type-pricing-strategy.md) — 차등 요금 설정
- [ ] [패키지 상품 구성 및 관리](room-product-config/package-product-management.md) — 부가 상품 구성

### PMS/키오스크/하드웨어 연동 (64건 기반, 2개 초안)
- [ ] [PMS 연동으로 객실 관리 효율화](pms-kiosk-hardware/pms-room-management.md) — PMS 연동
- [ ] [무인 체크인/체크아웃 시스템 구축](pms-kiosk-hardware/unmanned-checkin-system.md) — 키오스크 연동

### 운영 자동화/효율화 (52건 기반, 2개 초안)
- [ ] [야간 무인 운영 자동화](operations-automation/night-unmanned-operations.md) — 야간 무인 설정
- [ ] [직원 업무 자동화](operations-automation/staff-task-automation.md) — 청소/점검 자동화

### 대실/입퇴실 시간 관리 (51건 기반, 2개 초안)
- [ ] [대실 상품 운영 최적화](dayuse-checkin-time/dayuse-optimization.md) — 대실 시간/요금/재고
- [ ] [입퇴실 시간 유연 설정](dayuse-checkin-time/flexible-checkin-checkout.md) — 체크인/아웃 시간 관리

### 특정 채널 운영 (51건 기반, 1개 초안)
- [ ] [네이버/야놀자/여기어때 채널 운영 팁](specific-channel-ops/naver-yanolja-tips.md) — 국내 주요 채널별 팁

### 프로모션/특가 운영 (46건 기반, 2개 초안)
- [ ] [시즌 프로모션 운영](promotions-special-offers/seasonal-promotion-ops.md) — 시즌별 프로모션
- [ ] [도보특가/오픈특가 운영](promotions-special-offers/walk-in-special-deals.md) — 당일 할인 상품

### 수기/직접 예약 관리 (43건 기반, 1개 초안)
- [ ] [전화/현장 예약 등록 및 재고 연동](manual-direct-booking/manual-booking-inventory-sync.md) — 비연동 예약 관리

### 온보딩/시스템 설정 (40건 기반, 1개 초안)
- [ ] [VCMS 초기 세팅 가이드](onboarding-setup/vcms-initial-setup.md) — 도입 초기 설정

### 오버부킹 방지/처리 (26건 기반, 1개 초안)
- [ ] [오버부킹 방지 설정](overbooking-prevention/overbooking-prevention-setup.md) — 중복 예약 방지

### 다지점/사용자 관리 (21건 기반, 1개 초안)
- [ ] [다지점 숙소 통합 관리](multi-property-accounts/multi-property-management.md) — 지점별 권한/계정 분리

### 고객 커뮤니케이션 (19건 기반, 1개 초안)
- [ ] [예약 확인/안내 자동 메시지 설정](customer-communication/auto-message-system.md) — 자동 문자 발송

### 정산/매출 리포트 (13건 기반, 1개 초안)
- [ ] [채널별 정산 리포트 활용](settlement-reports/channel-settlement-reports.md) — 매출/정산 통계

---

### Slack 기반 추가 초안 — 연동/온보딩 (4개)

> **데이터 소스**: Slack `system-vcms-noti` (1,653건) + `public-vcms` (13,351건)
> **추출 방법**: `scripts/extract_slack_themes.py` → 9개 테마 클러스터링 → 4개 초안 선별

- [ ] [VCMS 온보딩 교육 준비 및 진행 가이드](onboarding-setup/onboarding-education-guide.md) — 교육 예약부터 사후 관리까지
- [ ] [채널 동기화 장애 발생 시 대응 가이드](channel-management/channel-sync-failure-response.md) — 야놀자 403, 네이버 장애 대응
- [ ] [떠나요닷컴 리피터 설치 및 운영 주의사항](specific-channel-ops/ddnayo-repeater-guide.md) — 설치 절차, 전용/쉐어드, 장애 대응
- [ ] [트립닷컴·아고다 연동 시 상품 매핑 주의사항](specific-channel-ops/tripdotcom-agoda-mapping.md) — 인원별 요금, 상품 재사용

---

## 샘플 초안 (3개 전문)

아래 3개는 가장 많은 VOC를 기반으로 한 대표 초안이에요.

---

### 샘플 1: 기간별/시즌별 요금 설정 (요금관리 361건 기반)

> 📄 전체 파일: `drafts/pricing-management/seasonal-pricing.md`

**이런 상황이신가요?**
- 성수기/비수기마다 각 채널에 접속해서 요금을 하나씩 변경하고 있어요.
- 공휴일이나 지역 축제 기간에 맞춰 요금을 미리 설정해두고 싶은데 방법을 모르겠어요.
- 주말과 평일의 요금 차이를 자동으로 적용하고 싶어요.

**VCMS로 이렇게 해결할 수 있어요**: 판매 관리에서 기간별 요금을 미리 설정해두면, 해당 날짜가 되었을 때 자동으로 적용되고 모든 채널에 동시 반영.

**대상**: 성수기/비수기 요금 차이가 큰 관광지 펜션·리조트, 요금 세분화 필요한 호텔

---

### 샘플 2: 다채널 통합 연동 설정 (채널관리 193건 기반)

> 📄 전체 파일: `drafts/channel-management/multi-channel-integration.md`

**이런 상황이신가요?**
- 각 채널의 관리자 페이지에 일일이 접속해서 재고와 요금을 수정하고 있어요.
- 스프레드시트로 예약을 관리하다가 누락과 오류가 빈번하게 발생해요.
- 새 채널을 추가하고 싶은데 관리 부담 때문에 망설이고 있어요.

**VCMS로 이렇게 해결할 수 있어요**: 야놀자, 여기어때, 네이버, 아고다, 부킹닷컴 등 직접 연동. 하나의 화면에서 통합 관리.

**대상**: 3개 이상 OTA 운영, 수기→시스템 전환 원하는 곳

---

### 샘플 3: 채널별 재고 연동 관리 (재고관리 206건 기반)

> 📄 전체 파일: `drafts/inventory-management/channel-inventory-sync.md`

**이런 상황이신가요?**
- 야놀자 3개, 여기어때 3개, 네이버 3개 — 총 5개 객실인데 9개를 올려둔 적 있으신가요?
- 한 채널에서 예약이 들어왔는데 다른 채널 재고가 안 줄어들어 오버부킹 발생.
- 수동으로 각 채널에 접속해서 재고 조정하는 데 매일 상당한 시간을 쓰고 있어요.

**VCMS로 이렇게 해결할 수 있어요**: 모든 채널 재고 통합 관리. 한 채널 예약 → 나머지 채널 실시간 자동 차감.

**대상**: 3개 이상 OTA, 재고 변동 잦은 곳, 수동 관리에 시간 낭비하는 곳

---

## 검토 방법

1. 위 체크리스트에서 각 초안을 승인(`[x]`), 수정요청(`[R]`), 거절(`[D]`) 표시
2. 수정 요청 시 해당 파일명 옆에 수정 사항 간단히 메모
3. 최소 1개 이상 승인되면 MDX 변환 → docs.vcms.io 배포 진행

---

## 기술 메모

- **PII 스캔**: 전 초안 0 violations (실제 업장명/담당자명/전화번호/금액 없음)
- **익명화**: 모든 업장 참조는 "부산 M호텔", "강원 B펜션" 형태로 치환
- **데이터 근거**: 각 초안은 최소 2건 이상의 VOC use_case를 기반으로 작성
- **톤**: docs.vcms.io 기존 스타일 (친근한 존댓말, -요 체)
