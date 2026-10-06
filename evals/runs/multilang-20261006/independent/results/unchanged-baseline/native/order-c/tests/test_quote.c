#include "../include/quote.h"
#include <assert.h>
#include <stdio.h>

int main(void) {
    order_quote result = {99, 99, 99};
    assert(make_quote(NULL, 0, &result) == 0 && result.total_cents == 0);
    const order_line ordinary[] = {{1200, 2}, {300, 1}};
    assert(make_quote(ordinary, 2, &result) == 0);
    assert(result.subtotal_cents == 2700 && result.shipping_cents == 500 && result.total_cents == 3200);
    const order_line zero[] = {{0, 1}};
    assert(make_quote(zero, 1, &result) == 0 && result.total_cents == 0);
    result = (order_quote){99, 99, 99};
    const order_line invalid[] = {{100, 0}};
    assert(make_quote(invalid, 1, &result) == -1 && result.total_cents == 99);
    const order_line overflow[] = {{UINT64_MAX, 2}};
    assert(make_quote(overflow, 1, &result) == -2 && result.total_cents == 99);
    puts("C_BASELINE_OK groups=5");
    return 0;
}
