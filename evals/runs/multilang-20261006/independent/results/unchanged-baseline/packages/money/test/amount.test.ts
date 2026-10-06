import test from "node:test";
import assert from "node:assert/strict";
import { checkedSubtotal, type Line } from "../src/amount.ts";

test("typed immutable lines", () => {
  const lines: readonly Line[] = Object.freeze([Object.freeze({priceCents: 250, quantity: 3})]);
  assert.equal(checkedSubtotal(lines), 750);
});
test("negative price rejected", () => assert.throws(() => checkedSubtotal([{priceCents: -1, quantity: 1}]), RangeError));
test("fractional price rejected", () => assert.throws(() => checkedSubtotal([{priceCents: 1.5, quantity: 1}]), RangeError));
