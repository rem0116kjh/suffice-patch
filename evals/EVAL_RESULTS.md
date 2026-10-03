# SufficePatch 연구 기록 — 종료 / A. Always Baseline

연구 상태: **종료**. 후속 skill 최적화·router 구현·추가 eval은 진행하지 않는다.
158단어 SKILL.md는 비용 목표에 실패한 실험 산출물로 보존한다. 아래 수치는 기존 실행 기록이며,
이번 정리는 새로운 성능 측정이 아니다. README에는 관측과 해석을 분리해 정리했다.

**이번 환경에서는 Always Baseline을 선택한다.** 기존 58회를 재분석했으며, 현재 v2와 baseline이 같은 과제로 짝지어지는 32회에서 비용 0의 완벽한 선택을 가정해도 token 절감 상한은 **1.38%**다. 실행별 결과까지 미리 아는 더 낙관적인 oracle도 **1.48%**에 그친다. 사용자 요청의 “최대 절감이 1–2% 수준이면 중단”을 이번 분석에서는 **≤2% 중단**으로 적용했다. 이는 통계적 유의성 기준이나 사전 등록된 실험 기준은 아니다.

따라서 실제 router 구현·새 모델 실행·stress fixture 추가는 진행하지 않았다. **Adaptive의 효과가 검증됐다는 주장은 없다.** 원본 SKILL.md, 158단어 후보, Codex/Claude 설치 사본은 변경하지 않았다. 선택적 활성화 분석 단계에서 보고서·집계 JSON·README를 갱신했고, 이후 연구 종료 정리에서는 README·이 보고서·원자료 보존용 .gitignore만 변경했다. 새로운 hook·dependency·framework·프로젝트 파일은 없다.

## Phase 1: 58회 데이터의 범위와 검증

| 기존 cohort | 내용 | 실행 수 | 이번 비교에서의 용도 |
|---|---|---:|---|
| expanded-20261003 | Baseline 16 + Lite 16 | 32 | Baseline 주 대조군, Lite 보조 비교 |
| compressed-20261003 | 최종 v2 158단어 | 16 | Baseline과 8과제 × 2회 비교 |
| ablation-20261003 | v1 / Lite / 46단어 body-only probe, native/shared 각 1회 | 6 | contemporary baseline이 없는 진단 결과 |
| regression-20261003 | 최종 v2의 native/shared/atomic/noop | 4 | contemporary baseline이 없는 회귀 결과 |
| 합계 | 독립 성공 기록 58/58 | 58 | **baseline/v2 직접 비교는 32회** |

58개 `events.jsonl`에서 usage와 completed tool events를 다시 집계하여 원본 `result.json` 및 cohort `results.json`과 일치함을 확인했다. 성공·timeout·checks·수정 경로 기록도 대조했고, 58개 prompt SHA-256 및 4개 cohort의 보존된 runner/tasks hash를 검증했다. 기존 채점 결과를 감사한 것이며 모델/채점기를 새로 실행한 것은 아니다. 초기 24회는 별도 과거 자료이며 이번 58회와 중복 합산하지 않았다.

전체 실행별 tokens/calls/읽기 proxy/수정 파일/성공/trace 경로는 [summary.json](summary.json)의 `adaptive_gate.runs`에 있다. 완전한 **files_read는 58회 모두 null**이다. 아래 “읽기”는 편집 전에 원본 파일 내용 또는 검색 일치 행이 반환된 고유 파일 수(`observed_context_files`)이며, listings·runtime import·후속 diff·생성 테스트는 제외한다. 진단/회귀 10회는 이 proxy도 미계측이다. 미계측을 0으로 대체하지 않았다.

## Task별 WIN / NEUTRAL / LOSS

비용은 input+output tokens이며 cached input을 중복 가산하지 않는다. 같은 성공률에서 **평균 token −2% 초과 절감 및 calls 비증가 = WIN**, **+2% 초과 증가 = LOSS**, 나머지 = NEUTRAL로 기술한다. 이 2% 구간은 작은 차이를 구분하기 위한 서술 기준이며 검증된 경제적 임계값이 아니다. WIN에도 반복 간 방향 일치 여부를 별도로 확인한다. **재현성 있는 WIN은 0개**다.

모든 행의 양쪽 성공은 2/2다. tokens는 실행당 **평균 = median**(n=2), calls/읽기/수정은 두 실행 **합계**이며 Baseline → v2다. 범주 내 표본분산은 아래 기존 v2 보고서와 JSON에 보존되어 있다.

| 과제 | Baseline tokens | v2 tokens | 차이 | calls | 읽기 proxy | 수정 파일 | 판정 |
|---|---:|---:|---:|---:|---:|---:|---|
| A trivial | 46,891.0 | 40,944.5 | -12.68% | 6 → 6 | 2 → 2 | 2 → 2 | WIN* |
| B localized | 54,072.0 | 55,354.0 | +2.37% | 8 → 8 | 2 → 2 | 2 → 2 | LOSS |
| C reuse | 54,247.0 | 55,519.0 | +2.34% | 8 → 8 | 9 → 10 | 3 → 4 | LOSS |
| D multifile | 54,915.0 | 56,189.5 | +2.32% | 8 → 8 | 8 → 8 | 4 → 4 | LOSS |
| E ambiguous | 55,540.5 | 63,368.5 | +14.09% | 8 → 9 | 12 → 9 | 2 → 4 | LOSS |
| F auth | 54,543.5 | 55,775.0 | +2.26% | 8 → 8 | 2 → 2 | 2 → 2 | LOSS |
| G dependency | 55,744.5 | 70,854.5 | +27.11% | 8 → 10 | 6 → 6 | 2 → 2 | LOSS |
| H refactor | 54,030.0 | 55,024.0 | +1.84% | 9 → 8 | 2 → 2 | 2 → 2 | NEUTRAL |

**A의 WIN*은 평균에서만 관측된 불안정한 이득이다.** Baseline은 53,641 / 40,141 tokens, v2는 40,935 / 40,954였다. 반복 번호로 짝지은 절감은 +12,706 / −813이며, 같은 prompt에서 방향이 뒤집힌다. baseline 2회차는 두 v2 실행 모두보다 저렴하다. 평균 WIN을 “오타에는 skill을 켜라”라는 규칙으로 변환할 근거가 없다. H는 tokens +1.84%와 calls −1의 tradeoff라 NEUTRAL이다. B–G는 모두 두 반복에서 v2가 더 비쌌다.

A baseline 첫 실행은 위치 listing → 별도 파일 read → Python 수정/검증의 shell 3회였다. 두 번째 baseline과 두 v2는 묶은 read → patch → 검증의 3개 tool event였다. 호출 수·읽은 파일·수정 파일 수가 같은데도 토큰이 달랐다. 이는 **total tokens를 calls 수만으로 설명할 수 없다는 trace 근거**다. per-request usage/비공개 추론 비용은 없어 차이를 특정 규칙이나 cache 원인으로 단정하지 않는다.

Lite까지 포함한 48개 주 실행의 과제별 원값과 평균·median·분산은 JSON의 `tasks`/`runs` 및 아래 기존 보고서에 있다. 나머지 10회는 다음과 같으며, 동일 cohort baseline이 없어 WIN/LOSS로 분류하지 않는다.

| 과제 | v1 진단 tokens / calls | Lite 진단 | 46단어 probe | 최종 v2 회귀 |
|---|---:|---:|---:|---:|
| native | 57,591 / 4 | 56,054 / 4 | 54,541 / 4 | 55,184 / 4 |
| shared | 59,239 / 4 | 72,855 / 5 | 55,711 / 4 | 56,564 / 4 |
| atomic | — | — | — | 56,450 / 4 |
| noop | — | — | — | 54,581 / 3 |

native는 모두 1파일, shared는 모두 2파일, atomic은 1파일, noop은 0파일 수정이다. 모두 성공했다. 46단어 probe를 최종 v2로 섞거나 과거 baseline을 추가해 oracle을 유리하게 만들지 않았다.

## Phase 2: 요청만으로 관찰 가능한 신호

