#ifndef ORDER_MONEY_H
#define ORDER_MONEY_H
#include <stddef.h>
#include <stdint.h>
typedef struct { uint64_t price_cents; uint64_t quantity; } order_line;
int money_subtotal(const order_line *lines, size_t count, uint64_t *result);
#endif
