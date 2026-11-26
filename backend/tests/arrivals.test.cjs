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
