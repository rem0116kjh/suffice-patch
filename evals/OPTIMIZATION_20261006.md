# SufficePatch 최적화 및 실제 실행 — 2026-10-06

작은 Python 수정의 문맥 수집을 돕는 스킬이다. 이번에는 **도우미의 중복 탐색 비용을 줄였고,
실제 Codex 과제에서도 자동 선택·도우미 실행·수정 성공을 확인했다.** 전체 에이전트가
더 빨라졌다거나 청구 비용이 줄었다는 결론은 내리지 않는다.

## 코드 변경

- 목록 앞 삭제와 대기 목록 선형 탐색을 `deque`와 집합으로 교체했다.
- 같은 경로·실제 파일을 다시 탐색하거나 읽지 않는다. 용량 초과·비 UTF-8 파일도 재시도하지 않는다.
- 첫 AST 분석에서 대상 심볼을 저장해 중복 파싱을 없앴다. `.pyi`처럼 직접 지정한 다른 확장자의 Python 심볼 검색도 유지했다.
- 파일 한도가 찼으면 전체 저장소의 caller 검색을 생략하고 누락 가능성을 표시한다.
- Git clean/process 필터와 ripgrep 설정의 전처리기 실행을 차단했다. 와일드카드가 들어간 실제 파일명도 Git diff에서는 문자 그대로 처리한다.
- 기본 16개 파일/40,000바이트 소스 한도, 기존 SKILL.md와 자동 선택 방식은 유지했다.

[코드](../scripts/collect_context.py), [회귀 검사](test_inspect.py), [벤치마크 실행기](bench_inspector.py).

## 도우미 실행 시간: 기존 코드 대 최종 코드

macOS arm64, Python 3.14.7에서 조건별 준비 실행 1쌍과 측정 7쌍을 실행했다.
실행 순서를 번갈아 바꾸었고, 아래 값은 프로세스 시작·검색·Git 호출을 포함한 중앙값이다.
이 측정에는 LLM 호출이 없다.

| 조건 | 기존 | 최종 | 시간 변화 |
|---|---:|---:|---:|
| 작은 Python 프로젝트 | 92.96ms | 102.84ms | 10.62% 증가 |
| 반복 import 2,000회 | 209.32ms | 121.09ms | 42.15% 감소 |
| 호출 후보 2,000개 | 644.51ms | 227.88ms | 64.64% 감소 |
| 호출 후보 2,000개, 파일 한도 1개 | 613.05ms | 123.95ms | 79.78% 감소 |

모든 조건에서 반환 소스의 파일명·SHA256·순서가 같았다. 앞의 세 조건은 stdout 전체도
일치했고, 파일 한도 조건은 caller 검색을 건너뛴 안내만 달랐다. 작은 프로젝트에는
Git 필터 확인용 프로세스 비용이 추가되어 약 10ms 느려졌다.

큰 합성 사례는 병목 확인용이며 일반 저장소의 대표 표본이 아니다. 파일 캐시는 준비된
상태이고 호스트 부하를 완전히 통제하지 않았다. 원시 측정값과 환경은
[bench.json](runs/optimization-20261006/bench.json)에 있다. 안전 옵션과 `.pyi` 회귀 수정으로
코드가 바뀔 때 다시 측정했으며, 앞선 측정은 `bench-initial.json`과
`bench-pre-stub-fix.json`에 보존했다.

## 실제 Codex 실행: 미사용 대 자동 선택, 각 1회

Codex CLI 0.160.0 / `gpt-6-astra` / `low`. 같은 `inventory.reserve_many` 과제를
미사용 조건부터 차례로 실행했다. 실패 시 재고 전체를 보존하고, 성공 시 재고를 수정하되
분리된 반환 복사본을 제공하는 작업이다. 평가용 정답·검사는 에이전트에 주입하지 않았다.

| 측정 | 스킬 미사용 | 자동 선택 |
|---|---:|---:|
| 과제 성공 | 1/1 | 1/1 |
| 독립 검사 그룹 | 3/3 | 3/3 |
| 입력 + 출력 토큰 | 54,549 | 42,875 |
| 입력 중 캐시 토큰 | 39,168 | 26,624 |
| 캐시 제외 입력 토큰 | 14,601 | 15,336 |
| 출력 토큰 | 780 | 915 |
| 완료 도구 이벤트 | 4 | 4 |
| 에이전트 경과 시간 | 26.441초 | 29.470초 |

**총 토큰은 21.40% 줄었지만, 시간은 11.46% 늘었다.** 캐시 제외 입력 토큰은 5.03%
늘었고 출력 토큰도 늘었다. 캐시 입력은 입력 토큰의 부분집합으로 중복 합산하지 않았다.
실제 청구 금액을 측정하지 않았으므로 토큰 총량 감소를 비용 절감으로 바꾸어 말하지 않는다.

