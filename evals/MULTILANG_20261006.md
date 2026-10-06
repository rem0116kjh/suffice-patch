# SufficePatch v4 다언어·모노레포 검증 — 2026-10-06

v4는 Python 전용 스킬을 여러 언어의 코드·테스트·설정·문서를 위한 제한된 문맥 수집과
수정·검증 절차로 확장했다. 큰 저장소는 관련 패키지를 지정해 나누어 읽고, 마지막에
변경이 닿는 패키지의 통합 검사를 수행하도록 안내한다.

이 문서는 기능·경계·실제 런타임 검증이다. v3에서 측정한 시간 −24.7%와 토큰 +20.4%는
v4의 성능 수치가 아니다. v4의 모델별 토큰·시간 개선은 비교 측정하지 않았다.

## 지원 깊이

- Python: AST 기반 로컬 import·상대 import·src 레이아웃과 정의 심볼.
- JS/TS 및 JSX/TSX: 상대 import/export/require/문자열 dynamic import, index 및 TS 확장자 후보.
- Vue/Svelte: inline script의 같은 JS/TS 규칙. template/style 의존성은 추가 확인.
- Go: go.mod 안의 로컬 import 패키지와 같은 패키지의 비테스트 소스 후보.
- Rust: mod, crate/self/super의 로컬 파일 후보. cfg·macro·Cargo target override는 해석하지 않음.
- C/C++: 따옴표 include와 가까운 include 디렉터리 후보. 컴파일러별 검색 경로는 해석하지 않음.
- Java/Kotlin/C#/Swift/Ruby/PHP·Shell·HTML/CSS·SQL·설정·문서: 파일 읽기, 텍스트 심볼·참조 검색,
  가까운 manifest 수집. 언어별 import 해석을 구현했다고 주장하지 않음.

`--scope`는 검색 범위를 제한한다. 필요한 로컬 import는 저장소 내부의 다른 패키지를
읽을 수 있다. 디렉터리 입력은 경로 목록만 반환하며 파일 본문을 자동 수집하지 않는다.
각 소스·검색·manifest·Git 출력에 한도가 있고 누락·시간초과는 알린다. Python은 도우미의
실행 환경이며 사용자 프로젝트에 Python 의존성을 추가할 필요가 없다.

## 검증 결과

| 검증 | 결과 | 범위 |
|---|---|---|
| 최종 회귀 검사 | 54/54 통과 | 수집기 29개 + 평가 도구 25개 |
| 별도 위치 복사 설치 | Python 3.12.14에서 수집기 29/29, Python 3.14.7에서 실제 소스 smoke 통과 | 새 3파일 번들, 같은 macOS 호스트 |
| 2,000개 무관 파일 fixture | 범위·소스·경로 목록·출력 한도 검사 통과 | 합성 대형 입력, 모델 성능 비교 아님 |
| 독립 에이전트의 실제 수정 | JS/TS·Go·C·Java 4개 서비스 변경·기존/새 테스트 실행 통과 | 배송비 경계 기능을 추가한 합성 모노레포 |
| 별도 API 검사기 | 수정본 57/57, 원본 37/57 | 새 기능 관련 원본 실패 20건을 구별 |
| 최종 도우미 재수집 | 8/8 호출 성공, 후속 수집으로 필요한 20파일 확인 | 코드·Git 상태·사용자 변경 모두 보존 |
| 설치 반영·검색 | Codex/Claude 설치본 갱신, Codex native skills/list에서 새 설명·enabled 확인 | 자동 선택 성공률 측정은 아님 |

API 검사 수는 JS/TS 15개, Go 13개, C 15개, Java 14개다. 기존 테스트·공유 도우미·
사용자의 dirty/untracked 파일·Rust 코드는 그대로이고, 허용된 소스 4개와 새 테스트 4개만
변경했다. JS/TS는 Node의 타입 제거 런타임으로 실행했다. `tsc`가 없어 정적 타입 검사는
하지 않았다. C는 macOS 네이티브 clang으로, Java는 JDK로 실제 컴파일·실행했다.
Rust는 모듈 탐색 검사만 통과했으며 rustc/cargo가 없어 빌드·런타임은 검증하지 않았다.
Java 등의 텍스트 탐색 지원을 import 자동 해석 지원과 혼동하지 않는다.

최초 독립 수정은 `bundle/`을 사용했고, 후속 검토에서 수집기의 지연과 Git 상태 표시를
고친 최종 버전은 `bundle-final/`에 보존했다. 최종 버전으로 54개 회귀 검사·복사 설치·
8회 실제 문맥 재수집을 확인했다. 수정된 네 서비스는 그대로 유지한 채 독립 API 검사를
수행했으며 새 성능 비교를 실행한 것은 아니다.

