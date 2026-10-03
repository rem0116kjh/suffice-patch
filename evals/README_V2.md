# SufficePatch

**Can an explicit minimalism skill make a modern coding agent cheaper without reducing task success?**

ECC와 Ponytail의 핵심 원칙을 압축한 coding-agent skill을 추가했을 때의 효과를
측정한 연구·실험 프로젝트다. **최적화 실험은 종료했다.**

| 조건 | Task success | Total tokens | Median tokens | Tool calls |
|---|---:|---:|---:|---:|
| Baseline | 16/16 | 859,967 | 54,421 | 63 |
| SufficePatch v2 | 16/16 | 906,058 | 55,617 | 65 |
| Zero-cost token oracle — 사후 계산 | 16/16¹ | 847,261–848,074 | 54,421 | 63 |

¹ Oracle은 기존 성공 실행들을 사후 선택한 계산이다. 새로운 실행 조건이나 실제 router가 아니다.
범위의 하한은 실행별 선택, 상한은 과제별로 같은 arm을 선택한 결과다.

**SufficePatch preserved task success but did not outperform the baseline agent on efficiency.**

Even a zero-cost perfect oracle could only improve token usage by approximately **1.4%**
on these recorded outcomes. Therefore the project recommends **Always Baseline for the tested environment**.

SufficePatch is not presented as an optimization that beat the baseline.
**The experiment found the opposite in the tested environment.**

v2는 baseline보다 합계 tokens **+5.36%**, median **+2.20%**, tool calls **+2**였다.
이 결과를 더 큰 지침 조합과의 비교로 가리거나 다른 환경의 성능으로 일반화하지 않는다.
[상세 결과·평균·median·분산](evals/EVAL_RESULTS.md)과 [집계 JSON](evals/summary.json)을 함께 제공한다.

## Evolution

```text
ECC + Ponytail 핵심 지침
  ↓
SufficePatch v1 — 586 words
  ↓
SufficePatch Lite — 308 words
  ↓
SufficePatch v2 — 158 words
  ↓
Adaptive routing hypothesis
  ↓
Oracle analysis
  ↓
STOP
```

| 단계 | 실제 관측과 다음 단계로 간 이유 |
|---|---|
| ECC + Ponytail | 초기 동일 6과제에서 선택한 핵심 지침 조합은 6/6 성공, 549,751 tokens, 42 calls였다. Baseline은 6/6, 343,674 tokens, 24 calls였다. 원칙을 작은 skill로 추출한다는 가설의 대조군이며, 전체 plugin 동시 설치를 평가한 것은 아니다. |
| v1 — 586 words | 같은 6과제에서 6/6, 364,668 tokens, 28 calls. 조합보다 토큰은 적었으나 baseline보다 +6.11%, calls +4여서 추가 행동의 원인을 감사하고 지침을 압축했다. |
| Lite — 308 words | 8과제 × 2회로 확장하자 16/16, 954,580 tokens, 72 calls. 같은 주 비교의 baseline 859,967 tokens / 63 calls를 넘어서 더 작은 후보를 시험했다. |
| v2 — 158 words | 16/16, 906,058 tokens, 65 calls. 성공률을 유지했지만 baseline 비용 목표에 실패했다. 더 줄이는 대신 선택적 활성화가 유효한지 질문을 바꿨다. |
| Adaptive hypothesis | 기본값을 baseline으로 두고 도움이 되는 요청에만 skill을 켠다는 가설을 세웠다. 구현 전에 기존 결과로 달성 가능한 상한을 계산했다. |
| Oracle analysis | 과제별 oracle 848,074 tokens(−1.38%), 실행별 oracle 847,261(−1.48%). 유일한 평균 이득은 오타 과제의 baseline 한 번 높은 사용량에 집중됐고, 반복 간 방향도 뒤집혔다. |
| STOP | 사전에 요청된 “최대 절감이 약 1–2%라면 중단”을 ≤2% gate로 적용했다. 이는 통계적 유의성 기준이 아니다. Router·추가 stress eval을 만들지 않았고, skill 최적화도 종료했다. |

