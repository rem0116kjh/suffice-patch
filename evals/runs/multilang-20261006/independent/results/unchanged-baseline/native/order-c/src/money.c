#include "../include/money.h"

int money_subtotal(const order_line *lines, size_t count, uint64_t *result) {
    if (!result || (count && !lines)) return -1;
    uint64_t total = 0;
    for (size_t i = 0; i < count; ++i) {
        if (!lines[i].quantity) return -1;
        if (lines[i].price_cents > UINT64_MAX / lines[i].quantity) return -2;
        uint64_t amount = lines[i].price_cents * lines[i].quantity;
        if (total > UINT64_MAX - amount) return -2;
        total += amount;
    }
    *result = total;
    return 0;
}
