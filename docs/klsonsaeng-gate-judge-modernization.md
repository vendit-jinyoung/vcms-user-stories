# klsonsaeng Gate/Judge 현대화 경로

## 작업 범위
- 대상: `scripts/klsonsaeng.py`의 Gate 2 AI judge runtime만 현대화한다.
- 유지: Gate 1 결정론적 린트, `.vcms-policy.yml`, `docs.vcms.io` 기반 팩트체크 흐름, CLI 명령 형태(`lint`, `judge`, `sweep`).
- 제외: 콘텐츠 생성 파이프라인 재설계, 전체 제품/에이전트 아키텍처 변경, 전역 provider migration.

## 현재 상태 요약
`klsonsaeng.py`는 이미 Gate 1 / Gate 2 분리를 갖고 있지만, Gate 2가 아래 전제에 강하게 묶여 있다.

1. `anthropic` SDK import + `ANTHROPIC_API_KEY`를 전제로 함
2. 모델이 `claude-sonnet-4-20250514`로 하드코딩되어 있음
3. 응답을 자유형 텍스트로 받은 뒤 정규식으로 JSON 블록을 추출함
4. 패키지 미설치, API 키 누락, 응답 파싱 실패 시 `None`을 반환하고 `(스킵)` 처리함
5. `JudgeResult` 주석에는 `line_hint`가 있으나 실제 프롬프트 출력 계약에는 빠져 있음

이 조합은 현재 OpenCode/OpenAI 중심 운영 환경과 어긋나고, judge 실패가 "판정 실패"가 아니라 "조용한 스킵"으로 묻히기 쉽다.

## 목표 방향
Gate 2를 **Claude 전용 호출**에서 **OpenAI-first 구조화 출력 judge**로 교체한다.

### 1) 교체 런타임
- 기본 런타임: Python 공식 `openai` SDK (`from openai import OpenAI`)
- 기본 인증: `OPENAI_API_KEY`
- 기본 모델 선택: `OPENAI_MODEL` 환경변수 우선, 미지정 시 초기 기준값은 `gpt-4.1`
- OpenCode와의 관계: 이 스크립트는 별도 에이전트 오케스트레이션을 내장하지 않고, **OpenCode/OpenAI 기준과 호환되는 단순 OpenAI client 호출**만 사용한다.

### 구현 전제
- 이 저장소에는 현재 Python dependency manifest가 없고, 로컬 확인 기준 `openai` 패키지도 기본 설치되어 있지 않았다.
- 따라서 실제 구현 PR에서는 `openai`(필요 시 `pydantic` 포함) 의존성 선언 또는 설치 절차를 **명시적으로 추가**해야 한다.
- OpenCode를 쓰고 있다는 사실만으로 Python CLI 안에서 OpenAI SDK가 자동으로 제공된다고 가정하지 않는다.

즉, 구현 범위는 "Anthropic 호출부를 OpenAI structured output 호출부로 치환"하는 데서 끝낸다. judge를 다른 서비스로 분리하거나 story pipeline 전체를 다시 짜지 않는다.

### 2) 유지할 외부 인터페이스
- `python3 scripts/klsonsaeng.py lint [target]`
- `python3 scripts/klsonsaeng.py judge [target]`
- `python3 scripts/klsonsaeng.py sweep`
- `python3 scripts/klsonsaeng.py sweep --full`

CLI와 Gate 1 동작은 유지하고, Gate 2 내부 runtime만 바꾼다.

## 목표 출력 계약
Gate 2는 자유형 텍스트가 아니라 **스키마 강제 structured output**을 반환해야 한다. 정규식 JSON 추출은 제거 대상이다.

### 필수 스키마
```json
{
  "verdict": "PASS | WARN | FAIL",
  "findings": [
    {
      "type": "WARN | FAIL",
      "claim": "문제가 된 문장 또는 주장",
      "suggestion": "수정 제안",
      "spec_ref": "관련 docs.vcms.io 경로 또는 null",
      "line_hint": 12
    }
  ]
}
```