v1 이전의 [702단어 prototype](evals/prototype-v1.md)은 초기 6과제에서 6/6,
418,665 tokens, 28 calls였다. 이후 586단어 v1에서 tokens는 줄었지만 baseline을 넘어서지는 못했다.
Prototype도 보존했다. 초기 24회에는
baseline·prototype·v1·핵심 지침 조합이 포함된다. 이후 58회는 진단 6회,
baseline/Lite 32회, v2 16회, 별도 회귀 4회다. **현재 baseline/v2의 직접 대응 비교는
8과제 × 2회 × 두 조건 = 32회**다. 서로 다른 task set의 합계를 하나의 성능 추세로 비교하지 않는다.
단어 수는 frontmatter를 포함한 전체 파일의 `str.split()` 기준이다.

## Observed

- 채점된 task success는 비교 조건 간 동일했다. 주 비교의 baseline, Lite, v2는 각각 16/16이다.
- 명시적 skill 지침을 넣은 조건의 aggregate token usage가 baseline보다 높았다.
- 주 비교에서 tool calls 합계는 baseline 63, Lite 72, v2 65로 감소하지 않았다.
- SKILL.md를 586 → 308 → 158단어로 줄였어도 각 비교에서 baseline 우위가 뒤집히지 않았다.
- 반복 모두에서 token 이득을 보인 task category는 없었다. 평균 기준 분류는 WIN 1 / NEUTRAL 1 / LOSS 6이며, WIN은 불안정했다.
- 기록된 결과에서 zero-cost oracle의 token 절감 여유는 약 1.4%였다. 두 token oracle 모두 median과 calls를 개선하지 않았다.

이 항목들은 관측 결과의 기술이며, 특정 문장이 overhead를 유발했다는 인과 증명이 아니다.
과제별 원값과 분류 기준은 [EVAL_RESULTS.md](evals/EVAL_RESULTS.md)에 있다.

## Interpretation — 검증되지 않은 해석

Modern coding agents **may** already contain enough minimal-change behavior that an
additional explicit skill duplicates existing behavior. 이는 가능한 해석이지, agent 내부
학습 내용이나 모든 modern model에 대해 증명한 사실이 아니다.

추가 지침의 처리 비용, 탐색·검증 분할 방식, 공통 harness 제약, 실행 변동이 결과에
기여했을 수도 있다. 여러 규칙을 함께 바꿨고 request별 token 분해가 없어 각 요인의
독립 효과를 확정할 수 없다. 다른 모델·대형 저장소·조직 정책에서 가치가 있을 것이라는
주장도 별도 evidence 없이 이 프로젝트의 결과로 내세우지 않는다.

## Reproducibility

### Baseline과 실행 조건

Baseline은 같은 Codex agent에 **공통 작업 지침과 동일 task request**를 주고,
추가 skill workflow를 주입하지 않은 조건이다. 공통 지침 자체에는 local checks,
무관한 변경 보존, dependency 설치·네트워크·다른 디렉터리 접근·agent spawning 금지가 있다.
기본 agent도 이 제약을 받으므로 “아무 지침도 없는 모델”의 성능을 측정한 것은 아니다.
정확한 prompt 구성은 [run.py의 COMMON과 run_one](evals/run.py)에 있다.

| 항목 | 기록된 조건 |
|---|---|
| Host / runner | macOS Apple Silicon, Python standard library, Git fixture, Codex CLI 0.160.0 |
| Model / effort | `gpt-6-astra` / `low` |
| Agent timeout | 실행당 240초; 실패와 timeout도 시도 분모에 포함 |
| Isolation | 실행마다 별도의 초기 Git fixture; `workspace-write`, `approval_policy=never` |
| 추가 context | user config 무시, host skill discovery·plugin·hook·app·memory·multi-agent 비활성화, project doc bytes 0 |
| Skill 주입 | 파일 내용을 prompt에 직접 주입. Native skill 발견·자동 활성화 비용은 측정하지 않음 |
| 실행 순서 | Baseline/Lite는 task·반복별 arm 순서 회전. 최종 v2는 그 후 별도 cohort에서 실행 |
| 보존 기록 | manifest의 model/effort/정확한 지침/파일 hashes, 실행별 command/prompt hash/events/result/diff |