아래는 저장된 **원래 user request**와 결과의 대응이다. 파일 수·code duplication·평가 범주명·실행 후 비용을 router 입력으로 간주하지 않는다. fixture 하나씩이라 인과 관계나 예측 정확도를 입증하지 못한다.

| 요청에서 확인할 수 있는 신호 | 실제 근거 | v2 결과 / 판단 |
|---|---|---|
| 명확한 위치와 작은 문자 수정 | A: `banner.py`, `Welome` → `Welcome`; H: `logs.error_line`의 colon | A 평균 −12.68%지만 방향 불일치, H +1.84%. trivial/complex 이분법을 지지하지 않음 |
| 기존 동작과 맞추기 | C: `api.customer_label`을 web view와 동일하게; F: `read_note`와 같은 access rules | C +2.34%, F +2.26%. 재사용 요구가 activation 이득을 예측하지 못함 |
| 여러 entrypoint | D: `api.order_summary`와 `csv_export.render_order` | +2.32%, 읽기·수정 파일 수 동일. multi-file signal의 이득 미관측 |
| 원인 진단 요구 | E: `/price` 오류를 “Diagnose and fix” | +14.09%, calls 8→9, 수정 파일 2→4. 읽기 proxy 12→9 감소가 비용 절감으로 이어지지 않음 |
| 인가와 거절 시 무변경 | F: access rules, rejected requests must not modify notes | 성공 양쪽 2/2, v2 +2.26%. 안전 하한을 약화시키지 않아도 baseline이 저렴했음 |
| dependency 선택 | G는 URL encoding 계약만 요청; dependency 선택 문구 없음 | +27.11%. `dependency temptation`이라는 평가 라벨은 사후 정보이므로 활성화 signal로 사용 불가 |
| broad refactor / architecture / repo-wide scope | 해당 요청 없음. H는 colon 수정일 뿐 | 측정되지 않은 신호. 이를 “complex WIN”으로 분류하면 안 됨 |

따라서 “복잡한 요청에서만 켜면 이득”이라는 가설을 이 자료가 지지하지 않는다. 명백한 실제 WIN 신호가 없으므로 default BASELINE에서 벗어날 규칙을 만들지 않았다.

## Phase 6: oracle 상한 — 구현 전 중단 gate

`C = input_tokens + output_tokens`. 성공률이 같을 때 각 과제의 두 반복 합계를 비교하여 `sum_task min(sum C_baseline, sum C_v2)`를 계산했다. 같은 prompt에는 같은 arm을 선택하는 task oracle과, 매 실행의 결과를 미리 아는 더 낙관적인 paired-run oracle을 구분했다. 둘 다 routing overhead=0인 **사후 계산**이며 실제 router가 아니다.

| 전략 | 성공 | total tokens | token median | calls 합계 / median | 읽기 proxy | 수정 파일 |
|---|---:|---:|---:|---:|---:|---:|
| A Always Baseline, 실측 | 16/16 | 859,967 | 54,421 | 63 / 4 | 43 | 19 |
| B Always v2, 실측 | 16/16 | 906,058 | 55,617 | 65 / 4 | 41 | 22 |
| Lite, 보조 실측 | 16/16 | 954,580 | 56,707 | 72 / 4 | 36 | 26 |
| C Adaptive, 미구현 | — | — | — | — | — | — |
| Task-token oracle, 계산 | 16/16 | **848,074** | 54,421 | 63 / 4 | 43 | 19 |
| Paired-run-token oracle, 계산 | 16/16 | **847,261** | 54,421 | 63 / 4 | 43 | 19 |
| Task-call oracle, token tie-break, 계산 | 16/16 | 850,062 | 54,700.5 | **62 / 4** | 43 | 19 |

- Task-token oracle은 A 두 번만 v2를 선택한다. 절감 **11,893 tokens = 1.3830%**. Lite도 선택지로 허용해도 결과는 동일하다.
- Paired-run oracle은 A의 첫 번째 반복에서만 v2를 고른다. 절감 **12,706 = 1.4775%**. 동일 요청인데 서로 다른 선택을 해야 하므로 prompt-only 결정 규칙으로 이 동작을 재현할 수 없다.
- Tools만 최소화하면 63→62로 **1회(1.5873%)** 절약 가능하다. tool 동률 때 tokens를 최소화하면 A와 H에서 v2를 선택하여 850,062 tokens(−1.1518%)다. token 최적 선택과 call 최적 선택은 다르며 임의 가중 비용으로 합치지 않았다. token oracle 자체의 call 절감은 **0회**다.
- 첫 반복만 보면 paired oracle 절감 2.9100%(436,625→423,919), 두 번째만 보면 **0%**(423,342→423,342)다. 1.48%를 안정적인 장기 절감으로 해석하지 않는다. 평균 이득이 한 높은 baseline 관측에 집중되며 token median 개선도 없다.

위 상한은 **고정된 관측 결과에서 arm만 선택할 때의 경험적 상한**이다. 미래 stress tasks나 새로운 population의 진짜 기대 절감 상한은 아니다. baseline/Lite는 interleaved였지만 최종 v2는 뒤 cohort에서 실행돼 시간/backend/cache 조건도 완전히 통제되지 않았다. n=2로 유의성을 주장하지 않는다.

독립 검산으로 8과제의 모든 256개 arm 선택 조합을 열거했다. 최소 tokens 848,074, 최소 calls 62, calls 우선/token 동률 해소 시 850,062가 위 직접 계산과 일치했다.

Token 평균 / 표본분산(n−1)은 baseline **53,747.9375 / 13,630,861.5292**, v2 **56,628.625 / 73,179,494.7833**, task oracle **53,004.625 / 22,554,581.85**다. 전체 분산은 과제 간 차이도 포함한다. 추가 지표의 평균·median·분산은 JSON에 저장했다.

## Phase 7: 손익분기점과 routing overhead

Task oracle을 그대로 맞힌다는 낙관적인 가정에서 총 routing overhead가 `R_total`이면 절감은 `11,893 − R_total` tokens다. 따라서 **R_total < 11,893**, 16개 요청마다 비용이 발생한다면 **평균 R < 743.3125 tokens/요청**이어야 한다. 활성화되는 A 두 번에만 비용이 생긴다고 가정하면 **R_activation < 5,946.5 tokens**다. 등호는 손익분기이며 strict improvement가 아니다. 이 수치는 one-shot prompt 길이의 token 수가 아니라 **turn 전체에서 추가로 집계되는 총 사용량**이다.

A의 관측 S는 +12,706와 −813으로 바뀌었다. B–H의 task 평균 S는 모두 음수이며, router가 공짜여도 token 관점에서 켤 이유가 없다. 잘못 활성화하면 이 작은 oracle 여유가 더 줄어든다. token oracle은 tools 절약이 없어서 **R_tools=0이어야 calls 비증가**를 유지한다. tool-only oracle의 최대 여유도 1회뿐이다. 0 tool calls라는 조건만으로 0 tokens가 되지는 않는다.

실제 router를 실행하지 않았으므로 **routing prompt overhead·추가 reasoning·실제 달러 비용은 미측정(null)**이다. cached input은 total input에 포함되지만 청구 단가가 없으므로 dollar break-even으로 바꾸지 않는다. oracle의 0은 가정이며 실제 router 측정치가 아니다.

S에는 기존 v2 지침 주입 비용이 이미 포함된다. R은 그 위에 더해지는 routing 비용만 의미하며, skill 비용을 다시 차감하지 않는다.

## Phase 3–5: router 규칙과 discrimination 지표

구현 gate가 실패했으므로 3–6개 활성화 규칙을 억지로 구성하지 않는다. 채택한 운영 결정은 **항상 BASELINE** 한 가지다. 별도의 dispatcher·router prompt·추가 skill context를 넣지 않는 선택이며, 실제 adaptive router가 아니다.

| 지표 | 실제 Adaptive Router | 상수 BASELINE 정책의 사후 감사 |
|---|---|---|
| 규칙 | 미구현 | 모든 요청에서 BASELINE |
| routing overhead tokens / tools | 미측정 | 추가 dispatcher/prompt가 없으므로 0 / 0 |
| task별 oracle label 일치 | 미측정 | 7/8 = 87.5% |
| false activation | 미측정 | 0/7 baseline-우세 과제 |
| missed activation | 미측정 | 1/1 v2-우세 과제(A) |
| activation precision | 미측정 | 정의되지 않음(활성화 0회) |
| paired-run oracle label 일치 | 미측정 | 15/16 = 93.75% |
| task-token oracle 대비 regret | 미측정 | 11,893 tokens |

