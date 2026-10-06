# Independent multilingual forward test

Completed the requested shipping rule in four source files. Each existing source has one changed condition: checked subtotals from 1 through 9999 cents cost 500 cents shipping; zero and subtotals of at least 10000 cost zero. Existing checked subtotal helpers and final overflow checks are unchanged.

Changed existing files:
- apps/storefront/src/quote.js
- services/order-go/quote/quote.go
- native/order-c/src/quote.c
- services/order-java/src/example/order/QuoteService.java

Added four new test files, one per language, covering 1, 9999, 10000, 10001, maximum representable subtotal, multi-line/quantity aggregation, invalid lines after crossing the threshold, and aggregate overflow. C also checks null arguments and preserved output on failure.

Validation: JS/TS 15 tests passed; Go 8 tests passed; existing C and Java suites plus new boundary suites compiled and passed. C used clang -std=c17 -Wall -Wextra -Werror; Java used OpenJDK 21 with assertions enabled. git diff --check passed. Exact commands, working directories, exit codes, elapsed times, stdout, and stderr are in checks.json and the per-check JSON/text files. Go ran with GOPROXY=off, GOSUMDB=off, GOTOOLCHAIN=local and an external cache.

SHA-256 comparison verified that only the four authorized existing files changed. All existing tests, local helpers, Rust files, LOCAL_NOTES.md user changes, and DRAFT.txt user untracked contents are preserved. Four new tests are the only added checkout files. See preservation.json and initial/final hashes.

Rust was not modified or tested: rustc and cargo were unavailable on PATH (environment.json). JS/TS checks executed with the project's declared Node test command; no separate static TypeScript check is declared or claimed. C's added test was compiled and executed explicitly because changing CMakeLists.txt was outside the authorized existing-file scope.

Helper use and limits:
- Used only the designated bundle's SKILL.md and read-only collect_context.py, from the fixture root. Both invocations' commands/stdout/stderr/exit codes are recorded in context* files.
- Initial four-language collection reached its 16-source file limit. A focused second collection included Java Money/Line and existing Java/Go tests; targeted reads supplied C money.c and the TypeScript money tests.
- Java provides textual references only, with no Java import/call-graph resolution. JS/TS, Go, and C import/include hints are limited; unresolved/external references were reported. No complete dependency graph is claimed.
- Scoped Git output omitted unrelated root-level dirty and untracked files. An independent full Git status plus before/after file hashes was necessary to establish preservation.
- The helper identifies manifests but does not select or run checks. AGENTS.md, package.json/go.mod/go.work/CMakeLists.txt, and the provided native compile-command evidence determined actual validation.

No external network, package installation, additional model calls, commits, or pushes were used. Root repository, skill, and bundle files were not modified. No token or time savings are inferred.

## Actual verification commands

- `javascript_typescript`: exit 0; cwd `/private/tmp/suffice-multilang-fixture-20261006-dua88vzs/monorepo`

  ```sh
  /opt/homebrew/bin/node --test apps/storefront/test/quote.test.js packages/money/test/amount.test.ts apps/storefront/test/shipping-threshold.test.js
  ```

- `go`: exit 0; cwd `/private/tmp/suffice-multilang-fixture-20261006-dua88vzs/monorepo/services/order-go`

  ```sh
  /opt/homebrew/opt/go/libexec/bin/go test -count=1 -v ./...
  ```

- `c_compile`: exit 0; cwd `/private/tmp/suffice-multilang-fixture-20261006-dua88vzs/monorepo`

  ```sh
  /usr/bin/clang -std=c17 -Wall -Wextra -Werror native/order-c/src/money.c native/order-c/src/quote.c native/order-c/tests/test_quote.c -o /private/tmp/suffice-multilang-fixture-20261006-dua88vzs/forward-evidence/build/test_quote
  ```

- `c_execute`: exit 0; cwd `/private/tmp/suffice-multilang-fixture-20261006-dua88vzs/monorepo`

  ```sh
  /private/tmp/suffice-multilang-fixture-20261006-dua88vzs/forward-evidence/build/test_quote
  ```

- `c_threshold_compile`: exit 0; cwd `/private/tmp/suffice-multilang-fixture-20261006-dua88vzs/monorepo`

  ```sh
  /usr/bin/clang -std=c17 -Wall -Wextra -Werror native/order-c/src/money.c native/order-c/src/quote.c native/order-c/tests/test_shipping_threshold.c -o /private/tmp/suffice-multilang-fixture-20261006-dua88vzs/forward-evidence/build/test_shipping_threshold
  ```

- `c_threshold_execute`: exit 0; cwd `/private/tmp/suffice-multilang-fixture-20261006-dua88vzs/monorepo`

  ```sh
  /private/tmp/suffice-multilang-fixture-20261006-dua88vzs/forward-evidence/build/test_shipping_threshold
  ```

- `java_compile`: exit 0; cwd `/private/tmp/suffice-multilang-fixture-20261006-dua88vzs/monorepo`

  ```sh
  /opt/homebrew/opt/openjdk@21/bin/javac -d /private/tmp/suffice-multilang-fixture-20261006-dua88vzs/forward-evidence/build/java services/order-java/src/example/order/Line.java services/order-java/src/example/order/Money.java services/order-java/src/example/order/QuoteService.java services/order-java/tests/example/order/QuoteTests.java services/order-java/tests/example/order/ShippingThresholdTests.java
  ```

- `java_execute`: exit 0; cwd `/private/tmp/suffice-multilang-fixture-20261006-dua88vzs/monorepo`

  ```sh
  /opt/homebrew/opt/openjdk@21/bin/java -ea -cp /private/tmp/suffice-multilang-fixture-20261006-dua88vzs/forward-evidence/build/java example.order.QuoteTests
  ```

- `java_threshold_execute`: exit 0; cwd `/private/tmp/suffice-multilang-fixture-20261006-dua88vzs/monorepo`

  ```sh
  /opt/homebrew/opt/openjdk@21/bin/java -ea -cp /private/tmp/suffice-multilang-fixture-20261006-dua88vzs/forward-evidence/build/java example.order.ShippingThresholdTests
  ```

- `diff_check`: exit 0; cwd `/private/tmp/suffice-multilang-fixture-20261006-dua88vzs/monorepo`

  ```sh
  git diff --check
  ```

