# Fynn Lab v1 스펙 (초안)

Kikoff 블로그 "Fynn at 100% scale"에 나온 두 가지 변화를 작게 재현합니다.

1. 단일 에이전트 라우팅을 스킬 기반 구조로 바꾼 것.
2. 스킬을 수정할 때마다 도는 회귀 테스트 루프.

웹사이트 하나에서 세 가지를 보여줍니다.

1. 두 버전과 직접 대화하며 비교하는 데모
2. 평가(모니터링) 프레임워크
3. 그 결과

## 0. 범위

### v1에 넣는 것

- Before / After 챗봇 두 개. 같은 지식을 쓰고, 라우팅과 구성 방식만 다릅니다.
- 가상 페르소나 6명
- 평가셋 약 40개 케이스, 데이터셋 4종
- 채점: 코드로 하는 객관 체크 + LLM judge. 케이스당 1회 실행합니다.
- 회귀 리포트: 통과/불통과, 개선/퇴보/유지, 실패 상세
- After 봇의 스킬 개선 시나리오 3개 (S1~S3)
- 의존 테스트 선택: 바뀐 스킬과 관련된 케이스만 다시 실행합니다.
- 사이트 3개 섹션

### 나중에 추가할 것 (v2 이후)

- 반복 실행, 통계 검정 (McNemar, 부트스트랩), 검정력
- 사람 라벨로 judge 검증 (TPR/TNR)과 보정
- 실제 대화 기반 오류 분석 루프
- 출시 후 운영 모니터링, 온라인 실험, 롤아웃 분석
- 라우터를 별도로 평가하는 지표 (스킬별 정밀도/재현율)

### 용어

v1에서 말하는 "모니터링"은 **출시 전 회귀 테스트**입니다. 오프라인에서 고정된 평가셋으로 돌립니다. 실서비스 트래픽을 보는 회귀 모니터링은 v2 이후에 다룹니다.

## 1. 사이트 구성

### 1-1. Demo: Before vs After

```
+----------------------------------------------------------------------+
| 페르소나: [Rebuilder v]   점수 588 (지난달 611) | 이용률 47% | 상품... |
| 예시 질문: [단일 질문] [블로그의 3-part 질문] [번호 목록 질문]         |
+-----------------------------------+----------------------------------+
| BEFORE: single-agent router       | AFTER: skill-based               |
| 설명 2~3문장                      | 설명 2~3문장                     |
| [아키텍처 다이어그램]             | [아키텍처 다이어그램]            |
| 이번 라우팅: Credit Products 1개  | 이번 라우팅: score-changes,      |
|                                   |   secured-card, marketplace      |
| [채팅창]                          | [채팅창]                         |
+-----------------------------------+----------------------------------+
| [ 질문 입력 -> 양쪽에 동시에 전송 ]                                   |
+----------------------------------------------------------------------+
```

- 각 열에는 짧은 설명, 아키텍처 다이어그램, 방금 메시지의 라우팅 결과, 채팅창이 들어갑니다.
- 라우팅 결과 표시가 핵심입니다. Before가 질문 3개 중 1개 분야만 골랐다는 걸 눈으로 보여줍니다.
- 아키텍처 다이어그램은 React 컴포넌트로 그립니다. 메시지마다 실제로 선택된 에이전트나 스킬 박스를 강조합니다.
- 입력 방식: 입력창 하나로 같은 질문을 양쪽에 동시에 보냅니다 (확정).

### 1-2. Monitoring framework

- 블로그 세 번째 다이어그램을 재현한 루프 그림: 스킬 수정 → (테스트 추가) → 의존 테스트 실행 → 회귀 리포트 → 안전? → 배포
- 평가셋 소개: 페르소나 카드, 데이터셋 4종, 케이스 예시
- 채점 방식: 객관 체크 목록, judge 프롬프트 원문
- 스킬 ↔ 테스트 의존 맵 (표)

### 1-3. Monitoring results

- **결과 A: Before vs After**
  - 데이터셋별 통과율 막대 그래프
  - 메시지 안 질문 수(1, 2, 3)별 통과율. 대표 차트입니다.
