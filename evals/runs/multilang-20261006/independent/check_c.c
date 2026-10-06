#include "quote.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static int passed, total;
static void record(const char *name, int okay) {
    if (total) fputc(',', stdout);
    printf("{\"name\":\"%s\",\"passed\":%s}", name, okay ? "true" : "false");
    total++; passed += !!okay;
}
static void check(const char *name, const order_line *lines, size_t count, order_quote expected, int error) {
    order_quote result = {91, 92, 93};
    order_line before[3];
    if (count) memcpy(before, lines, count * sizeof(*lines));
    int status = make_quote(lines, count, &result);
    int okay = status == error;
    if (!error) okay &= result.subtotal_cents == expected.subtotal_cents && result.shipping_cents == expected.shipping_cents && result.total_cents == expected.total_cents;
    else okay &= result.subtotal_cents == 91 && result.shipping_cents == 92 && result.total_cents == 93;
    if (count) okay &= memcmp(before, lines, count * sizeof(*lines)) == 0;
    record(name, okay);
}
int main(void) {
    fputs("{\"checks\":[", stdout);
    check("below_threshold", (order_line[]){{9999,1}}, 1, (order_quote){9999,500,10499}, 0);
    check("at_threshold", (order_line[]){{10000,1}}, 1, (order_quote){10000,0,10000}, 0);
    check("above_threshold", (order_line[]){{10001,1}}, 1, (order_quote){10001,0,10001}, 0);
    check("threshold_from_multiple_lines", (order_line[]){{7000,1},{3000,1}}, 2, (order_quote){10000,0,10000}, 0);
    check("threshold_from_quantity", (order_line[]){{2500,4}}, 1, (order_quote){10000,0,10000}, 0);
    check("below_from_quantity", (order_line[]){{3333,3}}, 1, (order_quote){9999,500,10499}, 0);
    check("empty", NULL, 0, (order_quote){0,0,0}, 0);
    check("zero_price", (order_line[]){{0,3}}, 1, (order_quote){0,0,0}, 0);
    check("maximum_representable_subtotal", (order_line[]){{UINT64_MAX,1}}, 1, (order_quote){UINT64_MAX,0,UINT64_MAX}, 0);
    check("invalid_quantity", (order_line[]){{1,0}}, 1, (order_quote){0,0,0}, -1);
    check("invalid_after_free_shipping_line", (order_line[]){{10000,1},{1,0}}, 2, (order_quote){0,0,0}, -1);
    check("multiplication_overflow", (order_line[]){{UINT64_MAX,2}}, 1, (order_quote){0,0,0}, -2);
    check("summation_overflow", (order_line[]){{UINT64_MAX,1},{1,1}}, 2, (order_quote){0,0,0}, -2);
    record("null_output", make_quote(NULL, 0, NULL) == -1);
    order_quote untouched = {91,92,93};
    record("null_nonempty_input", make_quote(NULL, 1, &untouched) == -1 && untouched.total_cents == 93);
    printf("],\"passed\":%d,\"total\":%d,\"failed\":%d}\n", passed, total, total-passed);
    return passed != total;
}
