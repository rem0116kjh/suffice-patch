export type Line = Readonly<{ priceCents: number; quantity: number }>;

export function checkedSubtotal(lines: readonly Line[]): number {
  let subtotal = 0;
  for (const line of lines) {
    if (!Number.isSafeInteger(line.priceCents) || line.priceCents < 0 ||
        !Number.isSafeInteger(line.quantity) || line.quantity <= 0) {
      throw new RangeError("invalid line");
    }
    const amount = line.priceCents * line.quantity;
    if (!Number.isSafeInteger(amount) || !Number.isSafeInteger(subtotal + amount)) {
      throw new RangeError("amount overflow");
    }
    subtotal += amount;
  }
  return subtotal;
}
