Keep unrelated user files and changes intact. Do not edit existing tests to satisfy new behavior.
This is a dependency-free synthetic multi-language fixture, not an external project benchmark.
JS/TS: node --test apps/storefront/test/quote.test.js packages/money/test/amount.test.ts
Go: cd services/order-go && GOPROXY=off GOSUMDB=off GOTOOLCHAIN=local go test ./...
Native C and Java compile commands are recorded outside this checkout in evidence.
