# SufficePatch 실제 호출 점검 — 2026-10-03

**판정: 설치된 스킬의 발견·호출과 작업 수행은 정상이다. 작업 테스트 5/5,
독립 assertion group 13/13을 통과했다. 효율 개선이나 지침의 완벽한 준수를
보장한다는 뜻은 아니다.**

## 실제 실행 결과

| 환경 / 호출 | 과제 | 결과 | 변경 파일 |
|---|---|---|---|
| Codex / `$suffice-patch` | 웹의 기존 이름 처리 함수를 API에서 재사용 | 3/3 통과 | `api.py`, `test_sample.py` |
| Codex / `$suffice-patch` | 기존 읽기 권한과 동일한 수정 권한 구현 | 3/3 통과 | `notes.py` |
| Codex / `$suffice-patch` | 이미 올바른 태그 정규화 확인 | 2/2 통과 | 없음 |
| Codex / 이름 없는 일반 요청 | 마지막 일부 chunk 누락 수정 | 2/2 통과 | `chunks.py` |
| Claude / `/suffice-patch` | 웹의 기존 이름 처리 함수를 API에서 재사용 | 3/3 통과 | `api.py` |

모든 실행이 정상 종료했고 timeout은 없었다. 별도 Python 프로세스에서
결과를 채점했으며, 보호 대상인 무관 파일의 내용은 모두 유지됐다.
권한 구현은 추가 독립 검사에서 사용자 4종 × 노트 3종의 **12개 조합**을
통과했다. 오류 종류·메시지, 거절 시 저장 상태, 반환 객체를 수정해도
저장 데이터가 바뀌지 않는 성질을 확인했다.

기존 **12개 채점기**의 자체 검사도 통과했다. 정상 구현은 승인하고
알려진 오류·빈 구현은 거절한다. 이는 모델 작업 12회 성공이라는 뜻이 아니다.

## 스킬이 실제로 로딩됐는지

- Codex의 새 app-server에 `skills/list`와 `forceReload: true`를 요청했다.
  `~/.agents/skills/suffice-patch/SKILL.md`가 `scope=user`, `enabled=true`로
  발견됐다. 대상 스킬 오류와 전체 discovery 오류 모두 0건이었다.
- 세 명시적 Codex 실행은 `$suffice-patch`라는 이름으로 호출했다.
  평가 코드가 SKILL.md 본문을 프롬프트에 붙이지 않았다. 세 실행 모두
  스킬 사용을 알리고 해당 작업을 완료했다.
- 이름을 전혀 넣지 않은 chunk 수정 요청에서도 Codex가 스킬을 자동 선택했다.
  설치 경로의 `SKILL.md`를 `cat`으로 읽어 **실제 본문을 반환받은 tool event**가
  남아 있다. 수정 후 chunk 경계·입력 보존·오류 처리를 채점했다.
- Claude 초기화 이벤트의 `skills`와 `slash_commands` 양쪽에 이름이 있었다.
  `/suffice-patch` 호출로 수정·검증이 완료됐다.
- Claude에는 **추가 읽기 전용 로딩 검사 1회**를 수행했다. 모델 도구를 모두
  비활성화하고, 본문을 프롬프트에 제공하지 않은 채 스킬의 첫 문장과 마지막
  문장을 물었다. 설치본과 정확히 일치하는 두 문장을 답했고 tool call은 0건이었다.
  따라서 명령 목록에 이름만 있는 상태가 아니라 본문까지 전달됨을 확인했다.

이번 Codex 자동 선택 관측은 **1건**이다. 모든 요청이나 기존 데스크톱 세션에서
항상 자동 선택된다는 보장은 아니다. 명시적으로 쓰려면 새 세션에서
Codex는 `$suffice-patch`, Claude Code는 `/suffice-patch`로 호출한다.

## 관찰된 한계

Claude는 이름 처리와 무관한 `legacy.md`도 읽었다. `reports.py`를 포함해
여러 파일을 읽으려는 shell 명령은 테스트 권한 설정에 의해 한 번 거절됐고,
이후 Read 도구로 필요한 파일과 `legacy.md`를 읽어 작업을 완료했다.
따라서 작업 성공과 “항상 최소한만 탐색한다”는 주장은 구분해야 한다.

기존 원자료를 다시 집계한 결과도 README와 일치했다.

| 기존 주 비교 | 성공 | 합계 tokens | tool calls |
|---|---:|---:|---:|
| Baseline | 16/16 | 859,967 | 63 |
| SufficePatch v2 | 16/16 | 906,058 | 65 |

기존 실험에서 v2는 토큰을 약 **5.36% 더 사용**했다. 이번 점검은 baseline과
짝지은 비용 실험이 아니며, 이 결론을 뒤집는 근거로 사용할 수 없다.
작은 기존 fixture를 재사용했으므로 독립 holdout이나 대형 프로젝트 검증도 아니다.

## 실행 조건과 보존

- Codex CLI `0.160.0`, `gpt-6-astra`, reasoning effort `low`.
- Claude Code `2.1.286`, 초기화 이벤트 모델 `claude-opus-5-5[1m]`.
- macOS에서 Python 표준 라이브러리 fixture만 실행했다. Linux 바이너리 실행은 없다.
- Codex는 host skill discovery를 켰고, user config·plugins·hooks·apps·memory·project
  docs·multi-agent를 끈 통제 조건이었다. Claude는 사용자 스킬 경로를 사용하고
  hooks와 외부 MCP를 제한했다. 전체 데스크톱 설정 조합의 평가와는 다르다.
- 원본 SKILL.md, Codex·Claude 설치본, 기존 README·summary·runner·tasks는
  SHA-256으로 변경 없음을 확인했다. 새 점검 파일과 격리된 fixture만 추가했다.
- 원본과 두 설치본의 SHA-256은 모두
  `5de93a4da0a4a8fa7f7c790ee95ef539352ee6dd5c4be5fee8d3254bde5e8230`이다.

## 증거 파일

- [집계 및 개별 결과](runs/runtime-audit-20261003/results.json)
- [Codex 발견 결과](runs/runtime-audit-20261003/discovery.json)
- [자동 선택 및 설치본 읽기 기록](runs/runtime-audit-20261003/codex-implicit-localized/events.jsonl)
- [Claude 본문 로딩 검사](runs/runtime-audit-20261003/claude-loading-result.json)
- [추가 권한 검사](runs/runtime-audit-20261003/auth-extra-check.json)
- [실행 조건·원본 hashes](runs/runtime-audit-20261003/manifest.json)
- [원본 보존 확인](runs/runtime-audit-20261003/preservation.json)
- [이번 점검 실행 코드](runs/runtime-audit-20261003/audit.py)

각 과제 디렉터리에 prompt, command, events, stderr, 결과 JSON과 diff를 보존했다.
기존 `.gitignore` 규칙에 따라 새 `runs` 출력은 Git 추적에서 제외된다.
기존 비용 최적화 실험과 historical summary는 수정하지 않았다.
