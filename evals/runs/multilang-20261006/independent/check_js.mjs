import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";
const { quote } = await import(pathToFileURL(path.join(process.argv[2], "apps/storefront/src/quote.js")).href);
const checks = [];
function check(name, lines, expected, expectedError) {
  const before = structuredClone(lines);
  try {
    if (expectedError) assert.throws(() => quote(lines), expectedError);
    else assert.deepEqual(quote(lines), {subtotalCents: expected[0], shippingCents: expected[1], totalCents: expected[2]});
    assert.deepEqual(lines, before);
    checks.push({name, passed: true});
  } catch (error) { checks.push({name, passed: false, error: String(error)}); }
}
const line = (priceCents, quantity = 1) => ({priceCents, quantity});
check("below_threshold", [line(9999)], [9999, 500, 10499]);
check("at_threshold", [line(10000)], [10000, 0, 10000]);
check("above_threshold", [line(10001)], [10001, 0, 10001]);
check("threshold_from_multiple_lines", [line(7000), line(3000)], [10000, 0, 10000]);
check("threshold_from_quantity", [line(2500, 4)], [10000, 0, 10000]);
check("below_from_quantity", [line(3333, 3)], [9999, 500, 10499]);
check("empty", [], [0, 0, 0]);
check("zero_price", [line(0, 3)], [0, 0, 0]);
check("maximum_representable_subtotal", [line(Number.MAX_SAFE_INTEGER)], [Number.MAX_SAFE_INTEGER, 0, Number.MAX_SAFE_INTEGER]);
check("invalid_quantity", [line(1, 0)], null, RangeError);
check("invalid_after_free_shipping_line", [line(10000), line(1, 0)], null, RangeError);
check("negative_price", [line(-1)], null, RangeError);
check("fractional_price", [line(0.5)], null, RangeError);
check("multiplication_overflow", [line(Number.MAX_SAFE_INTEGER, 2)], null, RangeError);
check("summation_overflow", [line(Number.MAX_SAFE_INTEGER), line(1)], null, RangeError);
const passed = checks.filter(row => row.passed).length;
console.log(JSON.stringify({passed, total: checks.length, failed: checks.length - passed, checks}));
process.exitCode = Number(passed !== checks.length);
