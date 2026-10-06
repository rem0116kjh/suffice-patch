#include "../include/quote.h"

int make_quote(const order_line *lines, size_t count, order_quote *result) {
    if (!result) return -1;
    uint64_t subtotal;
    int status = money_subtotal(lines, count, &subtotal);
    if (status) return status;
    uint64_t shipping = subtotal == 0 ? 0 : 500;
    if (subtotal > UINT64_MAX - shipping) return -2;
    *result = (order_quote){subtotal, shipping, subtotal + shipping};
    return 0;
}
