#ifndef ORDER_QUOTE_H
#define ORDER_QUOTE_H
#include "money.h"
typedef struct { uint64_t subtotal_cents; uint64_t shipping_cents; uint64_t total_cents; } order_quote;
int make_quote(const order_line *lines, size_t count, order_quote *result);
#endif
