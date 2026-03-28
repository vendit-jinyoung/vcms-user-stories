# vcms-user-stories

VCMS 채널매니저 내부 콘텐츠 사이트. 통화 VOC 데이터와 카카오톡 CS 대화에서 추출한 실제 운영 사례를 Mintlify 기반 문서로 제공한다.

## 목적

숙박업 채널매니저 운영 현장의 실제 사례를 정리해 고객 지원·온보딩에 활용.

## 기술 스택

- **프레임워크**: Mintlify (MDX 문서 사이트)
- **배포**: GitHub push → Mintlify 자동 빌드
- **설정**: `docs.json` (내비게이션/테마), `styles.css` (커스텀 CSS)

## 3탭 구조

| 탭 | 경로 | 설명 |
|---|---|---|
| VCMS 활용 | `ko/vcms-usage/` | Need→Setting→Solved 패턴, 13페이지 |
| 채널별 특이사항 | `ko/channels/` | 채널 동작 주의점, 15페이지 |
| 숙박 매거진 | `ko/magazine/` | 칼럼/에디토리얼, 7페이지 |

## Setup

콘텐츠 편집은 `ko/` 하위 MDX 파일을 직접 수정하고 push하면 Mintlify가 자동 빌드한다. 로컬 미리보기가 필요하면 Mintlify CLI를 사용한다.

```bash
# 로컬 미리보기 (Mintlify CLI 필요)
mintlify dev
```

콘텐츠 생성 파이프라인 (데이터 소스 → 초안):

```bash
# use-case 분류
python scripts/categorize_use_cases.py

# 초안 생성
python scripts/generate_use_case_drafts.py

# 콘텐츠 인텔리전스 DB 업데이트
python scripts/content_intel.py
```

## 디렉토리 구조

```
docs.json              Mintlify 설정 (내비게이션, 테마)
styles.css             사이드바 확장 + 브랜드 컬러
ko/channels/           채널별 특이사항 MDX
ko/vcms-usage/         VCMS 활용 MDX
ko/magazine/           숙박 매거진 MDX
ko/stories/            추가 스토리 MDX
scripts/               콘텐츠 생성·분류·검수 Python 스크립트
docs/                  콘텐츠 정책 문서
logo/                  브랜드 에셋
_archive/              v1 콘텐츠 백업 (삭제 금지)
_data/                 로컬 데이터 소스 (gitignored)
```

## 콘텐츠 정책 핵심 요약

- VCMS는 채널 매니저 Only — PMS/키오스크/SMS/부킹엔진 아님
- 비연동 채널(부킹닷컴, 익스피디아, 에어비앤비)은 "준비 중" 표기
- 용어: 요금·예약·상품·동기화 — `vcms-i18n-glossary.json` 기준
- 내부 수치(통화수, 클레임수) 및 직접 매출 수치 노출 금지
- 전체 정책: `docs/content-policy-vcms.md`
