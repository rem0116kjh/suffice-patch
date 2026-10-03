# SufficePatch v3 — 실제 자동 선택 검증

2026-10-03. 사용자가 자동 선택 유지를 선택하여, `v3-autoload`를 최종 설치했다.
작은 Python 수정에서 토큰 절감은 관측했지만, 자동 선택의 도구 호출 감소와
속도 향상은 달성하지 못했다. 아래 비교는 각각의 동일 과제 baseline과 대응한다.

## 최종 버전: native 자동 선택

`invoice`, `inventory` 두 과제 × 두 반복 × 두 조건 = **8회**.
Codex CLI 0.160.0, `gpt-6-astra`, reasoning `low`, macOS에서 측정했다.

| 측정 | Baseline | 최종 v3 자동 선택 | 변화 |
|---|---:|---:|---:|
| 과제 성공 | 4/4 | 4/4 | 동일 |
| 독립 assertion 그룹 | 12/12 | 12/12 | 동일 |
| 입력 + 출력 토큰 | 218,696 | 172,548 | **−21.10%** |
| 실행별 중앙값 토큰 | 54,656.5 | 43,205 | −20.95% |
| 완료된 도구 이벤트 | 16 | 19 | +18.75% |
| 측정 시간 합계 | 228.363초 | 269.690초 | +18.10% |

일반 작업 요청만 전달했고, `$suffice-patch`나 스킬 본문을 prompt에 넣지 않았다.
각 fixture의 `.agents/skills/suffice-patch`에서 Codex가 실제로 선택했다.
Baseline은 repo skill과 사용자 설치본을 모두 비활성화했고, treatment는 repo skill만
활성화했다. `skills/list`에서 이 분리를 확인했다. 모든 baseline의 도우미 실행은 0회,
모든 treatment는 1회였고, 무관한 파일과 스킬 파일도 보존했다.

본문을 읽기 전에도 실행 진입점을 알 수 있도록 description을 조정했다.
본문·도우미는 앞선 native 후보와 같고, 최종 후보를 별도로 동결한 후 비교했다.
변경 전체의 관측 결과이며 특정 문장 하나의 인과 효과를 입증한 실험은 아니다.

## 도우미와 수정 흐름 검증

새로운 네 과제(`invoice`, `inventory`, `download`, `noop`)를 조건별 두 번 실행했다.
금액 반올림·원자적 재고 변경·경로 탈출 방지·이미 올바른 코드 보존을 독립적으로 채점했다.

| 측정 | Baseline | 도우미 포함 workflow |
|---|---:|---:|
| 과제 성공 | 8/8 | 8/8 |
| 독립 assertion 그룹 | 22/22 | 22/22 |
| 총 토큰 | 437,123 | 342,907 (**−21.55%**) |
| 중앙값 토큰 | 54,858.5 | 43,079.5 (**−21.47%**) |
| 도구 이벤트 | 30 | 17 |

이 비교는 스킬을 `.suffice-tools`에 동일하게 배치하고 treatment에만 workflow를
주입했다. **자동 선택 비용은 포함하지 않는다.** 최종 설치본과 description이 다르므로
최종 native 성능으로 대체해서 읽으면 안 된다. 도우미에는 이후 빈 context에서 전체
Git diff를 읽지 않는 보호를 추가했다. 16개 완료 fixture에서 그 전후 출력이 모두
바이트 단위로 같았고, 빈 context 동작은 별도 테스트했다.

## 실패와 변경 기록

| 후보/비교 | 결과와 처리 |
|---|---|
| v2 역사 결과 | 16/16 성공, baseline보다 토큰 +5.36%. 기존 기록 보존. |
| v3 지침만 수정 | 2/2 성공, 토큰 +3.86%. gate 실패. |
| v3-1 지침 보정 | 2/2 성공, 토큰 +4.01%. gate 실패. 지침만 보정하는 접근 중단. |
| v3-tools 최초 pilot | baseline이 repo skill을 자동 로드한 설정 오류. 중단하고 비교에서 제외. 원자료와 사유 보존. |
| v3-tools 교정 pilot | 각 2/2 성공, 토큰 −21.20%, 호출 8→4. 도우미 방식 후속 검증 진행. |
| v3-tools 최초 native | 명시 호출 토큰 −21.38%, 자동 선택은 +2.77%. 각 조건 2/2 성공. |
| v3-autoload 최종 native | 사용자 요청대로 자동 선택 유지. 토큰 −21.10%, 호출 16→19. 각 4/4 성공. |

사전 계획의 정확도·토큰·도구 호출 기준은 controlled workflow 비교에서 통과했다.
**최종 자동 선택은 호출 비증가 기준을 통과하지 못했다.** 따라서 모든 효율 목표를
달성했다고 보고하지 않는다. 사용자 선택을 반영하여, 관측된 토큰 절감과 이 tradeoff를
명시한 자동 선택 버전을 설치했다. 반복 최적화 비용은 위 task당 절감 계산에 포함되지 않는다.