여기서 oracle label은 2% NEUTRAL 구간과 관계없이 **tokens가 조금이라도 낮은 arm**이다. 상수 정책의 총 비용은 기존 baseline 859,967, 성공 16/16과 정의상 같으며 새로운 C 조건 실측으로 세지 않았다. 87.5%/93.75%는 같은 자료에 대한 기술 통계이며 held-out routing accuracy가 아니다. 이 높은 수치는 다수의 LOSS 때문에 생겨 activation의 유용성을 입증하지 않는다.

## Phase 8–10: 범위와 최종 선택

**선택 A — Always Baseline.** 이 model/fixture에서는 native behavior가 동일 성공률로 더 저렴했다. 선택적 skill의 경제적 가치도 확인되지 않았다. 이는 모든 modern agent에서 skill이 무용하다는 보편 결론이 아니다. B는 실측 비용 증가, C는 oracle gate 미달, D는 다른 agent/environment의 비교 evidence 부재로 채택하지 않는다.

새 stress eval은 사용자 지정 oracle 중단 조건에 따라 **추가하지 않았다**. 현재 E는 작은 ambiguous bug, C는 기존 동작 재사용, G는 작은 URL utility, native는 짝 없는 browser-native 회귀 검사다. 실제 repo-wide feature·큰 repository의 local fix·명시적 broad refactor·새 dependency 선택·abstraction 유혹을 가진 대형 작업은 측정하지 않았다. 특히 H를 broad refactor stress로, 설치가 금지된 G를 실제 dependency 선택 평가로 포장하지 않는다. 이 미측정 영역에서의 효과는 주장하지 않는다.

A의 불안정한 평균 이득에 맞춰 rule을 overfit하거나, 실패한 가설을 구제하기 위해 평가 범위를 계속 늘리지 않았다. 구현이 필요하지 않다는 판단 자체가 이번 연구의 결과다. 기존 skill와 설치 상태는 보존했고 자동 활성화/비활성화 설정은 건드리지 않았다.

## 재계산과 보존

아래는 기존 원자료만 읽는 계산이며 모델 호출·repository 탐색·새 dependency가 없다. 분석용 코드이지 런타임 router가 아니다. `summary.json`의 `adaptive_gate`에 58회 inventory, 과제별 통계/신호, oracle, break-even, unknown 값과 입력 파일 hashes를 보존했다.

```python
import json
from pathlib import Path
p = Path("evals/runs")
b = [r for r in json.loads((p / "expanded-20261003/results.json").read_text())
     if r["arm"] == "baseline"]
v = json.loads((p / "compressed-20261003/results.json").read_text())
cost = lambda r: r["input_tokens"] + r["output_tokens"]
tasks = sorted({r["task"] for r in b})
assert len(b) == len(v) == 16 and all(r["success"] for r in b + v)
task_oracle = sum(min(sum(cost(r) for r in b if r["task"] == t),
                      sum(cost(r) for r in v if r["task"] == t)) for t in tasks)
key = lambda r: (r["task"], r["run"].split("-", 1)[0])
paired = {key(r): r for r in v}
run_oracle = sum(min(cost(r), cost(paired[key(r)])) for r in b)
baseline = sum(map(cost, b))
assert (baseline, task_oracle, run_oracle) == (859967, 848074, 847261)
print({"baseline": baseline, "task_oracle": task_oracle,
       "paired_run_oracle": run_oracle,
       "task_saving_percent": 100 * (baseline - task_oracle) / baseline,
       "run_saving_percent": 100 * (baseline - run_oracle) / baseline})
```

SKILL.md와 설치 사본 SHA-256은 모두 `5de93a4da0a4a8fa7f7c790ee95ef539352ee6dd5c4be5fee8d3254bde5e8230`로 유지된다. Raw trace는 `evals/runs/`에 보존한다. 연구 종료 정리에서 기록된 cohort의 evidence를 Git 제외 대상에서 해제했다. `workspace/`와 새 실행은 계속 제외하며, 기록된 결과를 감사하려면 함께 보존된 raw files를 사용한다.

---

아래는 이전 v2 최적화 단계의 결과이며, 현재 선택 정책은 위 재분석 결론을 따른다.

# SufficePatch v2 최적화 결과 — 비용 목표 미달

기존 24회 raw trace의 122개 tool event를 먼저 분류한 뒤 skill을 변경했다. 새로 58회 실행했고 모두 독립 기능 검사에 통과했다. 최종 v2는 **158단어**(v1 586, Lite 308)다. 단어 수는 frontmatter를 포함한 전체 파일의 공백 분리(`str.split`) 기준이다. hook·dependency·framework 추가는 없다.

**v2는 baseline보다 효율적이라는 목표를 달성하지 못했다.** 확장 8범주 × 2회에서 양쪽 성공률은 16/16이지만, v2 토큰 합계는 +5.36%, median은 +2.20%, tool calls는 65 대 63이다. Lite보다 작고 저렴한 압축본을 최종 파일로 남겼으며, baseline 비용 우위를 주장하지 않는다.

v2 선택은 통과한 후보 중 비용과 지침 크기를 줄이는 선택이다. 규칙 하나하나의 독립적인 인과 효과가 입증됐다는 뜻은 아니다. 안전 하한은 명시적 요구사항이므로 비용을 이유로 제거하지 않았다.

## 같은 8범주의 분포

각 arm은 16회이며 기능 성공 16/16, 독립 assertion group 32/32다. 분산은 표본분산(n−1), 단위는 tokens² 또는 calls²다. 전체 분산에는 과제 간 난이도 차이도 포함한다.

| 조건 | tokens 합계 | 평균 | median | 표본분산 | calls 합계 | 평균 | median | 표본분산 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 859,967 | 53,747.94 | 54,421.00 | 13,630,861.53 | 63 | 3.9375 | 4.0 | 0.1958 |
| Lite (308 words) | 954,580 | 59,661.25 | 56,707.00 | 173,092,696.20 | 72 | 4.5000 | 4.0 | 1.7333 |
| v2 compressed (158 words) | 906,058 | 56,628.62 | 55,617.00 | 73,179,494.78 | 65 | 4.0625 | 4.0 | 0.3292 |

| v2 판정 조건 | 결과 |
|---|---|
| task_success_at_least_baseline | PASS |
| median_tokens_at_most_baseline | FAIL |
| median_tools_at_most_baseline | PASS |

| 보조 지표 | Baseline | Lite | v2 |
|---|---:|---:|---:|
| 관측된 사전 코드 파일 수 (합계) | 43 | 36 | 41 |
| 수정 파일 수 (합계) | 19 | 26 | 22 |
| agent 실행 시간 초 (합계) | 756.417 | 865.051 | 784.368 |
| 추가 LOC (테스트 포함; 최적화 목표 아님) | 66 | 295 | 138 |
| 삭제 LOC | 24 | 24 | 24 |
| raw tool stdout bytes | 17,515 | 30,908 | 21,032 |
| 100k total tokens당 성공 과제 | 1.8605 | 1.6761 | 1.7659 |

`files_read`의 완전한 OS 계측값은 여전히 null이다. 위 사전 코드 파일 수는 편집 전에 내용이나 검색 일치 행이 agent에게 반환된 원본 파일의 고유 개수를 trace에서 수동 확인한 값이다. 목록 조회·runtime import·생성 테스트·후속 diff 읽기는 제외한다. [파일별 감사 목록](forensics.json)에 보존했다. 이를 전체 파일 I/O 횟수로 해석하지 않는다.

세 조건 모두 새 dependency 0개: 실행 명령·수정 경로·결과 Python import를 확인했다. 공통 harness가 설치를 금지하므로 dependency 0을 skill의 독립 효과로 주장하지 않는다. 실제 청구 달러는 제공되지 않아 null이며, total tokens는 input+output이다. 캐시와 reasoning 필드를 다시 더하지 않는다.