- **결과 B: After 봇의 스킬 개선 시나리오 3개** (3장 "스킬 개선 시나리오" 참고)
  - 시나리오마다: 무엇을 왜 고쳤는지, 미리 적어 둔 가설, 다시 돌린 케이스 수 (의존 테스트 선택 결과)
  - 요약: 통과/불통과, 개선·퇴보·유지 개수, 데이터셋별 변화
  - 실패 상세: 케이스, 이전 답, 새 답, judge 이유, (S3) 라우터가 고른 스킬의 변화
  - 판정: 배포해도 되는가, 그리고 가설이 맞았는가
- 결과는 미리 돌려서 커밋한 JSON을 읽어서 보여줍니다. 사이트에서 평가를 실시간으로 돌리지 않습니다 (비용과 재현성 때문).

## 2. 챗봇 설계

### 공통 원칙

- **지식은 스킬 파일(`skills/*.md`) 하나에서만 나옵니다.**
  - Before는 도메인별로 스킬 본문을 이어 붙여 "전문 에이전트 프롬프트"를 만듭니다. 공통 지침도 각 에이전트에 복제됩니다. 블로그가 말한 중복 문제를 그대로 재현하는 셈입니다.
  - 그래서 두 버전의 차이는 **라우팅/구성 방식 하나**뿐입니다. 공정한 비교가 되고, 결과를 해석하기도 쉽습니다.
- **페르소나 정보**(점수, 이용률, 보유 상품, 최근 이벤트)는 양쪽 모두 같은 형식으로 프롬프트에 들어갑니다.
- **회사와 상품은 가상**입니다. Kikoff 브랜드와 상품명을 쓰지 않고, "Kikoff 블로그 구조를 독립적으로 재현, Kikoff와 무관"이라고 표기합니다.
- **UI 언어**는 영어가 기본입니다 (지원용). 문서와 설명은 한국어로 같이 둡니다.

### Before: single-agent router

```
메시지 -> Agent Router (작은 LLM): 전문 에이전트 4개 중 정확히 1개 선택
       -> [정체성 + 공통 지침 | 회원 프로필 | 선택된 에이전트의 도메인 스킬] -> 답변 LLM -> 응답
```

전문 에이전트 4개:

| 에이전트 | 포함 스킬 |
|---|---|
| Credit score & reports | score-changes, utilization, payment-history |
| Credit-building products | credit-builder-account, secured-card, marketplace-offers |
| Rent & bill reporting | rent-reporting, bill-reporting |
| Debt & collections | debt-settlement, collections |

### After: skill-based

```
메시지 -> Skill Router (작은 LLM): 스킬 카탈로그(이름+설명) 보고 새로 0~3개 선택 (JSON 출력)
       -> + 직전 턴에 고른 스킬 최대 2개 이월
       -> [정체성 + 상시 스킬 | 회원 프로필 | 이번 메시지의 주제 스킬] -> 답변 LLM -> 응답
```

- 상시 스킬: `tone`, `response-rules`, `guardrails`
- 주제 스킬 10개: 위 표의 스킬 전부
- 프롬프트는 바뀌지 않는 것부터 쌓습니다(`|`가 블록 경계). 앞의 두 블록에 캐시 지점을 둡니다. 조립은 `fynn/prompts.py`가 합니다.
- **스킬 예산 (설정값, M3에서 비교).** 새로 고르는 스킬은 최대 3개(`MAX_NEW_SKILLS_PER_TURN`), 직전 턴에서 이월하는 스킬은 최대 2개(`MAX_CARRIED_SKILLS`)입니다.
  - 상한 3은 블로그에서 온 숫자가 아니라 설계 선택입니다. 상한을 두는 이유는 지침 집중도와 라우터의 과다 선택 방지입니다.
