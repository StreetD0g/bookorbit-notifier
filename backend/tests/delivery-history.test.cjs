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
  const context = {document: {querySelector: selector => entries[selector], createElement: node}, strings: () => labels, statusLabel: value => value, deliveries: [{...base, status:"RETRY"}, {...base, status:"SENDING"}, {...base, status:"SENT"}], deliveryOffset: 0, actionButton: () => node("button")};
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

test("delivery history explains an empty filtered result", () => {
  const source = fs.readFileSync(path.join(__dirname, "../app/static/admin.js"), "utf8");
  const start = source.indexOf("function renderDeliveries("), end = source.indexOf("function historyFilterParams(", start);
  const entries = {"#delivery-list": node("div"), "#history-previous": {}, "#history-next": {}, "#history-page": {}};
  const context = {document: {querySelector: selector => entries[selector], createElement: node}, strings: () => ({page: "Page", noDeliveries: "No deliveries match"}), deliveries: [], deliveryOffset: 0};
  vm.runInNewContext(source.slice(start, end), context);
  context.renderDeliveries();
  assert.equal(entries["#delivery-list"].children[0].textContent, "No deliveries match");
  assert.equal(entries["#history-next"].disabled, true);
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

test("status labels translate for both languages without changing API values", () => {
  const source = fs.readFileSync(path.join(__dirname, "../app/static/admin.js"), "utf8");
  const html = fs.readFileSync(path.join(__dirname, "../app/static/index.html"), "utf8");
  const start = source.indexOf("function statusLabel("), end = source.indexOf("// Changing views", start);
  assert.ok(start >= 0 && end > start);
  let labels = {waiting_for_metadata: "Warten auf Metadaten", sent: "Gesendet", failedCount: "Fehlgeschlagen", statusCompleted: "Abgeschlossen"};
  const context = {strings: () => labels};
  vm.runInNewContext(source.slice(start, end), context);
  assert.equal(context.statusLabel("WAITING_FOR_METADATA"), "Warten auf Metadaten");
  assert.equal(context.statusLabel("SENT"), "Gesendet");
  assert.equal(context.statusLabel("FAILED"), "Fehlgeschlagen");
  assert.equal(context.statusLabel("COMPLETED"), "Abgeschlossen");
  assert.equal(context.statusLabel("FUTURE_STATE"), "FUTURE_STATE");
  labels = {waiting_for_metadata: "Waiting for metadata", sent: "Sent", failedCount: "Failed", statusCompleted: "Completed"};
  assert.equal(context.statusLabel("WAITING_FOR_METADATA"), "Waiting for metadata");
  assert.equal(context.statusLabel("SENT"), "Sent");
  assert.equal(context.statusLabel("FAILED"), "Failed");
  assert.equal(context.statusLabel("COMPLETED"), "Completed");
  assert.equal((html.match(/value="WAITING_FOR_METADATA" data-text="waiting_for_metadata"/g) || []).length, 2);
});