## 범주별 결과

각 셀은 **token 평균 = median / 표본분산**이다. 각 범주의 반복 수가 2이므로 평균과 median이 수학적으로 같다. 범주 내 변동을 보려면 분산과 raw 두 값을 함께 봐야 한다. 모든 셀의 성공은 2/2다.

| 범주 / task | Baseline | Lite | v2 |
|---|---:|---:|---:|
| A trivial | 46,891.0 / 91,125,000.0 | 41,512.0 / 1,568.0 | 40,944.5 / 180.5 |
| B localized bug | 54,072.0 / 2.0 | 56,197.5 / 15,664.5 | 55,354.0 / 4,050.0 |
| C existing-code reuse | 54,247.0 / 13,778.0 | 56,370.5 / 35,644.5 | 55,519.0 / 50.0 |
| D multi-file | 54,915.0 / 15,842.0 | 56,982.5 / 10,512.5 | 56,189.5 / 17,484.5 |
| E ambiguous bug | 55,540.5 / 2,112.5 | 88,573.0 / 520,200.0 | 63,368.5 / 97,371,012.5 |
| F security | 54,543.5 / 1,984.5 | 57,106.0 / 71,442.0 | 55,775.0 / 8,450.0 |
| G dependency temptation | 55,744.5 / 2,380.5 | 64,784.0 / 109,224,200.0 | 70,854.5 / 0.5 |
| H refactoring temptation | 54,030.0 / 10,368.0 | 55,764.5 / 24,420.5 | 55,024.0 / 242.0 |

각 셀은 **tool-call 평균 = median / 표본분산**이다.

| 범주 | Baseline | Lite | v2 |
|---|---:|---:|---:|
| A trivial | 3.0 / 0.00 | 3.0 / 0.00 | 3.0 / 0.00 |
| B localized bug | 4.0 / 0.00 | 4.0 / 0.00 | 4.0 / 0.00 |
| C existing-code reuse | 4.0 / 0.00 | 4.5 / 0.50 | 4.0 / 0.00 |
| D multi-file | 4.0 / 0.00 | 4.0 / 0.00 | 4.0 / 0.00 |
| E ambiguous bug | 4.0 / 0.00 | 7.5 / 0.50 | 4.5 / 0.50 |
| F security | 4.0 / 0.00 | 4.0 / 0.00 | 4.0 / 0.00 |
| G dependency temptation | 4.0 / 0.00 | 4.5 / 0.50 | 5.0 / 0.00 |
| H refactoring temptation | 4.5 / 0.50 | 4.5 / 0.50 | 4.0 / 0.00 |

## v1과 원래 6과제의 비교

원래 baseline/v1은 각 6회 단발 실행이다. v2의 아래 6개 값은 새 확장 cohort의 첫 reuse/auth 실행 + 별도 native/shared/atomic/noop 회귀 검증이다. 가장 좋은 반복을 고르지 않았다. 같은 과제의 참고 비교지만 서로 다른 시점/cohort이며, 주 판정은 위 8범주 결과다.

| 원래 6과제 | 성공 | tokens 합계 | 평균 | median | calls 합계 |
|---|---:|---:|---:|---:|---:|
| Baseline (historical) | 6/6 | 343,674 | 57,279.00 | 54,566.50 | 24 |
| User-v1 (historical) | 6/6 | 364,668 | 60,778.00 | 58,036.00 | 28 |
| v2 reference subset | 6/6 | 334,133 | 55,688.83 | 55,677.00 | 23 |

v2는 원래 6개 과제의 토큰 합계에서는 더 낮지만 median은 여전히 높다. 과거 baseline shared의 72,049 tokens가 평균을 끌어올린다. 반면 과거 v1의 +6.1%는 여섯 과제 모두에서 증가했으므로 한 outlier만의 문제는 아니었다.

## 실제 overhead와 실패 행동

- 과거 추가 4 calls: native의 분리된 status +1; shared에서 status +1, 테스트/구현 패치 분리 +1, RED +1, 별도 diff +1, baseline의 bytecode cleanup이 없어진 −1 = shared 순증 +3. 각 event ID/원문/JSONL 위치는 [forensics.json](forensics.json)에 있다.
- v1 raw 탐색 출력은 7,528→3,109 bytes로 줄었으나, 검증/cleanup/함께 실행한 diff 출력은 1,646→38,819 bytes로 늘었다. shared의 RED 출력만 35,211 bytes였다. 상태 확인은 stdout 0이어도 호출 비용이 있다.
- 입력 +20,793, 출력 +201 = 총 +20,994 tokens. 지침은 prompt마다 4,310 bytes가 추가된다. 정확한 지침/탐색/출력/추론/검증별 **토큰** 분해는 보존 로그로 불가능하다. 규칙과 행동의 대응은 증거가 있는 가설이며, 특정 문장이 반드시 그 행동을 유발했다고 단정하지 않는다.
- 같은 v1 shared를 재실행하면 8회가 아닌 4회였다. Lite ambiguous는 7/8회, v2는 4/5회, baseline은 4/4회였다. 고정 workflow 순서를 없애도 분할 읽기는 남았다.
- v2 dependency는 두 반복 모두 `links.py` 뒤에 `reports.py`/`legacy.md`를 따로 읽었다. 5/5 calls, 약 70.9k tokens로 baseline 4/4보다 비쌌다. 명시적 search stop 문장만으로 이 행동이 사라지지 않았다.
- 기능 실패·timeout은 새 58회에서 0이다. 그러나 **효율 기준 실패**는 Lite와 v2 모두에서 발생했다. RED 테스트의 의도된 실패와 최종 기능 실패를 혼동하지 않는다.

## 최종 규칙 결정

| 단위 | 결정 | 최종 상태 / 근거 |
|---|---|---|
| L0–L4 context tiers | SIMPLIFY | 이름과 단계 checklist 제거. 현재 구현/안전 판단을 바꿀 정보만 탐색한다. 단계 이름의 독립 이득은 관측 못함. |
| solution/change/dependency ladders | MERGE | 재사용·표준/native 우선과 필요한 변경이라는 원칙으로 합침. baseline도 동일 기능을 이미 달성했다. |
| over-engineering detector | MERGE | 선택적 helper/refactor/docs/features 제외라는 한 문장. 별도 체크리스트 없음. |
| verification budget | MERGE | 의미 있는 가까운 검사 + 공유 계약/교차 모듈/보안/데이터/실패/프로젝트 요구 때 확대. 문법부터 순차 실행할 의무 없음. |
| conditional test-first ceremony | REMOVE | Lite ambiguous 7/8 calls에서 비용이 재발. 필요한 테스트는 유지하고 테스트 작성/실행 순서는 강제하지 않음. |
| separate plan/review phases | MERGE | 빠른 경로는 read→edit→check→stop. diff 검토를 검증과 함께 수행. |
| safety floor | KEEP | 사용자 필수 조건. auth와 atomic 실패 경로·데이터 보존 회귀 검증 통과. 전체 보안 증명을 의미하지 않음. |
| STOP | KEEP | noop 무변경 검증 통과. optional work를 이어가지 않음. |
| remember/improve/mode/extra-skill instructions | REMOVE | 공통 harness가 memory/hooks를 비활성화했으므로 이 환경에서는 개선 근거 없음. 실사용의 독립 효과는 미측정이며 런타임 기능도 추가하지 않음. |

압축본은 200–350단어 Lite(308단어)가 비용 기준에 실패한 뒤, 더 작은 원칙 중심 후보를 시험한 결과다. 최종 158단어는 단어 수 목표를 맞추기 위해 내용을 늘리지 않았다. 여러 규칙을 함께 없앤 ablation이므로 개별 규칙의 인과 효과는 분리하지 못했다.

## 사용하지 않는 편이 더 효율적인 범위

이 fixture에서는 오타 수정(A)을 제외한 **B–H 모두 v2의 범주 token median이 baseline보다 높았다**. 특히 이미 위치와 구현 방법이 좁혀져 있고 기본 agent가 읽기·수정·가까운 검증을 수행하는 작은 작업은 baseline을 우선한다. URL 처리(G)처럼 표준 API로 명백하게 해결되는 작업에서 재사용 탐색이 오히려 추가 비용이 됐다.

