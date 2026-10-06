import { checkedSubtotal } from "../../../packages/money/src/amount.ts";

export function quote(lines) {
  const subtotalCents = checkedSubtotal(lines);
  const shippingCents = subtotalCents === 0 ? 0 : 500;
  const totalCents = subtotalCents + shippingCents;
  if (!Number.isSafeInteger(totalCents)) throw new RangeError("amount overflow");
  return { subtotalCents, shippingCents, totalCents };
}
