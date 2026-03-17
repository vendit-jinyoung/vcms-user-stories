# KakaoTalk CS Data → Content Enrichment Map

## Data Summary
- 12 CSVs, 3,302 lines total
- Richest: 청주 브릭료칸(1,256L, 102 vendit msgs), 구리 호텔다운(489L, 56), 사천 부엉이(426L, 35)

## HIGH PRIORITY Enrichments

### channel-connect-basics.mdx
- Repeater: "1분마다 야놀자/네이버 예약 fetch + 재고 변경" (구리)
- 24hr PC: "200+업장 부하관리" (구리)
- CMS migration: "이전 CMS 예약→VCMS 기준 재생성" (청주)
- Password change: "vcms>설정>채널에서 재로그인" (청주)

### agoda/ (net-rate + promotion)
- Connectivity: "요금&예약 설정관리>커넥티비티>Vendit 등록" (구리)
- New product rate bug: 크리스마스 요금 미적용→평일가 판매→벤디트 보상 (청주)
- Per-person pricing: "기준인원 기반, 아고다는 인원수별 차등 가능" (청주)
- Force-assign→재고 풀림→아고다 예약 (구리)

### stop-sell-and-reopen.mdx
- Auto stop-sell: "예약 불러올수없을때 오버부킹 방지 자동 판매중지" (구리)
- 야놀자 26곳 일괄 차단 사례 (구리)
- 아고다 특정요일 마감 (청주)

### seasonal-rate-setup.mdx
- 설정-상품(전기간) vs 판매관리 일괄변경(특정기간) 차이 (구리)

## MEDIUM PRIORITY
- yanolja/sync: 보안업데이트 일괄차단 (구리)
- room-type-mapping: 특가상품 매핑, 상품명변경→ID유지 (사천,청주)
- channel-rate-markup: 네이버 일요일 요금만 변경 사례 (구리)
- auto-replenish: 강제배정→재고 재집계 (구리)

## LOW PRIORITY
- multi-property-permissions: 180일 연동기간 (청주)
- 에어비앤비: 2차인증, 네이버/구글 로그인만 가능, 프로모션 충돌 (청주,구리)
