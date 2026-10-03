# SufficePatch v3

작은 Python 코드 수정에 필요한 소스·로컬 import·호출부·테스트·Git 변경을
한 번에 수집하는 Codex/Claude 스킬이다. **자동 선택을 유지한 채 설치했다.**

문장을 짧게 만드는 것만으로는 효율이 좋아지지 않았다. v3는 읽기 전용 도우미를
추가하고 탐색·수정·검증을 묶어 실행하도록 바꿨다. 필수 검사와 무관한 변경 보존은 유지한다.

## 실제 측정 결과

최종 버전을 Codex가 자동 선택하는 조건으로 두 Python 과제를 두 번씩 비교했다.

| 측정 | 스킬 비활성 | v3 자동 선택 |
|---|---:|---:|
| 과제 성공 | 4/4 | 4/4 |
| 총 토큰 | 218,696 | 172,548 (**21.1% 감소**) |
| 도구 이벤트 | 16 | 19 |
| 측정 시간 합계 | 228초 | 270초 |

**관측된 개선은 토큰 사용량이다. 더 빠르거나 호출 수가 적다고 주장하지 않는다.**
Codex CLI 0.160.0 / `gpt-6-astra` / `low`의 작은 합성 과제 결과이며,
청구 금액이나 실제 대형 저장소 전반의 절감을 보장하지 않는다.

별도 네 과제 × 두 반복의 workflow 비교도 두 조건 모두 8/8 통과했고,
토큰은 21.6% 줄었다. 그 비교에는 native 자동 선택 비용이 포함되지 않는다.
실패한 후보, 측정 오류로 제외한 pilot, 상세 수치와 원자료는
[검증 보고서](evals/V3_RESULTS.md)에 보존했다.

## 사용

Python 모듈과 수정할 동작을 설명하면 Codex가 관련 요청에서 자동 선택할 수 있다.
항상 선택된다는 보장은 없다. 명시적으로 사용할 수도 있다.

```text
$suffice-patch api.customer_label을 web 표시와 같게 수정해줘. 응답 형식은 유지해줘.
```

Claude Code에서는 `/suffice-patch`로 명시 호출한다. Claude의 기능 검증과
Codex의 비교 측정은 서로 다른 증거이며 Claude의 토큰 절감은 아직 측정하지 않았다.

현재 설치 위치:

- Codex: `~/.agents/skills/suffice-patch/`
- Claude: `~/.claude/skills/suffice-patch/`

새 설치에는 **SKILL.md와 scripts/를 함께** 복사한다. 자동 선택을 끄는 설정은 추가하지 않는다.

```sh
mkdir -p "$HOME/.agents/skills/suffice-patch/scripts"
cp SKILL.md "$HOME/.agents/skills/suffice-patch/SKILL.md"
cp scripts/collect_context.py "$HOME/.agents/skills/suffice-patch/scripts/collect_context.py"
```

## 도우미와 한계

Python 3.9 이상, `rg`, `git`을 사용한다. 프로젝트 root에서 직접 확인할 수도 있다.

```sh
python3 -B scripts/collect_context.py api.py web
python3 -B -m unittest evals/test_inspect.py -v
```

도우미는 프로젝트 코드를 실행하지 않으며 저장소 밖 경로를 읽지 않는다.
기본 소스 한도는 16개 파일/40,000바이트다. 누락·한도·검색 실패를 표시한다.
동적 호출이나 다른 언어의 테스트까지 완전하게 찾는 도구는 아니므로, 보고된 빈틈은
추가 확인해야 한다. 파이썬 이외의 작업에는 이 스킬의 효율 결과를 적용하지 않는다.

## 보존한 기록

v2는 성공률을 유지했지만 토큰이 5.36% 늘었다. 당시의 중단 결론을 덮어쓰지 않고
[v2 README](evals/README_V2.md)와 [v2 상세 결과](evals/EVAL_RESULTS.md)로 보존했다.
새 결과는 사용자 요청으로 재개한 별도 v3 실험이다. 이전 설치본도
[백업과 설치 기록](evals/installation-v3.json)에 남겼다.