- **멀티턴 이월 (2026-10-19 실측 버그 대응).** 스킬을 메시지마다 새로 고르기 때문에, 후속 질문에서 앞 답변의 근거 스킬이 빠지는 일이 생겼습니다. 실제로 After 봇이 1턴에 맞게 안내한 내용을 2턴에 "확인할 수 없다"며 철회했습니다.
  - 대응 1: 직전 턴에 고른 스킬을 한 턴 더 유지합니다.
  - 대응 2: `response-rules`에 "지금 안 보이는 지침에 근거한 이전 발언을 그 이유만으로 철회하지 말라"는 규칙을 추가했습니다.
  - API는 상태를 저장하지 않으므로, 클라이언트가 이전 응답의 `routing.selected`를 `carry_skills`로 돌려보냅니다.
- **라우터 실패 시.** 거절, 출력 잘림, 잘못된 출력이 나오면 새로 고른 스킬 없이 답합니다. 이월된 스킬이 있으면 그것과 상시 지침으로, 없으면 상시 지침만으로 답합니다. `routing.error`에 원인을 남기고, 실패한 라우터 호출의 토큰도 사용량에 포함합니다. Before는 도메인 전문성 없이 공통 지침만으로 답합니다.

### 스킬 파일 형식

```markdown
---
name: secured-card
description: Explains how the secured card works, deposits, shipping and
  activation, and how it affects utilization. Use when the user mentions the
  card, deposit, shipping, or activation.
type: topic                 # always_on | topic
domain: credit-products     # Before 버전에서 어느 에이전트에 들어가는지
---
## Facts
...
## How to answer
...
## Do not
...
```

## 3. 평가 프레임워크 (v1 기본)

### 페르소나 6명 (JSON)

| ID | 설명 |
|---|---|
| new-to-credit | 신용 기록이 거의 없음 |
| rebuilder | 30일 연체 1건, 이용률 47%, 점수 하락 (블로그 예시용) |
| high-util | 결제 관리 중, 이용률 높음 |
| renter | 렌트 리포팅 사용 중 |
| collections | 추심 계정 보유 |
| multi-product | 여러 상품 사용 |

### 데이터셋 4종, 약 40개 케이스

| 데이터셋 | 무엇을 보나 | 케이스 수 |
|---|---|---|
| single_topic | 질문 하나에 정확히 답하는가 | 12 |
| multi_intent | 질문 2~3개가 섞인 메시지에 모두 제대로 답하는가 | 12 |
| context_use | 페르소나 정보를 제대로 쓰는가 (숫자, 보유 상품) | 8 |
| safety_basic | 점수 상승 보장 금지, 정확한 연체 삭제 약속 금지 등 | 8 |

### 테스트 케이스 형식 (YAML)

```yaml
- id: mi-001
  dataset: multi_intent
  persona: rebuilder
  message: >
    Why did my score drop last month? And why hasn't my secured card arrived?
    Should I get the travel card from your marketplace?
  skills: [score-changes, secured-card, marketplace-offers]  # 의존 스킬 = 라우터 정답
  expected_facts:
    - Names the 30-day late payment and 47% utilization as likely causes
    - Gives the card's ship date from the persona
    - Mentions a hard inquiry for a new card and does not promise approval
  must_not_regex: ['(?i)\bguaranteed (approval|to be approved)\b', '(?i)\bI guarantee\b', '(?i)\bwill definitely (raise|increase|improve|boost)\b']
```

- 정규식은 **부정 문맥과 헷갈릴 수 없는 긍정형 표현만** 잡습니다. 단순 문자열 `"guarantee"`를 금지하거나 `guarantee you` 같은 넓은 패턴을 쓰면 "I can't guarantee you'll be approved" 같은 올바른 면책 문구까지 실패 처리됩니다.
- 부정 여부를 문맥으로 판단해야 하는 경우("보장한다"는 취지인지)는 judge에게 맡깁니다.
- M3에서는 패턴마다 걸려야 하는 문장과 걸리면 안 되는 문장의 예시 테스트를 먼저 만들고 씁니다.

### 채점

1. **객관 체크 (코드)**
   - `must_not_regex`의 패턴이 답변에 없어야 합니다.
   - 필요하면 페르소나 숫자를 언급했는지 확인합니다.
   - (After만) 라우터가 고른 스킬이 정답 스킬을 포함하는지 기록합니다. 정보용이고 통과 판정에는 넣지 않습니다.
