# SufficePatch 외부 저장소 평가 결과

계획 24회 중 24회 기록, 미완료 0회. 비교 무효 0회. 성공·실패·스킬 미선택을 모두 포함했습니다.

토큰 개선 기준: **미충족**. 전체 에이전트 시간 개선 기준: **충족**. 실제 청구 비용은 측정하지 않았습니다.

| 항목 | baseline | 자동 선택 |
| --- | ---: | ---: |
| 성공 / 계획 | 12 / 12 | 12 / 12 |
| total_tokens 합계 | 1176381 (관측 12/12, 기록 내 누락 0) | 1450245 (관측 12/12, 기록 내 누락 0) |
| input_tokens 합계 | 1160331 (관측 12/12, 기록 내 누락 0) | 1435584 (관측 12/12, 기록 내 누락 0) |
| cached_input_tokens 합계 | 921088 (관측 12/12, 기록 내 누락 0) | 1108992 (관측 12/12, 기록 내 누락 0) |
| uncached_input_tokens 합계 | 239243 (관측 12/12, 기록 내 누락 0) | 326592 (관측 12/12, 기록 내 누락 0) |
| output_tokens 합계 | 16050 (관측 12/12, 기록 내 누락 0) | 14661 (관측 12/12, 기록 내 누락 0) |
| tool_calls 합계 | 82 (관측 12/12, 기록 내 누락 0) | 79 (관측 12/12, 기록 내 누락 0) |
| duration_seconds 합계 | 756.894 (관측 12/12, 기록 내 누락 0) | 611.213 (관측 12/12, 기록 내 누락 0) |

총 토큰은 input + output입니다. cached input은 input에 이미 포함되므로 다시 더하지 않았습니다. 누락값을 0으로 대체하지 않았으며, 합계는 관측된 모든 시도의 합입니다.

## 과제별 결과

| 과제 | 유형 | baseline 성공 | 자동 선택 성공 | 토큰 비율 중앙값 | 시간 비율 중앙값 |
| --- | --- | ---: | ---: | ---: | ---: |
| dotenv-backslash-roundtrip | 버그 수정 | 3/3 | 3/3 | 1.201 | 0.839 |
| packaging_epoch_prefix | 버그 수정 | 3/3 | 3/3 | 1.397 | 0.832 |
| itsdangerous-invalid-timestamp | 버그 수정 | 3/3 | 3/3 | 1.099 | 0.677 |
| itsdangerous-expiration-noop | 변경 불필요 | 3/3 | 3/3 | 1.138 | 0.681 |

비율은 자동 선택 / baseline이며 1보다 작으면 적게 사용한 것입니다. 각 과제의 모든 반복쌍을 포함하며 하나라도 필요한 값이 없으면 그 과제 중앙값을 산출하지 않습니다.

- 사전 플랫폼 제외 (dotenv-backslash-roundtrip): tests/test_cli.py::test_run_with_command_flags — This historical test invokes GNU printenv --version; macOS BSD printenv has no --version. The complete unchanged base suite reports 222 passed and this 1 unrelated failure.

## 사전 고정한 통계

| 지표 | 과제 동일 가중 기하평균 비율 | 과제 bootstrap 95% | 프로젝트 cluster bootstrap 95% |
| --- | ---: | --- | --- |
| total_tokens | 1.204 | 1.118 – 1.327 | 1.118 – 1.397 |
| input_tokens | 1.208 | 1.121 – 1.332 | 1.121 – 1.404 |
| cached_input_tokens | 1.149 | 1.013 – 1.326 | 1.013 – 1.438 |
| uncached_input_tokens | 1.351 | 1.271 – 1.432 | 1.225 – 1.432 |
| output_tokens | 0.962 | 0.880 – 1.052 | 0.860 – 1.052 |
| tool_calls | 1.003 | 0.822 – 1.225 | 0.750 – 1.225 |
| duration_seconds | 0.753 | 0.679 – 0.836 | 0.679 – 0.839 |

반복쌍 비율 → 과제별 중앙값 → 4개 과제 동일 가중 기하평균 순서입니다. seed 20261006, 10,000회 복원추출, percentile 95% 구간입니다. 프로젝트 보조 구간은 동일 프로젝트의 두 과제를 함께 재표집합니다. 적은 편의 표본의 기술적 구간이며 사용자 모집단의 통계적 보장이 아닙니다.

- tokens: 미충족; 요구 비율 ≤ 0.9, 과제 구간 상한 < 1.0; 사유: ratio_threshold_not_met, task_bootstrap_upper_not_below_one.
- latency: 충족; 요구 비율 ≤ 0.95, 과제 구간 상한 < 1.0; 사유: 모든 사전 기준 충족.

