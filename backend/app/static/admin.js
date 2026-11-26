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
Object.assign(messages.de, {historyHelp: "Zustellungen in Seiten zu je 50. Ein erneuter Versand bereits zugestellter Nachrichten erzeugt eine weitere Discord-Nachricht."});
Object.assign(messages.en, {historyHelp: "Deliveries in pages of 50. Resending a delivered notification creates another Discord message."});
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
Object.assign(messages.de, {previewWebhook: "Webhook für Profilvorschau", previewLibrary: "Bibliothek für Profilvorschau", noContext: "Keine Auswahl", previewAvatarCustom: "Profilbild-URL konfiguriert (Bildvorschau noch nicht verfügbar)", previewAvatarOriginal: "Originales Webhook-Profilbild (nicht abgerufen)", previewProfileInvalid: "Absenderprofil ungültig"});
Object.assign(messages.en, {previewWebhook: "Webhook for profile preview", previewLibrary: "Library for profile preview", noContext: "No selection", previewAvatarCustom: "Avatar URL configured (image preview not yet available)", previewAvatarOriginal: "Original webhook avatar (not retrieved)", previewProfileInvalid: "Invalid sender profile"});
Object.assign(messages.de, {sendPreview: "Vorschau als Testnachricht senden", chooseWebhook: "Bitte wähle einen Webhook für die Vorschau.", confirmPreview: "Diese Vorschau mit Beispieldaten tatsächlich an den ausgewählten Discord-Webhook senden?"});
Object.assign(messages.en, {sendPreview: "Send preview as test message", chooseWebhook: "Please select a webhook for the preview.", confirmPreview: "Send this preview with sample data to the selected Discord webhook?"});
Object.assign(messages.de, {embedColor: "Embed-Farbe", addField: "Als Metadatenfeld hinzufügen", fieldHelp: "Felder lassen sich ziehen oder mit den Schaltflächen verschieben; leere Werte werden ausgelassen.", moveUp: "Nach oben", moveDown: "Nach unten", removeField: "Entfernen", fieldLimit: "Ein Feld darf nur einmal und höchstens 25 Felder dürfen ausgewählt werden."});
Object.assign(messages.en, {embedColor: "Embed color", addField: "Add as metadata field", fieldHelp: "Drag fields or use the buttons to reorder them; empty values are omitted.", moveUp: "Move up", moveDown: "Move down", removeField: "Remove", fieldLimit: "Each field can only be selected once, with at most 25 fields."});
messages.de.previewAvatarCustom = "Benutzerdefiniertes Profilbild";
messages.en.previewAvatarCustom = "Custom avatar";
Object.assign(messages.de, {previewAvatarFailed: "Profilbild konnte im Browser nicht geladen werden."});
Object.assign(messages.en, {previewAvatarFailed: "The browser could not load the avatar."});
Object.assign(messages.de, {avatarPrivacy: "Profilbilder werden für die Vorschau direkt im Browser vom Bildanbieter geladen. Der Anbieter sieht dabei deine IP-Adresse."});
Object.assign(messages.en, {avatarPrivacy: "Avatar images are loaded directly from their host in your browser. The host can see your IP address."});
Object.assign(messages.de, {loadOriginal: "Originales Webhook-Profil von Discord laden", originalLoaded: "Originales Webhook-Profil geladen.", originalAvatarLoaded: "Originales Webhook-Profilbild", originalNoAvatar: "Für diesen Webhook ist kein individuelles Profilbild gespeichert."});
Object.assign(messages.en, {loadOriginal: "Load original webhook profile from Discord", originalLoaded: "Original webhook profile loaded.", originalAvatarLoaded: "Original webhook avatar", originalNoAvatar: "This webhook has no custom avatar."});
Object.assign(messages.de, {showCover: "Cover in Benachrichtigungen anzeigen", coverPreviewHint: "Die Vorschau und ihre Testnachricht verwenden ein Beispiel-Cover, kein echtes BookOrbit-Cover.", variableUnavailable: "noch nicht verfügbar"});
Object.assign(messages.en, {showCover: "Show covers in notifications", coverPreviewHint: "The preview and its test message use a sample cover, not a real BookOrbit cover.", variableUnavailable: "not available yet"});
Object.assign(messages.de, {mainNavigation: "Hauptnavigation", arrivalPages: "Neuzugänge Seiten", historyPages: "Zustellungen Seiten"});
Object.assign(messages.en, {mainNavigation: "Main navigation", arrivalPages: "Arrival pages", historyPages: "Delivery pages"});
Object.assign(messages.de, {settings: "Settings", sectionNavigation: "Bereichsnavigation"});
Object.assign(messages.en, {settings: "Settings", sectionNavigation: "Section navigation"});
Object.assign(messages.de, {arrivalView: "Ansicht", arrivalList: "Liste", arrivalTable: "Tabelle", arrivalGrid: "Cover-Grid", arrivalSource: "Quelle", arrivalDate: "Erkannt", arrivalStatus: "Status"});
Object.assign(messages.en, {arrivalView: "View", arrivalList: "List", arrivalTable: "Table", arrivalGrid: "Cover grid", arrivalSource: "Source", arrivalDate: "Detected", arrivalStatus: "Status"});
Object.assign(messages.de, {serverScanOverview: "Letzter Bibliotheksscan je Server", serverScanHelp: "Der zuletzt protokollierte Bibliotheksscan ist keine Live-Verbindungsprüfung und bewertet nicht alle Bibliotheken eines Servers.", scanUnknown: "Noch kein Bibliotheksscan protokolliert", scanDisabled: "Deaktiviert", scanSucceeded: "Erfolgreich", scanPartial: "Unvollständig", scanFailed: "Fehlgeschlagen"});
Object.assign(messages.en, {serverScanOverview: "Latest library scan per server", serverScanHelp: "The latest recorded library scan is not a live connection check and does not evaluate every library on a server.", scanUnknown: "No library scan recorded yet", scanDisabled: "Disabled", scanSucceeded: "Succeeded", scanPartial: "Incomplete", scanFailed: "Failed"});
Object.assign(messages.de, {nextScan: "Nächster geplanter Scan", runtimeOff: "Automatische Verarbeitung deaktiviert", runtimeOn: "Automatische Verarbeitung aktiviert", nextScanHint: "Scanzeiten sind geplante Zeitpunkte und können sich durch laufende Aufgaben verzögern."});
Object.assign(messages.en, {nextScan: "Next scheduled scan", runtimeOff: "Automatic processing disabled", runtimeOn: "Automatic processing enabled", nextScanHint: "Scan times are scheduled estimates and may be delayed by ongoing work."});
Object.assign(messages.de, {scanHistory: "Scan-Protokoll", scanHistoryHelp: "Ergebnisse einzelner Bibliotheksscans in UTC. Verbindungsdaten und Fehlermeldungen werden nicht angezeigt.", scanFrom: "Abgeschlossen ab (UTC)", scanTo: "Abgeschlossen bis (UTC)", scanPages: "Scan-Protokoll Seiten", scanStarted: "Begonnen", scanCompleted: "Abgeschlossen", scanSeen: "Medien erfasst", scanAdded: "Neu erfasst", noScans: "Keine Scans für diese Auswahl."});
Object.assign(messages.en, {scanHistory: "Scan history", scanHistoryHelp: "Results of individual library scans in UTC. Connection details and error messages are not shown.", scanFrom: "Completed from (UTC)", scanTo: "Completed through (UTC)", scanPages: "Scan history pages", scanStarted: "Started", scanCompleted: "Completed", scanSeen: "Media seen", scanAdded: "Newly recorded", noScans: "No scans match these filters."});
Object.assign(messages.de, {latestArrivals: "Zuletzt erkannte Medien", latestArrivalsHelp: "Nur erkannte Neuzugänge; die stille Ersterfassung ist nicht enthalten.", allArrivals: "Alle Neuzugänge anzeigen"});
Object.assign(messages.en, {latestArrivals: "Recently detected media", latestArrivalsHelp: "Detected arrivals only; the silent initial baseline is excluded.", allArrivals: "Show all arrivals"});
Object.assign(messages.de, {connectionSettings: "Verbindungseinstellungen", publicUrl: "Öffentliche Server-URL (optional)", connectionTimeout: "Verbindungs-Timeout in Sekunden", verifySsl: "TLS-Zertifikat prüfen", publicUrlHelp: "Die öffentliche URL wird gespeichert; direkte Buchlinks werden noch nicht erzeugt.", verifySslHelp: "Ohne Zertifikatsprüfung kann die Serveridentität nicht überprüft werden."});
Object.assign(messages.en, {connectionSettings: "Connection settings", publicUrl: "Public server URL (optional)", connectionTimeout: "Connection timeout in seconds", verifySsl: "Verify TLS certificate", publicUrlHelp: "The public URL is stored; direct book links are not generated yet.", verifySslHelp: "Without certificate verification, the server identity cannot be verified."});
Object.assign(messages.de, {probeLibrary: "Bibliothek für Beispielprüfung", probeContent: "Metadaten und Cover prüfen", probeEmpty: "Kein Beispielmedium in dieser Bibliothek gefunden.", probeCoverOk: "Metadaten und Cover sind für das Beispiel abrufbar.", probeCoverMissing: "Metadaten sind abrufbar; für das Beispiel ist kein Cover vorhanden.", probeFailed: "Beispielprüfung fehlgeschlagen. Bitte Verbindung und Leseberechtigung prüfen."});
Object.assign(messages.en, {probeLibrary: "Library for sample check", probeContent: "Check metadata and cover", probeEmpty: "No sample media found in this library.", probeCoverOk: "Metadata and cover are accessible for the sample.", probeCoverMissing: "Metadata is accessible; the sample has no cover.", probeFailed: "Sample check failed. Check the connection and read access."});
messages.de.loadCover = "Cover laden";
messages.en.loadCover = "Load cover";
Object.assign(messages.de, {seriesNumbered: "Serientag mit Nummer", seriesUnnumbered: "Serientag ohne Nummer", seriesTagHelp: "Verwende {{series_tag}} als Variable oder Metadatenfeld. Ohne Reihe bleibt der Serientag leer. In beiden Vorlagen sind {{series}} und {{series_index}} verfügbar.", sampleSeries: "Serienbeispiel für die Vorschau", sampleSeriesNumbered: "Reihe mit Nummer", sampleSeriesUnnumbered: "Reihe ohne Nummer", sampleSeriesNone: "Keine Reihe"});
Object.assign(messages.en, {seriesNumbered: "Series tag with number", seriesUnnumbered: "Series tag without number", seriesTagHelp: "Use {{series_tag}} as a variable or metadata field. It is empty when there is no series. Both formats support {{series}} and {{series_index}}.", sampleSeries: "Series example for preview", sampleSeriesNumbered: "Numbered series", sampleSeriesUnnumbered: "Unnumbered series", sampleSeriesNone: "No series"});
messages.de.previewOriginal = "Originaler Webhook-Name (nicht abgerufen)";
messages.en.previewOriginal = "Original webhook name (not retrieved)";
let counts = null;
let overview = null;
let scopes = {libraries: [], webhooks: []};
let profileRequest = 0;
let previewRequest = 0, previewTimer;
let selectedMetadata = [], draggedField = null;
let senderPreviewRequest = 0, senderPreviewTimer;
const originalProfiles = new Map();
let servers = [], webhooks = [], libraries = [];
let deliveries = [];
let deliveryOffset = 0, deliveryRequest = 0;
let templates = [];
let arrivals = [];
let latestArrivals = [];
let arrivalsRequest = 0;
let arrivalsOffset = 0;
let scanRows = [], scanOffset = 0, scanRequest = 0, scanHasMore = false;
function strings() { return messages[language.value]; }

