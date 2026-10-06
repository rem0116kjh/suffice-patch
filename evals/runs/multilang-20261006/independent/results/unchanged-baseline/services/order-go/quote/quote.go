package quote

import (
    "errors"
    "example.test/order/internal/money"
)

type Line = money.Line
type Quote struct { SubtotalCents uint64; ShippingCents uint64; TotalCents uint64 }

func Calculate(lines []Line) (Quote, error) {
    subtotal, err := money.Subtotal(lines)
    if err != nil { return Quote{}, err }
    var shipping uint64
    if subtotal != 0 { shipping = 500 }
    if subtotal > ^uint64(0) - shipping { return Quote{}, errors.New("amount overflow") }
    return Quote{subtotal, shipping, subtotal + shipping}, nil
}