2. **LLM judge**: `expected_facts`와 비교해서 PASS/FAIL과 이유를 냅니다. 블로그와 같은 reference-based 방식입니다.
3. **최종 판정**: 객관 체크와 judge를 모두 통과하면 PASS입니다.

### 회귀 리포트

- 입력: baseline 결과 JSON, candidate 결과 JSON
- 출력:
  - 요약: 데이터셋별 통과율 변화, 개선/퇴보/유지 개수, 전체 Passed/Not passed
  - 실패 상세: 퇴보 케이스마다 이전 답, 새 답, judge 이유
- 형식: JSON (사이트가 읽음) + Markdown (터미널에서 읽음)

### 의존 테스트 선택

스킬마다 `description` 해시와 본문 해시를 따로 저장해 두고, 무엇이 바뀌었는지에 따라 다시 돌릴 범위를 정합니다.

| 바뀐 것 | 다시 돌리는 케이스 | 이유 |
|---|---|---|
| 주제 스킬의 본문 | 그 스킬을 `skills` 라벨에 가진 케이스 + baseline 실행에서 라우터가 실제로 그 스킬을 고른 케이스 | 본문은 그 스킬이 선택됐을 때만 프롬프트에 들어감. 라벨이 없어도 실제로 선택됐다면 답이 바뀔 수 있음 (그래서 결과 JSON에 케이스별 라우팅을 저장) |
| 주제 스킬의 `description` | 전체 | 라우터가 읽는 부분이라, 다른 주제 질문의 라우팅까지 바뀔 수 있음 |
| 상시 스킬 | 전체 | 모든 프롬프트에 들어감 |
| 주제 스킬의 `domain` (메타 해시) | Before 케이스 전체 (After에는 영향 없음) | Before의 에이전트 구성과 라우터 카탈로그가 바뀜 |
| 스킬의 `type` (메타 해시) | 전체 | 상시/주제 사이를 옮기면 두 봇의 프롬프트가 모두 바뀜 |
| 라우터 프롬프트, 모델 | 전체 | 모든 케이스에 영향 |

### 스킬 개선 시나리오 3개 (After 봇)

Before/After 비교는 "아키텍처를 바꾼 게 맞았나"를 봅니다. 시나리오는 그 다음 단계로, **After 구조 안에서 스킬 하나를 고쳤을 때 그 변경이 안전한가**를 블로그의 회귀 리포트 방식으로 봅니다. 결과가 서로 다르게 나오도록 세 가지를 골랐습니다.

| | S1. 본문 개선 | S2. 상시 스킬 수정 | S3. description 수정 |
|---|---|---|---|
| 고칠 스킬 | `score-changes` 본문 | `response-rules` (상시) | `utilization`의 description |
| 바꾸는 내용 | 잔액이 늘어난 시점에 점수가 떨어졌으면, 카드별 이용률을 계산하고 먼저 갚을 카드를 짚도록 안내 추가 | "답변을 250단어 이하로"를 "120단어 이하로"로 줄임 (짧은 답을 원하는 제품 요청을 가정) | "점수가 떨어졌다"는 질문에도 라우터가 이 스킬을 고르도록 description을 넓힘 |
| 동기 | 2026-10-19 실측에서 After의 점수 답변이 Before보다 덜 구체적이었음 (Before는 도메인 스킬 3개를 다 받아서 카드별 이용률까지 계산) | 블로그가 말한 "짧지만 중요한 내용을 빠뜨리는 답" | S1과 같은 문제를 라우팅으로 풀어 보려는 시도 |
| 다시 돌리는 범위 | `score-changes` 의존 케이스만 (약 8~10개) | 전체 | 전체 |
| 가설 (미리 적어 둠) | 점수 하락 케이스 개선, 퇴보 없음 → 배포 가능 | 단일 질문은 유지, 여러 질문 케이스에서 사실 누락으로 퇴보 → 배포 불가 | 단일 점수 질문은 개선. 하지만 질문 3개짜리 메시지에서는 스킬 상한 3개 때문에 다른 스킬이 밀려나 퇴보 → 트레이드오프 |
| 보여주는 것 | 의존 테스트만 돌려도 되는 깔끔한 개선 | 상시 스킬 수정은 왜 전체를 돌려야 하는가 | description 한 줄이 다른 주제의 라우팅을 바꾸는 숨은 회귀 |

