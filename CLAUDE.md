# vcms-user-stories

## 프로젝트 개요
VCMS(숙박업 채널 매니저) 내부 콘텐츠 사이트. Mintlify 기반, 통화 VOC 데이터(1,413건 녹음, 6,419 claims)와 카카오톡 CS 대화(12건)에서 추출한 실제 운영 사례로 구성.

## 기술 스택
- **프레임워크**: Mintlify (MDX 기반 문서 사이트)
- **배포**: GitHub → Mintlify 자동 빌드
- **레포**: vendit-jinyoung/vcms-user-stories (public)
- **설정**: docs.json (내비게이션/테마), styles.css (커스텀 CSS)

## 3탭 구조
| 탭 | 경로 | 페이지 수 | 설명 |
|---|---|---|---|
| VCMS 활용 | ko/vcms-usage/ | 13 (index + 12) | Need→Setting→Solved 패턴 |
| 채널별 특이사항 | ko/channels/ | 15 (index + 11 채널 + 3 준비중) | 채널 자체 동작 방식 주의점 |
| 숙박 매거진 | ko/magazine/ | 7 (index + 6) | 칼럼/에디토리얼 포맷 |

## 콘텐츠 정책 (docs/content-policy-vcms.md)
- VCMS는 채널 매니저 ONLY. PMS/키오스크/SMS/부킹엔진 아님
- 연동 채널: 야놀자, 여기어때, 네이버, 아고다, 트립닷컴, 떠나요닷컴, 온다 펜션플러스
- 비연동 채널: 부킹닷컴, 익스피디아, 에어비앤비 — "준비 중" 표기, 절대 active 취급 금지
- 용어: 요금(not 가격), 예약(Booking), 상품(Package), 동기화(Sync) — glossary.json 기준
- 특정 채널 공격 금지 — 중립 어투("운영상 특성", "주의점")
- 정확한 내부 수치(통화수, 클레임수) 노출 금지, 직접 매출 수치 금지
- customer_quote/evidence_quote 사용 금지 (PII 리스크)
- PMS/정산 콘텐츠 front-and-center 배치 금지
- 여기어때: 사장님앱(모텔) vs 파트너센터(펜션/호텔/글램핑) 구분 필수

## 데이터 소스 (_data/ — gitignored, 로컬 전용)
- `_data/voc-extractions/` — 1,414 VOC JSON (통화 녹음 추출)
- `_data/category-data/` — 16개 카테고리별 claim JSON
- `_data/_category_deep_data.json` — 6,419 claims 통합
- `_data/categories.json` — 1,415 use_cases 분류
- `_data/kakao-chats/` — 12개 카카오톡 CS 대화 CSV

## 파일 구조
```
docs.json              # Mintlify 설정 (3탭, expanded:true)
styles.css             # 사이드바 확장 + 브랜드 컬러
.gitignore             # _data/, _archive/ 제외
ko/channels/           # 탭1: 채널별 특이사항
ko/vcms-usage/         # 탭2: VCMS 활용
ko/magazine/           # 탭3: 숙박 매거진
_archive/              # v1 콘텐츠 백업 (78파일)
_data/                 # 로컬 데이터 (gitignored)
docs/                  # 콘텐츠 정책 문서
logo/                  # VCMS 브랜드 에셋
```

## 주의사항
- `expanded: true` — 모든 navigation group은 펼쳐진 상태 유지
- GitHub 바로가기 — navbar/footer에서 제거됨 (다시 붙이지 말 것)
- push 시 배치 단위 — Mintlify 빌드 큐 혼잡 방지
- _archive/ 콘텐츠 — 구조 변경 전 백업, 삭제하지 말 것

## 외부 참조 (수정 금지)
- docs.vcms.io — Vendit-cms/docs 레포 (팩트체크 20% 참조만)
- vcms-web — yujy118/vcms-web (ARCHITECTURE.md, SPEC.md, DESIGN_SYSTEM.md)
- glossary.json — 36개 용어, 6개 언어