주 비교 task 정의와 grader는 [tasks.py](evals/tasks.py)에 있다.

| 범주 | Task | 검증 대상 |
|---|---|---|
| A trivial | `trivial` | 제목 오타, subtitle/render 보존 |
| B localized bug | `localized` | 마지막 chunk와 입력 경계 |
| C existing-code reuse | `reuse` | web과 동일한 고객 이름 표시 |
| D multi-file | `multifile` | API/CSV currency 계약과 escaping |
| E ambiguous bug | `ambiguous` | 통화별 cache 분리와 재사용 |
| F security-sensitive | `auth` | 수정 권한과 거절 시 데이터 보존 |
| G dependency temptation | `dependency` | URL query encoding과 기존 query/fragment 보존 |
| H refactoring temptation | `refactor` | 누락된 colon과 다른 로그 동작 보존 |

각 과제는 조건별 두 번 실행했다. `native`, `shared`, `atomic`, `noop`도 정의에 남아 있으며
초기 평가·별도 회귀에 사용했다. G/H라는 범주명은 실험자의 설명이다. G는 설치가 금지된
작은 URL utility이고 H는 colon 수정이므로, 실제 dependency 선택이나 broad refactor stress를
검증했다고 해석하지 않는다.

### 성공 기준과 측정 방법

**Task success**는 정상 agent 종료, timeout 없음, 완료 usage 기록, 모든 독립 assertion group 통과,
보호된 무관 fixture 보존, 해당 시 no-op 무변경을 모두 요구한다. Agent의 자기 평가를 점수로
쓰지 않는다. 각 assertion group은 작업 후 별도 Python process에서 실행한다. 이 결과는 fixture
계약에 대한 성공이며 production 보안·접근성 전체를 증명하지 않는다.

v2의 채택 목표는 `task success ≥ baseline`, `median tokens ≤ baseline`,
`median tool calls ≤ baseline`을 모두 만족하는 것이었다. 성공과 call median 기준은 통과했지만
**token median 기준에 실패**했다. 이후 oracle gate도 통과하지 못했다.

| 지표 | 정의 / 한계 |
|---|---|
| Total tokens | `turn.completed.usage`의 reported input + output을 합산. cached input과 reasoning을 다시 더하지 않음. usage 누락은 null |
| Tool calls | `item.completed`에서 `agent_message`, `reasoning`, `error`를 제외한 항목 수. 묶은 shell subcommands는 하나의 event; patch도 포함. 모델 request 수와 같다고 가정하지 않음 |
| Files read | 완전한 OS I/O 계측은 null. 편집 전 원본 내용/검색 일치 행이 반환된 고유 파일 수만 `observed_context_files`로 수동 감사 |
| Files modified / LOC | 전후 snapshot diff; Git/cache 산출물 제외. 테스트 LOC 별도 집계. LOC 자체는 성공 목표가 아님 |
| Execution time | CLI 시작부터 종료까지의 wall clock; fixture setup·독립 채점 제외 |
| Mean / median / variance | 실행별 값의 기술 통계; 분산은 표본분산(n−1). 전체 분산에는 task 간 차이도 포함 |
| Cost | Tokens는 비용 proxy다. 실제 API billing dollars는 null. 설계 대화·연구·grader 개발 비용은 비교에 포함하지 않음 |

같은 성공률에서 비용을 비교하며 실패 비용을 제외하지 않는다. 시간·tokens·calls·LOC를
임의 가중치로 더한 단일 점수는 사용하지 않았다.

### 원자료와 버전

