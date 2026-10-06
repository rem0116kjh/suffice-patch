package money

import "errors"

type Line struct { PriceCents uint64; Quantity uint64 }

func Subtotal(lines []Line) (uint64, error) {
    var total uint64
    for _, line := range lines {
        if line.Quantity == 0 { return 0, errors.New("invalid quantity") }
        if line.PriceCents > ^uint64(0) / line.Quantity { return 0, errors.New("amount overflow") }
        amount := line.PriceCents * line.Quantity
        if total > ^uint64(0) - amount { return 0, errors.New("amount overflow") }
        total += amount
    }
    return total, nil
}
