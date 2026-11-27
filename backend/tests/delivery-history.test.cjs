// Verify queue timing is visible only for the delivery states where it is meaningful.
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

function node(tag) {
  return {tag, children: [], textContent: "", append(...items) { this.children.push(...items); },
    replaceChildren(...items) { this.children = items; }, addEventListener() {}};
}

test("delivery history shows only relevant scheduling timestamps", () => {
  const source = fs.readFileSync(path.join(__dirname, "../app/static/admin.js"), "utf8");
  const start = source.indexOf("function renderDeliveries("), end = source.indexOf("async function loadDeliveries(", start);
  const entries = {"#delivery-list": node("div"), "#history-previous": {}, "#history-next": {}, "#history-page": {}};
  const labels = {page: "Page", attempts: "Attempts", detectedAt: "Detected", sentAt: "Sent", nextRetry: "Retry", sendingStarted: "Started", lastError: "Error", discordId: "ID", showHistory: "History", retryAction: "Retry"};
  const base = {book_title: "Book", server_name: "Server", library_name: "Library", webhook_name: "Target", attempt_count: 1, next_retry_at: "next", sending_started_at: "started"};
  const context = {document: {querySelector: selector => entries[selector], createElement: node}, strings: () => labels, deliveries: [{...base, status:"RETRY"}, {...base, status:"SENDING"}, {...base, status:"SENT"}], deliveryOffset: 0, actionButton: () => node("button")};
  vm.runInNewContext(source.slice(start, end), context);
  context.renderDeliveries();
  const lines = card => card.children.filter(item => item.tag === "p").map(item => item.textContent);
  const cards = entries["#delivery-list"].children;
  assert.ok(lines(cards[0]).includes("Retry: next"));
  assert.ok(!lines(cards[0]).includes("Started: started"));
  assert.ok(lines(cards[1]).includes("Started: started"));
  assert.ok(!lines(cards[2]).includes("Retry: next"));
  assert.ok(!lines(cards[2]).includes("Started: started"));
});

test("CSV export follows the selected delivery status", async () => {
  const source = fs.readFileSync(path.join(__dirname, "../app/static/admin.js"), "utf8");
  const start = source.indexOf('document.querySelector("#history-status").addEventListener("change"');
  const end = source.indexOf('document.querySelector("#history-previous").addEventListener', start);
  assert.ok(start >= 0 && end > start);
  const status = {addEventListener(_type, callback) { this.change = callback; }}, link = {};
  let refreshes = 0;
  const context = {document: {querySelector: selector => selector === "#history-status" ? status : link}, deliveryOffset: 50, loadDeliveries: async () => { refreshes++; }, encodeURIComponent};
  vm.runInNewContext(source.slice(start, end), context);
  status.change({currentTarget: {value: "RETRY"}});
  assert.equal(link.href, "/api/v1/admin/notifications/export.csv?delivery_status=RETRY");
  status.change({currentTarget: {value: ""}});
  assert.equal(link.href, "/api/v1/admin/notifications/export.csv");
  assert.equal(context.deliveryOffset, 0);
  assert.equal(refreshes, 2);
});