A의 평균 절감도 baseline 한 번이 53,641 tokens를 쓴 영향이 크다. 두 번째 baseline 40,141은 두 v2 실행 40,935/40,954보다 저렴했다. 따라서 오타 작업에서조차 skill 사용을 일반적인 비용 절감법으로 추천하지 않는다. 실무 대규모 저장소나 Claude Code의 성능은 이 결과로 판단하지 않는다.

## 재현과 한계

```sh
python3 -B evals/run.py --selftest
python3 -B evals/run.py --out /tmp/suffice-v2-fresh --arms baseline,suffice --repeats 2 \
  --tasks trivial,localized,reuse,multifile,ambiguous,auth,dependency,refactor
python3 -B evals/run.py --summarize evals/runs/expanded-20261003
python3 -B evals/run.py --summarize evals/runs/compressed-20261003
```

`--summarize`는 model을 호출하지 않는다. 범주별 평균/median/표본분산을 raw 결과에서 재계산한다. 집계 원자료는 [summary.json](summary.json), event 감사는 [forensics.json](forensics.json)이다. raw JSONL·workspace·diff·manifest·실행 당시 runner/tasks는 `evals/runs/`에 남아 있다. 연구 종료 정리에서 기록된 cohort의 raw evidence는 Git 제외 대상에서 해제했다. 재생성 가능한 `workspace/`와 새 실행 디렉터리는 계속 제외한다.

- 동일 Codex CLI/model/effort/fixture/요청/timeout, host skill·plugin·hook·memory 없이 지침만 주입했다. native skill 발견·로드 자체의 비용은 이 비교에 포함하지 않았다. Claude는 형식/설치 호환만 확인한다.
- Baseline/Lite는 순서를 교차했다. 압축 후보는 그 후 별도 cohort에서 실행했으므로 시점/cache/backend 변동이 confounder다. 정밀한 인과/통계적 비열등성 증명이 아니다.
- n=2/category는 변동을 보여주는 작은 synthetic eval이다. 보안·데이터 무결성은 fixture의 계약만 검증한다. 원자적 저장/무변경을 포함한 기존 6과제도 최종 후보로 통과했다.
- 전체 분산과 범주 내 반복 분산을 분리했다. 실패/timeout을 결과에서 지우지 않았으며, 새 실행에서는 발생하지 않았다. 달러 비용과 완전한 파일 I/O 수는 모른다.
- 새 eval 자체는 58회 / 3,299,375 total tokens를 사용했다. 비교 지표는 각 eval agent의 비용이며 이 설계 대화·grader 개발 비용은 제외한다. 후속 지침을 더 붙이며 성공을 주장하는 대신 측정된 실패에서 실험을 종료한다.

---

## 이전 조사·원문 감사 기록

이하의 “최종판 / Final / SufficePatch final”은 당시 **586단어 v1**을 가리킨다.
당시 “v1 / Prototype v1”은 **702단어 초기 prototype**이다. 과거 이름과 미래형 계획 문장은
실험 당시 기록으로 보존하며 현재 버전이나 진행 중인 계획을 뜻하지 않는다.
현재 최종 artifact는 158단어이고, 운영 권고는 위 Always Baseline이다.

# Eval results — 2026-10-03

## 결론

최종판은 6개 synthetic 과제에서 **6/6 task**, 독립 assertion group **16/16** 통과했다. baseline과 핵심 지침 조합 조건도 각각 6/6 통과했다.

최종판의 reported input+output 합계는 **364,668 tokens**다. baseline 대비 **+6.1%**, 지침 조합 대비 **-33.7%**, 초기 prototype 대비 **-12.9%**다.

이번 pilot에서는 baseline이 더 저렴했다. 지침 조합 대비 절감은 관측했지만, baseline보다 우수한 비용 효율은 입증하지 못했다. 실제 plugin 동시 설치 비용이나 달러 절감률을 증명한 것도 아니다.

## 전체 집계

| 조건 | 성공 | 입력 tokens | 출력 tokens | 합계 proxy | 도구 호출 | agent 실행 초 | 성공/100k tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 6/6 | 339,533 | 4,141 | 343,674 | 24 | 297.9 | 1.746 |
| Prototype v1 | 6/6 | 413,571 | 5,094 | 418,665 | 28 | 337.6 | 1.433 |
| SufficePatch final | 6/6 | 360,326 | 4,342 | 364,668 | 28 | 323.6 | 1.645 |
| ECC + Ponytail instructions | 6/6 | 543,827 | 5,924 | 549,751 | 42 | 447.6 | 1.091 |

입력/출력은 CLI가 보고한 누계다. cached input은 입력의 별도 보고 값으로 아래 원자료에 보존하며 proxy에 다시 더하지 않는다. reasoning 필드도 별도 보존한다. 캐시 상태와 가격에 따라 실제 과금 순위는 달라질 수 있다.

| 조건 | 수정 파일 합계 | 전체 LOC + / − | 테스트 LOC + / − | source LOC + / − | 새 dependency |
|---|---:|---:|---:|---:|---:|
| Baseline | 6 | +67 / -6 | +37 / -0 | +30 / -6 | 0 |
| Prototype v1 | 9 | +159 / -6 | +129 / -0 | +30 / -6 | 0 |
| SufficePatch final | 8 | +111 / -6 | +81 / -0 | +30 / -6 | 0 |
| ECC + Ponytail instructions | 9 | +148 / -6 | +116 / -0 | +32 / -6 | 0 |

테스트 증가는 별도 표기한다. 안전성·회귀 방지를 위한 테스트를 지우면 점수가 좋아진다고 해석하지 않는다. files read는 shell 간접 읽기 때문에 정확한 자동 계측이 안 되어 null이다. dependency 0은 diff/import/명령 trace 검토에 근거한다.

## 과제별 비교

| 과제 | Baseline tokens / tools | v1 tokens / tools | Final tokens / tools | 조합 tokens / tools | Final 성공 |
|---|---:|---:|---:|---:|---:|
| reuse | 54,940 / 4 | 73,437 / 5 | 57,901 / 4 | 87,213 / 9 | PASS |
| native | 53,831 / 4 | 58,153 / 4 | 57,473 / 5 | 65,773 / 5 | PASS |
| shared | 72,049 / 5 | 110,033 / 8 | 75,662 / 8 | 109,535 / 7 | PASS |
| auth | 54,313 / 4 | 59,378 / 4 | 58,171 / 4 | 112,605 / 9 | PASS |
| atomic | 54,820 / 4 | 59,723 / 4 | 58,776 / 4 | 109,053 / 9 | PASS |
| noop | 53,721 / 3 | 57,941 / 3 | 56,685 / 3 | 65,572 / 3 | PASS |

`reuse`: 기존 helper 활용. `native`: HTML date picker/label/constraint 보존. `shared`: API/web/export 공통 정상화. `auth`: 비로그인/다른 소유자 거부와 무변경. `atomic`: JSON 저장·실패 시 원본 보존·임시 파일 정리. `noop`: 동작 확인 후 파일 변경 없이 종료.

## Phase 7에서 바꾼 것과 유지한 것

- v1의 알려진 파일까지 탐색부터 하게 만들 수 있는 표현을 고쳤다. 파일을 이미 알면 직접 읽고, 독립적인 읽기/검사를 묶도록 했다.
- 중복 설명을 줄여 702 → 586 words, 5,120 → 4,310 bytes로 축소했다. 조합 instruction 11,685 bytes와 비교하면 63.1% 작다. 이는 파일 크기이며 활성 context token 추정치가 아니다.
- context/change/verification budget, safety floor, STOP은 요청된 핵심 조건이므로 유지했다. 최종판도 같은 6개 과제를 모두 재실행했다.
- hook, rule 사본, mode machine, 자동 memory/learning, 추가 agent, model router, runtime script는 추가하지 않았다. 관측된 이득을 위해 필요하지 않았다.
- 단일 요소의 인과 효과를 입증한 ablation은 아니다. 개별 budget의 성능 기여를 확정하지 않는다. runtime 원칙과 측정된 패키지 결과를 구분한다.

## 재현과 한계