- 각 시나리오는 `scenarios/<id>/`에 둡니다. 고친 스킬 파일과 `scenario.yaml`(제목, 동기, 가설, 바뀐 파일)이 들어갑니다. 실제 `skills/`는 건드리지 않고, 실행할 때만 덮어씌웁니다.
- 가설은 결과를 보기 전에 적어 둡니다. 결과가 가설과 다르면 그것도 그대로 보고합니다.
- 평가셋에는 이 시나리오들을 확인할 수 있는 케이스가 있어야 합니다. 잔액 증가와 함께 점수가 떨어진 단일 질문(rebuilder, high-util 페르소나)과, 질문 3개짜리 메시지가 필요합니다.

### CLI (예시)

```
fynn eval --bot before                  # 전체 실행
fynn eval --bot after
fynn eval --bot after --changed         # 바뀐 스킬 관련 케이스만
fynn eval --bot after --scenario s1     # 시나리오 스킬을 덮어씌워 의존 케이스만 실행
fynn report results/a.json results/b.json
```

## 4. 기술 스택 (확정)

### 구성: Python 코어 + Next.js 프론트

- **백엔드 (Python 3.12)**
  - 챗봇 코어와 평가 코드가 같은 패키지(`fynn`)를 씁니다. 데모에서 보는 봇과 평가하는 봇이 같은 코드라는 게 중요합니다.
  - FastAPI로 HTTP API를 엽니다.
  - Anthropic Python SDK, pydantic (구조화 출력과 데이터 검증), PyYAML (테스트 케이스), pytest를 씁니다.
- **프론트엔드 (Next.js + TypeScript)**
  - 페이지 3개: `/` Demo, `/framework`, `/results`. 상단 내비로 이동합니다.
  - Tailwind로 스타일링하고, 차트는 Recharts로 그립니다.
  - API 키는 백엔드 `.env`에만 둡니다. 프론트는 키를 절대 보지 않습니다.
- **평가 결과**
  - `results/*.json`으로 커밋합니다.
  - Results 페이지는 Next.js 서버 컴포넌트가 이 파일들을 읽어서 그립니다.
  - Framework 페이지도 같은 방식으로 `skills/`, `personas/`, `evals/cases/`를 읽습니다.
- **실행**
  - 로컬: 백엔드 `uvicorn` (포트 8000), 프론트 `npm run dev` (포트 3000)
  - 배포는 M6에서 정합니다 (예: 백엔드 Render 또는 Fly, 프론트 Vercel).

### 백엔드 API (v1)

| 엔드포인트 | 입력 | 출력 |
|---|---|---|
| `POST /chat` | `bot` (before/after), `persona_id`, `messages` (user로 시작·끝, 번갈아), `carry_skills` (선택; After 전용, 이전 응답의 `routing.selected`. Before는 무시, 모르는 이름은 버림) | `bot`, `reply`, `model`, `stop_reason`, `routing` (strategy, selected, carried, reason, error), `usage` (캐시 읽기·쓰기 포함). 모든 에러는 CORS 헤더가 붙은 JSON `{detail, retryable}` |
| `GET /personas` | 없음 | 페르소나 목록 |
| `GET /architecture` | 없음 | 에이전트-스킬 매핑, 스킬 카탈로그 (다이어그램용) |

- v1은 스트리밍 없이 응답이 다 오면 표시하고, 기다리는 동안 로딩 표시를 합니다. 스트리밍은 나중에 붙입니다.
- 프론트는 같은 메시지로 `bot=before`와 `bot=after`를 동시에 호출합니다.

### 모델 (확정)

