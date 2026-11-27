// Exercise the actual navigation code with the views and links from the shipped HTML.
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const staticDir = path.join(__dirname, "../app/static");
const html = fs.readFileSync(path.join(staticDir, "index.html"), "utf8");
const source = fs.readFileSync(path.join(staticDir, "admin.js"), "utf8");

function elements(attribute) {
  const pattern = new RegExp(`<[^>]*\\b${attribute}="([^"]+)"[^>]*>`, "g");
  return Array.from(html.matchAll(pattern), match => {
    const href = match[0].match(/href="([^"]+)"/)?.[1];
    const element = {dataset: {[attribute.slice(5)]: match[1]}, hidden: false, attrs: {}, draft: "unsaved"};
    element.getAttribute = name => name === "href" ? href : element.attrs[name];
    element.setAttribute = (name, value) => { element.attrs[name] = value; };
    element.removeAttribute = name => { delete element.attrs[name]; };
    return element;
  });
}

test("navigation selects the requested section and retains unsaved controls", () => {
  const groups = {"[data-view]": elements("data-view"), "[data-category]": elements("data-category"), "[data-menu]": elements("data-menu")};
  const location = {hash: ""}, listeners = {};
  const context = {location, document: {querySelectorAll: selector => groups[selector]}, window: {addEventListener: (event, handler) => { listeners[event] = handler; }}};
  const start = source.indexOf("const viewCategories =");
  const end = source.indexOf("function translate()", start);
  assert.ok(start >= 0 && end > start);
  vm.runInNewContext(source.slice(start, end), context);
  const cases = {"#view-overview": ["overview", "overview"], "#view-libraries": ["libraries", "bookorbit"], "#view-presets": ["presets", "presets"], "#view-arrivals": ["arrivals", "imports"], "#view-scan-history": ["scan-history", "imports"], "#view-history": ["history", "discord"], "#view-servers": ["servers", "settings"], "#view-webhooks": ["webhooks", "settings"], "#view-sender": ["sender", "settings"], "#view-logs": ["logs", "settings"], "#servers-heading": ["servers", "settings"], "#unknown": ["overview", "overview"]};
  for (const [hash, [view, category]] of Object.entries(cases)) {
    location.hash = hash; listeners.hashchange();
    assert.deepEqual(new Set(groups["[data-view]"].filter(item => !item.hidden).map(item => item.dataset.view)), new Set([view]));
    assert.deepEqual(groups["[data-category]"].filter(item => item.attrs["aria-current"]).map(item => item.dataset.category), [category]);
    assert.ok(groups["[data-menu]"].filter(item => !item.hidden).every(item => item.dataset.menu === category));
    assert.equal(groups["[data-menu]"].filter(item => item.attrs["aria-current"] === "page").length, 1);
    assert.ok(groups["[data-view]"].every(item => item.draft === "unsaved"));
  }
});

test("language redraw preserves management drafts only for matching records", () => {
  function container(key, values, open = []) {
    return {dataset: {draftKey: key}, controls: values.map(([type, value, checked]) => ({type, value, checked})), details: open.map(value => ({open: value})),
      querySelectorAll(selector) { return selector === "details" ? this.details : this.controls; }};
  }
  const old = [container("server:1", [["password", "temporary-key", false], ["checkbox", "on", false]], [true]),
    container("library:1", [["select-one", "BATCH", false], ["number", "123", false]])];
  let active = old;
  const context = {document: {querySelectorAll: () => active}};
  const start = source.indexOf("function captureManagementDrafts("), end = source.indexOf("function translate()", start);
  assert.ok(start >= 0 && end > start);
  vm.runInNewContext(source.slice(start, end), context);
  const drafts = context.captureManagementDrafts();
  active = [container("library:1", [["select-one", "SINGLE", false], ["number", "300", false]]),
    container("server:1", [["password", "", false], ["checkbox", "on", true]], [false]),
    container("server:2", [["password", "", false]])];
  context.restoreManagementDrafts(drafts);
  assert.equal(active[0].controls[0].value, "BATCH");
  assert.equal(active[0].controls[1].value, "123");
  assert.equal(active[1].controls[0].value, "temporary-key");
  assert.equal(active[1].controls[1].checked, false);
  assert.equal(active[1].details[0].open, true);
  assert.equal(active[2].controls[0].value, "");
});