- Codex CLI 0.160.0, model `gpt-6-astra`, effort `low`. 같은 task source hash: `15533796b36e5157b940688959cdd1496950ae88a993a57d9f3ef382b5cc8a9f`.
- v1 skill SHA-256: `e69ed461e626507f807abfd46e57ad0cd7f832d5ab8f72b90a493c5f17f1efe9`. Final: `36f9f42bec37e9fc93ae981c3567e34e089c0ea564f10ce47fc9a5d938783ca5`.
- Round 1: 6 tasks × 3 arms × 1회 = 18 runs, arm 순서 회전. Round 2: final만 같은 6개 task로 6회 재검증. 총 24개 채점된 실행을 보존했다.
- Final은 개발에 사용한 동일 task set에서 후속 실행했다. holdout·다중 model·통계적 유의성·보편적 우월성은 입증되지 않았다. Round 2는 baseline을 동시에 재실행하지 않았으므로 시간/cache 변동의 영향도 남는다.
- combined는 upstream에서 선택한 세 지침의 수동 주입이다. 전체 ECC/Ponytail plugin의 자동 로딩·hooks·MCP·memory·각종 profile을 재현하지 않는다.
- 실제 Claude Code 실행 eval은 하지 않았다. 동일 SKILL.md의 표준 형식과 공식 설치 경로로 호환 설치하며, Codex native `skills/list`에서 user scope와 enabled 상태를 확인했다. [설치 검증 기록](installation.json).
- synthetic Python/HTML, 주로 L1–L2의 작은 범위다. HTML 검사는 실제 browser 렌더링/키보드 테스트를 대체하지 않는다. 대규모 architecture, production 보안, 장기 memory에는 외삽하지 않는다.
- 성공에는 정상 agent 종료, 독립 correctness 검사, 무관한 fixture 보존, no-op 무변경이 포함된다. 실패/timeout을 결과에서 제거하는 로직은 없다. 이번 채점된 실행에는 실패가 없었다.
- API 연결 확인과 Git fixture 없는 초기 setup 실행 1건은 성능 실험 밖이다. 후자는 중단 후 Git fixture를 갖춘 새 디렉터리에서 모든 조건을 시작했다. setup 비용을 0으로 주장하지 않는다.
- model seed/서버 부하/cache는 완전히 통제하지 못한다. 실제 USD와 정확한 파일 읽기 수는 null이며 성공률을 희생해 비용을 낮추지 않는다.

## 원자료

- [집계 JSON](summary.json)
- [Round 1 manifest](runs/git-pilot-20261003/manifest.json), [결과](runs/git-pilot-20261003/results.json)
- [Final manifest](runs/final-20261003/manifest.json), [결과](runs/final-20261003/results.json)
- 각 run 폴더에 `events.jsonl`, `stderr.log`, `changes.diff`, `result.json`, 최종 `workspace/`를 보존했다.
- [초기 prototype](prototype-v1.md), [eval runner](run.py), [fixture와 독립 grader](tasks.py)
- 재실행은 README의 명령을 사용한다. 당시 초기 prototype은 `--skill evals/prototype-v1.md`, 이후 586단어 v1은 `--skill evals/v1.md`로 선택한다.



## v2 optimization: historical forensics (before edits)

Current user-v1 is the 586-word, 4,310-byte root SKILL (SHA256
`36f9f42bec37e9fc93ae981c3567e34e089c0ea564f10ce47fc9a5d938783ca5`).
The older 702-word `prototype-v1.md` is called **prototype** here to avoid ambiguity.
`v1.md` preserves the user-v1 exactly. The complete event-by-event audit is
[forensics.json](forensics.json): 24 runs, 122 completed tool events, original
trace path + JSONL line + item ID, command, output bytes, classification and reason.
Classification is a contextual judgment, not proof of a counterfactual minimum.
Mixed shell calls receive one primary class; speculative subactions remain visible.

| Historical arm | ESSENTIAL | USEFUL | REDUNDANT | SPECULATIVE (whole call) | OVER-VERIFICATION |
|---|---:|---:|---:|---:|---:|
| Baseline |17|7|0|0|0|
| Prototype |19|9|0|0|0|
| User-v1 |17|11|0|0|0|
| ECC+Ponytail core instructions |18|19|2|0|3|

Extra four calls, aligned rather than guessed:

- **native +1:** final `item_2` / line 7 is standalone `git status --short`, absent
  in baseline. Relevant read, patch and behavioral check otherwise align.
- **shared +3 net:** standalone status **+1**; separate test and implementation
  patches **+1**; pre-fix RED run **+1**; post-test diff-only call **+1**; baseline's
  bytecode cleanup absent **−1**. Both still have initial listing, relevant reads,
  implementation and successful behavioral verification. See baseline items
  1/2/4/5/6 versus final items 1/2/3/5/6/7/8/9.
- Shared v1's RED output is **35,211 UTF-8 bytes**; baseline has no RED run.
  This is USEFUL diagnostic evidence, not a repeated already-passing test.
  There is no evidence that removing required shared-caller regression coverage
  would be safe; the candidate removes ceremonial sequencing, not that coverage.
- Both arms still list already-known paths. v1 avoids baseline's unrelated
  `legacy.md` reads on reuse/shared, yet fails to reduce total calls.

Token attribution (observed, not invented causal percentages):

| Measurement | Baseline | User-v1 | Delta |
|---|---:|---:|---:|
| Input tokens |339,533|360,326|+20,793|
| Output tokens |4,141|4,342|+201|
| Total tokens |343,674|364,668|+20,994 (+6.109%)|
| Tool output bytes |9,174|43,520|+34,346|
| Visible command bytes |6,396|4,172|−2,224|
| Visible message bytes |3,018|3,192|+174|
| Reasoning-output tokens (subset, not added again) |169|184|+15|

SKILL input overhead is 4,310 bytes per injected prompt versus zero; all six v1
runs use more tokens, including four with unchanged tool-call counts. This is
consistent with instruction/history overhead, but **not an exact attribution**.
The CLI only records aggregate turn usage, not per-model-request input and
reasoning/tool-output token attribution. Raw persisted stdout may also differ from the truncated tool text presented to the model. Bytes are not tokens; repeated history,
cache reuse, tool batching, model variability and different rounds prevent
splitting +20,994 exactly into instruction/exploration/verification/reasoning.
The 35KB RED output is an observed verification-output increase; relevant read
output falls in reuse/shared. We do not allocate the unexplained remainder by
assumption or fit a causal percentage to six samples.

Rule links are hypotheses tested by ablation, not hidden-thought claims:
`Preserve ... unrelated changes` aligns with state checks; `Reproduce bugs/add
regression tests first` aligns with shared RED + split patches; `Review the diff`
aligns with a separate diff call. `Batch independent reads` did not prevent those
calls. No log names a rule as its reason, so individual rule causality is unknown.

| Unit | Candidate decision | Evidence / reason |
|---|---|---|
| L0–L4 context ladder | SIMPLIFY | No architecture case in old suite; named levels add text without observable benefit. Keep uncertainty-driven scope expansion. |
| Solution + change ladders | MERGE | All arms reuse helper/native UI; duplicate ordering has no demonstrated gain. |
| Detector | MERGE | Preserve necessity gate in reuse rule, omit repeated checklist. |
| Verification ladder | SIMPLIFY | Keep meaningful nearest check and explicit broadening triggers; avoid mandatory syntax→test sequence. |
| Safety floor | KEEP | auth/atomic checks exercise denial and data preservation. Safety is a constraint even without measured savings. |
| STOP | KEEP | noop remains unchanged; prohibit post-completion optional work. Incremental causal benefit unproven. |
| TDD ordering | SIMPLIFY | shared adds RED output and split calls; retain pre-fix evidence when cause/coverage is uncertain. |
| Plan ceremony | REMOVE | Trivial tasks require no separate artifact; keep mental plan. |
| Search stop + escalation | MERGE | Stop unless a missing fact can change implementation or safety. |
| Memory/improve/mode restrictions | REMOVE | No relevant action in 24 traces; platform rules still apply. |

The candidate is a bundled ablation; individual effects cannot be isolated by
this sample. No safety rule is dropped because the sample happens to pass.

