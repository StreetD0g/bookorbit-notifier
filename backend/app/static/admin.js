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
let counts = null;
let scopes = {libraries: [], webhooks: []};
let profileRequest = 0;
function strings() { return messages[language.value]; }
function translate() {
  document.documentElement.lang = language.value;
  document.querySelectorAll("[data-text]").forEach(element => { element.textContent = strings()[element.dataset.text]; });
  if (counts) renderCounts(counts);
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
}
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
  await selectScope();
  renderCounts(counts);
  authPanel.hidden = true;
  dashboard.hidden = false;
}
language.addEventListener("change", translate);
document.querySelector("#profile-scope").addEventListener("change", () => selectScope().catch(() => { message.textContent = strings().failed; }));
document.querySelector("#profile-target").addEventListener("change", () => loadProfile().catch(() => { message.textContent = strings().failed; }));
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
