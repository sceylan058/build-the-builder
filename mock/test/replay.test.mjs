// Replay every entry of the pack through lookup() and require the exact http, body and delay.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { lookup, matchCard } from "../src/lookup.js";
const DATA = JSON.parse(readFileSync(new URL("../src/test-customers.json", import.meta.url)));
let n = 0;
for (const c of DATA.customers) {
  for (const [svc, v] of Object.entries(c.services)) {
    const visit = (node, card, week) => {
      if (node && typeof node === "object" && "http" in node) {
        const r = lookup(svc, c.customerNo, card, week);
        assert.equal(r.http, node.http, `${c.customerNo} ${svc} ${card} ${week}`);
        assert.deepEqual(r.response, node.response);
        assert.equal(r.delaySeconds, node.delaySeconds || 0);
        n++; return;
      }
      for (const [k, x] of Object.entries(node)) {
        if (["cards.balance", "statement.week.get", "statement.week.decide", "statement.week.change"].includes(svc) && card === undefined) visit(x, k, undefined);
        else visit(x, card, k);
      }
    };
    visit(v, undefined, undefined);
  }
}
// card matching variants
const keys = ["540000******1234", "540000******5678"];
assert.equal(matchCard(keys, "5400********1234"), "540000******1234");
assert.equal(matchCard(keys, "1234"), "540000******1234");
assert.equal(matchCard(keys, "5400001111111234"), "540000******1234");
assert.equal(matchCard(keys, "9999"), null);
assert.equal(matchCard(["540000******1234", "550000******1234"], "1234"), null);   // ambiguous last 4
assert.equal(lookup("cards.list", "00000000").http, 404);
console.log(`replay OK: ${n} entries`);
