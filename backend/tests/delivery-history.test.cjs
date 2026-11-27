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

test("CSV export follows the selected server, library and status", () => {
  const source = fs.readFileSync(path.join(__dirname, "../app/static/admin.js"), "utf8");
  const start = source.indexOf("function historyFilterParams()"), end = source.indexOf("function populateHistoryFilters()", start);
  assert.ok(start >= 0 && end > start);
  const elements = {"#history-server": {value: "2"}, "#history-library": {value: "3"}, "#history-status": {value: "RETRY"}, "#history-export": {}};
  const context = {document: {querySelector: selector => elements[selector]}, URLSearchParams};
  vm.runInNewContext(source.slice(start, end), context);
  context.updateHistoryExport();
  assert.equal(elements["#history-export"].href, "/api/v1/admin/notifications/export.csv?server_id=2&library_id=3&delivery_status=RETRY");
  elements["#history-server"].value = ""; elements["#history-library"].value = ""; elements["#history-status"].value = "";
  context.updateHistoryExport();
  assert.equal(elements["#history-export"].href, "/api/v1/admin/notifications/export.csv");
});

test("delivery list requests the same filters and current page offset", async () => {
  const source = fs.readFileSync(path.join(__dirname, "../app/static/admin.js"), "utf8");
  const start = source.indexOf("function historyFilterParams()"), end = source.indexOf("function changeHistoryFilters()", start);
  const elements = {"#history-server": {value: "2"}, "#history-library": {value: "3"}, "#history-status": {value: "FAILED"}};
  let requested;
  const context = {document: {querySelector: selector => elements[selector]}, URLSearchParams, deliveryRequest: 0, deliveryOffset: 50,
    call: async url => { requested = url; return []; }, renderDeliveries() {}};
  vm.runInNewContext(source.slice(start, end), context);
  await context.loadDeliveries();
  assert.equal(requested, "/notifications?server_id=2&library_id=3&delivery_status=FAILED&offset=50");
});
