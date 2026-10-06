import test from "node:test";
import assert from "node:assert/strict";
import { quote } from "../src/quote.js";

test("empty order", () => assert.deepEqual(quote([]), {subtotalCents: 0, shippingCents: 0, totalCents: 0}));
test("ordinary order and unchanged input", () => {
  const lines = [{priceCents: 1200, quantity: 2}, {priceCents: 300, quantity: 1}];
  const before = JSON.stringify(lines);
  assert.deepEqual(quote(lines), {subtotalCents: 2700, shippingCents: 500, totalCents: 3200});
  assert.equal(JSON.stringify(lines), before);
});
test("zero price", () => assert.equal(quote([{priceCents: 0, quantity: 1}]).totalCents, 0));
test("invalid quantity", () => assert.throws(() => quote([{priceCents: 100, quantity: 0}]), RangeError));
test("multiplication overflow", () => assert.throws(() => quote([{priceCents: Number.MAX_SAFE_INTEGER, quantity: 2}]), RangeError));