| 자료 | 내용 |
|---|---|
| [EVAL_RESULTS.md](evals/EVAL_RESULTS.md) | 최종 판정, 과제별 분포, oracle, break-even, 실험 과정과 한계 |
| [summary.json](evals/summary.json) | 과거 집계, `v2_optimization`, `v2_decision`, `adaptive_gate`의 58회 inventory·oracle·원자료 hashes |
| [forensics.json](evals/forensics.json) | 초기 24회에서 완료된 122개 tool event의 분류·원문 위치, 후속 읽기 proxy 감사. 필요성 분류는 문맥에 따른 판단이며 반사실적 증명이 아님 |
| [v1.md](evals/v1.md), [lite.md](evals/lite.md), [compressed.md](evals/compressed.md) | 586 / 308 / 158단어 실험 지침. `compressed.md`는 root SKILL.md와 같은 bytes |
| [prototype-v1.md](evals/prototype-v1.md) | 702단어 초기 prototype. 과거 JSON의 `Prototype v1`에 해당 |
| [installation.json](evals/installation.json) | 당시 Codex discovery·설치 사본 hash 기록. Claude 실행 검증을 의미하지 않음 |

과거 JSON의 `SufficePatch final`은 **586단어 v1**이다. 최종 158단어 v2는
`v2_decision`과 `adaptive_gate`를 기준으로 읽는다. CLI의 `--arms compressed`는 **46단어 진단용 body**이며,
158단어 v2를 재실행하려면 `--arms suffice --skill SKILL.md`를 쓴다.

| 보존된 cohort | 결과 / manifest | 용도 |
|---|---|---|
| `git-pilot-20261003` | [results](evals/runs/git-pilot-20261003/results.json) / [manifest](evals/runs/git-pilot-20261003/manifest.json) | 초기 18회: baseline·prototype·핵심 지침 조합 |
| `final-20261003` | [results](evals/runs/final-20261003/results.json) / [manifest](evals/runs/final-20261003/manifest.json) | v1 6회 |
| `ablation-20261003` | [results](evals/runs/ablation-20261003/results.json) / [manifest](evals/runs/ablation-20261003/manifest.json) | native/shared 진단 6회, v1/Lite/46단어 body 비교 |
| `expanded-20261003` | [results](evals/runs/expanded-20261003/results.json) / [manifest](evals/runs/expanded-20261003/manifest.json) | baseline/Lite 주 비교 32회 |
| `compressed-20261003` | [results](evals/runs/compressed-20261003/results.json) / [manifest](evals/runs/compressed-20261003/manifest.json) | 최종 v2 주 비교 16회 |
| `regression-20261003` | [results](evals/runs/regression-20261003/results.json) / [manifest](evals/runs/regression-20261003/manifest.json) | v2 별도 회귀 4회 |

각 실행의 `events.jsonl`, `result.json`, `changes.diff`, `stderr.log`를 보존했다.
중단된 초기 setup 자료인 `pilot-20261003`도 남겨 두되 성능 비교 분모에서 제외했다.
당시 runner/tasks 사본이 있는 cohort는 함께 보존하며, `final-20261003`은 manifest hash만 있고
runner/tasks 사본은 없다. 원자료의 이 차이를 숨기지 않는다.

[.gitignore](.gitignore)는 기록된 cohort의 원자료를 제외하지 않는다. 재생성 가능한 `workspace/`,
Python cache와 새 실행 디렉터리는 제외한다. 기존 local workspace는 삭제하지 않았다.
이 문서 정리에서 원자료·집계·측정 코드를 변경하거나 새 모델을 실행하지 않았다.

### 결과 재계산과 실험 재실행

저장소 루트에서 아래 명령은 **모델 호출 없이** 집계를 재계산한다.

```sh
python3 -B evals/run.py --summarize evals/runs/expanded-20261003
python3 -B evals/run.py --summarize evals/runs/compressed-20261003
# 기존 grader의 알려진 정상/실패/빈 구현 검사:
python3 -B evals/run.py --selftest
```