### 계약 규칙
- `verdict`는 `PASS`, `WARN`, `FAIL` 중 하나만 허용
- `findings`가 비어 있으면 `verdict=PASS`
- `FAIL` finding이 하나라도 있으면 `verdict=FAIL`
- `WARN`만 있으면 `verdict=WARN`
- `type`은 `WARN` 또는 `FAIL`만 허용 (`PASS` finding 금지)
- `claim`, `suggestion`은 비어 있지 않은 문자열
- `spec_ref`는 docs 경로 문자열 또는 `null`
- `line_hint`는 가능하면 정수, 찾지 못하면 `null` 허용
- 스키마 밖의 자유형 설명 텍스트는 금지

### 왜 이 계약을 유지하나
- 현재 `JudgeResult`의 핵심 구조(`verdict`, `findings`)를 보존해 코드 변경 범위를 최소화할 수 있다.
- 동시에 지금 주석에만 존재하는 `line_hint`를 계약에 포함해 후속 수정성을 높일 수 있다.
- OpenAI structured output/Pydantic parsing 경로를 쓰면 정규식 추출보다 실패 조건이 명확해진다.

## 구현 시 런타임 규칙
1. 모델 호출은 **스키마 기반 파싱**을 사용한다.
2. 응답이 스키마에 맞지 않으면 "judge PASS"가 아니라 **runtime failure**로 취급한다.
3. `judge` 또는 `sweep --full`을 명시적으로 실행한 경우, Gate 2 초기화 실패(`openai` 미설치, API 키 누락, 파싱 실패)는 조용히 스킵하지 말고 비정상 종료 대상으로 다룬다.
4. `docs.vcms.io` 전체 스펙 + `.vcms-policy.yml` few-shot/policy는 그대로 judge 입력에 유지한다.
5. Gate 1 결과 집계/Slack 알림 동작은 이 패스의 변경 대상이 아니다.

## 권장 내부 분리
실구현 시에는 provider 이름이 아니라 역할 이름으로 나눈다.

- `gate2_judge(...)` : 판정 orchestration 유지
- `run_openai_judge(...)` 또는 `judge_runtime_openai(...)` : 모델 호출 전담
- `JudgePayload` 또는 Pydantic 모델: structured output schema 정의

이렇게 두면 향후 다른 runtime을 붙이더라도 Gate 2 로직 전체를 다시 쓰지 않아도 된다. 다만 이번 결정은 **OpenAI runtime 하나만 공식 경로로 둔다**는 전제를 갖는다.

## 검증 기준
현대화 구현 단계에서는 아래만 통과하면 된다.

### A. 계약 검증
- 구조화 출력 스키마 테스트: 정상 PASS/WARN/FAIL 응답 각각 1개 이상
- 잘못된 응답(자유형 텍스트, 누락 필드, 잘못된 enum)이 runtime failure로 처리되는지 확인

### B. 동작 검증
- 단일 MDX 파일 `judge` 실행 시 Gate 1 → Gate 2 순서가 유지되는지 확인
- `sweep --full` 실행 시 Gate 1/Gate 2 집계 형식이 기존과 크게 달라지지 않는지 확인
- Gate 1 only 경로(`lint`, `sweep`)는 OpenAI API 없이도 그대로 동작하는지 확인

### C. 범위 검증
- story generation, category extraction, Mintlify build, 문서 구조는 건드리지 않음
- `.vcms-policy.yml` 의미 변경 없이 judge runtime만 교체함
- 결과적으로 이 문서는 "AI judge/runtime 현대화" 결정을 완결시키되, 제품 전체 redesign 문서가 되지 않음

## 구현 전 체크리스트
- [ ] Anthropic 전용 import / env / 모델 상수 제거 계획 수립
- [ ] OpenAI SDK + schema parsing 방식 선택
- [ ] `JudgeResult`와 structured output schema의 필드 합치기 (`line_hint` 포함)
- [ ] runtime failure를 skip이 아닌 명시적 실패로 처리
- [ ] 최소 fixture 기반 검증 케이스 준비

## 이번 문서의 결정
`vcms-user-stories`의 Gate/Judge 현대화는 **Claude 호출을 유지한 채 프롬프트만 손보는 방향이 아니라**, **OpenAI-first structured-output judge로 교체하는 방향**으로 간다. 이때 핵심은 모델 교체 자체보다도 **정규식 기반 JSON 추출을 버리고, 스키마 검증 가능한 출력 계약을 공식화하는 것**이다.