| 역할 | 모델 | 이유 | 가격 (입력/출력, 1M 토큰당) |
|---|---|---|---|
| 라우터 (Before, After) | `claude-haiku-5-5` | 블로그의 "small LLM" | $0.10 / $0.50 |
| 답변 에이전트 | `claude-sonnet-5-5` | 비용 대비 품질 (2026-10-19 Opus에서 변경; 최종 데모 모델은 M3 평가로 결정) | $2 / $10 |
| judge | `claude-opus-5-5` | 채점 품질 | $4 / $20 |

- 라우터는 구조화 출력(JSON 스키마)으로 받습니다. 자유 텍스트를 파싱하지 않습니다.
- 답변 에이전트는 effort를 낮게 잡아서 응답 속도와 비용을 맞춥니다.
- 모델 이름은 설정 파일 한 곳에서 관리합니다.

### 비용

**어디에 쓰이나** (2026-10-19 실측, 토큰 카운트 API 기준). After 봇이 블로그 예시 질문에 답할 때 입력은 이렇게 나뉩니다.

| 부분 | 토큰 | 요청마다 같은가 |
|---|---|---|
| 정체성 문구 + 상시 스킬 3개 (그중 guardrails 1,646) | 약 3,090 | 모든 요청에서 같음 |
| 회원 프로필 | 약 1,015 (압축 JSON) | 대화 하나 안에서 같음 |
| 선택된 주제 스킬 3개 | 약 2,210 | 메시지마다 바뀜 |
| 라우터 입력 (Haiku) | 약 2,060 | 거의 같음, 단가가 낮아 무시할 만함 |

출력은 봇당 약 800~900 토큰이고, thinking 토큰이 포함됩니다. 답변 모델의 입력과 출력이 비용 대부분을 차지합니다.

**적용한 절감 (품질 영향 없음)**
- **Prompt caching.** 시스템 프롬프트를 안정적인 순서(상시 지침 → 프로필 → 주제 스킬)로 재배치하고, 앞 두 블록에 캐시 지점을 둡니다. 캐시 읽기는 $0.20/1M로, Sonnet 5.5 기준 기본 입력 단가의 10%(Opus 5.5 기준 5%)입니다. 5분 캐시 쓰기는 기본 입력의 1.25배입니다. 5분 안에 다시 요청하면 입력의 약 65%가 이 단가로 처리됩니다. Before도 같은 순서(공통 지침 → 프로필 → 도메인 전문성)로 맞췄습니다.
- **프로필 압축 JSON.** 들여쓰기를 없애 약 280 토큰을 줄였습니다.

**M3에서 적용할 절감**
- **Batch API.** 평가는 기다리는 사람이 없으니 모든 토큰이 50% 할인됩니다. 캐시 할인과 겹쳐서 적용됩니다.

**모델 선택에 따른 추정** (캐시가 적중한 상태, 출력 토큰은 Opus 실측치를 가정; 확인 필요)

| 답변 모델 | 데모 메시지 1개 (양쪽) | 평가 1회 (Batch, judge는 Opus) |
|---|---|---|
| Opus 5.5 (캐시 전, 실측) | 약 $0.08 | 약 $4.4 (Batch 없이) |
| Opus 5.5 + 캐시 | 약 $0.05 | 약 $1.6 |
| Sonnet 5.5 + 캐시 | 약 $0.03 | 약 $1.1 |
| Haiku 5.5 | 약 $0.002 | 약 $0.6 |

- 두 봇은 항상 같은 답변 모델을 씁니다. 비교의 공정성을 지키기 위해서입니다.
- 답변 모델이 싸지면 judge(Opus)가 평가 비용의 대부분을 차지합니다. judge는 채점 품질이 중요해서 Opus를 유지합니다.

### API 키

`backend/.env`에 넣었습니다 (2026-10-19). `.gitignore`가 `.env*`를 모두 막고 `.env.example`만 허용합니다. `fynn/config.py`가 다른 설정보다 먼저 이 파일을 읽고, 셸에서 export한 값이 우선합니다. CI나 배포 환경에서는 고정 키 대신 Workload Identity Federation을 검토합니다 (M6).

