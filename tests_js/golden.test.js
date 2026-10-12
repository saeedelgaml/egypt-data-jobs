// The browser chatbot must answer exactly like the Python chatbot. tests/data/router_golden.json is
// written by make_router_golden.py from the Python code; every case is replayed here.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createChatbot } from "../site/js/answer.js";

const golden = JSON.parse(readFileSync(new URL("../tests/data/router_golden.json", import.meta.url), "utf8"));
const bot = createChatbot(golden.data);

test("the golden file has the cases we expect", () => {
  assert.ok(golden.cases.length > 250);
});

for (const [index, c] of golden.cases.entries()) {
  test(`golden #${index}: ${JSON.stringify(c.q).slice(0, 70)}`, () => {
    const reply = bot.ask(c.q);
    assert.equal(reply.ok, c.ok);
    assert.equal(reply.text, c.text);
    assert.equal(reply.function, c.function);
    assert.deepEqual(reply.params, c.params);
    assert.deepEqual(reply.data, c.data);
    assert.equal(reply.understood, c.understood);
    assert.deepEqual(reply.notes, c.notes);
    assert.deepEqual(reply.follow_ups, c.follow_ups);
    assert.equal(reply.hint, c.hint);
    assert.equal(reply.tips.length > 0, c.has_tips);
  });
}

for (const s of golden.suggestions) {
  test(`suggestions for ${JSON.stringify(s.typed)}`, () => {
    assert.deepEqual(bot.suggest(s.typed), s.out);
  });
}