[최종 회귀 로그](runs/multilang-20261006/unit-tests.stderr.log),
[독립 API 결과](runs/multilang-20261006/independent/results/summary.json),
[최종 수집·보존 증거](runs/multilang-20261006/forward/final-helper/verification.json),
[설치·ZIP 기록](runs/multilang-20261006/installation.json),
[Codex 검색 결과](runs/multilang-20261006/native-discovery/selected.json)에 상세 증거를 보존한다.
독립 검사기가 사용한 당시 메타데이터도 해시가 일치하는
[입력 스냅샷](runs/multilang-20261006/independent/verification-input.json)으로 별도 보존했다.

## 검증 중 수정한 결함

- Java 프로젝트의 설정·문서 입력에서 pom.xml이 빠지던 문제: 일반 텍스트 대상도
  가까운 언어별 manifest 후보를 수집하도록 수정.
- 빈줄이 많은 문서에서 정규식이 줄바꿈을 반복 탐색하던 문제: 줄 안의 공백으로
  범위를 제한하고 관련 입력에 실행 시간 상한 회귀 검사를 추가.
  정규식 대신 선형으로 주석·문자열을 건너뛰고 미완성 Go/C 구문의 과도한 재탐색도 제한했다.
  40KB 빈줄 문서의 순수 분석은 약 0.0034초였으며 이것은 모델 실행 시간이 아니다.
  [전후 측정](runs/multilang-20261006/regex-regression.json)에 원자료를 남겼다.
- 검색 패키지 밖의 기존 사용자 변경이 scoped Git status에 나타나지 않던 문제:
  상태는 저장소 root 범위에서 제한된 크기로 표시하고 diff는 수집한 파일에 한정.

최초 검증 번들과 최종 번들은 각각 별도로 보존한다. 실패를 감추거나 이전 버전으로
실행한 결과를 최종 버전에서 실행한 것처럼 표시하지 않는다.

## 재현과 원자료

```sh
python3 -B -m unittest evals.test_inspect evals.test_multilang evals.test_external_run evals.test_external_summary -v
```

[다언어 검사](test_multilang.py), [기존 읽기 전용 검사](test_inspect.py),
[검증 원자료](runs/multilang-20261006/verification.json), [실제 혼합 프로젝트의 원본](runs/multilang-20261006/fixture-before.tar)에
코드와 근거를 보존한다. 혼합 프로젝트는 검증용으로 작성한 합성 fixture이며 외부 프로젝트가 아니다.

실제 수정 결과를 새 위치에서 API 검사로 재확인하려면 해당 언어 도구가 설치된 환경에서
다음 명령을 실행한다. Node의 TS 타입 제거를 지원하는 버전이 필요하며 실제 사용 버전은
[baseline 기록](runs/multilang-20261006/baseline.json)에 있다. 생성된 빌드·캐시는 저장소 밖에 둔다.

```sh
mkdir /tmp/suffice-v4-replay
tar -xf evals/runs/multilang-20261006/fixture-after.tar -C /tmp/suffice-v4-replay
python3 -B evals/runs/multilang-20261006/independent/run.py \
  --fixture /tmp/suffice-v4-replay --out /tmp/suffice-v4-api-check
```

위 검사는 에이전트를 다시 호출하지 않는다. 원래 임시 경로가 담긴 로그는 당시 실행의
기록이며, 경로가 달라지면 `--fixture`와 새 출력 경로를 사용한다.

현재 배포 [ZIP](../dist/suffice-patch.zip)은 SKILL.md와 Python 도우미 두 파일을 포함한다.
SHA256은 `c7f11aa2797684514c4396e22eb0b77e2eeb9f61b0d1d7ee0d616bee24e599ff`다.
기존 전역 설치본은 백업 후 교체했고, 자동 선택을 끄는 설정은 추가하지 않았다.

기존 v3 평가의 동결 코드·원자료는 수정하지 않았다. 이전 성능 비교의 정확한 후보로
재현하려면 [v3 보고서](GENERALIZATION_20261006.md)의 당시 커밋을 사용한다.

## 한계

파일·시간·출력 한도 준수는 대형 프로젝트의 모든 영향을 찾는다는 보장이 아니다.
별칭, 동적 로딩, 생성 코드, 조건부 빌드와 언어별 도구 설정은 추가 확인해야 한다.
컴파일러 의미 분석이나 전체 호출 그래프 대신 실제 파일과 참조 후보를 제공한다.
동일 macOS 호스트에서의 검증이며 Linux·Windows 및 다른 사용자의 환경은 미검증이다.