Pre-registered comparison: diagnostic native/shared tasks compare archived v1,
Lite, and a single-principle compression once each. Independent expanded set uses
8 categories × baseline/Lite × 2 repeats, interleaved arm order, same model/effort,
fresh Git fixture, independent hidden behavioral graders, no hooks/dependencies.
The candidate is frozen before expanded results; no winner selection on those
results. Two repeats describe variability but do not establish statistical power.

Historical paired task totals (same tasks, different rounds; n=1 each):

| Task | Baseline tokens / calls | v1 tokens / calls | Token delta |
|---|---:|---:|---:|
| atomic | 54,820 / 4 | 58,776 / 4 | +3,956 |
| auth | 54,313 / 4 | 58,171 / 4 | +3,858 |
| native | 53,831 / 4 | 57,473 / 5 | +3,642 |
| noop | 53,721 / 3 | 56,685 / 3 | +2,964 |
| reuse | 54,940 / 4 | 57,901 / 4 | +2,961 |
| shared | 72,049 / 5 | 75,662 / 8 | +3,613 |

Historical distribution across heterogeneous tasks (sample variance, tokens² / calls²; **not** repeat variance):

| Arm | Token mean | Token median | Token variance | Call mean | Call median | Call variance |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 57,279.00 | 54,566.50 | 52,603,145.20 | 4.00 | 4.00 | 0.40 |
| combined | 91,625.17 | 98,133.00 | 486,242,828.17 | 7.00 | 8.00 | 6.40 |
| prototype | 69,777.50 | 59,550.50 | 423,674,304.70 | 4.67 | 4.00 | 3.07 |
| v1 | 60,778.00 | 58,036.00 | 53,658,142.40 | 4.67 | 4.00 | 3.07 |

## Diagnostic ablation results

All six attempts passed. Same two tasks and configuration; one run per arm/task.
The compressed instruction was 46 words (body only; exact text is archived in the manifest).

| Task | v1 tokens / calls | Lite tokens / calls | Compressed tokens / calls |
|---|---:|---:|---:|
| native | 57,591 / 4 | 56,054 / 4 | 54,541 / 4 |
| shared | 59,239 / 4 | 72,855 / 5 | 55,711 / 4 |

Lite is **not** the diagnostic winner: its shared run adds a bytecode-cleanup call, while the fresh v1 and compressed runs both finish in four calls. Historical v1 shared needed eight calls. This directly demonstrates stochastic behavior and prevents a claim that a specific v1 sentence necessarily causes four extra calls. The compressed candidate has no observed quality failure in these two cases, but this diagnostic is not a broad safety/noninferiority evaluation. The frozen Lite candidate proceeds to the pre-registered eight-category comparison; its results will not be hidden if worse.


Diagnostic-triggered extension, declared before completing the expanded Lite
cohort: the 46-word body-only diagnostic won both tasks, so a deployable compressed
candidate (frontmatter, explicit fast path, complete safety floor) will also run
8 categories × 2 repeats after the Lite cohort. Exact injected text is
`compressed.md` and is frozen before those runs. This is a separate, later cohort,
not interleaved with baseline; time/cache/backend drift and exploratory selection
limit causal/generalization claims. The 46-word diagnostic is not presented as
identical to the deployable candidate. No added runtime mechanism is involved.

Raw output bytes grouped by mixed-call purpose (not a tokenizer attribution):

| Purpose | Baseline | v1 |
|---|---:|---:|
| edit | 0 | 0 |
| exploration_including_metadata_and_batched_state | 7,528 | 3,109 |
| review | 0 | 1,592 |
| state | 0 | 0 |
| verification_or_cleanup_including_batched_review | 1,646 | 38,819 |

The state-only calls produce zero stdout but still cost a tool invocation; output bytes alone miss this overhead. Mixed verification calls also contain diff output, so review and verification tokens cannot be separated exactly.

Telemetry limit checked locally: `codex exec --help` defines `--ephemeral` as not persisting session files. All benchmark commands use that flag; an exact diagnostic thread-ID lookup found no saved session. Thus historical per-request token attribution cannot be recovered from these retained artifacts; aggregate usage and command/output evidence are the available measurements.

A completed CLI tool item is **not** necessarily a separate model request: tool calls can be batched. Expanded trivial baseline runs both have 3 tool items but use 53,641 versus 40,141 tokens. We therefore do not multiply tool-item count by instruction tokens to claim exact instruction overhead.

## Expanded Lite comparison (completed, rejected for cost)

Both conditions pass 16/16 tasks and 32/32 independent assertion groups.

| Arm | Tokens total | Mean | Median | Sample variance (tokens²) | Calls total | Mean | Median | Sample variance (calls²) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 859,967 | 53,747.94 | 54,421.00 | 13,630,861.53 | 63 | 3.9375 | 4.0 | 0.1958 |
| suffice | 954,580 | 59,661.25 | 56,707.00 | 173,092,696.20 | 72 | 4.5000 | 4.0 | 1.7333 |

Lite fails the requested median-token criterion. It is kept as an experimental ablation artifact, not claimed as the winning v2.

Observed failures of efficiency:

- `1-dependency-suffice` adds a pure speculative `cat reports.py; cat legacy.md` after reading the relevant implementation. The second repeat omits it.
- `1-ambiguous-suffice` uses split exploration + RED/GREEN (7 calls); repeat 2 adds a redundant symbol search and separates diff review (8 calls). Baseline uses 4 calls in each repeat.
- Both localized Lite runs use 4 calls, matching baseline, but pay instruction overhead.
- Trivial baseline varies from 53,641 to 40,141 tokens at the same 3-call count, demonstrating why one favorable run cannot prove the skill caused the saving.


---

<a id="upstream-research"></a>

## 초기 upstream·이름 조사 기록 — 2026-10-03

이하 내용은 최초 README에서 옮긴 조사 기록이다. 이번 종료 정리에서 upstream을 새로 조사한 것이 아니며,
현재 구조·이름 충돌 현황이나 성능 우위를 주장하지 않는다. runtime skill의 효율 결과와 구분한다.


최신 기본 브랜치를 shallow clone한 뒤 아래 커밋으로 고정했다. upstream 코드는 이 프로젝트에
vendoring하지 않았다. 두 upstream 모두 MIT이며, 여기서는 원칙을 독립적으로 재서술했다.