## 5. 레포 구조

```
fynn-lab/
├── README.md
├── SPEC.md
├── docs/                 # products.md: 가상 상품 기준 문서 (스킬, 페르소나, 기대 답변의 근거)
├── skills/               # 스킬 마크다운 (git으로 버전 관리; 백엔드와 프론트가 같이 읽음)
├── personas/             # 페르소나 JSON
├── results/              # 커밋되는 평가 결과 JSON
├── backend/
│   ├── pyproject.toml
│   ├── .env.example      # ANTHROPIC_API_KEY=
│   ├── fynn/             # 챗봇 코어 (데모와 평가가 같은 코드 사용)
│   │   ├── config.py     # .env 로딩, 모델 이름, 스킬 예산, 경로
│   │   ├── skills.py     # 스킬 로딩, 검증, 해시 (description/본문/메타 분리)
│   │   ├── personas.py   # 페르소나 로딩, 프로필 렌더링
│   │   ├── prompts.py    # 시스템 프롬프트 블록 조립 (캐시 지점 포함)
│   │   ├── llm.py        # Anthropic SDK 래퍼 (구조화 출력, fallback, 캐시)
│   │   ├── routers.py    # Before/After 라우터
│   │   ├── bots.py       # BeforeBot, AfterBot (이월, 라우터 실패 처리)
│   │   └── chat.py       # 터미널 채팅 CLI
│   ├── api/
│   │   └── main.py       # FastAPI
│   ├── evals/
│   │   ├── cases/        # 데이터셋별 YAML
│   │   ├── checks.py     # 객관 체크
│   │   ├── judge.py
│   │   ├── run.py
│   │   └── report.py     # 회귀 리포트
│   └── tests/            # pytest (LLM 호출은 가짜로 대체해서 테스트)
└── web/                  # Next.js
    ├── app/
    │   ├── page.tsx          # Demo
    │   ├── framework/page.tsx
    │   └── results/page.tsx
    └── components/           # ChatColumn, ArchitectureDiagram, PersonaCard, charts
```

## 6. 구현 순서

각 단계가 끝날 때마다 Young이 검토하고 다음으로 넘어갑니다.

| 단계 | 내용 | 확인 방법 |
|---|---|---|
| M1 | 스킬 파일, 페르소나, Before/After 봇 (백엔드 코어) | pytest + 터미널에서 두 봇과 대화 |
| M2 | FastAPI + Next.js Demo 페이지 (좌우 채팅, 라우팅 결과, 다이어그램) | 브라우저에서 비교 |
| M3 | 평가셋, 객관 체크, judge, 실행기 (Batch API); 스킬 예산 비교 (새 스킬 상한 3/5/무제한, 이월 0/2); 답변 모델 비교 | 두 버전 전체 평가 결과 JSON |
| M4 | 회귀 리포트, 의존 테스트 선택, 스킬 개선 시나리오 3개 (S1~S3) | 시나리오별 리포트 Markdown + 가설 대비 결과 |
| M5 | Framework, Results 페이지 | 사이트 3개 섹션 완성 |
| M6 (선택) | 배포 (공개 데모면 사용량 제한 필요) | 공개 URL |

## 7. 결정 사항

| 항목 | 결정 |
|---|---|
| 기술 스택 | Python 코어 (FastAPI) + Next.js 프론트 |
| 레포 위치 | `~/projects/fynn-lab` 로컬 git 레포. GitHub에는 검토가 끝난 뒤 올림 |
| 라우터 / 답변 / judge 모델 | Haiku 5.5 / Sonnet 5.5 / Opus 5.5 (답변 모델은 2026-10-19 Opus에서 변경) |
| 데모 입력 | 입력창 하나로 양쪽에 동시 전송 |
| UI 언어 | 영어 (문서는 한국어 병행) |
| 스킬 예산 | 새로 고르는 스킬 3개 + 직전 턴 이월 2개 (설정값, M3에서 비교) |
| 남은 것 | 배포 여부와 배포 환경 인증 방식 (M6에서 결정) |
