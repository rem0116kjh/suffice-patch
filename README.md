한국어 · [English](README.en.md)

# SufficePatch v4

[프로젝트 웹페이지](https://rem0116kjh.github.io/suffice-patch/) · [웹페이지 소스](index.html) · [업데이트 모아 보기](https://rem0116kjh.github.io/suffice-patch/#updates)

여러 언어로 된 코드·테스트·설정·문서를 수정할 때 필요한 파일과 참조를 제한된 범위로
모아 주는 Codex/Claude 스킬이다. 모노레포는 패키지별로 탐색하고, 큰 변경은 관련 부분을
차례로 처리한 뒤 통합 검증한다. 도우미는 Python으로 작성했지만 대상 프로젝트 언어는
Python으로 제한하지 않는다. 자동 선택을 유지한다.

## 다언어와 모노레포 지원

| 대상 | 수집 방식 |
|---|---|
| Python | AST 기반 로컬 import, src 레이아웃, 상대 import, 정의 심볼 |
| JS/TS·JSX/TSX·Vue/Svelte | 상대 import·export·require·문자열 dynamic import, TS 확장자와 index 후보 |
| Go | go.mod 안의 로컬 패키지와 같은 패키지의 소스 후보 |
| Rust | mod 및 crate/self/super 경로의 로컬 모듈 후보 |
| C/C++ | 따옴표 include와 가까운 include 디렉터리 후보 |
| Java/Kotlin/C#/Swift/Ruby/PHP·Shell·HTML/CSS·SQL·설정·문서 | 텍스트와 심볼 참조 검색, 가까운 프로젝트 manifest |

언어별 탐색은 완전한 컴파일러 분석이 아니다. alias, workspace 간 package 이름,
동적 참조, 조건부 빌드와 생성 코드는 누락 안내를 보고 추가 확인해야 한다.
Vue/Svelte의 의존성 탐색은 inline script 범위다. 다른 언어의 테스트도 검색하지만
실행 명령은 프로젝트 manifest와 지침에서 확인한다.

```sh
# 모노레포의 한 패키지 안에서 후보 경로만 확인
python3 -B scripts/collect_context.py . --scope packages/web
# 실제 파일·의존성·참조·테스트 수집
python3 -B scripts/collect_context.py packages/web/src/cart.ts --scope packages/web
# 연결된 두 패키지를 함께 검색하고 특정 심볼로 좁히기
python3 -B scripts/collect_context.py services/api/main.go --scope services/api --scope packages/shared --symbol Calculate
```

기본 한도는 소스 16개/40,000바이트, 검색 후보 200개, 검색당 5초다. `--scope`는
경로 목록과 참조 검색의 범위이며, 실제 연결된 로컬 import는 저장소 안의 다른 패키지도
읽을 수 있다. 폴더를 지정하면 내용을 자동으로 덤프하지 않고 파일 지도만 반환한다.
의존성·빌드 산출물은 검색에서 제외하고 검색/Git 출력도 크기와 시간을 제한한다.

v4는 회귀 검사 54/54와 JS/TS·Go·C·Java의 독립 API 검사 57/57을 통과했다.
2,000개 무관 파일 fixture의 수집 한도도 확인했다. Rust 실행·TS 정적 타입 검사는 미검증이다.
[v4 검증 기록](evals/MULTILANG_20261006.md)에 지원 깊이와 실행하지 못한 검사를 구분한다.
**아래 시간·토큰 수치는 이전 Python 전용 v3의 결과이며 v4의 성능 근거가 아니다.**
v4의 토큰 절감이나 시간 개선은 아직 비교 측정하지 않았다.

## 이전 Python 전용 v3 외부 저장소 검증 (2026-10-06)

`python-dotenv`, `packaging`, `itsdangerous`의 실제 과거 버그 3개와 변경 불필요
과제 1개를 각 조건에서 3번씩 비교했다. 사전 계획을 고정한 **24회 실행**에서
스킬 사용·미사용 모두 12/12회 성공했다. 성공에는 독립 행동 검사, 기존 테스트,
무관한 파일 보존이 모두 필요하다. 자동 선택 조건의 12회 모두 도우미 실행을 확인했다.

| 사전 지정한 주지표 | 자동 선택 / 미사용 | 판정 |
|---|---:|---|
| 에이전트 실행 시간 | 0.753 (**24.7% 감소**) | 개선 기준 충족 |
| 총 토큰 | 1.204 (**20.4% 증가**) | 개선 기준 미충족 |
| 정확성 | 양쪽 12/12 성공 | 관측된 성공률 동일 |

비율은 반복쌍 → 과제별 중앙값 → 4과제 동일 가중 기하평균으로 계산했다.
시간 비율의 과제 bootstrap 95% 구간은 0.679–0.836, 토큰은 1.118–1.327이다.
원시 합계는 시간 756.9 → 611.2초, 총 토큰 1,176,381 → 1,450,245였다.
캐시 제외 입력도 239,243 → 326,592로 늘었으며 실제 청구 비용은 측정하지 않았다.

**이번 근거가 지지하는 장점은 제한된 Python 유지보수 과제에서의 시간 단축이다.**
토큰 절감이나 정확성 향상을 입증하지 않았다. 작은 공개 저장소 3개와 같은 macOS
호스트·Codex CLI 0.160.0·`gpt-6-astra`·`low`에서 얻은 결과이며, 다른 사용자·모델·언어·
대형 저장소에도 같은 효과가 난다는 보장은 아니다. 과거 공개 문제의 학습 오염 가능성도 있다.

[검증 보고서](evals/GENERALIZATION_20261006.md), [사전 계획](evals/GENERALIZATION_PLAN_20261006.md),
[24회 전체 결과](evals/runs/generalization-20261006/RESULTS.md),
[원자료 감사](evals/runs/generalization-20261006/audit.json)에 성공·사용량·한계와 재현 절차를 공개했다.
아래의 이전 합성 과제 결과와 합산하지 않는다.

## 이전 v3 코드 최적화와 재실행 (2026-10-06)

도우미의 중복 경로 탐색·AST 분석·대기 목록 처리를 줄이고, 한도 소진 후 검색을
생략했다. Git 필터와 ripgrep 전처리기 실행도 차단했다. 회귀 검사 12/12를 통과했고
Codex·Claude 설치본의 도우미에도 반영했다.

실제 Codex 재고 예약 수정 과제를 미사용/자동 선택 조건으로 각각 한 번 실행해
양쪽 모두 독립 검사 3/3을 통과했다. 총 토큰은 **54,549 → 42,875 (21.4% 감소)**,
시간은 **26.4초 → 29.5초**, 도구 이벤트는 4 → 4였다. 캐시 제외 입력 토큰은
오히려 5.0% 늘어 비용 절감으로 단정할 수 없다.

최종 도우미의 별도 실행 시간은 반복 import 사례에서 42.2%, 호출 후보 2,000개
사례에서 64.6% 줄었다. 작은 프로젝트에서는 약 10ms 늘었다. 이는 합성 사례의
관측이며 전체 에이전트 속도 향상을 뜻하지 않는다. 실행 버전과 후속 `.pyi` 수정의
구분, 원자료, 재현 명령은 [최적화 보고서](evals/OPTIMIZATION_20261006.md)에 있다.

## 기존 v3 측정 결과 (2026-10-03)

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

수정할 파일·기능·대상 패키지를 설명하면 Codex가 관련 요청에서 자동 선택할 수 있다.
항상 선택된다는 보장은 없다. 명시적으로 사용할 수도 있다.

```text
$suffice-patch packages/web의 장바구니 계산과 services/api의 검증을 함께 수정해줘. 기존 응답 형식은 유지해줘.
```

Claude Code에서는 `/suffice-patch`로 명시 호출한다. Claude의 기능 검증과
Codex의 비교 측정은 서로 다른 증거이며 Claude의 토큰 절감은 아직 측정하지 않았다.

현재 설치 위치:

- Codex: `~/.agents/skills/suffice-patch/`
- Claude: `~/.claude/skills/suffice-patch/`

새 설치에는 **SKILL.md와 scripts/를 함께** 복사한다. [설치용 ZIP](dist/suffice-patch.zip)은
현재 v4의 SKILL.md와 두 Python 도우미 파일을 담는다. 프로젝트에 Python 코드를
추가할 필요는 없다. Linux·Windows 및 다른 사용자의 설치는 아직 시험하지 않았다.
자동 선택을 끄는 설정은 추가하지 않는다.

```sh
mkdir -p "$HOME/.agents/skills/suffice-patch/scripts"
cp SKILL.md "$HOME/.agents/skills/suffice-patch/SKILL.md"
cp scripts/collect_context.py scripts/context_languages.py "$HOME/.agents/skills/suffice-patch/scripts/"
```

## 도우미와 한계

Python 3.9 이상, `rg`, `git`을 사용한다. 프로젝트 root에서 직접 확인할 수도 있다.

```sh
python3 -B scripts/collect_context.py src/lib.rs --scope src
python3 -B -m unittest evals.test_inspect evals.test_multilang -v
```

도우미는 프로젝트 코드를 실행하지 않으며 저장소 밖 경로를 읽지 않는다.
기본 소스 한도는 16개 파일/40,000바이트다. 누락·한도·검색 실패를 표시한다.
검색 결과는 참조 후보이며 완전한 호출 그래프가 아니다. 보고된 빈틈을 추가 확인하고
필수 언어별 검사·통합 검사를 수행해야 한다. 수집 한도 준수는 대형 저장소에서의
성능 우위나 모든 변경 영향의 발견을 보장하지 않는다.

## 업데이트 기록

- **2026-10-06 · 문서 자동 동기화** — 한국어·영어 README에서 웹 본문을 생성하고, 언어 전환과 목차를 연결했다. 블루·블랙 디자인은 유지한다.
- **2026-10-06 · v4** — 여러 언어와 모노레포 탐색, 반복 `--scope`, `--symbol`, 파일 지도와 출력 한도를 추가했다. [기능 검증과 한계](evals/MULTILANG_20261006.md)
- **2026-10-06 · 문서 웹사이트** — 하나의 프로젝트 페이지에서 한국어·영어 README, 설치 방법, 누적 업데이트와 검증 보고서를 연결했다. [웹사이트 소스](index.html) · [English README](README.en.md)
- **2026-10-06 · 웹 디자인** — 프로젝트 페이지에 블루·블랙 색상과 문서 중심 레이아웃을 적용했다. [프로젝트 페이지](https://rem0116kjh.github.io/suffice-patch/)
- **2026-10-06 · v3 외부 저장소 평가** — 실제 과거 문제의 24회 비교와 원자료 감사를 완료하고, 새 경로의 평가 준비를 모델 재호출 없이 확인했다. [보고서](evals/GENERALIZATION_20261006.md) · [사전 계획](evals/GENERALIZATION_PLAN_20261006.md) · [전체 결과](evals/runs/generalization-20261006/RESULTS.md)
- **2026-10-06 · v3 최적화** — 수집기의 중복 작업과 한도 소진 후 검색을 줄이고, 도우미 단독 측정과 에이전트 재실행을 구분해 기록했다. [최적화 기록](evals/OPTIMIZATION_20261006.md)
- **2026-10-03 · v3 자동 선택** — 자동 선택 조건의 Python 과제 비교, 별도 workflow 비교와 실패한 후보를 함께 보존했다. [v3 측정 기록](evals/V3_RESULTS.md)
- **2026-10-03 · v2** — 양쪽 16/16 성공에도 토큰이 5.36% 늘어 연구를 중단한 결론을 보존했다. [상세 결과](evals/EVAL_RESULTS.md) · [당시 README](evals/README_V2.md)
- **초기 설계 · v1 (날짜 미기록)** — 의도 → 맥락 → 최소한의 해결 → 구현 → 검증 → 중단의 작업 흐름을 설계했다. [초기 초안](evals/prototype-v1.md) · [v1 기록](evals/v1.md)

## 보존한 기록

v2는 성공률을 유지했지만 토큰이 5.36% 늘었다. 당시의 중단 결론을 덮어쓰지 않고
[v2 README](evals/README_V2.md)와 [v2 상세 결과](evals/EVAL_RESULTS.md)로 보존했다.
새 결과는 사용자 요청으로 재개한 별도 v3 실험이다. 이전 설치본도
[백업과 설치 기록](evals/installation-v3.json)에 남겼다.

## 문서와 웹페이지 업데이트

한국어 웹 본문은 `README.md`, 영어 웹 본문은 `README.en.md`에서 가져온다.
내용을 수정하고 `main`에 커밋·푸시하면 GitHub Pages가 두 문서를 정적 HTML로
변환해 배포한다. 반영 시점은 Pages 빌드와 배포가 끝난 뒤다.

`index.html`은 블루·블랙 디자인과 문서 연결을 담당하는 템플릿이다.
소개·지원 범위·수치·업데이트는 해당 언어의 README에서 수정하면 되고,
웹페이지 목차도 README 제목에서 만들어진다. 디자인을 바꿀 때만 템플릿을 수정한다.