// Changing views only hides existing controls, so unsaved editor input is retained.
const viewCategories = {overview: "overview", libraries: "bookorbit", presets: "presets", arrivals: "imports", "scan-history": "imports", history: "discord", servers: "settings", webhooks: "settings", sender: "settings"};
const legacyViews = {"dashboard-title": "overview", "arrivals-heading": "arrivals", "servers-heading": "servers", "libraries-heading": "libraries", "webhooks-heading": "webhooks", "preview-heading": "presets", "history-heading": "history", "account-settings": "servers"};
function selectView() {
  const fragment = location.hash.slice(1);
  const candidate = fragment.startsWith("view-") ? fragment.slice(5) : legacyViews[fragment];
  const view = Object.hasOwn(viewCategories, candidate) ? candidate : "overview", category = viewCategories[view];
  document.querySelectorAll("[data-view]").forEach(element => { element.hidden = element.dataset.view !== view; });
  document.querySelectorAll("[data-category]").forEach(link => {
    if (link.dataset.category === category) link.setAttribute("aria-current", "true"); else link.removeAttribute("aria-current");
  });
  document.querySelectorAll("[data-menu]").forEach(link => {
    link.hidden = link.dataset.menu !== category;
    if (link.getAttribute("href") === "#view-" + view) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
  });
}
window.addEventListener("hashchange", selectView);
selectView();
function translate() {
  document.documentElement.lang = language.value;
  document.querySelectorAll("[data-text]").forEach(element => { element.textContent = strings()[element.dataset.text]; });
  document.querySelectorAll("[data-label]").forEach(element => { element.setAttribute("aria-label", strings()[element.dataset.label]); });
  if (counts) renderCounts(counts);
  if (overview) renderOverview(overview);
  renderManagement();
  renderDeliveries();
  populateTemplateSelector();
  renderMetadataFields();
  for (const option of document.querySelectorAll("#preview-variable option")) {
    option.textContent = "{{" + option.value + "}}" + (option.disabled ? " — " + strings().variableUnavailable : "");
  }
  populateArrivalFilters();
  renderArrivals();
  renderLatestArrivals();
  renderScanHistory();
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
  ++senderPreviewRequest;
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
function profileDraft() {
  const scope = document.querySelector("#profile-scope").value, target = document.querySelector("#profile-target").value;
  if (scope !== "global" && !target) return null;
  const field = name => { const choice = document.querySelector("#" + name + "-choice").value; return {choice, value: choice === "custom" ? document.querySelector("#" + name + "-value").value : null}; };
  const webhook = scope === "webhook" ? target : document.querySelector("#preview-webhook").value;
  const library = scope === "library" ? target : document.querySelector("#preview-library").value;
  return {scope, scope_id: scope === "global" ? null : Number(target), webhook_id: webhook ? Number(webhook) : null, library_id: library ? Number(library) : null, username: field("username"), avatar_url: field("avatar")};
}
function updatePreviewSender() {
  clearTimeout(senderPreviewTimer);
  const request = ++senderPreviewRequest;
  senderPreviewTimer = setTimeout(async () => {
    const payload = profileDraft();
    if (!payload) return;
    try {
      const result = await call("/sender-profile-preview", {method: "POST", headers: {"Content-Type": "application/json", "X-CSRF-Token": cookie("bookorbit_csrf")}, body: JSON.stringify(payload)});
      if (request !== senderPreviewRequest) return;
      const original = originalProfiles.get(payload.webhook_id);
      document.querySelector("#preview-sender").textContent = result.username ?? original?.username ?? strings().previewOriginal;
      const imageUrl = result.avatar_url ?? original?.avatar_url ?? null;
      document.querySelector("#preview-avatar-status").textContent = result.avatar_url ? strings().previewAvatarCustom : original ? (original.avatar_url ? strings().originalAvatarLoaded : strings().originalNoAvatar) : strings().previewAvatarOriginal;
      const avatar = document.querySelector("#preview-avatar-image"), fallback = document.querySelector("#preview-avatar-fallback");
      avatar.hidden = !imageUrl; fallback.hidden = Boolean(imageUrl);
      if (imageUrl) avatar.src = imageUrl; else avatar.removeAttribute("src");
    } catch { if (request === senderPreviewRequest) document.querySelector("#preview-sender").textContent = strings().previewProfileInvalid; }
  }, 250);
}
document.querySelector("#preview-avatar-image").addEventListener("error", () => {
  document.querySelector("#preview-avatar-image").hidden = true;
  document.querySelector("#preview-avatar-fallback").hidden = false;
  document.querySelector("#preview-avatar-status").textContent = strings().previewAvatarFailed;
});
document.querySelector("#load-original-profile").addEventListener("click", async event => {
  const draft = profileDraft();
  if (!draft?.webhook_id) { message.textContent = strings().chooseWebhook; return; }
  const webhookId = draft.webhook_id, button = event.currentTarget; button.disabled = true;
  try {
    const profile = await call("/webhooks/" + webhookId + "/original-profile", {...mutationOptions({}), method: "POST"});
    originalProfiles.set(webhookId, profile); message.textContent = strings().originalLoaded; updatePreviewSender();
  } catch { message.textContent = strings().failed; } finally { button.disabled = false; }
});
function populatePreviewContexts() {
  for (const [selector, entries] of [["#preview-webhook", scopes.webhooks], ["#preview-library", scopes.libraries]]) {
    const select = document.querySelector(selector), previous = select.value; select.replaceChildren();
    const empty = document.createElement("option"); empty.value = ""; empty.textContent = strings().noContext; select.append(empty);
    for (const entry of entries) { const option = document.createElement("option"); option.value = String(entry.id); option.textContent = entry.server_name ? entry.server_name + " — " + entry.name : entry.name; select.append(option); }
    if ([...select.options].some(option => option.value === previous)) select.value = previous;
  }
  document.querySelector("#preview-webhook").disabled = document.querySelector("#profile-scope").value === "webhook";
  document.querySelector("#preview-library").disabled = document.querySelector("#profile-scope").value === "library";
  if (document.querySelector("#preview-webhook").disabled) document.querySelector("#preview-webhook").value = document.querySelector("#profile-target").value;
  if (document.querySelector("#preview-library").disabled) document.querySelector("#preview-library").value = document.querySelector("#profile-target").value;
}
async function renderPreview() {
  const request = ++previewRequest;
  const error = document.querySelector("#preview-error");
  try {
    const data = await call("/template-preview", {method: "POST", headers: {"Content-Type": "application/json", "X-CSRF-Token": cookie("bookorbit_csrf")}, body: JSON.stringify(previewDraft())});
    if (request !== previewRequest) return;
    document.querySelector("#preview-rendered-title").textContent = data.title;
    document.querySelector("#preview-rendered-description").textContent = data.description;
    document.querySelector("#preview-rendered-footer").textContent = data.footer?.text || "";
    document.querySelector(".discord-embed").style.borderLeftColor = "#" + data.color.toString(16).padStart(6, "0");
    const fields = document.querySelector("#preview-rendered-fields"); fields.replaceChildren();
    for (const field of data.fields || []) { const term = document.createElement("dt"), value = document.createElement("dd"); term.textContent = field.name; value.textContent = field.value; fields.append(term, value); }
    error.textContent = "";
  } catch { if (request === previewRequest) error.textContent = strings().previewInvalid; }
}
function queuePreview() { clearTimeout(previewTimer); ++previewRequest; previewTimer = setTimeout(renderPreview, 250); }
function previewDraft() {
  return {title: document.querySelector("#preview-title").value, description: document.querySelector("#preview-description").value,
    footer: document.querySelector("#preview-footer").value, color: parseInt(document.querySelector("#preview-color").value.slice(1), 16), metadata_fields: [...selectedMetadata], show_cover: document.querySelector("#template-show-cover").checked,
    series_numbered_template: document.querySelector("#series-numbered").value, series_unnumbered_template: document.querySelector("#series-unnumbered").value, sample_series: document.querySelector("#sample-series").value};
}
function renderMetadataFields() {
  const list = document.querySelector("#metadata-fields"); list.replaceChildren();
  selectedMetadata.forEach((name, index) => {
    const item = document.createElement("li"), label = document.createElement("span"); item.draggable = true;
    label.textContent = "{{" + name + "}}" + (["book_url", "cover_url"].includes(name) ? " — " + strings().variableUnavailable : ""); item.append(label);
    const move = (destination) => { if (destination < 0 || destination >= selectedMetadata.length) return; const [value] = selectedMetadata.splice(index, 1); selectedMetadata.splice(destination, 0, value); renderMetadataFields(); queuePreview(); };
    for (const [caption, delta] of [[strings().moveUp, -1], [strings().moveDown, 1]]) {
      const button = document.createElement("button"); button.type = "button"; button.textContent = caption; button.setAttribute("aria-label", caption + " " + name);
      button.disabled = index + delta < 0 || index + delta >= selectedMetadata.length; button.addEventListener("click", () => move(index + delta)); item.append(button);
    }
    const remove = document.createElement("button"); remove.type = "button"; remove.textContent = strings().removeField; remove.setAttribute("aria-label", strings().removeField + " " + name);
    remove.addEventListener("click", () => { selectedMetadata.splice(index, 1); renderMetadataFields(); queuePreview(); }); item.append(remove);
    item.addEventListener("dragstart", () => { draggedField = index; });
    item.addEventListener("dragover", event => event.preventDefault());
    item.addEventListener("drop", event => { event.preventDefault(); if (draggedField === null || draggedField === index) return; const [value] = selectedMetadata.splice(draggedField, 1); selectedMetadata.splice(index, 0, value); draggedField = null; renderMetadataFields(); queuePreview(); });
    item.addEventListener("dragend", () => { draggedField = null; }); list.append(item);
  });
}
document.querySelector("#add-metadata-field").addEventListener("click", () => {
  const value = document.querySelector("#preview-variable").value;
  if (!value || selectedMetadata.includes(value) || selectedMetadata.length >= 25) { message.textContent = strings().fieldLimit; return; }
  selectedMetadata.push(value); renderMetadataFields(); queuePreview();
});
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
  populatePreviewContexts();
  await loadProfile();
}
async function refresh() {
  counts = await call("/notifications/summary");
  overview = await call("/dashboard");
  scopes = await call("/profile-scopes");
  [servers, webhooks, libraries, templates] = await Promise.all([call("/servers"), call("/webhooks"), call("/libraries"), call("/templates")]);
  await loadDeliveries();
  populateArrivalFilters();
  populateScanFilters();
  await loadArrivals();
  await loadScanHistory();
  latestArrivals = await call("/arrivals?limit=5"); renderLatestArrivals();
  populateTemplateSelector();
  renderManagement();
  renderDeliveries();
  const variables = await call("/template-variables");
  const variableSelect = document.querySelector("#preview-variable");
  variableSelect.replaceChildren();
  for (const variable of variables) {
    const option = document.createElement("option"); option.value = variable; option.disabled = ["book_url", "cover_url"].includes(variable);
    option.textContent = "{{" + variable + "}}" + (option.disabled ? " — " + strings().variableUnavailable : ""); variableSelect.append(option);
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
  const scans = document.querySelector("#overview-server-scans"); scans.replaceChildren();
  for (const server of data.servers) {
    const item = document.createElement("li"), status = {SUCCEEDED: strings().scanSucceeded, PARTIAL: strings().scanPartial, FAILED: strings().scanFailed}[server.last_library_scan_status] || strings().scanUnknown;
    item.textContent = [server.name, server.enabled ? null : strings().scanDisabled, status, server.last_library_scan_at, server.next_scan_at ? strings().nextScan + ": " + server.next_scan_at : null].filter(Boolean).join(" · "); scans.append(item);
  }
  document.querySelector("#runtime-status").textContent = data.runtime_enabled ? strings().runtimeOn : strings().runtimeOff;
}
function renderLatestArrivals() {
  const container = document.querySelector("#overview-arrivals"); container.replaceChildren();
  if (!latestArrivals.length) { const empty = document.createElement("p"); empty.textContent = strings().noArrivals; container.append(empty); return; }
  for (const arrival of latestArrivals) {
    const card = document.createElement("article"); card.className = "library-card";
    const image = document.createElement("img"); image.className = "arrival-grid-cover"; image.loading = "lazy"; image.alt = strings().coverAlt;
    image.addEventListener("error", () => { image.removeAttribute("src"); image.alt = strings().coverUnavailable; });
    image.src = "/api/v1/admin/arrivals/" + encodeURIComponent(arrival.event_id) + "/cover";
    const title = document.createElement("h4"); title.textContent = arrival.title || "—";
    const authors = document.createElement("p"); authors.textContent = arrival.authors.join(", ");
    const source = document.createElement("p"); source.textContent = [arrival.server_name, arrival.library_name].join(" · ");
    card.append(image, title, authors, source); container.append(card);
  }
}
function fillFilter(select, entries, previous) {
  select.replaceChildren();
  const all = document.createElement("option"); all.value = ""; all.textContent = strings().all; select.append(all);
  for (const entry of entries) { const option = document.createElement("option"); option.value = String(entry.id); option.textContent = entry.name; select.append(option); }
  if ([...select.options].some(option => option.value === previous)) select.value = previous;
}
function populateScanFilters() {
  const server = document.querySelector("#scan-server"), library = document.querySelector("#scan-library");
  const previousServer = server.value, previousLibrary = library.value;
  fillFilter(server, servers, previousServer);
  fillFilter(library, libraries.filter(entry => !server.value || String(entry.server_id) === server.value), previousLibrary);
}
async function loadScanHistory() {
  const request = ++scanRequest, params = new URLSearchParams({offset: String(scanOffset)});
  for (const [selector, key] of [["#scan-server", "server_id"], ["#scan-library", "library_id"], ["#scan-status", "scan_status"], ["#scan-from", "from_date"], ["#scan-to", "to_date"]]) {
    const value = document.querySelector(selector).value; if (value) params.set(key, value);
  }
  const result = await call("/scan-history?" + params.toString());
  if (request !== scanRequest) return;
  scanRows = result.items; scanHasMore = result.has_more; renderScanHistory();
}
function renderScanHistory() {
  const container = document.querySelector("#scan-history-list"); container.replaceChildren();
  document.querySelector("#scan-previous").disabled = scanOffset === 0;
  document.querySelector("#scan-next").disabled = !scanHasMore;
  document.querySelector("#scan-page").textContent = strings().page + " " + (Math.floor(scanOffset / 50) + 1);
  if (!scanRows.length) { const empty = document.createElement("p"); empty.textContent = strings().noScans; container.append(empty); return; }
  for (const scan of scanRows) {
    const item = document.createElement("article"); item.className = "library-card";
    const title = document.createElement("h3"); title.textContent = scan.server_name + " · " + scan.library_name; item.append(title);
    const status = document.createElement("p"); status.textContent = {SUCCEEDED: strings().scanSucceeded, PARTIAL: strings().scanPartial, FAILED: strings().scanFailed}[scan.status] || scan.status; item.append(status);
    const info = document.createElement("p"); info.textContent = [strings().scanStarted + ": " + scan.started_at, strings().scanCompleted + ": " + scan.completed_at, strings().scanSeen + ": " + scan.books_seen, strings().scanAdded + ": " + scan.books_added].join(" · "); item.append(info);
    container.append(item);
  }
}
document.querySelector("#scan-server").addEventListener("change", populateScanFilters);
document.querySelector("#scan-history-filters").addEventListener("submit", event => { event.preventDefault(); scanOffset = 0; loadScanHistory().catch(() => { message.textContent = strings().failed; }); });
document.querySelector("#scan-previous").addEventListener("click", () => { scanOffset = Math.max(0, scanOffset - 50); loadScanHistory().catch(() => { message.textContent = strings().failed; }); });
document.querySelector("#scan-next").addEventListener("click", () => { scanOffset += 50; loadScanHistory().catch(() => { message.textContent = strings().failed; }); });
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
function createArrivalDetails(arrival) {
    const details = document.createElement("details"), summary = document.createElement("summary"), content = document.createElement("div");
    summary.textContent = strings().details; details.append(summary, content);
    details.addEventListener("toggle", async () => {
      if (!details.open || content.dataset.loaded === "true") return;
      try {
        const data = await call("/arrivals/" + arrival.event_id); content.replaceChildren();
        const coverButton = document.createElement("button"), coverStatus = document.createElement("span");
        coverButton.type = "button"; coverButton.textContent = strings().loadCover;
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
    return details;
}
function renderArrivals() {
  const container = document.querySelector("#arrivals-list"), view = document.querySelector("#arrivals-view").value;
  container.replaceChildren(); container.className = view === "grid" && arrivals.length ? "arrival-grid" : "";
  document.querySelector("#arrivals-previous").disabled = arrivalsOffset === 0;
  document.querySelector("#arrivals-next").disabled = arrivals.length < 50;
  document.querySelector("#arrivals-page").textContent = strings().page + " " + (Math.floor(arrivalsOffset / 50) + 1);
  if (!arrivals.length) { const empty = document.createElement("p"); empty.textContent = strings().noArrivals; container.append(empty); return; }
  let tableBody = null;
  if (view === "table") {
    const wrap = document.createElement("div"), table = document.createElement("table"), head = document.createElement("thead"), row = document.createElement("tr");
    wrap.className = "arrival-table-wrap"; table.className = "arrival-table";
    for (const label of [strings().title, strings().authors, strings().arrivalSource, strings().arrivalDate, strings().arrivalStatus, strings().details]) {
      const header = document.createElement("th"); header.scope = "col"; header.textContent = label; row.append(header);
    }
    head.append(row); tableBody = document.createElement("tbody"); table.append(head, tableBody); wrap.append(table); container.append(wrap);
  }
  for (const arrival of arrivals) {
    const source = [arrival.server_name, arrival.library_name].join(" · ");
    const state = strings().eventStatus + ": " + arrival.status + " · " + strings().deliveryStates + ": " + arrival.delivery_statuses.join(", ");
    if (tableBody) {
      const row = document.createElement("tr");
      for (const value of [arrival.title || "—", arrival.authors.join(", "), source, arrival.detected_at, state]) {
        const cell = document.createElement("td"); cell.textContent = value; row.append(cell);
      }
      const detailsCell = document.createElement("td"); detailsCell.append(createArrivalDetails(arrival)); row.append(detailsCell); tableBody.append(row);
      continue;
    }
    const card = document.createElement("div"); card.className = "library-card";
    if (view === "grid") {
      const image = document.createElement("img"); image.className = "arrival-grid-cover"; image.loading = "lazy"; image.alt = strings().coverAlt;
      image.addEventListener("error", () => { image.removeAttribute("src"); image.alt = strings().coverUnavailable; });
      image.src = "/api/v1/admin/arrivals/" + encodeURIComponent(arrival.event_id) + "/cover"; card.append(image);
    }
    const title = document.createElement("h3"); title.textContent = arrival.title || "—"; card.append(title);
    const authors = document.createElement("p"); authors.textContent = arrival.authors.join(", "); card.append(authors);
    const sourceLine = document.createElement("p"); sourceLine.textContent = [source, arrival.detected_at].join(" · "); card.append(sourceLine);
    const stateLine = document.createElement("p"); stateLine.textContent = state; card.append(stateLine);
    card.append(createArrivalDetails(arrival)); container.append(card);
  }
}
document.querySelector("#arrivals-view").addEventListener("change", renderArrivals);
document.querySelector("#arrivals-server").addEventListener("change", () => { arrivalsOffset = 0; populateArrivalFilters(); loadArrivals().catch(() => { message.textContent = strings().failed; }); });
document.querySelector("#arrivals-library").addEventListener("change", () => { arrivalsOffset = 0; loadArrivals().catch(() => { message.textContent = strings().failed; }); });
document.querySelector("#arrivals-refresh").addEventListener("click", () => loadArrivals().catch(() => { message.textContent = strings().failed; }));
document.querySelector("#arrivals-filters").addEventListener("submit", event => { event.preventDefault(); arrivalsOffset = 0; loadArrivals().catch(() => { message.textContent = strings().failed; }); });
document.querySelector("#arrivals-previous").addEventListener("click", () => { arrivalsOffset = Math.max(0, arrivalsOffset - 50); loadArrivals().catch(() => { message.textContent = strings().failed; }); });
document.querySelector("#arrivals-next").addEventListener("click", () => { arrivalsOffset += 50; loadArrivals().catch(() => { message.textContent = strings().failed; }); });
function renderDeliveries() {
  const list = document.querySelector("#delivery-list"); list.replaceChildren();
  document.querySelector("#history-previous").disabled = deliveryOffset === 0;
  document.querySelector("#history-next").disabled = deliveries.length < 50;
  document.querySelector("#history-page").textContent = strings().page + " " + (Math.floor(deliveryOffset / 50) + 1);
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
async function loadDeliveries() {
  const request = ++deliveryRequest, params = new URLSearchParams({offset: String(deliveryOffset)});
  const status = document.querySelector("#history-status").value;
  if (status) params.set("delivery_status", status);
  const data = await call("/notifications?" + params.toString());
  if (request !== deliveryRequest) return;
  deliveries = data; renderDeliveries();
}
document.querySelector("#history-status").addEventListener("change", () => { deliveryOffset = 0; loadDeliveries().catch(() => { message.textContent = strings().failed; }); });
document.querySelector("#history-previous").addEventListener("click", () => { deliveryOffset = Math.max(0, deliveryOffset - 50); loadDeliveries().catch(() => { message.textContent = strings().failed; }); });
document.querySelector("#history-next").addEventListener("click", () => { deliveryOffset += 50; loadDeliveries().catch(() => { message.textContent = strings().failed; }); });
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
    const probeLabel = document.createElement("label"), probeLibrary = document.createElement("select"); probeLabel.textContent = " " + strings().probeLibrary + " ";
    for (const library of libraries.filter(entry => entry.server_id === server.id)) {
      const option = document.createElement("option"); option.value = String(library.id); option.textContent = library.name; probeLibrary.append(option);
    }
    probeLabel.append(probeLibrary); item.append(probeLabel);
    const probe = document.createElement("button"); probe.type = "button"; probe.textContent = strings().probeContent;
    probe.disabled = !server.enabled || !probeLibrary.options.length;
    probe.addEventListener("click", async () => {
      probe.disabled = true;
      try {
        const result = await call("/servers/" + server.id + "/libraries/" + encodeURIComponent(probeLibrary.value) + "/probe", {...mutationOptions({}), method: "POST"});
        message.textContent = result.metadata === "no_sample" ? strings().probeEmpty : result.cover === "available" ? strings().probeCoverOk : strings().probeCoverMissing;
      } catch { message.textContent = strings().probeFailed; } finally { probe.disabled = false; }
    });
    item.append(probe);
    const details = document.createElement("details"), summary = document.createElement("summary"), form = document.createElement("form");
    summary.textContent = strings().edit; details.append(summary);
    const notice = document.createElement("p"); notice.textContent = strings().sourceIdentity; form.append(notice);
    function field(labelText, type, initial) { const label = document.createElement("label"), input = document.createElement("input"); label.textContent = labelText; input.type = type; input.value = initial; label.append(input); form.append(label); return input; }
    const name = field(strings().name, "text", server.name); name.maxLength = 120; name.required = true;
    const interval = field(strings().interval, "number", String(server.scan_interval_seconds)); interval.min = "30"; interval.max = "86400"; interval.required = true;
    const publicUrl = field(strings().publicUrl, "url", server.public_url || ""); publicUrl.maxLength = 2048;
    const timeout = field(strings().connectionTimeout, "number", String(server.timeout_seconds)); timeout.min = "1"; timeout.max = "120"; timeout.required = true;
    const verifyLabel = document.createElement("label"), verify = document.createElement("input"); verify.type = "checkbox"; verify.checked = server.verify_ssl;
    verifyLabel.append(verify, document.createTextNode(" " + strings().verifySsl)); form.append(verifyLabel);
    const publicHelp = document.createElement("p"); publicHelp.textContent = strings().publicUrlHelp; form.append(publicHelp);
    const verifyHelp = document.createElement("p"); verifyHelp.textContent = strings().verifySslHelp; form.append(verifyHelp);
    const key = field(strings().replaceKey, "password", ""); key.autocomplete = "off";
    const save = document.createElement("button"); save.type = "submit"; save.textContent = strings().saveChanges; form.append(save);
    form.addEventListener("submit", async event => {
      event.preventDefault(); save.disabled = true;
      try {
        await call("/servers/" + server.id, mutationOptions({name: name.value, scan_interval_seconds: Number(interval.value), api_key: key.value || null, public_url: publicUrl.value || null, timeout_seconds: Number(timeout.value), verify_ssl: verify.checked}));
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
        originalProfiles.delete(webhook.id);
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
  document.querySelector("#template-show-cover").checked = template?.show_cover ?? true;
  document.querySelector("#series-numbered").value = template?.series_numbered_template ?? "Teil {{series_index}} von {{series}}";
  document.querySelector("#series-unnumbered").value = template?.series_unnumbered_template ?? "{{series}}";
  document.querySelector("#preview-cover").hidden = !document.querySelector("#template-show-cover").checked;
  if (template) {
    document.querySelector("#preview-title").value = template.title_template;
    document.querySelector("#preview-description").value = template.description_template;
    document.querySelector("#preview-footer").value = template.footer_template || "";
    document.querySelector("#preview-color").value = "#" + template.color.toString(16).padStart(6, "0");
    selectedMetadata = [...template.metadata_fields]; renderMetadataFields();
    queuePreview();
  } else { selectedMetadata = []; renderMetadataFields(); document.querySelector("#preview-color").value = "#2f855a"; queuePreview(); }
});
document.querySelector("#save-template").addEventListener("click", async () => {
  const selected = templates.find(item => String(item.id) === document.querySelector("#template-select").value);
  const payload = {name: document.querySelector("#template-name").value, title_template: document.querySelector("#preview-title").value, description_template: document.querySelector("#preview-description").value, footer_template: document.querySelector("#preview-footer").value || null, color: parseInt(document.querySelector("#preview-color").value.slice(1), 16), show_cover: document.querySelector("#template-show-cover").checked, metadata_fields: [...selectedMetadata], series_numbered_template: document.querySelector("#series-numbered").value, series_unnumbered_template: document.querySelector("#series-unnumbered").value};
  try {
    const result = await call(selected ? "/templates/" + selected.id : "/templates", {...mutationOptions(payload), method: selected ? "PUT" : "POST"});
    await refresh();
    document.querySelector("#template-select").value = String(selected?.id ?? result.id);
    message.textContent = strings().configuredOk;
  } catch { message.textContent = strings().failed; }
});
document.querySelector("#send-preview").addEventListener("click", async event => {
  const draft = profileDraft();
  if (!draft?.webhook_id) { message.textContent = strings().chooseWebhook; return; }
  if (!window.confirm(strings().confirmPreview)) return;
  const button = event.currentTarget; button.disabled = true;
  const preview = previewDraft();
  try {
    await call("/webhooks/" + draft.webhook_id + "/test", {...mutationOptions({library_id: draft.library_id, preview, sender_profile: draft}), method: "POST"});
    message.textContent = strings().testSent;
  } catch { message.textContent = strings().failed; } finally { button.disabled = false; }
});
language.addEventListener("change", translate);
document.querySelector("#profile-scope").addEventListener("change", () => selectScope().catch(() => { message.textContent = strings().failed; }));
document.querySelector("#profile-target").addEventListener("change", () => { populatePreviewContexts(); loadProfile().catch(() => { message.textContent = strings().failed; }); });
for (const selector of ["#preview-title", "#preview-description", "#preview-footer", "#preview-color"]) document.querySelector(selector).addEventListener("input", queuePreview);
for (const selector of ["#series-numbered", "#series-unnumbered", "#sample-series"]) document.querySelector(selector).addEventListener("input", queuePreview);
document.querySelector("#template-show-cover").addEventListener("change", event => { document.querySelector("#preview-cover").hidden = !event.target.checked; });
for (const selector of ["#username-choice", "#username-value", "#avatar-choice", "#avatar-value", "#preview-webhook", "#preview-library"]) document.querySelector(selector).addEventListener("input", updatePreviewSender);
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
    originalProfiles.clear(); counts = null; dashboard.hidden = true; authPanel.hidden = false; message.textContent = strings().passwordChanged;
  } catch { message.textContent = strings().failed; }
  finally { current.value = ""; replacement.value = ""; repeat.value = ""; button.disabled = false; }
});
document.querySelector("#refresh").addEventListener("click", async () => {
  try { await refresh(); } catch { message.textContent = strings().failed; }
});
document.querySelector("#server-form").addEventListener("submit", async event => {
  event.preventDefault();
  const name = document.querySelector("#server-name"), url = document.querySelector("#server-url"), key = document.querySelector("#server-key");
  const publicUrl = document.querySelector("#server-public-url"), interval = document.querySelector("#server-interval"), timeout = document.querySelector("#server-timeout"), verify = document.querySelector("#server-verify-ssl");
  try { await call("/servers", {...mutationOptions({name: name.value, base_url: url.value, api_key: key.value, public_url: publicUrl.value || null, scan_interval_seconds: Number(interval.value), timeout_seconds: Number(timeout.value), verify_ssl: verify.checked}), method: "POST"}); name.value = ""; url.value = ""; publicUrl.value = ""; interval.value = "60"; timeout.value = "15"; verify.checked = true; await refresh(); message.textContent = strings().configuredOk; }
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
    originalProfiles.clear(); counts = null; dashboard.hidden = true; authPanel.hidden = false; message.textContent = strings().signedOut;
  } catch { message.textContent = strings().failed; }
});
refresh().catch(() => {});