Oracle 계산은 [EVAL_RESULTS.md의 재계산 코드](evals/EVAL_RESULTS.md#재계산과-보존)에 있다.
`--summarize`는 파일을 쓰지 않으며, 수동 감사 proxy나 historical summary.json을 자동 생성하지 않는다.

다음은 **종료된 실험을 다른 사람이 재실행하기 위한 기록**이다. Python 3, Git,
사용 가능한 동일 model과 로그인된 Codex CLI가 필요하며 모델 사용량을 소비한다.
각 `--out`에는 존재하지 않는 디렉터리를 지정한다. Baseline/Lite 후 별도 v2라는 기존 순서를 재현한다.

```sh
python3 -B evals/run.py --out /tmp/suffice-reproduce-expanded   --skill evals/lite.md --arms baseline,suffice --model gpt-6-astra --effort low   --timeout 240 --repeats 2   --tasks trivial,localized,reuse,multifile,ambiguous,auth,dependency,refactor
python3 -B evals/run.py --out /tmp/suffice-reproduce-v2   --skill SKILL.md --arms suffice --model gpt-6-astra --effort low   --timeout 240 --repeats 2   --tasks trivial,localized,reuse,multifile,ambiguous,auth,dependency,refactor
```

과거 v1/prototype 지침은 `--skill evals/v1.md` 또는 `--skill evals/prototype-v1.md`로 선택한다.
과거 핵심 지침 조합은 `--arms baseline,suffice,combined --ecc /path/to/ECC --ponytail /path/to/ponytail`,
당시 task set은 `--tasks reuse,native,shared,auth,atomic,noop --repeats 1`이다.
Combined 재실행에는 [원래 manifest](evals/runs/git-pilot-20261003/manifest.json)의 commit과
source hashes가 일치하는 upstream checkout이 필요하다. 최종 코드의 재실행이 과거 runner bytes까지
완전히 같다는 뜻은 아니므로 보존된 manifest/사본과 차이를 확인해야 한다.

Seed·모델 응답·backend·서버 부하·cache를 완전히 고정하지 못했다. baseline/Lite의 순서 회전은
무작위 배정이 아니며 최종 v2는 나중 cohort다. **같은 절차를 재실행해도 같은 숫자를 보장하지 않는다.**

## Limitations

- 표본이 제한적이다. 주 비교는 과제당 두 번이며 작은 synthetic fixture이고, 개발에 사용한 과제를 재사용했다. 독립 holdout·통계적 유의성·비열등성을 입증하지 않았다.
- Codex CLI와 기록된 `gpt-6-astra` 조건 중심 평가다. **Claude Code 실행 eval은 없다.** 파일 형식/설치 기록을 실행 성능으로 대체하지 않는다.
- Large repository·실제 repo-wide feature·architecture 변경 검증이 부족하다. 좁은 fixture 결과를 대형 프로젝트에 외삽하지 않는다.
- 다른 모델·agent·환경에서 결과가 다를 수 있다. 다른 환경에서 skill이 유효하다는 evidence도 현재 없다.
- Tokens는 실제 API billing cost와 같지 않다. Cache 가격·출력 가격·과금 체계와 연구 자체 비용을 반영한 달러 비교는 하지 않았다.
- Oracle은 관측값의 **사후 선택**이며 실제 router가 아니다. **Routing overhead는 실제 측정하지 않았다.** 동일 prompt에서 미래의 실행 변동을 알 수 있다고 가정한 상한도 포함한다.
- Native skill discovery·자동 활성화, hooks, memory의 실사용 비용은 통제 밖이다. Core instructions 조합 비교는 ECC/Ponytail 전체 설치 비교가 아니다.
- 공통 harness가 dependency 설치와 scope 확장을 이미 제한한다. 이 제약이 없는 agent에서도 같은 결과가 나오는지 알 수 없다.
- 정확한 files-read I/O와 request별 instruction/exploration/reasoning token 분해는 없다. File-read proxy 감소를 실제 비용 절감으로 해석하지 않는다.

## Repository structure and preserved artifact

```text
suffice-patch/
├── README.md
├── SKILL.md                 # 최종 158단어 experimental artifact
├── .gitignore
└── evals/
    ├── EVAL_RESULTS.md
    ├── summary.json
    ├── forensics.json
    ├── run.py
    ├── tasks.py
    ├── prototype-v1.md
    ├── v1.md
    ├── lite.md
    ├── compressed.md
    ├── installation.json
    ├── name-search.json
    └── runs/                # 기존 raw evidence; workspace는 Git 제외
```

[SKILL.md](SKILL.md)는 baseline을 이기지 못한 **experimental artifact**로 그대로 보존한다.
배포 효율 개선 도구로 권장하거나 추가 최적화하지 않는다. Runtime hook·dependency·router는 추가하지 않았다.
기존 Codex/Claude 설치와 activation 설정은 이 기록 정리에서 변경하지 않았다.

보존된 root SKILL.md의 SHA-256:
`5de93a4da0a4a8fa7f7c790ee95ef539352ee6dd5c4be5fee8d3254bde5e8230`.

## Install and invoke — experimental artifact

스킬 이름은 **`suffice-patch`**다. 별도 설치 플래그나 package installer는 제공하지 않으며,
`SKILL.md`를 agent의 skill 디렉터리에 복사한다. Dependency나 hook 설치는 필요하지 않다.
아래는 실험 산출물을 직접 사용하려는 사람을 위한 안내이며, 테스트한 환경의 권고는
계속 **Always Baseline**이다. Claude Code의 실행 성능은 평가하지 않았다.

저장소를 내려받거나 파일을 전달받은 뒤, **SKILL.md가 있는 저장소 루트**에서
사용할 agent의 명령을 실행한다. 아래 명령은 사용자 전역 경로에 설치한다.

### Codex

```sh
mkdir -p ~/.agents/skills/suffice-patch
cp SKILL.md ~/.agents/skills/suffice-patch/SKILL.md
```

새 Codex 세션에서 호출한다.

```text
$suffice-patch 이 버그를 수정해줘
```

### Claude Code

```sh
mkdir -p ~/.claude/skills/suffice-patch
cp SKILL.md ~/.claude/skills/suffice-patch/SKILL.md
```

새 Claude Code 세션에서 호출한다.

```text
/suffice-patch 이 버그를 수정해줘
```

### Eval 옵션과의 구분

`--skill`은 `evals/run.py`가 평가에 주입할 지침 파일을 선택하는 **eval 실행 옵션**이다.
예를 들어 `--arms suffice --skill SKILL.md`는 최종 v2를 평가 조건으로 선택한다.
이 옵션은 agent의 skill 디렉터리에 파일을 설치하지 않는다.

## Provenance

설계 원칙은 [ECC ef648e0](https://github.com/affaan-m/ECC/tree/ef648e01899ba3e8dc6371642deaaf64b4477775)와
[Ponytail c982cd4](https://github.com/dietrichgebert/ponytail/tree/c982cd411abb53323c4baa1baa3c2f020b8d0b08)를
조사해 추출했다. Core comparison은 ECC의 `development-workflow`, `verification-loop`, Ponytail의
main skill 세 문서만 주입했다. ECC 전체나 Ponytail 전체를 합친 framework를 구현하지 않았다.
[초기 upstream 구조·선택 근거·이름 조사](evals/EVAL_RESULTS.md#upstream-research)는 역사 자료로 보존하며
현재 upstream의 구조나 프로젝트 이름의 독점 가능성을 주장하지 않는다.

## What we learned

**Sometimes the cheapest instruction is no additional instruction.**

이 실험에서는 공통 지침을 받는 기본 agent가 추가 skill 없이 같은 task success를 기록했고
사용 tokens와 tool calls가 적었다. 이 교훈은 **테스트한 환경**에 한정된다.
모든 지침·skill이 무익하거나 안전 검사를 생략해야 한다는 뜻이 아니다.

**STOP is part of optimization.**

개선을 계속하는 행위도 연구 비용을 발생시킨다. 이 기록에서 비용이 0인 oracle의 여유마저
약 1.4%에 그쳤으므로 구현 복잡성과 추가 실험 비용을 늘리지 않고 종료했다.
프로젝트의 가치는 baseline을 이겼다는 주장에 있지 않고, 그 질문을 검증하고
부정적 결과·원자료·한계를 함께 남겼다는 데 있다.
