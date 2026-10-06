package main

import (
    "encoding/json"
    "fmt"
    "os"
    "reflect"
    q "example.test/order/quote"
)

type Check struct { Name string `json:"name"`; Passed bool `json:"passed"`; Error string `json:"error,omitempty"` }
func main() {
    checks := []Check{}
    check := func(name string, lines []q.Line, expected q.Quote, wantError bool) {
        var before []q.Line
        if lines != nil { before = append([]q.Line{}, lines...) }
        got, err := q.Calculate(lines)
        passed := reflect.DeepEqual(before, lines) && ((wantError && err != nil && got == (q.Quote{})) || (!wantError && err == nil && got == expected))
        detail := ""
        if !passed { detail = fmt.Sprintf("got=%+v err=%v expected=%+v wantError=%v", got, err, expected, wantError) }
        checks = append(checks, Check{name, passed, detail})
    }
    check("below_threshold", []q.Line{{9999,1}}, q.Quote{9999,500,10499}, false)
    check("at_threshold", []q.Line{{10000,1}}, q.Quote{10000,0,10000}, false)
    check("above_threshold", []q.Line{{10001,1}}, q.Quote{10001,0,10001}, false)
    check("threshold_from_multiple_lines", []q.Line{{7000,1},{3000,1}}, q.Quote{10000,0,10000}, false)
    check("threshold_from_quantity", []q.Line{{2500,4}}, q.Quote{10000,0,10000}, false)
    check("below_from_quantity", []q.Line{{3333,3}}, q.Quote{9999,500,10499}, false)
    check("empty", nil, q.Quote{}, false)
    check("zero_price", []q.Line{{0,3}}, q.Quote{}, false)
    check("maximum_representable_subtotal", []q.Line{{^uint64(0),1}}, q.Quote{^uint64(0),0,^uint64(0)}, false)
    check("invalid_quantity", []q.Line{{1,0}}, q.Quote{}, true)
    check("invalid_after_free_shipping_line", []q.Line{{10000,1},{1,0}}, q.Quote{}, true)
    check("multiplication_overflow", []q.Line{{^uint64(0),2}}, q.Quote{}, true)
    check("summation_overflow", []q.Line{{^uint64(0),1},{1,1}}, q.Quote{}, true)
    passed := 0
    for _, check := range checks { if check.Passed { passed++ } }
    json.NewEncoder(os.Stdout).Encode(map[string]any{"passed":passed,"total":len(checks),"failed":len(checks)-passed,"checks":checks})
    if passed != len(checks) { os.Exit(1) }
}