## 버그 수정과 변경 불필요 과제

| 그룹 | baseline 성공 / 계획 | 자동 선택 성공 / 계획 | 토큰 기하평균 비율 | 시간 기하평균 비율 |
| --- | ---: | ---: | ---: | ---: |
| bug_only | 9/9 | 9/9 | 1.227 | 0.779 |
| noop | 3/3 | 3/3 | 1.138 | 0.681 |

아래는 그룹별 모든 기록의 관측 합계입니다. 누락 횟수와 과제별 세부 합계는 `summary.json`에 보존합니다.

| 그룹 / 조건 | 총 토큰 | cached input | uncached input | output | 시간(s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| bug_only / baseline | 963563 | 760192 | 188835 | 14536 | 627.583 |
| bug_only / implicit | 1209534 | 942336 | 254108 | 13090 | 518.202 |
| noop / baseline | 212818 | 160896 | 50408 | 1514 | 129.311 |
| noop / implicit | 240711 | 166656 | 72484 | 1571 | 93.011 |

도우미 성공 실행: 계획된 자동 선택 시도 전체 12회 중 12회. 기록된 자동 선택 시도는 12회입니다. 미완료는 미선택으로 확정하지 않습니다.

## 모든 계획 시도

| 과제 | 반복 | 조건 | 성공 | 비교 유효 | 총 토큰 | 시간(s) | 도우미 성공 |
| --- | ---: | --- | --- | --- | ---: | ---: | --- |
| packaging_epoch_prefix | 3 | baseline | 성공 | True | 140010 | 92.008 | False |
| packaging_epoch_prefix | 3 | implicit | 성공 | True | 142318 | 76.593 | True |
| dotenv-backslash-roundtrip | 3 | implicit | 성공 | True | 163184 | 57.355 | True |
| dotenv-backslash-roundtrip | 3 | baseline | 성공 | True | 88186 | 68.333 | False |
| itsdangerous-expiration-noop | 3 | baseline | 성공 | True | 70110 | 45.972 | False |
| itsdangerous-expiration-noop | 3 | implicit | 성공 | True | 79763 | 31.295 | True |
| dotenv-backslash-roundtrip | 1 | implicit | 성공 | True | 130956 | 62.036 | True |
| dotenv-backslash-roundtrip | 1 | baseline | 성공 | True | 129243 | 74.485 | False |
| itsdangerous-expiration-noop | 2 | implicit | 성공 | True | 81203 | 26.082 | True |
| itsdangerous-expiration-noop | 2 | baseline | 성공 | True | 71236 | 39.190 | False |
| itsdangerous-invalid-timestamp | 3 | implicit | 성공 | True | 80357 | 24.565 | True |
| itsdangerous-invalid-timestamp | 3 | baseline | 성공 | True | 67730 | 39.891 | False |
| itsdangerous-invalid-timestamp | 1 | implicit | 성공 | True | 80930 | 39.940 | True |
| itsdangerous-invalid-timestamp | 1 | baseline | 성공 | True | 74550 | 44.634 | False |
| packaging_epoch_prefix | 1 | baseline | 성공 | True | 146543 | 89.149 | False |
| packaging_epoch_prefix | 1 | implicit | 성공 | True | 204766 | 71.952 | True |
| itsdangerous-expiration-noop | 1 | baseline | 성공 | True | 71472 | 44.149 | False |
| itsdangerous-expiration-noop | 1 | implicit | 성공 | True | 79745 | 35.634 | True |
| packaging_epoch_prefix | 2 | implicit | 성공 | True | 170739 | 75.229 | True |
| packaging_epoch_prefix | 2 | baseline | 성공 | True | 114405 | 83.460 | False |
| dotenv-backslash-roundtrip | 2 | baseline | 성공 | True | 129779 | 91.758 | False |
| dotenv-backslash-roundtrip | 2 | implicit | 성공 | True | 155928 | 80.817 | True |
| itsdangerous-invalid-timestamp | 2 | baseline | 성공 | True | 73117 | 43.865 | False |
| itsdangerous-invalid-timestamp | 2 | implicit | 성공 | True | 80356 | 29.715 | True |

## 한계

- Three small Python projects, named localized tasks, one computer/model/configuration; no other-user or broad language/platform claim
- Historical public fixes may occur in model training data
- Four tasks are not 24 independent tasks; one project's two tasks are dependent
- Repeated runs are not independent human users; bootstrap intervals are descriptive
- Failed attempts and automatic non-selection remain in accuracy, totals, and paired ratios
- No actual billing or monetary savings were measured

원시 기록은 `results.json`, 고정 조건은 `manifest.json`, 기계 판독 가능한 전체 합계·반복쌍·판정은 `summary.json`에 있습니다.
