"use strict";

// Keep all server-provided text out of HTML parsing and never store secrets in localStorage.
const messages = {
  de: {language: "Sprache", login: "Anmelden", password: "Passwort", setup: "Ersteinrichtung", setupToken: "Einrichtungsschlüssel", newPassword: "Neues Passwort (mindestens 12 Zeichen)", createAccount: "Administratorkonto erstellen", dashboard: "Benachrichtigungen", refresh: "Aktualisieren", logout: "Abmelden", configured: "Konto erstellt. Bitte melde dich an.", failed: "Die Aktion ist fehlgeschlagen. Bitte überprüfe deine Angaben.", signedOut: "Abgemeldet.", waiting_for_metadata: "Warten auf Metadaten", ready: "Bereit", queued: "Eingeplant", sending: "Wird gesendet", retry: "Erneuter Versuch", sent: "Gesendet", failedCount: "Fehlgeschlagen", skipped: "Übersprungen"},
  en: {language: "Language", login: "Sign in", password: "Password", setup: "Initial setup", setupToken: "Setup key", newPassword: "New password (at least 12 characters)", createAccount: "Create administrator", dashboard: "Notifications", refresh: "Refresh", logout: "Sign out", configured: "Account created. Please sign in.", failed: "The action failed. Please check your input.", signedOut: "Signed out.", waiting_for_metadata: "Waiting for metadata", ready: "Ready", queued: "Scheduled", sending: "Sending", retry: "Retry", sent: "Sent", failedCount: "Failed", skipped: "Skipped"}
};
const language = document.querySelector("#language");
const message = document.querySelector("#message");
const authPanel = document.querySelector("#auth-panel");
const dashboard = document.querySelector("#dashboard");
Object.assign(messages.de, {globalProfile: "Globales Absenderprofil", senderName: "Absendername", avatar: "Profilbild", inherit: "Übernehmen", original: "Webhook-Original", custom: "Benutzerdefiniert", nameValue: "Benutzerdefinierter Name", avatarValue: "Öffentliche HTTPS-Bild-URL", save: "Speichern", saved: "Absenderprofil gespeichert."});
Object.assign(messages.en, {globalProfile: "Global sender profile", senderName: "Sender name", avatar: "Avatar", inherit: "Inherit", original: "Original webhook", custom: "Custom", nameValue: "Custom name", avatarValue: "Public HTTPS image URL", save: "Save", saved: "Sender profile saved."});
Object.assign(messages.de, {senderProfile: "Absenderprofil", profileScope: "Konfigurationsebene", globalScope: "Global", webhookScope: "Webhook", libraryScope: "Bibliothek", profileTarget: "Auswahl", noTargets: "Für diese Ebene ist noch kein Eintrag vorhanden."});
Object.assign(messages.en, {senderProfile: "Sender profile", profileScope: "Configuration level", globalScope: "Global", webhookScope: "Webhook", libraryScope: "Library", profileTarget: "Selection", noTargets: "No entries exist for this level yet."});
Object.assign(messages.de, {previewTitle: "Discord-Live-Vorschau", previewHint: "Beispieldaten; Änderungen an dieser Vorschau werden nicht gespeichert oder versendet.", embedTitle: "Titel", embedDescription: "Beschreibung", embedFooter: "Fußzeile", variable: "Variable", insertVariable: "In Beschreibung einfügen", previewInvalid: "Ungültige Vorlage. Bitte prüfe die Variablen.", previewOriginal: "Original / übergeordnet"});
Object.assign(messages.en, {previewTitle: "Discord live preview", previewHint: "Sample data; preview changes are not saved or sent.", embedTitle: "Title", embedDescription: "Description", embedFooter: "Footer", variable: "Variable", insertVariable: "Insert into description", previewInvalid: "Invalid template. Please check the variables.", previewOriginal: "Original / inherited"});
Object.assign(messages.de, {servers: "BookOrbit-Server", name: "Name", serverUrl: "Server-URL", serverKey: "BookOrbit-Leseschlüssel", addServer: "Server hinzufügen", webhooks: "Discord-Webhooks", webhookUrl: "Webhook-URL", addWebhook: "Webhook hinzufügen", libraries: "Bibliotheken", libraryHelp: "Bibliotheken werden über den jeweiligen Server aktualisiert. Die erste Erfassung erzeugt keine Benachrichtigungen.", syncLibraries: "Bibliotheken aktualisieren", disable: "Deaktivieren", enable: "Aktivieren", monitored: "Überwachen", saveRouting: "Zuordnung speichern", configuredOk: "Konfiguration gespeichert.", syncOk: "Bibliotheken aktualisiert.", destination: "Discord-Ziele"});
Object.assign(messages.en, {servers: "BookOrbit servers", name: "Name", serverUrl: "Server URL", serverKey: "BookOrbit read-only key", addServer: "Add server", webhooks: "Discord webhooks", webhookUrl: "Webhook URL", addWebhook: "Add webhook", libraries: "Libraries", libraryHelp: "Refresh libraries from their server. The initial baseline does not generate notifications.", syncLibraries: "Refresh libraries", disable: "Disable", enable: "Enable", monitored: "Monitor", saveRouting: "Save routing", configuredOk: "Configuration saved.", syncOk: "Libraries refreshed.", destination: "Discord destinations"});
let counts = null;
let scopes = {libraries: [], webhooks: []};
let profileRequest = 0;
let previewRequest = 0, previewTimer;
let servers = [], webhooks = [], libraries = [];
function strings() { return messages[language.value]; }
function translate() {
  document.documentElement.lang = language.value;
  document.querySelectorAll("[data-text]").forEach(element => { element.textContent = strings()[element.dataset.text]; });
  if (counts) renderCounts(counts);
  renderManagement();
  updatePreviewSender();
}
function cookie(name) {
  const value = document.cookie.split("; ").find(item => item.startsWith(name + "="));
  return value ? decodeURIComponent(value.slice(name.length + 1)) : "";
}
async function call(path, options = {}) {
  const response = await fetch("/api/v1/admin" + path, {credentials: "same-origin", cache: "no-store", ...options});
  if (!response.ok) throw new Error("Request failed");
  return response.json();
}
function renderCounts(data) {
  const list = document.querySelector("#counts");
  list.replaceChildren();
  for (const [key, value] of Object.entries(data)) {
    const label = document.createElement("dt"), count = document.createElement("dd");
    label.textContent = strings()[key === "failed" ? "failedCount" : key] || key;
    count.textContent = String(value);
    list.append(label, count);
  }
}
function profilePath() {
  const scope = document.querySelector("#profile-scope").value;
  const target = document.querySelector("#profile-target").value;
  return "/sender-profiles/" + scope + (scope === "global" ? "" : "?scope_id=" + encodeURIComponent(target));
}
async function loadProfile() {
  const request = ++profileRequest;
  const form = document.querySelector("#profile-form");
  form.hidden = true;
  if (document.querySelector("#profile-scope").value !== "global" && !document.querySelector("#profile-target").value) return;
  const profile = await call(profilePath());
  if (request !== profileRequest) return;
  for (const [name, field] of [["username", profile.username], ["avatar", profile.avatar_url]]) {
    document.querySelector("#" + name + "-choice").value = field.choice;
    document.querySelector("#" + name + "-value").value = field.value || "";
  }
  form.hidden = false;
  updatePreviewSender();
}
function updatePreviewSender() {
  const choice = document.querySelector("#username-choice").value;
  document.querySelector("#preview-sender").textContent = choice === "custom" ? document.querySelector("#username-value").value : strings().previewOriginal;
}
async function renderPreview() {
  const request = ++previewRequest;
  const error = document.querySelector("#preview-error");
  try {
    const data = await call("/template-preview", {method: "POST", headers: {"Content-Type": "application/json", "X-CSRF-Token": cookie("bookorbit_csrf")}, body: JSON.stringify({title: document.querySelector("#preview-title").value, description: document.querySelector("#preview-description").value, footer: document.querySelector("#preview-footer").value})});
    if (request !== previewRequest) return;
    document.querySelector("#preview-rendered-title").textContent = data.title;
    document.querySelector("#preview-rendered-description").textContent = data.description;
    document.querySelector("#preview-rendered-footer").textContent = data.footer?.text || "";
    error.textContent = "";
  } catch { if (request === previewRequest) error.textContent = strings().previewInvalid; }
}
function queuePreview() { clearTimeout(previewTimer); ++previewRequest; previewTimer = setTimeout(renderPreview, 250); }
async function selectScope() {
  const scope = document.querySelector("#profile-scope").value;
  const target = document.querySelector("#profile-target");
  const selected = target.value;
  target.replaceChildren();
  const entries = scope === "library" ? scopes.libraries : scope === "webhook" ? scopes.webhooks : [];
  for (const entry of entries) {
    const option = document.createElement("option");
    option.value = String(entry.id);
    option.textContent = entry.server_name ? entry.server_name + " — " + entry.name : entry.name;
    target.append(option);
  }
  if ([...target.options].some(option => option.value === selected)) target.value = selected;
  target.hidden = scope === "global";
  document.querySelector("#profile-target-label").hidden = target.hidden;
  document.querySelector("#profile-unavailable").hidden = scope === "global" || entries.length > 0;
  await loadProfile();
}
async function refresh() {
  counts = await call("/notifications/summary");
  scopes = await call("/profile-scopes");
  [servers, webhooks, libraries] = await Promise.all([call("/servers"), call("/webhooks"), call("/libraries")]);
  renderManagement();
  const variables = await call("/template-variables");
  const variableSelect = document.querySelector("#preview-variable");
  variableSelect.replaceChildren();
  for (const variable of variables) {
    const option = document.createElement("option"); option.value = variable; option.textContent = "{{" + variable + "}}"; variableSelect.append(option);
  }
  await selectScope();
  queuePreview();
  renderCounts(counts);
  authPanel.hidden = true;
  dashboard.hidden = false;
}
function mutationOptions(body) {
  return {method: "PUT", headers: {"Content-Type": "application/json", "X-CSRF-Token": cookie("bookorbit_csrf")}, body: JSON.stringify(body)};
}
function actionButton(label, action) {
  const button = document.createElement("button"); button.type = "button"; button.textContent = label;
  button.addEventListener("click", async () => { try { await action(); await refresh(); message.textContent = strings().configuredOk; } catch { message.textContent = strings().failed; } });
  return button;
}
function renderManagement() {
  const serverList = document.querySelector("#server-list"); serverList.replaceChildren();
  for (const server of servers) {
    const item = document.createElement("li"); item.append(document.createTextNode(server.name + " — " + server.base_url));
    item.append(actionButton(server.enabled ? strings().disable : strings().enable, () => call("/servers/" + server.id + "/enabled", mutationOptions({enabled: !server.enabled}))));
    const sync = actionButton(strings().syncLibraries, () => call("/servers/" + server.id + "/sync-libraries", {...mutationOptions({}), method: "POST"}));
    sync.disabled = !server.enabled; item.append(sync); serverList.append(item);
  }
  const webhookList = document.querySelector("#webhook-list"); webhookList.replaceChildren();
  for (const webhook of webhooks) { const item = document.createElement("li"); item.textContent = webhook.name; webhookList.append(item); }
  const libraryList = document.querySelector("#library-list"); libraryList.replaceChildren();
  for (const library of libraries) {
    const card = document.createElement("div"); card.className = "library-card";
    const heading = document.createElement("h3"), server = servers.find(item => item.id === library.server_id);
    heading.textContent = (server?.name || "") + " — " + library.name; card.append(heading);
    const monitorLabel = document.createElement("label"), monitored = document.createElement("input");
    monitored.type = "checkbox"; monitored.checked = library.monitored; monitorLabel.append(monitored, document.createTextNode(" " + strings().monitored)); card.append(monitorLabel);
    const legend = document.createElement("p"); legend.textContent = strings().destination; card.append(legend);
    const choices = [];
    for (const webhook of webhooks) {
      const label = document.createElement("label"), checkbox = document.createElement("input");
      checkbox.type = "checkbox"; checkbox.checked = library.webhook_ids.includes(webhook.id); choices.push([webhook.id, checkbox]);
      label.append(checkbox, document.createTextNode(" " + webhook.name)); card.append(label);
    }
    card.append(actionButton(strings().saveRouting, () => call("/libraries/" + library.id + "/routing", mutationOptions({monitored: monitored.checked, webhook_ids: choices.filter(([, checkbox]) => checkbox.checked).map(([id]) => id), template_id: library.template_id}))));
    libraryList.append(card);
  }
}
language.addEventListener("change", translate);
document.querySelector("#profile-scope").addEventListener("change", () => selectScope().catch(() => { message.textContent = strings().failed; }));
document.querySelector("#profile-target").addEventListener("change", () => loadProfile().catch(() => { message.textContent = strings().failed; }));
for (const selector of ["#preview-title", "#preview-description", "#preview-footer"]) document.querySelector(selector).addEventListener("input", queuePreview);
for (const selector of ["#username-choice", "#username-value"]) document.querySelector(selector).addEventListener("input", updatePreviewSender);
document.querySelector("#insert-variable").addEventListener("click", () => {
  const input = document.querySelector("#preview-description");
  input.setRangeText("{{" + document.querySelector("#preview-variable").value + "}}", input.selectionStart, input.selectionEnd, "end");
  input.focus(); queuePreview();
});
document.querySelector("#login-form").addEventListener("submit", async event => {
  event.preventDefault();
  const input = document.querySelector("#password");
  try {
    await call("/login", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({password: input.value})});
    message.textContent = "";
    await refresh();
  } catch { message.textContent = strings().failed; } finally { input.value = ""; }
});
document.querySelector("#setup-form").addEventListener("submit", async event => {
  event.preventDefault();
  const token = document.querySelector("#setup-token"), password = document.querySelector("#new-password");
  try {
    await call("/setup", {method: "POST", headers: {"Content-Type": "application/json", "X-Setup-Token": token.value}, body: JSON.stringify({password: password.value})});
    message.textContent = strings().configured;
  } catch { message.textContent = strings().failed; } finally { token.value = ""; password.value = ""; }
});
document.querySelector("#refresh").addEventListener("click", async () => {
  try { await refresh(); } catch { message.textContent = strings().failed; }
});
document.querySelector("#server-form").addEventListener("submit", async event => {
  event.preventDefault();
  const name = document.querySelector("#server-name"), url = document.querySelector("#server-url"), key = document.querySelector("#server-key");
  try { await call("/servers", {...mutationOptions({name: name.value, base_url: url.value, api_key: key.value}), method: "POST"}); name.value = ""; url.value = ""; await refresh(); message.textContent = strings().configuredOk; }
  catch { message.textContent = strings().failed; } finally { key.value = ""; }
});
document.querySelector("#webhook-form").addEventListener("submit", async event => {
  event.preventDefault();
  const name = document.querySelector("#webhook-name"), url = document.querySelector("#webhook-url");
  try { await call("/webhooks", {...mutationOptions({name: name.value, webhook_url: url.value}), method: "POST"}); name.value = ""; await refresh(); message.textContent = strings().configuredOk; }
  catch { message.textContent = strings().failed; } finally { url.value = ""; }
});
document.querySelector("#profile-form").addEventListener("submit", async event => {
  event.preventDefault();
  const field = name => {
    const choice = document.querySelector("#" + name + "-choice").value;
    return {choice, value: choice === "custom" ? document.querySelector("#" + name + "-value").value : null};
  };
  try {
    await call(profilePath(), {method: "PUT", headers: {"Content-Type": "application/json", "X-CSRF-Token": cookie("bookorbit_csrf")}, body: JSON.stringify({username: field("username"), avatar_url: field("avatar")})});
    message.textContent = strings().saved;
  } catch { message.textContent = strings().failed; }
});
document.querySelector("#logout").addEventListener("click", async () => {
  try {
    await call("/logout", {method: "POST", headers: {"X-CSRF-Token": cookie("bookorbit_csrf")}});
    counts = null; dashboard.hidden = true; authPanel.hidden = false; message.textContent = strings().signedOut;
  } catch { message.textContent = strings().failed; }
});
refresh().catch(() => {});
