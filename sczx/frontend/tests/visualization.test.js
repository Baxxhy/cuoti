import test from "node:test";
import assert from "node:assert/strict";
import { balanceSpec, applyBalance } from "../src/lib/visualization.js";
test("balance single and common actions preserve actual relation and bounds", () => {
  const s = balanceSpec({ type: "balance", base: 5, step: 1, max: 3 });
  let v = applyBalance(s, s.initial, "left_add");
  assert.deepEqual(v, { left: 6, right: 5 });
  v = applyBalance(s, v, "right_add");
  assert.deepEqual(v, { left: 6, right: 6 });
  assert.deepEqual(applyBalance(s, v, "both_subtract"), { left: 5, right: 5 });
  assert.throws(() => applyBalance(s, { left: 0, right: 0 }, "both_subtract"));
  assert.throws(() =>
    balanceSpec({ type: "javascript", initial: { left: 1, right: 1 } }),
  );
});
