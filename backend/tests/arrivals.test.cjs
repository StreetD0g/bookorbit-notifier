// Exercise all arrival layouts without contacting BookOrbit or Discord.
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

function node(tag) {
  return {tag, children: [], dataset: {}, handlers: {}, textContent: "", className: "", append(...items) { this.children.push(...items); },
    replaceChildren(...items) { this.children = items; }, addEventListener(type, callback) { this.handlers[type] = callback; },
    removeAttribute(name) { delete this[name]; }};
}
function descendants(item, tag) { return [item, ...item.children.flatMap(child => descendants(child, tag))].filter(child => child.tag === tag); }

test("arrival views keep details and use authenticated lazy cover URLs", () => {
  const source = fs.readFileSync(path.join(__dirname, "../app/static/admin.js"), "utf8");
  const start = source.indexOf("function createArrivalDetails("), end = source.indexOf('document.querySelector("#arrivals-view").addEventListener', start);
  assert.ok(start >= 0 && end > start);
  const entries = {"#arrivals-list": node("div"), "#arrivals-view": {value: "list"}, "#arrivals-previous": {}, "#arrivals-next": {}, "#arrivals-page": {}};
  const arrival = {event_id: 123, title: "<script>not HTML</script>", authors: ["Author"], server_name: "Server", library_name: "Library", detected_at: "2026", status: "READY", delivery_statuses: ["SENT"]};
  const labels = {page: "Page", noArrivals: "None", eventStatus: "Event", deliveryStates: "Delivery", details: "Details", title: "Title", authors: "Authors", arrivalSource: "Source", arrivalDate: "Date", arrivalStatus: "Status", coverAlt: "Cover", coverUnavailable: "No cover"};
  const context = {document: {querySelector: selector => entries[selector], createElement: node}, strings: () => labels, arrivals: [arrival], arrivalsOffset: 0, encodeURIComponent};
  vm.runInNewContext(source.slice(start, end), context);
  context.renderArrivals();
  assert.equal(descendants(entries["#arrivals-list"], "h3")[0].textContent, arrival.title);
  assert.equal(descendants(entries["#arrivals-list"], "details").length, 1);
  entries["#arrivals-view"].value = "table"; context.renderArrivals();
  assert.equal(descendants(entries["#arrivals-list"], "th").length, 6);
  assert.equal(descendants(entries["#arrivals-list"], "details").length, 1);
  entries["#arrivals-view"].value = "grid"; context.renderArrivals();
  const cover = descendants(entries["#arrivals-list"], "img")[0];
  assert.equal(cover.src, "/api/v1/admin/arrivals/123/cover");
  assert.equal(cover.loading, "lazy");
  cover.handlers.error(); assert.equal(cover.alt, "No cover");
  assert.equal(descendants(entries["#arrivals-list"], "details").length, 1);
});

test("dashboard recent arrivals use only local authenticated cover paths", () => {
  const source = fs.readFileSync(path.join(__dirname, "../app/static/admin.js"), "utf8");
  const start = source.indexOf("function renderLatestArrivals("), end = source.indexOf("function fillFilter(", start);
  assert.ok(start >= 0 && end > start);
  const container = node("div"), arrival = {event_id: 7, title: "<b>Title</b>", authors: ["Author"], server_name: "Server", library_name: "Library"};
  const context = {document: {querySelector: () => container, createElement: node}, strings: () => ({coverAlt: "Cover", coverUnavailable: "Unavailable", noArrivals: "None"}), latestArrivals: [arrival], encodeURIComponent};
  vm.runInNewContext(source.slice(start, end), context);
  context.renderLatestArrivals();
  assert.equal(descendants(container, "h4")[0].textContent, arrival.title);
  const cover = descendants(container, "img")[0];
  assert.equal(cover.src, "/api/v1/admin/arrivals/7/cover");
  assert.equal(cover.loading, "lazy");
  cover.handlers.error(); assert.equal(cover.alt, "Unavailable");
  context.latestArrivals = []; context.renderLatestArrivals();
  assert.equal(descendants(container, "p")[0].textContent, "None");
});

test("arrival details show waiting and retry diagnostics as text", async () => {
  const source = fs.readFileSync(path.join(__dirname, "../app/static/admin.js"), "utf8");
  const start = source.indexOf("function createArrivalDetails("), end = source.indexOf("function renderArrivals(", start);
  const labels = {details: "Details", loadCover: "Cover", metadataProcessing: "Metadata", eventStatus: "Status", metadataAttempts: "Checks", metadataNextCheck: "Check", metadataDeadline: "Deadline", metadataLastFailed: "Failed", processingTimesHint: "May be late", nextRetry: "Retry", sendingStarted: "Started"};
  const context = {document: {createElement: node}, strings: () => labels, encodeURIComponent, call: async () => ({metadata: {}, metadata_processing: {status: "WAITING_FOR_METADATA", attempt_count: 2, not_before_at: "soon", deadline_at: "later", last_attempt_failed: true}, deliveries: [{webhook_name: "Target", status: "RETRY", next_retry_at: "tomorrow", attempts: []}], history_truncated: false})};
  vm.runInNewContext(source.slice(start, end), context);
  const details = context.createArrivalDetails({event_id: 1}); details.open = true;
  await details.handlers.toggle();
  const lines = descendants(details, "li").map(item => item.textContent);
  assert.ok(lines.includes("Checks: 2"));
  assert.ok(lines.includes("Check: soon"));
  assert.ok(lines.includes("Deadline: later"));
  assert.ok(lines.includes("Failed: ✓"));
  assert.ok(lines.includes("Retry: tomorrow"));
});