- [ECC ef648e0](https://github.com/affaan-m/ECC/tree/ef648e01899ba3e8dc6371642deaaf64b4477775), manifest 2.2.3.
  실제 `skills/*/SKILL.md` 293개, `agents/` 파일 68개, `rules/` 파일 122개.
  Codex manifest 설명의 281은 실제 파일 수와 다르므로 그대로 인용하지 않았다.
- [Ponytail c982cd4](https://github.com/dietrichgebert/ponytail/tree/c982cd411abb53323c4baa1baa3c2f020b8d0b08), manifest 4.10.3.
  root `SKILL.md`는 없으며 `skills/` 아래 6개 skill, root `AGENTS.md`, platform별 rule 사본과 hook이 있다.

| 조사 대상 | 확인한 구조와 의미 | 채택 / 제외 |
|---|---|---|
| [ECC development-workflow](https://github.com/affaan-m/ECC/blob/ef648e01899ba3e8dc6371642deaaf64b4477775/rules/common/development-workflow.md) | research/reuse → planner → RED/GREEN/refactor → code review → commit/check. 여러 계획 문서와 80% coverage를 요구 | 의도·계획·회귀 검증 채택. 매번 문서/coverage 목표/commit 요구 제외 |
| [ECC agents](https://github.com/affaan-m/ECC/tree/ef648e01899ba3e8dc6371642deaaf64b4477775/agents) | planner, tdd-guide, code-reviewer가 역할별 frontmatter와 절차를 가짐. reviewer는 구체적 실패 근거, 주변 코드, zero findings 허용 | 근거 중심 diff review 채택. 매번 별도 agent 호출 제외 |
| [ECC verification-loop](https://github.com/affaan-m/ECC/blob/ef648e01899ba3e8dc6371642deaaf64b4477775/skills/verification-loop/SKILL.md) | build/type/lint/coverage/security grep/diff의 6단계 | 증거 기반 완료 채택. 고정 전체 pipeline은 영향 범위에 따른 escalation으로 축소 |
| [ECC search-first](https://github.com/affaan-m/ECC/blob/ef648e01899ba3e8dc6371642deaaf64b4477775/skills/search-first/SKILL.md) | repo, registries, MCP, skills, GitHub를 탐색하고 adopt/extend/compose/build 판단 | 재사용 조사 채택. 외부 검색은 local evidence 부족 시만 |
| [ECC context-budget](https://github.com/affaan-m/ECC/blob/ef648e01899ba3e8dc6371642deaaf64b4477775/skills/context-budget/SKILL.md), [strategic-compact](https://github.com/affaan-m/ECC/blob/ef648e01899ba3e8dc6371642deaaf64b4477775/skills/strategic-compact/SKILL.md) | 전자는 로드된 구성의 비용 audit; 후자는 phase 전환과 transcript token/tool-count 기반 compact 제안 | 비용 인식 채택. L0–L4는 이 프로젝트의 설계이며 upstream 기능으로 주장하지 않음 |
| [ECC memory hooks](https://github.com/affaan-m/ECC/blob/ef648e01899ba3e8dc6371642deaaf64b4477775/hooks/memory-persistence/README.md), [session-start.js](https://github.com/affaan-m/ECC/blob/ef648e01899ba3e8dc6371642deaaf64b4477775/scripts/hooks/session-start.js) | SessionStart 제한 context(기본 8,000자), PreCompact, SessionEnd, tool observation. profile/opt-out 지원 | 명시적으로 요청된 교훈만 기존 memory 경로로. 자동 transcript 저장 제외 |
| [ECC continuous-learning-v2](https://github.com/affaan-m/ECC/blob/ef648e01899ba3e8dc6371642deaaf64b4477775/skills/continuous-learning-v2/SKILL.md) | hook 관찰 → project별 observations → observer → confidence instinct → evolve/promote. v1은 deprecated | eval로 개선한다는 원칙만 채택. observer/instinct DB/self-modification 제외 |
| [ECC evaluate-session.js](https://github.com/affaan-m/ECC/blob/ef648e01899ba3e8dc6371642deaaf64b4477775/scripts/hooks/evaluate-session.js) | 구형 Stop evaluator 실제 코드는 message count를 검사하고 학습 평가 안내를 출력; 스스로 학습 결과를 생성하지 않음 | 문서의 자동 학습 설명과 실제 실행 기능을 구분 |
| [ECC agentic-engineering](https://github.com/affaan-m/ECC/blob/ef648e01899ba3e8dc6371642deaaf64b4477775/skills/agentic-engineering/SKILL.md) | 완료 조건 → baseline eval → 구현 → 재평가; token/retry/time/success 추적 | 성공률 우선 비용 비교 채택. 자동 model routing 제외 |
| [ECC Codex manifest](https://github.com/affaan-m/ECC/blob/ef648e01899ba3e8dc6371642deaaf64b4477775/.codex-plugin/plugin.json), [Codex hooks](https://github.com/affaan-m/ECC/blob/ef648e01899ba3e8dc6371642deaaf64b4477775/hooks/codex-hooks.json) | 공유 skills + MCP + SessionStart 1개. Claude hook graph에는 7개 event 종류. repo `.agents/skills`, `.codex/AGENTS.md`, config도 별도 존재 | 공통 SKILL.md frontmatter만 사용. 두 host의 hook 동등성 가정 제외 |
| [Ponytail main skill](https://github.com/dietrichgebert/ponytail/blob/c982cd411abb53323c4baa1baa3c2f020b8d0b08/skills/ponytail/SKILL.md), [AGENTS.md](https://github.com/dietrichgebert/ponytail/blob/c982cd411abb53323c4baa1baa3c2f020b8d0b08/AGENTS.md) | 요청에 제시된 7단 ladder가 실제로 존재. 실제 흐름과 caller를 이해한 뒤 최소 해법 선택. safety/접근성/검증 보존 | ladder, root cause, safety floor 채택. one-liner 강박과 요구사항 축소는 제외 |
| [Ponytail hooks](https://github.com/dietrichgebert/ponytail/blob/c982cd411abb53323c4baa1baa3c2f020b8d0b08/hooks/claude-codex-hooks.json), [mode tracker](https://github.com/dietrichgebert/ponytail/blob/c982cd411abb53323c4baa1baa3c2f020b8d0b08/hooks/ponytail-mode-tracker.js) | SessionStart/SubagentStart/UserPromptSubmit. lite/full/ultra/off, env/config 기본값, session 상태, mode별 instruction filtering | mode와 반복 주입 제외. 일반 skill 호출 수명 사용 |
| [Ponytail review](https://github.com/dietrichgebert/ponytail/blob/c982cd411abb53323c4baa1baa3c2f020b8d0b08/skills/ponytail-review/SKILL.md), [audit](https://github.com/dietrichgebert/ponytail/blob/c982cd411abb53323c4baa1baa3c2f020b8d0b08/skills/ponytail-audit/SKILL.md) | diff/whole-repo 복잡성 보고. correctness/security/performance는 명시적으로 범위 밖이며 fix 적용 안 함 | 불필요한 구성 detector 채택. 이 검사를 correctness review 대용으로 쓰지 않음 |
| [Ponytail agentic benchmark](https://github.com/dietrichgebert/ponytail/blob/c982cd411abb53323c4baa1baa3c2f020b8d0b08/benchmarks/agentic/README.md) | 실 agent + seeded repo + baseline. LOC와 안전성/완성도를 구분하고 good/bad reference로 grader 검증 | 실제 파일·독립 correctness gate 채택. upstream 절감 수치를 우리 효과로 재사용하지 않음 |

**ECC의 7단 흐름 판정:** plan/test/implement/review는 규칙과 agent에,
verify는 skill/hook에, remember/improve는 persistence/learning/eval에 분산되어 있다.
`plan → test → implement → review → verify → remember → improve` 전체를 강제하는
하나의 실행 state machine으로 보기는 어렵다. 설정·host·hook profile·실제 호출 여부에 따라 달라진다.

**충돌 해결:** research-first는 minimum sufficient research로, 항상 TDD/full verification은
위험에 맞는 증거로, 자동 remember/improve는 별도 요청 작업으로 바꿨다. Ponytail의 최소 구현
리뷰에 ECC의 correctness/security review를 합쳐 안전 검사를 빠뜨리지 않는다.

## 이름 조사

2026-10-03 GitHub repository search(`NAME in:name`, 최대 3개 대표 결과), 선택 이름은 npm/PyPI도 확인.
검색은 부분 일치도 포함하므로 결과 수는 정확한 동명 상표 수가 아니다. 공개 검색 범위의 충돌 점검이며
이름 독점·상표 안전을 보장하지 않는다. 원자료: [name-search.json](name-search.json).

| 후보 | 의미 | 관측한 충돌 |
|---|---|---|
| LeanAgent | 가벼운 agent | 16개; lean-dojo/LeanAgent, coding workflow 유사 이름도 존재 |
| MinContext | 최소 context | 5개; agent context 최소화 도구 존재 |
| SmallStep | 작은 단계 | 303개; smallstep 인증서/CLI 생태계와 충돌 |
| JustEnough | 필요한 만큼 | 154개; JustEnoughItems 등 다수 |
| Needle | 좁고 정밀한 수정 | 5,257개; Cactus 모델, Uber framework 등 |
| Occam | 단순한 해법 | 607개; 다수 software 이름 |
| LeanLoop | 가벼운 검증 loop | 13개; AI task delegation 프로젝트 존재 |
| Scopepin | 범위 고정 | 1개; browser context 도구 존재 |
| Patchlight | 가벼운 patch | 55개; 다수 동명 저장소 |
| **SufficePatch** | 충분한 변경에서 멈춤 | GitHub 0개, `suffice-patch` npm/PyPI 404. 선택 |

추가 검토한 Proofstep은 AI eval 프로젝트와 겹쳤고 ScopeLatch는 기존 제품이 있어 제외했다.
처음 선택 이름 검색에 rate limit이 있었으나 재조회로 GitHub 0건을 확인했다.