발견 검사는 미사용 조건에서 사용자 설치본과 저장소 설치본을 모두 끄고, 자동 선택 조건에서
평가용 저장소 설치본만 켰음을 확인했다. 원시 실행 기록에서 자동 선택 조건만 SKILL.md를
읽고 `collect_context.py inventory.py`를 종료 코드 0으로 실행했다. 스킬 읽기와 도우미 실행은
각각 별도 도구 호출이었으며, 전체 도구 이벤트 수는 줄지 않았다. 두 조건 모두
`inventory.py`만 수정했고 무관 파일과 평가용 스킬 파일을 보존했다.

이 비교는 **스킬 유무의 차이**를 본 1개 합성 과제의 기술적 관측이다. 이전 스킬과 최종
스킬을 LLM으로 직접 비교한 결과가 아니며, 큰 저장소·다른 과제·Claude에 일반화할 수 없다.
기존 2026-10-03 결과도 [V3_RESULTS.md](V3_RESULTS.md)에 별도로 보존했다.

### 평가 코드 버전의 구분

네이티브 실행은 도우미 `76c6314d8574b1514b827c1d45c425dfd0182e3cab8aa7ee8097c9e182ffc54c`로
진행했다. 실행 중 검토에서 직접 지정한 `.pyi` 대상의 심볼 검색 누락을 발견해 최종 코드에서
복구했다. 최종 도우미는 `a2968d41be8c1fb5954d0399777ef122ab99bc201c67bc5d33cb9bf4ff91347e`다.
이 후속 수정은 요청한 비 `.py` 파일의 분석에만 영향을 주며, 같은 초기 `inventory` fixture에서
두 도우미의 **stdout 완전 일치**를 별도 프로세스로 확인했다. 최종 도우미에 대한 LLM 재실행은
하지 않았다. 위 도우미 시간 측정은 최종 코드에 대한 것이다.

- [네이티브 원자료](runs/optimization-native-20261006/results.json) · [실행 감사](runs/optimization-native-20261006/audit.json)
- [발견 검사](runs/optimization-20261006/native-discovery.json) · [도우미 출력 동등성](runs/optimization-20261006/final-helper-equivalence.json)

## 검증과 설치

최종 코드의 회귀 검사 **12/12 통과**. 외부 경로·심볼릭 링크 탈출, 입력 파일 보존,
상대 import, 소스 한도, 중복 읽기, 불필요한 검색, Git 외부 diff/textconv/fsmonitor와
clean/process 필터, ripgrep 전처리기, Git 파일명 처리, `.pyi` 심볼 검색을 확인했다.
채점기 자체 검사도 4개 과제에서 알려진 정답을 수용하고 오답·빈 구현을 거부했다.

현재 Codex와 Claude의 설치된 도우미를 백업 후 최종 코드로 갱신했고, 소스 SHA256 일치를
확인했다. SKILL.md와 자동 선택 설정은 바꾸지 않았다.
[설치 경로·백업·해시 기록](runs/optimization-20261006/installation.json).
Claude 에이전트의 별도 실시간 실행은 이번에 하지 않았다.

도우미는 정적·텍스트 탐색이다. 동적 호출, 다른 언어 테스트, `src/` 패키지 경로 해석,
대상 외 디렉터리에 있는 추가 AGENTS.md를 완전히 수집하지 않는다. 발견한 다른 파일을
수정할 때에는 그 디렉터리의 지침을 별도로 확인해야 한다. 소스 한도는 검색 시간이나
모든 하위 프로세스 출력의 엄격한 메모리 한도를 뜻하지 않는다.

## 재현

저장소 루트에서 최종 도우미와 단위 검사를 실행한다.

```sh
python3 -B scripts/collect_context.py scripts/collect_context.py
python3 -B -m unittest evals/test_inspect.py -v
python3 -B evals/bench_inspector.py \
  --before evals/runs/optimization-20261006/collect_context.before.py \
  --after scripts/collect_context.py --output /tmp/suffice-inspector-benchmark.json
```

같은 고정 번들로 네이티브 비교를 재현하려면 새 출력 경로를 사용한다.
이 명령은 Codex 모델을 다시 호출한다. `--skill`에는 저장소 루트 대신 두 파일만 담긴
평가용 번들의 SKILL.md를 지정한다.

```sh
python3 -B evals/v3_native.py \
  --out /tmp/suffice-native-recheck \
  --skill evals/runs/optimization-native-20261006/skill/SKILL.md \
  --tasks inventory --arms baseline,implicit --repeats 1 \
  --model gpt-6-astra --effort low --timeout 240
```
