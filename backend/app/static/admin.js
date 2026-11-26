"use strict";

// Keep all server-provided text out of HTML parsing and never store secrets in localStorage.
const messages = {
  de: {language: "Sprache", login: "Anmelden", password: "Passwort", setup: "Ersteinrichtung", setupToken: "Einrichtungsschlüssel", newPassword: "Neues Passwort (mindestens 12 Zeichen)", createAccount: "Administratorkonto erstellen", dashboard: "Benachrichtigungen", refresh: "Aktualisieren", logout: "Abmelden", configured: "Konto erstellt. Bitte melde dich an.", failed: "Die Aktion ist fehlgeschlagen. Bitte überprüfe deine Angaben.", signedOut: "Abgemeldet.", waiting_for_metadata: "Warten auf Metadaten", ready: "Bereit", queued: "Eingeplant", sending: "Wird gesendet", retry: "Erneuter Versuch", sent: "Gesendet", failedCount: "Fehlgeschlagen", skipped: "Übersprungen"},
  en: {language: "Language", login: "Sign in", password: "Password", setup: "Initial setup", setupToken: "Setup key", newPassword: "New password (at least 12 characters)", createAccount: "Create administrator", dashboard: "Notifications", refresh: "Refresh", logout: "Sign out", configured: "Account created. Please sign in.", failed: "The action failed. Please check your input.", signedOut: "Signed out.", waiting_for_metadata: "Waiting for metadata", ready: "Ready", queued: "Scheduled", sending: "Sending", retry: "Retry", sent: "Sent", failedCount: "Failed", skipped: "Skipped"}
};
const language = document.querySelector("#language");
const theme = document.querySelector("#theme");
try { if (localStorage.getItem("bookorbit-theme") === "light") theme.value = "light"; } catch { /* Storage is optional. */ }
document.documentElement.dataset.theme = theme.value;
theme.addEventListener("change", () => {
  document.documentElement.dataset.theme = theme.value;
  try { localStorage.setItem("bookorbit-theme", theme.value); } catch { /* The setting remains active for this page. */ }
});
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
Object.assign(messages.de, {history: "Zustellhistorie", historyHelp: "Die neuesten 50 Zustellungen. Ein erneuter Versand bereits zugestellter Nachrichten erzeugt eine weitere Discord-Nachricht.", attempts: "Versuche", detectedAt: "Erkannt", sentAt: "Gesendet", lastError: "Letzter Fehler", discordId: "Discord-Nachrichten-ID", retryAction: "Erneut senden", resendConfirm: "Diese Nachricht wurde bereits gesendet. Wirklich eine weitere Discord-Nachricht senden?", showHistory: "Versuche anzeigen"});
Object.assign(messages.en, {history: "Delivery history", historyHelp: "The latest 50 deliveries. Resending a delivered notification creates another Discord message.", attempts: "Attempts", detectedAt: "Detected", sentAt: "Sent", lastError: "Last error", discordId: "Discord message ID", retryAction: "Retry", resendConfirm: "This notification was already sent. Send another Discord message?", showHistory: "Show attempts"});
Object.assign(messages.de, {previewHint: "Die Vorschau zeigt Beispieldaten. Änderungen werden erst beim Speichern übernommen und nicht versendet.", templateSelect: "Vorlage", newTemplate: "Neue Vorlage", templateName: "Vorlagenname", saveTemplate: "Vorlage speichern", libraryTemplate: "Vorlage für diese Bibliothek", defaultTemplate: "Standardvorlage"});
Object.assign(messages.en, {previewHint: "The preview shows sample data. Changes are only applied when saved and are not sent.", templateSelect: "Template", newTemplate: "New template", templateName: "Template name", saveTemplate: "Save template", libraryTemplate: "Template for this library", defaultTemplate: "Default template"});
Object.assign(messages.de, {deliveryMode: "Versandmodus", modeSingle: "Einzeln", modeBatch: "Gebündelt", modeDaily: "Tägliche Zusammenfassung", batchSeconds: "Sammelzeit in Sekunden (30–86400)", dailyTime: "Uhrzeit der Zusammenfassung", timezone: "Zeitzone (IANA)", saveDelivery: "Versandmodus speichern", deliveryHint: "Bereits eingeplante Nachrichten behalten ihren Versandzeitpunkt."});
Object.assign(messages.en, {deliveryMode: "Delivery mode", modeSingle: "Individual", modeBatch: "Batch", modeDaily: "Daily summary", batchSeconds: "Batch window in seconds (30–86400)", dailyTime: "Summary time", timezone: "Time zone (IANA)", saveDelivery: "Save delivery mode", deliveryHint: "Already scheduled notifications retain their due time."});
Object.assign(messages.de, {testMessage: "Testnachricht senden", testProfile: "Profil für Testnachricht", defaultProfile: "Webhook- und globale Einstellungen", testSent: "Testnachricht gesendet."});
Object.assign(messages.en, {testMessage: "Send test message", testProfile: "Profile for test message", defaultProfile: "Webhook and global settings", testSent: "Test message sent."});
Object.assign(messages.de, {refreshFailed: "Die Aktion war erfolgreich, aber die Ansicht konnte nicht aktualisiert werden."});
Object.assign(messages.en, {refreshFailed: "The action succeeded, but the view could not be refreshed."});
Object.assign(messages.de, {edit: "Bearbeiten", interval: "Scanintervall in Sekunden", replaceKey: "Neuer Leseschlüssel (leer lassen, um den bisherigen zu behalten)", saveChanges: "Änderungen speichern", replaceWebhook: "Neue Webhook-URL (leer lassen, um die bisherige zu behalten)", webhookEnabled: "Webhook aktiv", confirmWebhookChange: "Die Zieladresse wird ersetzt. Wartende Nachrichten können an das neue Ziel gesendet werden. Fortfahren?", manualScan: "Jetzt scannen", sourceIdentity: "Die Server-URL bleibt unverändert, damit vorhandene Bibliotheks-IDs zugeordnet bleiben."});
Object.assign(messages.en, {edit: "Edit", interval: "Scan interval in seconds", replaceKey: "New read-only key (leave empty to keep the existing one)", saveChanges: "Save changes", replaceWebhook: "New webhook URL (leave empty to keep the existing one)", webhookEnabled: "Webhook enabled", confirmWebhookChange: "The destination will be replaced. Pending notifications may be sent to the new destination. Continue?", manualScan: "Scan now", sourceIdentity: "The server URL remains unchanged to preserve existing library identities."});
Object.assign(messages.de, {changePassword: "Passwort ändern", currentPassword: "Bisheriges Passwort", repeatPassword: "Neues Passwort wiederholen", passwordSessions: "Nach der Änderung werden alle Sitzungen abgemeldet.", passwordMismatch: "Die neuen Passwörter stimmen nicht überein.", passwordChanged: "Passwort geändert. Bitte melde dich erneut an."});
Object.assign(messages.en, {changePassword: "Change password", currentPassword: "Current password", repeatPassword: "Repeat new password", passwordSessions: "All sessions will be signed out after the change.", passwordMismatch: "The new passwords do not match.", passwordChanged: "Password changed. Please sign in again."});
Object.assign(messages.de, {arrivals: "Neuzugänge", arrivalsHelp: "Erkannte Neuzugänge; die stille Ersterfassung ist nicht enthalten.", arrivalsServer: "Server", arrivalsLibrary: "Bibliothek", all: "Alle", noArrivals: "Keine Neuzugänge für diese Auswahl.", eventStatus: "Ereignisstatus", deliveryStates: "Zustellstatus"});
Object.assign(messages.en, {arrivals: "New arrivals", arrivalsHelp: "Detected arrivals; the silent initial baseline is excluded.", arrivalsServer: "Server", arrivalsLibrary: "Library", all: "All", noArrivals: "No arrivals match this selection.", eventStatus: "Event status", deliveryStates: "Delivery status"});
Object.assign(messages.de, {overview: "Übersicht", utcNote: "Zeiträume beziehen sich auf UTC. Der Serverstatus zeigt die Konfiguration, keine Live-Erreichbarkeit.", library_count: "Bibliotheken", monitored_count: "Überwachte Bibliotheken", book_count: "Bekannte Medien", arrivals_today: "Neuzugänge heute", arrivals_week: "Neuzugänge diese Woche", arrivals_month: "Neuzugänge diesen Monat", last_successful_scan: "Letzter erfolgreicher Scan", configuredServers: "Aktive / konfigurierte Server"});
Object.assign(messages.en, {overview: "Overview", utcNote: "Periods use UTC. Server status describes configuration, not live connectivity.", library_count: "Libraries", monitored_count: "Monitored libraries", book_count: "Known media", arrivals_today: "Arrivals today", arrivals_week: "Arrivals this week", arrivals_month: "Arrivals this month", last_successful_scan: "Last successful scan", configuredServers: "Enabled / configured servers"});
Object.assign(messages.de, {advancedFilters: "Weitere Filter", filterAuthor: "Autor", filterGenre: "Genre", filterFormat: "Medienformat", filterLanguage: "Sprache", filterFrom: "Erkannt ab (UTC)", filterTo: "Erkannt bis (UTC)", applyFilters: "Filter anwenden"});
Object.assign(messages.en, {advancedFilters: "More filters", filterAuthor: "Author", filterGenre: "Genre", filterFormat: "Media format", filterLanguage: "Language", filterFrom: "Detected from (UTC)", filterTo: "Detected through (UTC)", applyFilters: "Apply filters"});
Object.assign(messages.de, {previous: "Zurück", next: "Weiter", page: "Seite"});
Object.assign(messages.en, {previous: "Previous", next: "Next", page: "Page"});
Object.assign(messages.de, {theme: "Darstellung", darkTheme: "Dunkel", lightTheme: "Hell"});
Object.assign(messages.en, {theme: "Appearance", darkTheme: "Dark", lightTheme: "Light"});
Object.assign(messages.de, {details: "Details und Zustellhistorie", historyTruncated: "Weitere ältere Zustellversuche werden hier nicht angezeigt.", title: "Titel", subtitle: "Untertitel", authors: "Autoren", series: "Reihe", series_index: "Reihennummer", genres: "Genres", languageField: "Sprache", formats: "Formate", narrators: "Sprecher", duration_seconds: "Dauer (Sekunden)", description: "Beschreibung", isbn10: "ISBN-10", isbn13: "ISBN-13", publisher: "Verlag", published_date: "Erscheinungsdatum", published_year: "Erscheinungsjahr", page_count: "Seiten", tags: "Schlagwörter", edition_name: "Ausgabe"});
Object.assign(messages.en, {details: "Details and delivery history", historyTruncated: "Further older delivery attempts are not displayed here.", title: "Title", subtitle: "Subtitle", authors: "Authors", series: "Series", series_index: "Series number", genres: "Genres", languageField: "Language", formats: "Formats", narrators: "Narrators", duration_seconds: "Duration (seconds)", description: "Description", isbn10: "ISBN-10", isbn13: "ISBN-13", publisher: "Publisher", published_date: "Published date", published_year: "Published year", page_count: "Pages", tags: "Tags", edition_name: "Edition"});
Object.assign(messages.de, {showCover: "Cover laden", coverUnavailable: "Cover nicht verfügbar", coverAlt: "Cover des Mediums"});
Object.assign(messages.en, {showCover: "Load cover", coverUnavailable: "Cover unavailable", coverAlt: "Media cover"});
Object.assign(messages.de, {testConnection: "Verbindung prüfen", connectionOk: "BookOrbit-Verbindung erfolgreich.", knownBooks: "Bekannte Medien", libraryArrivals: "Erkannte Neuzugänge", lastScan: "Letzter Scan"});
Object.assign(messages.en, {testConnection: "Test connection", connectionOk: "BookOrbit connection successful.", knownBooks: "Known media", libraryArrivals: "Detected arrivals", lastScan: "Last scan"});
let counts = null;
let overview = null;
let scopes = {libraries: [], webhooks: []};
let profileRequest = 0;
let previewRequest = 0, previewTimer;
let servers = [], webhooks = [], libraries = [];
let deliveries = [];
let templates = [];
let arrivals = [];
let arrivalsRequest = 0;
let arrivalsOffset = 0;
function strings() { return messages[language.value]; }
function translate() {
  document.documentElement.lang = language.value;
  document.querySelectorAll("[data-text]").forEach(element => { element.textContent = strings()[element.dataset.text]; });
  if (counts) renderCounts(counts);
  if (overview) renderOverview(overview);
  renderManagement();
  renderDeliveries();
  populateTemplateSelector();
  populateArrivalFilters();
  renderArrivals();
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
  overview = await call("/dashboard");
  scopes = await call("/profile-scopes");
  [servers, webhooks, libraries, deliveries, templates] = await Promise.all([call("/servers"), call("/webhooks"), call("/libraries"), call("/notifications"), call("/templates")]);
  populateArrivalFilters();
  await loadArrivals();
  populateTemplateSelector();
  renderManagement();
  renderDeliveries();
  const variables = await call("/template-variables");
  const variableSelect = document.querySelector("#preview-variable");
  variableSelect.replaceChildren();
  for (const variable of variables) {
    const option = document.createElement("option"); option.value = variable; option.textContent = "{{" + variable + "}}"; variableSelect.append(option);
  }
  await selectScope();
  queuePreview();
  renderCounts(counts);
  renderOverview(overview);
  authPanel.hidden = true;
  dashboard.hidden = false;
}
function renderOverview(data) {
  const list = document.querySelector("#overview-counts"); list.replaceChildren();
  for (const key of ["library_count", "monitored_count", "book_count", "arrivals_today", "arrivals_week", "arrivals_month", "last_successful_scan"]) {
    const label = document.createElement("dt"), value = document.createElement("dd");
    label.textContent = strings()[key]; value.textContent = data[key] ?? "—"; list.append(label, value);
  }
  const label = document.createElement("dt"), value = document.createElement("dd");
  label.textContent = strings().configuredServers; value.textContent = data.servers.filter(server => server.enabled).length + " / " + data.servers.length;
  list.append(label, value);
}
function fillFilter(select, entries, previous) {
  select.replaceChildren();
  const all = document.createElement("option"); all.value = ""; all.textContent = strings().all; select.append(all);
  for (const entry of entries) { const option = document.createElement("option"); option.value = String(entry.id); option.textContent = entry.name; select.append(option); }
  if ([...select.options].some(option => option.value === previous)) select.value = previous;
}
function populateArrivalFilters() {
  const server = document.querySelector("#arrivals-server"), library = document.querySelector("#arrivals-library");
  const serverValue = server.value, libraryValue = library.value;
  fillFilter(server, servers, serverValue);
  fillFilter(library, libraries.filter(entry => !server.value || String(entry.server_id) === server.value), libraryValue);
}
async function loadArrivals() {
  const request = ++arrivalsRequest;
  const params = new URLSearchParams();
  const server = document.querySelector("#arrivals-server").value, library = document.querySelector("#arrivals-library").value;
  if (server) params.set("server_id", server);
  if (library) params.set("library_id", library);
  params.set("offset", String(arrivalsOffset));
  for (const [selector, key] of [["#arrivals-author", "author"], ["#arrivals-genre", "genre"], ["#arrivals-format", "media_format"], ["#arrivals-language", "language"], ["#arrivals-from", "detected_from"], ["#arrivals-to", "detected_to"], ["#arrivals-status", "delivery_status"]]) {
    const value = document.querySelector(selector).value.trim(); if (value) params.set(key, value);
  }
  const result = await call("/arrivals?" + params.toString());
  if (request !== arrivalsRequest) return;
  arrivals = result; renderArrivals();
}
function renderArrivals() {
  const container = document.querySelector("#arrivals-list"); container.replaceChildren();
  document.querySelector("#arrivals-previous").disabled = arrivalsOffset === 0;
  document.querySelector("#arrivals-next").disabled = arrivals.length < 50;
  document.querySelector("#arrivals-page").textContent = strings().page + " " + (Math.floor(arrivalsOffset / 50) + 1);
  if (!arrivals.length) { const empty = document.createElement("p"); empty.textContent = strings().noArrivals; container.append(empty); return; }
  for (const arrival of arrivals) {
    const card = document.createElement("div"); card.className = "library-card";
    const title = document.createElement("h3"); title.textContent = arrival.title || "—"; card.append(title);
    const authors = document.createElement("p"); authors.textContent = arrival.authors.join(", "); card.append(authors);
    const source = document.createElement("p"); source.textContent = [arrival.server_name, arrival.library_name, arrival.detected_at].join(" · "); card.append(source);
    const state = document.createElement("p"); state.textContent = strings().eventStatus + ": " + arrival.status + " · " + strings().deliveryStates + ": " + arrival.delivery_statuses.join(", "); card.append(state);
    const details = document.createElement("details"), summary = document.createElement("summary"), content = document.createElement("div");
    summary.textContent = strings().details; details.append(summary, content);
    details.addEventListener("toggle", async () => {
      if (!details.open || content.dataset.loaded === "true") return;
      try {
        const data = await call("/arrivals/" + arrival.event_id); content.replaceChildren();
        const coverButton = document.createElement("button"), coverStatus = document.createElement("span");
        coverButton.type = "button"; coverButton.textContent = strings().showCover;
        coverButton.addEventListener("click", () => {
          const image = document.createElement("img"); image.className = "arrival-cover"; image.alt = strings().coverAlt;
          image.addEventListener("error", () => { image.remove(); coverStatus.textContent = strings().coverUnavailable; });
          image.src = "/api/v1/admin/arrivals/" + encodeURIComponent(arrival.event_id) + "/cover";
          coverButton.disabled = true; content.insertBefore(image, coverStatus);
        });
        content.append(coverButton, coverStatus);
        const metadata = document.createElement("dl");
        for (const [key, value] of Object.entries(data.metadata)) {
          if (value === null || value === "" || (Array.isArray(value) && value.length === 0)) continue;
          const term = document.createElement("dt"), description = document.createElement("dd");
          term.textContent = strings()[key === "language" ? "languageField" : key] || key;
          description.textContent = Array.isArray(value) ? value.join(", ") : String(value); metadata.append(term, description);
        }
        content.append(metadata);
        for (const delivery of data.deliveries) {
          const title = document.createElement("strong"); title.textContent = delivery.webhook_name + " · " + delivery.status; content.append(title);
          const list = document.createElement("ul");
          for (const attempt of delivery.attempts) { const item = document.createElement("li"); item.textContent = [attempt.attempted_at, attempt.status, attempt.error, attempt.discord_message_id].filter(Boolean).join(" · "); list.append(item); }
          content.append(list);
        }
        if (data.history_truncated) { const note = document.createElement("p"); note.textContent = strings().historyTruncated; content.append(note); }
        content.dataset.loaded = "true";
      } catch { message.textContent = strings().failed; }
    });
    card.append(details);
    container.append(card);
  }
}
document.querySelector("#arrivals-server").addEventListener("change", () => { arrivalsOffset = 0; populateArrivalFilters(); loadArrivals().catch(() => { message.textContent = strings().failed; }); });
document.querySelector("#arrivals-library").addEventListener("change", () => { arrivalsOffset = 0; loadArrivals().catch(() => { message.textContent = strings().failed; }); });
document.querySelector("#arrivals-refresh").addEventListener("click", () => loadArrivals().catch(() => { message.textContent = strings().failed; }));
document.querySelector("#arrivals-filters").addEventListener("submit", event => { event.preventDefault(); arrivalsOffset = 0; loadArrivals().catch(() => { message.textContent = strings().failed; }); });
document.querySelector("#arrivals-previous").addEventListener("click", () => { arrivalsOffset = Math.max(0, arrivalsOffset - 50); loadArrivals().catch(() => { message.textContent = strings().failed; }); });
document.querySelector("#arrivals-next").addEventListener("click", () => { arrivalsOffset += 50; loadArrivals().catch(() => { message.textContent = strings().failed; }); });
function renderDeliveries() {
  const list = document.querySelector("#delivery-list"); list.replaceChildren();
  for (const delivery of deliveries) {
    const card = document.createElement("div"); card.className = "library-card";
    const heading = document.createElement("h3"); heading.textContent = delivery.book_title || "—"; card.append(heading);
    const source = document.createElement("p"); source.textContent = [delivery.server_name, delivery.library_name, delivery.webhook_name].join(" · "); card.append(source);
    const state = document.createElement("p"); state.textContent = delivery.status + " · " + strings().attempts + ": " + delivery.attempt_count; card.append(state);
    for (const [label, value] of [[strings().detectedAt, delivery.detected_at], [strings().sentAt, delivery.sent_at], [strings().lastError, delivery.last_error], [strings().discordId, delivery.discord_message_id]]) {
      if (value) { const line = document.createElement("p"); line.textContent = label + ": " + value; card.append(line); }
    }
    const details = document.createElement("ul"); details.hidden = true; card.append(details);
    const show = document.createElement("button"); show.type = "button"; show.textContent = strings().showHistory;
    show.addEventListener("click", async () => {
      try {
        const entries = await call("/notifications/" + delivery.id + "/history"); details.replaceChildren();
        for (const entry of entries) { const row = document.createElement("li"); row.textContent = [entry.attempted_at, entry.status, entry.error, entry.discord_message_id].filter(Boolean).join(" · "); details.append(row); }
        details.hidden = false;
      } catch { message.textContent = strings().failed; }
    });
    card.append(show);
    if (["FAILED", "RETRY", "SENT"].includes(delivery.status)) {
      card.append(actionButton(strings().retryAction, async () => {
        const resend = delivery.status === "SENT";
        if (resend && !window.confirm(strings().resendConfirm)) return false;
        await call("/notifications/" + delivery.id + "/retry", {...mutationOptions({confirm_sent_resend: resend}), method: "POST"});
      }));
    }
    list.append(card);
  }
}
function mutationOptions(body) {
  return {method: "PUT", headers: {"Content-Type": "application/json", "X-CSRF-Token": cookie("bookorbit_csrf")}, body: JSON.stringify(body)};
}
function actionButton(label, action, success = null) {
  const button = document.createElement("button"); button.type = "button"; button.textContent = label;
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      try { if (await action() === false) return; }
      catch { message.textContent = strings().failed; return; }
      try { await refresh(); message.textContent = success || strings().configuredOk; }
      catch { message.textContent = strings().refreshFailed; }
    } finally { button.disabled = false; }
  });
  return button;
}
function renderManagement() {
  const serverList = document.querySelector("#server-list"); serverList.replaceChildren();
  for (const server of servers) {
    const item = document.createElement("li"); item.append(document.createTextNode(server.name + " — " + server.base_url));
    item.append(actionButton(server.enabled ? strings().disable : strings().enable, () => call("/servers/" + server.id + "/enabled", mutationOptions({enabled: !server.enabled}))));
    const sync = actionButton(strings().syncLibraries, () => call("/servers/" + server.id + "/sync-libraries", {...mutationOptions({}), method: "POST"}));
    sync.disabled = !server.enabled; item.append(sync);
    const test = actionButton(strings().testConnection, () => call("/servers/" + server.id + "/test", {...mutationOptions({}), method: "POST"}), strings().connectionOk);
    test.disabled = !server.enabled; item.append(test);
    const scan = actionButton(strings().manualScan, () => call("/servers/" + server.id + "/scan", {...mutationOptions({}), method: "POST"}));
    scan.disabled = !server.enabled; item.append(scan);
    const details = document.createElement("details"), summary = document.createElement("summary"), form = document.createElement("form");
    summary.textContent = strings().edit; details.append(summary);
    const notice = document.createElement("p"); notice.textContent = strings().sourceIdentity; form.append(notice);
    function field(labelText, type, initial) { const label = document.createElement("label"), input = document.createElement("input"); label.textContent = labelText; input.type = type; input.value = initial; label.append(input); form.append(label); return input; }
    const name = field(strings().name, "text", server.name); name.maxLength = 120; name.required = true;
    const interval = field(strings().interval, "number", String(server.scan_interval_seconds)); interval.min = "30"; interval.max = "86400"; interval.required = true;
    const key = field(strings().replaceKey, "password", ""); key.autocomplete = "off";
    const save = document.createElement("button"); save.type = "submit"; save.textContent = strings().saveChanges; form.append(save);
    form.addEventListener("submit", async event => {
      event.preventDefault(); save.disabled = true;
      try {
        await call("/servers/" + server.id, mutationOptions({name: name.value, scan_interval_seconds: Number(interval.value), api_key: key.value || null}));
        try { await refresh(); message.textContent = strings().configuredOk; } catch { message.textContent = strings().refreshFailed; }
      } catch { message.textContent = strings().failed; } finally { key.value = ""; save.disabled = false; }
    });
    details.append(form); item.append(details); serverList.append(item);
  }
  const webhookList = document.querySelector("#webhook-list"); webhookList.replaceChildren();
  for (const webhook of webhooks) {
    const item = document.createElement("li"); item.append(document.createTextNode(webhook.name));
    const label = document.createElement("label"), selection = document.createElement("select"); label.textContent = " " + strings().testProfile + " ";
    const standard = document.createElement("option"); standard.value = ""; standard.textContent = strings().defaultProfile; selection.append(standard);
    for (const library of libraries.filter(entry => entry.webhook_ids.includes(webhook.id))) {
      const option = document.createElement("option"), source = servers.find(server => server.id === library.server_id);
      option.value = String(library.id); option.textContent = (source?.name || "") + " — " + library.name; selection.append(option);
    }
    label.append(selection); item.append(label);
    const test = actionButton(strings().testMessage, () => call("/webhooks/" + webhook.id + "/test", {...mutationOptions({library_id: selection.value ? Number(selection.value) : null}), method: "POST"}), strings().testSent);
    test.disabled = !webhook.enabled; item.append(test);
    const details = document.createElement("details"), summary = document.createElement("summary"), form = document.createElement("form");
    summary.textContent = strings().edit; details.append(summary);
    const nameLabel = document.createElement("label"), name = document.createElement("input"); nameLabel.textContent = strings().name; name.value = webhook.name; name.maxLength = 120; name.required = true; nameLabel.append(name); form.append(nameLabel);
    const enabledLabel = document.createElement("label"), enabled = document.createElement("input"); enabled.type = "checkbox"; enabled.checked = webhook.enabled; enabledLabel.append(enabled, document.createTextNode(" " + strings().webhookEnabled)); form.append(enabledLabel);
    const urlLabel = document.createElement("label"), url = document.createElement("input"); urlLabel.textContent = strings().replaceWebhook; url.type = "password"; url.autocomplete = "off"; urlLabel.append(url); form.append(urlLabel);
    const save = document.createElement("button"); save.type = "submit"; save.textContent = strings().saveChanges; form.append(save);
    form.addEventListener("submit", async event => {
      event.preventDefault(); const replacing = url.value !== "";
      if (replacing && !window.confirm(strings().confirmWebhookChange)) return;
      save.disabled = true;
      try {
        await call("/webhooks/" + webhook.id, mutationOptions({name: name.value, enabled: enabled.checked, webhook_url: replacing ? url.value : null, confirm_destination_change: replacing}));
        try { await refresh(); message.textContent = strings().configuredOk; } catch { message.textContent = strings().refreshFailed; }
      } catch { message.textContent = strings().failed; } finally { url.value = ""; save.disabled = false; }
    });
    details.append(form); item.append(details); webhookList.append(item);
  }
  const libraryList = document.querySelector("#library-list"); libraryList.replaceChildren();
  for (const library of libraries) {
    const card = document.createElement("div"); card.className = "library-card";
    const heading = document.createElement("h3"), server = servers.find(item => item.id === library.server_id);
    heading.textContent = (server?.name || "") + " — " + library.name; card.append(heading);
    const facts = document.createElement("p");
    facts.textContent = strings().knownBooks + ": " + library.book_count + " · " + strings().libraryArrivals + ": " + library.arrival_count + " · " + strings().lastScan + ": " + (library.last_scan || "—"); card.append(facts);
    const monitorLabel = document.createElement("label"), monitored = document.createElement("input");
    monitored.type = "checkbox"; monitored.checked = library.monitored; monitorLabel.append(monitored, document.createTextNode(" " + strings().monitored)); card.append(monitorLabel);
    const legend = document.createElement("p"); legend.textContent = strings().destination; card.append(legend);
    const choices = [];
    for (const webhook of webhooks) {
      const label = document.createElement("label"), checkbox = document.createElement("input");
      checkbox.type = "checkbox"; checkbox.checked = library.webhook_ids.includes(webhook.id); choices.push([webhook.id, checkbox]);
      label.append(checkbox, document.createTextNode(" " + webhook.name)); card.append(label);
    }
    const templateLabel = document.createElement("label"), templateSelect = document.createElement("select");
    templateLabel.textContent = strings().libraryTemplate;
    const fallback = document.createElement("option"); fallback.value = ""; fallback.textContent = strings().defaultTemplate; templateSelect.append(fallback);
    for (const template of templates) { const option = document.createElement("option"); option.value = String(template.id); option.textContent = template.name; templateSelect.append(option); }
    templateSelect.value = library.template_id === null ? "" : String(library.template_id);
    templateLabel.append(templateSelect); card.append(templateLabel);
    card.append(actionButton(strings().saveRouting, () => call("/libraries/" + library.id + "/routing", mutationOptions({monitored: monitored.checked, webhook_ids: choices.filter(([, checkbox]) => checkbox.checked).map(([id]) => id), template_id: templateSelect.value ? Number(templateSelect.value) : null}))));
    const delivery = document.createElement("form");
    const modeLabel = document.createElement("label"), mode = document.createElement("select"); modeLabel.textContent = strings().deliveryMode;
    for (const [value, label] of [["SINGLE", strings().modeSingle], ["BATCH", strings().modeBatch], ["DAILY_SUMMARY", strings().modeDaily]]) {
      const option = document.createElement("option"); option.value = value; option.textContent = label; mode.append(option);
    }
    mode.value = library.delivery_mode; modeLabel.append(mode); delivery.append(modeLabel);
    function inputField(labelText, type, value) {
      const label = document.createElement("label"), input = document.createElement("input");
      label.textContent = labelText; input.type = type; input.value = String(value); input.required = true; label.append(input); delivery.append(label); return input;
    }
    const batch = inputField(strings().batchSeconds, "number", library.batch_window_seconds); batch.min = "30"; batch.max = "86400";
    const daily = inputField(strings().dailyTime, "time", library.daily_summary_time);
    const zone = inputField(strings().timezone, "text", library.timezone); zone.maxLength = 64;
    const hint = document.createElement("p"); hint.textContent = strings().deliveryHint; delivery.append(hint);
    const save = document.createElement("button"); save.type = "submit"; save.textContent = strings().saveDelivery; delivery.append(save);
    delivery.addEventListener("submit", async event => {
      event.preventDefault();
      try {
        await call("/libraries/" + library.id + "/delivery", mutationOptions({delivery_mode: mode.value, batch_window_seconds: Number(batch.value), daily_summary_time: daily.value, timezone: zone.value}));
        await refresh(); message.textContent = strings().configuredOk;
      } catch { message.textContent = strings().failed; }
    });
    card.append(delivery);
    libraryList.append(card);
  }
}
function populateTemplateSelector() {
  const select = document.querySelector("#template-select"), current = select.value;
  select.replaceChildren();
  const empty = document.createElement("option"); empty.value = ""; empty.textContent = strings().newTemplate; select.append(empty);
  for (const template of templates) { const option = document.createElement("option"); option.value = String(template.id); option.textContent = template.name; select.append(option); }
  if ([...select.options].some(option => option.value === current)) select.value = current;
}
document.querySelector("#template-select").addEventListener("change", event => {
  const template = templates.find(item => String(item.id) === event.target.value);
  document.querySelector("#template-name").value = template?.name || "";
  if (template) {
    document.querySelector("#preview-title").value = template.title_template;
    document.querySelector("#preview-description").value = template.description_template;
    document.querySelector("#preview-footer").value = template.footer_template || "";
    queuePreview();
  }
});
document.querySelector("#save-template").addEventListener("click", async () => {
  const selected = templates.find(item => String(item.id) === document.querySelector("#template-select").value);
  const payload = {name: document.querySelector("#template-name").value, title_template: document.querySelector("#preview-title").value, description_template: document.querySelector("#preview-description").value, footer_template: document.querySelector("#preview-footer").value || null, color: selected?.color ?? 0x2f855a, show_cover: selected?.show_cover ?? true, metadata_fields: selected?.metadata_fields ?? []};
  try {
    const result = await call(selected ? "/templates/" + selected.id : "/templates", {...mutationOptions(payload), method: selected ? "PUT" : "POST"});
    await refresh();
    document.querySelector("#template-select").value = String(selected?.id ?? result.id);
    message.textContent = strings().configuredOk;
  } catch { message.textContent = strings().failed; }
});
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
document.querySelector("#change-password-form").addEventListener("submit", async event => {
  event.preventDefault();
  const current = document.querySelector("#current-password"), replacement = document.querySelector("#replacement-password"), repeat = document.querySelector("#repeat-password");
  if (replacement.value !== repeat.value) { message.textContent = strings().passwordMismatch; return; }
  const button = event.currentTarget.querySelector("button[type=submit]"); button.disabled = true;
  try {
    await call("/change-password", {...mutationOptions({current_password: current.value, new_password: replacement.value}), method: "POST"});
    counts = null; dashboard.hidden = true; authPanel.hidden = false; message.textContent = strings().passwordChanged;
  } catch { message.textContent = strings().failed; }
  finally { current.value = ""; replacement.value = ""; repeat.value = ""; button.disabled = false; }
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
