// The built-in image is shown locally while Discord receives its public URL.
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

test("sender preview displays bundled avatar locally and preserves custom URLs", async () => {
  const source = fs.readFileSync(path.join(__dirname, "../app/static/admin.js"), "utf8");
  const start = source.indexOf("function updatePreviewSender("), end = source.indexOf('document.querySelector("#preview-avatar-image").addEventListener', start);
  assert.ok(start >= 0 && end > start);
  const elements = Object.fromEntries(["#preview-sender", "#preview-avatar-status", "#preview-avatar-image", "#preview-avatar-fallback"].map(key => [key, {removeAttribute(name) { delete this[name]; }}]));
  let response = {username: "Example", avatar_url: "https://cdn.example/logo.png", avatar_is_bundled: true}, pending;
  const context = {
    document: {querySelector: selector => elements[selector]}, senderPreviewRequest: 0, senderPreviewTimer: null,
    clearTimeout() {}, setTimeout(callback) { pending = callback(); return 1; },
    profileDraft: () => ({webhook_id: 1}), call: async () => response, cookie: () => "fixture",
    originalProfiles: new Map(), strings: () => ({previewBundledLogo: "Bundled", previewAvatarCustom: "Custom", previewOriginal: "Original"}),
  };
  vm.runInNewContext(source.slice(start, end), context);
  context.updatePreviewSender(); await pending;
  assert.equal(elements["#preview-avatar-image"].src, "/admin-assets/notifier-logo.png");
  assert.equal(elements["#preview-avatar-status"].textContent, "Bundled");
  response = {...response, avatar_url: "https://images.example/custom.png", avatar_is_bundled: false};
  context.updatePreviewSender(); await pending;
  assert.equal(elements["#preview-avatar-image"].src, response.avatar_url);
  assert.equal(elements["#preview-avatar-status"].textContent, "Custom");
});