## 구현과 검증 범위

- `scripts/collect_context.py`는 Python 표준 라이브러리와 기존 `rg`, `git`으로
  소스·로컬 import·텍스트상 호출부/테스트·AGENTS.md·Git 변경을 모은다.
- 프로젝트 코드를 import/실행하지 않는다. 저장소 밖 경로와 symlink를 거절하고,
  파일 수·소스 바이트 한도와 누락을 표시한다. Git external diff/textconv/fsmonitor를
  비활성화한다. 별도 API나 유료 서비스는 추가하지 않았다.
- 도우미 테스트 5개 통과: 소스/호출부/지침 수집과 원본 보존, 외부 경로 거절,
  상대 import와 중첩 지침, 한도 고지, Git helper 실행 방지.
- 최종 설치본도 Codex 자동 선택과 Claude 명시 호출 각각 1회 실행하여 2/2 성공,
  외부 assertion 그룹 6/6 통과를 확인했다. 두 실행 모두 설치된 도우미의 성공 출력이
  남았다. Codex `skills/list`의 `enabled=true`와 오류 없음도 확인했다.
- Claude에서는 복합 shell 명령 한 번이 권한 검사에서 거절되었으나 Read/Edit와
  허용된 검사로 복구했다. 기존 v2 검사기는 SKILL.md 읽기/Skill 호출만 추적하여
  도우미 직접 실행을 놓쳤다. 원자료를 보존하고 도구 호출과 성공 응답을 대응시켜
  검증했으며 유리한 결과를 얻기 위한 재실행은 하지 않았다.
- 작은 합성 Python 과제 결과다. 실제 대형 저장소, 다른 언어·모델·설정으로
  일반화하지 않는다. 동적 import/caller, 비 Python 테스트는 추가 탐색이 필요하다.
- 토큰은 CLI의 `input_tokens + output_tokens`다. cached input을 다시 더하지 않았다.
  청구 금액이나 캐시 가격을 측정한 것이 아니다. 도구 이벤트 수는 모델 왕복 수가 아니다.
- 일부 cohort는 동시에 실행되어 시간 비교에 영향을 줄 수 있다. 최종 native에서도
  시간이 더 걸렸으므로 속도 개선을 주장하지 않는다. 통계적 유의성 실험이 아니다.
- Claude는 설치 후 기능 smoke만 확인하며 효율 개선은 별도 비교하지 않는다.

## 원자료와 재현

- [최종 자동 선택 집계](runs/v3-autoload-native-20261003/summary.json),
  [각 실행 결과](runs/v3-autoload-native-20261003/results.json),
  [원시 usage 재집계 검사](runs/v3-autoload-native-20261003/usage-audit.json)
- [새 네 과제 집계](runs/v3-tools-holdout-20261003/summary.json),
  [도우미 출력 동등성](runs/v3-tools-holdout-20261003/helper-equivalence.json)
- [최초 native 집계](runs/v3-tools-native-20261003/summary.json),
  [잘못된 pilot 제외 사유](runs/v3-tools-pilot-20261003/INVALID_COMPARISON.json)
- [설치 기록](installation-v3.json), [설치 후 smoke](runs/v3-installed-smoke-20261003/results.json),
  [설치본 실행 증거 검사](runs/v3-installed-smoke-20261003/verification.json),
  [실제 설치본 검색](runs/v3-installed-smoke-20261003/discovery.json)
- [계획](V3_PLAN.md), [v2 역사 README](README_V2.md), [v2 결과](EVAL_RESULTS.md)

각 run 폴더에는 prompt, JSONL events, stderr, diff, 외부 grader 결과가 있다.
과거 결과를 덮어쓰지 않았다. 이 보고서가 인용하는 raw run은 첫 Git 커밋에 함께
포함했다. 생성된 작업용 checkout과 임시 검증 환경은 제외한다. 이후 새 실험 출력은
검토하여 명시적으로 포함할 때까지 `.gitignore` 정책에 따라 제외된다.

재현에는 기존에 인증된 Codex CLI가 필요하고 모델 사용량이 발생한다. 새 output 경로를 쓴다.

```sh
python3 -B -m unittest evals/test_inspect.py -v
python3 -B evals/v3_native.py --out /tmp/suffice-native-new \
  --skill candidates/v3-autoload/suffice-patch/SKILL.md \
  --tasks invoice,inventory --arms baseline,implicit --repeats 2
```

최종 bundle SHA256:

```text
SKILL.md                  f365978b6a24b55d5312dd551cfb7f0a5775595ffd6b8205162cb1df973f9ea1
scripts/collect_context.py b67f30fc48cb80db564a5e83bcadcb2722e946e816a5183a32f3476b76bfe674
```
