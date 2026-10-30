// End-to-End-Prüfung der Pilot-Version (FastAPI-App) über das Chrome DevTools Protocol.
// Nur Node-Bordmittel, keine Pakete. Aufruf: make e2e  (oder: node tests/e2e-pilot.mjs)
// Umgebung: CHROME_PFAD (Standard: Google Chrome unter /Applications).
// Screenshots landen in tests/.e2e/bilder-pilot/.
//
// Aufbau: Abschnitt «Gerüst» (Hilfsfunktionen für alle Abläufe) und Abschnitt «Abläufe».
// Spätere Issues ergänzen ihre Abläufe im Abschnitt «Abläufe» mit oeffne(), js(), klick(),
// screenshot() und pruefe().
import { spawn, spawnSync } from "node:child_process";
import { createServer } from "node:net";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { setTimeout as warte } from "node:timers/promises";

const HIER = new URL("./.e2e/", import.meta.url).pathname;
const BILDER = `${HIER}bilder-pilot/`;
const DATEN = `${HIER}daten-pilot/`;
const PROFIL = `${HIER}profil-pilot/`;
const PROJEKT = new URL("../", import.meta.url).pathname;
const PW_AUFTRAGGEBERIN = "e2e-passwort-projektleitung";
const CHROME = process.env.CHROME_PFAD || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

// ---------------------------------------------------------------- Gerüst

let app;
let chrome;
let ws;
let basis;
let nr = 0;
const offen = new Map();
const ereignisse = [];
const konsolenfehler = [];
let ok = 0;
const probleme = [];

async function freierPort() {
  const s = createServer();
  await new Promise((r) => s.listen(0, "127.0.0.1", r));
  const { port } = s.address();
  await new Promise((r) => s.close(r));
  return port;
}

// Fehler beim Starten eines Prozesses (z. B. falscher CHROME_PFAD); lässt wartende Schritte sofort scheitern.
let startFehler = null;
const CDP_ZEITLIMIT = 15000;

async function warteBis(pruefung, text, versuche = 100) {
  for (let i = 0; i < versuche; i++) {
    if (startFehler) throw startFehler;
    try {
      const wert = await pruefung();
      if (wert) return wert;
    } catch {}
    await warte(200);
  }
  throw new Error(`Zeitüberschreitung: ${text}`);
}

async function starteApp() {
  const port = await freierPort();
  app = spawn("uv", ["run", "uvicorn", "--factory", "app.main:erstelle_app", "--port", String(port)], {
    cwd: PROJEKT,
    env: { ...process.env, DATEN_VERZEICHNIS: DATEN },
    stdio: "ignore",
    detached: true, // eigene Prozessgruppe, damit auch uvicorn (Kindprozess von uv) beendet wird
  });
  app.once("error", (e) => (startFehler = new Error(`App startet nicht: ${e.message}`)));
  basis = `http://127.0.0.1:${port}`;
  await warteBis(async () => (await fetch(`${basis}/healthz`, { signal: AbortSignal.timeout(2000) })).status === 200, "App antwortet nicht auf /healthz");
}

async function starteChrome() {
  const port = await freierPort();
  chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${PROFIL}`,
      "--no-first-run",
      "--no-default-browser-check",
      "--hide-scrollbars",
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
      "about:blank",
    ],
    { stdio: "ignore" },
  );
  chrome.once("error", (e) => (startFehler = new Error(`Chrome startet nicht (${CHROME}): ${e.message}`)));
  const ziel = await warteBis(async () => {
    const liste = await (await fetch(`http://127.0.0.1:${port}/json`, { signal: AbortSignal.timeout(2000) })).json();
    return liste.find((t) => t.type === "page");
  }, "Chrome startet nicht");
  ws = new WebSocket(ziel.webSocketDebuggerUrl);
  await new Promise((r, f) => {
    ws.onopen = r;
    ws.onerror = f;
  });
  ws.onclose = () => {
    // Chrome beendet oder abgestürzt: alle wartenden Aufrufe scheitern lassen.
    for (const [, { reject }] of offen) reject(new Error("Verbindung zu Chrome geschlossen"));
    offen.clear();
  };
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && offen.has(d.id)) {
      const { resolve, reject, method } = offen.get(d.id);
      offen.delete(d.id);
      if (d.error) reject(new Error(`${method}: ${d.error.message}`));
      else resolve(d);
      return;
    }
    ereignisse.push(d.method);
    if (d.method === "Runtime.exceptionThrown") {
      konsolenfehler.push(d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text);
    } else if (d.method === "Runtime.consoleAPICalled" && d.params.type === "error") {
      konsolenfehler.push(d.params.args.map((a) => a.value ?? a.description).join(" "));
    } else if (
      d.method === "Log.entryAdded" &&
      d.params.entry.level === "error" &&
      !d.params.entry.url?.endsWith("/favicon.ico") // Chrome fragt das Icon ungefragt an; die App hat noch keines
    ) {
      // Auch Verstösse gegen die Content-Security-Policy und fehlgeschlagene Ladevorgänge landen hier.
      konsolenfehler.push(`${d.params.entry.source}: ${d.params.entry.text} ${d.params.entry.url ?? ""}`.trim());
    }
  };
  await cdp("Runtime.enable");
  await cdp("Log.enable");
  await cdp("Page.enable");
}

const cdp = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = ++nr;
    const timer = setTimeout(() => {
      offen.delete(id);
      reject(new Error(`${method}: keine Antwort von Chrome nach ${CDP_ZEITLIMIT / 1000} s`));
    }, CDP_ZEITLIMIT);
    offen.set(id, {
      method,
      resolve: (d) => (clearTimeout(timer), resolve(d)),
      reject: (e) => (clearTimeout(timer), reject(e)),
    });
    try {
      ws.send(JSON.stringify({ id, method, params }));
    } catch (e) {
      offen.delete(id);
      clearTimeout(timer);
      reject(new Error(`${method}: ${e.message}`));
    }
  });

/** Wertet JavaScript im Seitenkontext aus und gibt das Ergebnis zurück. */
async function js(ausdruck) {
  const r = await cdp("Runtime.evaluate", { expression: ausdruck, awaitPromise: true, returnByValue: true });
  if (r.result.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description);
  return r.result.result.value;
}

/** Öffnet einen Pfad der App (z. B. "/") und wartet, bis die Seite geladen ist. */
async function oeffne(pfad) {
  const vorher = ereignisse.filter((e) => e === "Page.loadEventFired").length;
  await cdp("Page.navigate", { url: `${basis}${pfad}` });
  await warteBis(() => ereignisse.filter((e) => e === "Page.loadEventFired").length > vorher, `Seite ${pfad} lädt nicht`);
  await warte(150);
}

const klick = (sel) => js(`document.querySelector(${JSON.stringify(sel)}).click()`);
const text = () => js("document.body.innerText");

async function screenshot(name) {
  await warte(150);
  const r = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  writeFileSync(`${BILDER}${name}.png`, Buffer.from(r.result.data, "base64"));
}

/** Handy-Breite (390 px) oder Desktop (1280 px). */
let sollBreite = 390; // Chrome weitet mobil das Fenster bei Überlauf aus; darum nicht gegen innerWidth prüfen
const handy = () => (sollBreite = 390, cdp("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true }));
const desktop = () => (sollBreite = 1280, cdp("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false }));
const farbschema = (wert) => cdp("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: wert }] });

/** Eine Zeile pro Prüfung: «ok …» oder «FEHLER …». */
function pruefe(bedingung, beschreibung) {
  if (bedingung) ok++;
  else probleme.push(beschreibung);
  console.log(`${bedingung ? "ok    " : "FEHLER"} ${beschreibung}`);
}

/** Wie pruefe, bricht den Ablauf aber ab: für Schritte, auf denen spätere Schritte aufbauen. */
function muss(bedingung, beschreibung) {
  pruefe(bedingung, beschreibung);
  if (!bedingung) throw new Error(`Abbruch, Voraussetzung nicht erfüllt: ${beschreibung}`);
}

/** Setzt den Wert eines Feldes und löst «input» aus. */
const tippe = (sel, wert) =>
  js(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); e.value = ${JSON.stringify(wert)}; e.dispatchEvent(new Event("input", { bubbles: true })); })()`);

/** Klickt den Absende-Knopf und wartet, bis die nächste Seite geladen ist. */
async function sende(sel) {
  const vorher = ereignisse.filter((e) => e === "Page.loadEventFired").length;
  await klick(sel);
  await warteBis(() => ereignisse.filter((e) => e === "Page.loadEventFired").length > vorher, `Seite nach Absenden von ${sel} lädt nicht`);
  await warte(150);
}

const pfad = () => js("location.pathname");
const ueberschrift = () => js("document.querySelector('h1')?.innerText");

async function keinUeberlauf(name) {
  const scroll = await js("document.documentElement.scrollWidth");
  const breite = sollBreite;
  pruefe(scroll <= breite, `kein horizontales Scrollen: ${name} (${scroll} <= ${breite})`);
}

/** Prüft, dass seit dem Aufruf von merke() keine Konsolenfehler oder CSP-Verstösse dazukamen. */
const merke = () => konsolenfehler.length;
function keineFehlerSeit(stand, name, erwartet = []) {
  // erwartet: Teile von Meldungen, die der Ablauf absichtlich auslöst (z. B. «status of 403» bei verweigertem Zugriff).
  const neu = konsolenfehler.slice(stand).filter((f) => !erwartet.some((e) => f.includes(e)));
  pruefe(neu.length === 0, `keine Konsolenfehler und CSP-Verstösse: ${name}${neu.length ? ` (${neu.join("; ")})` : ""}`);
}

/** Beendet Chrome und die App (inkl. Kindprozesse von uv). Synchron, damit es auch in Signal-Handlern geht. */
function aufraeumen() {
  try {
    ws?.close();
  } catch {}
  chrome?.kill();
  if (app?.pid) {
    try {
      process.kill(-app.pid);
    } catch {}
  }
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    aufraeumen();
    process.exit(1);
  });
}

// ---------------------------------------------------------------- Abläufe

/** Meldet ein Konto an (vorher Cookies löschen, damit keine alte Sitzung stört). */
async function meldeAn(benutzername, passwort) {
  await cdp("Network.clearBrowserCookies");
  await oeffne("/");
  await tippe("#benutzername", benutzername);
  await tippe("#passwort", passwort);
  await sende("form[action='/anmelden'] button[type=submit]");
}

/** Als Auftraggeberin angemeldet: legt einen Zugang an und gibt das Passwort von der Bestätigungsseite zurück. */
async function legeZugangAn(anzeigename, benutzername) {
  await oeffne("/verwaltung/zugaenge");
  await tippe("#anzeigename", anzeigename);
  await tippe("#benutzername", benutzername);
  await sende("form[action='/verwaltung/zugaenge'] button[type=submit]");
  muss((await text()).includes(benutzername), `Zugang ${benutzername} angelegt`);
  return js("document.querySelector('dl.zugangsdaten dd:last-of-type').innerText.trim()");
}

async function ablaufLehrperson() {
  const platzhalter = JSON.parse(readFileSync(`${PROJEKT}tests/platzhalter/inhalte.json`, "utf8"));
  const titelRunde1 = platzhalter.runden[0].titel;
  const titelRunde2 = platzhalter.runden[1].titel;
  const impuls1 = platzhalter.impulse[0].text;
  const abmelden = ".seitenkopf form[action='/abmelden'] button";
  const dialoge = () => ereignisse.filter((e) => e === "Page.javascriptDialogOpening").length;
  const dialogeVorher = dialoge();
  const SPEICHERN = "form.formular button[type=submit]";
  const meldung = async () => (await js("document.querySelector('.meldung')?.innerText")) ?? "";
  const knoepfeOk = (sel) =>
    js(`[...document.querySelectorAll(${JSON.stringify(sel)})].every((e) => { const r = e.getBoundingClientRect(); return r.height >= 43.5 && r.left >= 0 && r.right <= ${sollBreite}; })`);
  await handy();
  await farbschema("light");

  // Vorbereitung: erster Tag = heute (der Ablauf von #15 hat ihn in die Zukunft gesetzt), zwei Zugänge anlegen.
  const d = new Date();
  const heute = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  await meldeAn("projektleitung", PW_AUFTRAGGEBERIN);
  muss((await text()).includes("Abmelden"), "Lehrperson-Ablauf: Auftraggeberin angemeldet");
  await oeffne("/verwaltung/inhalte/allgemein");
  await tippe("#projektstart", heute);
  await sende(SPEICHERN);
  muss((await js("document.querySelector('#projektstart').value")) === heute, "Lehrperson-Ablauf: erster Tag auf heute gesetzt");
  const pwEins = await legeZugangAn("Erika Eins", "lp.e2e.eins");
  const pwZwei = await legeZugangAn("Zora Zwei", "lp.e2e.zwei");
  await sende(abmelden);

  // 1. Anmelden, Startseite
  let stand = merke();
  await meldeAn("lp.e2e.eins", pwEins);
  muss((await ueberschrift()) === "Hallo, Erika Eins", "Lehrperson: Startseite mit Anzeigename");
  let t = await text();
  muss(/woche 1/i.test(t), "Start: «Woche 1»"); // die Überzeile ist per CSS in Grossbuchstaben
  pruefe(t.includes("Willkommen!"), "Start: Begrüssung steht da");
  pruefe(await js("(document.querySelector('.hinweis')?.innerText.length ?? 0) > 20"), "Start: Hinweis «wer sieht was» steht da");
  pruefe(/impuls dieser woche/i.test(t) && t.includes(impuls1), "Start: Impuls dieser Woche");
  muss(t.includes(titelRunde1), "Start: Titel von Runde 1");
  pruefe(t.includes("Nächste Runde ab"), "Start: «Nächste Runde ab …»");
  pruefe(!t.includes(titelRunde2), "Start: Titel von Runde 2 steht nicht im Text");
  pruefe(await knoepfeOk("main .knopf, main a.runde, main a.karte--link, .tabs a"), "Start: Knöpfe, Runden und Leiste ganz im Bild und mindestens 44 px hoch");
  await keinUeberlauf("Lehrperson-Start 390 px");
  await screenshot("20-lp-start");
  keineFehlerSeit(stand, "Lehrperson-Start");

  // 2. Infoblock
  stand = merke();
  await sende("a.karte--link[href$='/info']");
  muss((await ueberschrift()) === "Worum es geht", "Infoblock: Titel");
  const anzahl = await js("document.querySelectorAll('details.aufklapp').length");
  pruefe(anzahl >= 2, "Infoblock: mehrere Abschnitte");
  pruefe((await js("document.querySelector('details.aufklapp:last-of-type summary').innerText")) === "Datenschutz", "Infoblock: Datenschutz ist der letzte Abschnitt");
  const zweiter = "details.aufklapp:nth-of-type(2)";
  const vorher = await js(`document.querySelector(${JSON.stringify(zweiter)}).open`);
  await klick(`${zweiter} summary`);
  pruefe((await js(`document.querySelector(${JSON.stringify(zweiter)}).open`)) === !vorher, "Infoblock: Abschnitt lässt sich aufklappen");
  await keinUeberlauf("Infoblock 390 px");
  await screenshot("23-lp-infoblock");
  await klick(`${zweiter} summary`);
  pruefe((await js(`document.querySelector(${JSON.stringify(zweiter)}).open`)) === vorher, "Infoblock: Abschnitt lässt sich wieder zuklappen");
  keineFehlerSeit(stand, "Infoblock");

  // 3. Runde 1: Fallbeispiel, kleines Speichern, unterbrochene Eingabe
  stand = merke();
  await oeffne("/lehrperson");
  await sende(`a.runde[href$='/runden/1']`);
  muss((await ueberschrift()) === titelRunde1, "Runde 1: Titel");
  const rundenPfad = await pfad();
  pruefe(!!(await js("document.querySelector('.fall')")), "Runde 1: Fallbeispiel steht da");
  pruefe(await knoepfeOk("main .knopf:not([data-entwurf-hinweis] .knopf)"), "Runde 1: Knöpfe ganz im Bild und mindestens 44 px hoch");
  await keinUeberlauf("Runde 1 390 px");
  await screenshot("24-lp-runde");
  const erstesFeld = await js("document.querySelector('textarea').id");
  const antwort1 = "Mein erster Gedanke: erst einmal nachfragen.";
  await tippe(`#${erstesFeld}`, antwort1);
  await sende(`button[name=anker][value=${erstesFeld}]`);
  pruefe((await js("location.hash")) === `#${erstesFeld}`, "Runde 1: nach dem kleinen Speichern steht die Seite bei der Frage");
  pruefe((await meldung()).includes("Gespeichert."), "Runde 1: «Gespeichert.»");
  await keinUeberlauf("Runde 1 gespeichert 390 px");
  await screenshot("25-lp-runde-gespeichert");
  await oeffne(rundenPfad);
  pruefe((await js(`document.getElementById(${JSON.stringify(erstesFeld)}).value`)) === antwort1, "Runde 1: nach neuem Laden steht der Text im Feld (unterbrochene Eingabe)");
  await cdp("Network.clearBrowserCookies");
  await oeffne("/");
  await tippe("#benutzername", "lp.e2e.eins");
  await tippe("#passwort", pwEins);
  await sende("form[action='/anmelden'] button[type=submit]");
  await oeffne(rundenPfad);
  pruefe((await js(`document.getElementById(${JSON.stringify(erstesFeld)}).value`)) === antwort1, "Runde 1: nach neuer Anmeldung steht der Text im Feld");
  // Skala wählen, unten speichern: Startseite zeigt «Angefangen»
  await klick("fieldset input[type=radio][value='4']");
  await sende("form.formular > button[type=submit]");
  await oeffne("/lehrperson");
  pruefe((await text()).includes("Angefangen"), "Start: Runde 1 «Angefangen»");
  await oeffne(rundenPfad);
  pruefe(await js("document.querySelector('fieldset input[value=\"4\"]').checked"), "Runde 1: gewählter Skalawert gespeichert");
  for (const id of await js("[...document.querySelectorAll('textarea')].map((e) => e.id)")) await tippe(`#${id}`, `Antwort zu ${id}`);
  await sende("form.formular > button[type=submit]");
  await oeffne("/lehrperson");
  pruefe((await text()).includes("Beantwortet"), "Start: Runde 1 «Beantwortet»");
  keineFehlerSeit(stand, "Runde 1");

  // 4. Runde 2 ist nicht erreichbar
  stand = merke();
  await oeffne("/lehrperson/runden/2");
  pruefe((await ueberschrift()) === "Nicht gefunden", "Runde 2 (nicht freigeschaltet): «Nicht gefunden»");
  pruefe(!(await text()).includes(titelRunde2), "Runde 2: Titel steht nicht in der Antwort");
  await keinUeberlauf("Nicht gefunden 390 px");
  await screenshot("30-lp-nicht-gefunden");
  keineFehlerSeit(stand, "Runde 2 direkt", ["status of 404"]);

  // 5. Tagebuch: frei (mit Skript und langem Wort), zum Impuls, zu einer Leitfrage
  stand = merke();
  await oeffne("/lehrperson/tagebuch/neu");
  muss((await ueberschrift()) === "Tagebuch", "Tagebuch: Wahlseite");
  pruefe(await knoepfeOk("main a.karte--link"), "Tagebuch: Auswahlkarten ganz im Bild und tippbar hoch");
  await keinUeberlauf("Tagebuch-Wahl 390 px");
  await screenshot("26-lp-tagebuch-wahl");
  await sende("a[href$='/tagebuch/neu/frei']");
  const bosTexte = `Vor ${"a".repeat(300)} nach <script>alert(1)</script> fett **bleibt**`;
  await tippe("#text", bosTexte);
  await sende(SPEICHERN);
  muss(/^\/lehrperson\/tagebuch\/\d+$/.test(await pfad()), "Tagebuch frei: nach dem Speichern auf der Seite des Eintrags");
  const freiPfad = await pfad();
  pruefe((await meldung()).includes("Gespeichert."), "Tagebuch frei: «Gespeichert.»");
  pruefe((await js("document.querySelector('#text').value")) === bosTexte, "Tagebuch frei: Skript und langes Wort stehen als Text im Feld");
  pruefe(dialoge() === dialogeVorher, "Tagebuch frei: kein Dialog durch den Skript-Text");
  await keinUeberlauf("Eintrag mit langem Wort 390 px");
  await oeffne("/lehrperson/tagebuch/neu");
  await oeffne("/lehrperson");
  await sende("section.karte--impuls a.knopf");
  muss(/\/tagebuch\/neu\/impuls\/\d+$/.test(await pfad()), "Tagebuch Impuls: Formular zum Impuls");
  pruefe((await text()).includes(impuls1), "Tagebuch Impuls: Impulstext steht über dem Feld");
  await keinUeberlauf("Eintrag zum Impuls 390 px");
  await screenshot("27-lp-eintrag-impuls");
  await tippe("#text", "Ein Moment mit der Hofaufsicht, über den ich nachdenke.");
  await sende(SPEICHERN);
  muss(/^\/lehrperson\/tagebuch\/\d+$/.test(await pfad()), "Tagebuch Impuls: gespeichert");
  await oeffne("/lehrperson/tagebuch/neu");
  await sende("a[href*='/tagebuch/neu/leitfrage/']");
  await tippe("#text", "Es ging um eine Absprache im Team.");
  await sende(SPEICHERN);
  muss(/^\/lehrperson\/tagebuch\/\d+$/.test(await pfad()), "Tagebuch Leitfrage: gespeichert");
  const leitPfad = await pfad();

  // Meine Einträge: vier Karten
  await oeffne("/lehrperson/eintraege");
  muss((await ueberschrift()) === "Meine Einträge", "Meine Einträge: Titel");
  pruefe((await js("document.querySelectorAll('a.karte--eintrag').length")) === 4, "Meine Einträge: vier Karten (Runde, Tagebuch, Impuls, Tagebuch)");
  pruefe(await js("[...document.querySelectorAll('a.karte--eintrag .marke')].some((e) => e.innerText === 'Runde')"), "Meine Einträge: Karte mit Marke «Runde»");
  pruefe(await knoepfeOk("a.karte--eintrag"), "Meine Einträge: Karten ganz im Bild");
  await keinUeberlauf("Meine Einträge 390 px");
  await screenshot("28-lp-meine-eintraege");
  // Eintrag ändern: «geändert» erscheint
  await warte(1100);
  await oeffne(leitPfad);
  await tippe("#text", "Es ging um eine Absprache im Team, die ich anders sehe.");
  await sende(SPEICHERN);
  pruefe((await text()).includes("geändert"), "Eintrag geändert: «geändert» steht auf der Seite");
  await oeffne("/lehrperson/eintraege");
  pruefe((await text()).includes("geändert"), "Meine Einträge: «geändert» an der Karte");
  await keinUeberlauf("Meine Einträge nach Änderung 390 px");
  // Löschen über die Bestätigung
  await oeffne(leitPfad);
  await sende("a[href$='/loeschen']");
  pruefe(await js("!!document.querySelector('form button.knopf')") && (await text()).includes("Endgültig löschen"), "Löschen: Bestätigung mit Knopf");
  await keinUeberlauf("Löschen-Seite 390 px");
  await screenshot("29-lp-loeschen");
  await sende("form.formular button[type=submit]");
  await oeffne("/lehrperson/eintraege");
  pruefe((await js("document.querySelectorAll('a.karte--eintrag').length")) === 3, "Meine Einträge: nach dem Löschen drei Karten");
  keineFehlerSeit(stand, "Tagebuch und Meine Einträge");

  // 6. Entwurfsschutz: tippen, ohne Speichern neu laden
  stand = merke();
  const entwurfSchluessel = () => js('Object.keys(sessionStorage).filter((k) => k.startsWith("entwurf:")).length');
  const hinweisSichtbar = () => js('(() => { const h = document.querySelector("[data-entwurf-hinweis]"); return !!h && !h.hidden && h.getBoundingClientRect().height > 0; })()');
  await oeffne(rundenPfad);
  const gespeichert = await js(`document.getElementById(${JSON.stringify(erstesFeld)}).value`);
  pruefe(!(await hinweisSichtbar()), "Entwurf: ohne Änderung kein Hinweis");
  const entwurfText = "Noch nicht gespeichert: ein Gedanke zum Fall.";
  await tippe(`#${erstesFeld}`, entwurfText);
  pruefe((await entwurfSchluessel()) === 1, "Entwurf: beim Tippen liegt ein Entwurf im Tab");
  await oeffne(rundenPfad);
  muss((await js(`document.getElementById(${JSON.stringify(erstesFeld)}).value`)) === entwurfText, "Entwurf: nach neuem Laden steht der getippte Text im Feld");
  pruefe(await hinweisSichtbar(), "Entwurf: Hinweis ist sichtbar");
  pruefe((await text()).includes("Nicht gespeicherter Text wurde wiederhergestellt."), "Entwurf: Text des Hinweises");
  pruefe(await knoepfeOk("[data-entwurf-hinweis] button"), "Entwurf: «Verwerfen» ganz im Bild und tippbar hoch");
  await keinUeberlauf("Entwurf 390 px");
  await screenshot("32-lp-entwurf");
  await klick("[data-entwurf-hinweis] button");
  pruefe((await js(`document.getElementById(${JSON.stringify(erstesFeld)}).value`)) === gespeichert, "Entwurf: «Verwerfen» setzt das Feld auf den gespeicherten Stand");
  pruefe(!(await hinweisSichtbar()), "Entwurf: nach «Verwerfen» kein Hinweis");
  pruefe((await entwurfSchluessel()) === 0, "Entwurf: nach «Verwerfen» kein Entwurf im Tab");
  await oeffne(rundenPfad);
  pruefe(!(await hinweisSichtbar()) && (await js(`document.getElementById(${JSON.stringify(erstesFeld)}).value`)) === gespeichert, "Entwurf: nach neuem Laden bleibt der gespeicherte Stand");
  // Speichern räumt den Entwurf weg
  await tippe(`#${erstesFeld}`, `${gespeichert} Ergänzung.`);
  await sende("form.formular > button[type=submit]");
  pruefe((await entwurfSchluessel()) === 0, "Entwurf: nach dem Speichern kein Entwurf im Tab");
  // Neuer Tagebucheintrag: nach dem Anlegen ist der Entwurf des Formulars «neu» weg
  await oeffne("/lehrperson/tagebuch/neu/frei");
  await tippe("#text", "Ein Eintrag, der gleich gespeichert wird.");
  pruefe((await entwurfSchluessel()) === 1, "Entwurf: neuer Eintrag legt einen Entwurf an");
  await sende(SPEICHERN);
  pruefe((await entwurfSchluessel()) === 0, "Entwurf: nach dem Anlegen kein Entwurf im Tab");
  // Ein anderer, noch nicht gespeicherter Neu-Entwurf bleibt, wenn die Seite des Eintrags neu lädt («Zurück»)
  const konto = await js('document.querySelector("form[data-entwurf]").dataset.entwurf.split(":")[0]');
  await js(`sessionStorage.setItem("entwurf:${konto}:neu-frei:text", "Ein anderer, noch offener Gedanke.")`);
  await oeffne(`${await pfad()}?erledigt=gespeichert`);
  pruefe((await entwurfSchluessel()) === 1, "Entwurf: fremder Neu-Entwurf bleibt nach erneutem Laden der Eintragsseite");
  await js('sessionStorage.clear()');
  // Abmelden räumt alles weg
  await oeffne(rundenPfad);
  await tippe(`#${erstesFeld}`, entwurfText);
  pruefe((await entwurfSchluessel()) === 1, "Entwurf: vor dem Abmelden liegt ein Entwurf im Tab");
  await sende(abmelden);
  pruefe((await entwurfSchluessel()) === 0, "Entwurf: nach «Abmelden» kein Entwurf im Tab");
  await meldeAn("lp.e2e.eins", pwEins);
  keineFehlerSeit(stand, "Entwurfsschutz");

  // Dunkel und Computer
  stand = merke();
  await farbschema("dark");
  await oeffne("/lehrperson");
  await keinUeberlauf("Lehrperson-Start 390 px dunkel");
  await screenshot("21-lp-start-dunkel");
  await oeffne(rundenPfad);
  await keinUeberlauf("Runde 1 390 px dunkel");
  await farbschema("light");
  await desktop();
  await oeffne("/lehrperson");
  await keinUeberlauf("Lehrperson-Start 1280 px");
  await screenshot("22-lp-start-desktop");
  await oeffne(rundenPfad);
  await keinUeberlauf("Runde 1 1280 px");
  await screenshot("31-lp-runde-desktop");
  await oeffne("/lehrperson/eintraege");
  await keinUeberlauf("Meine Einträge 1280 px");
  await handy();
  keineFehlerSeit(stand, "Dunkel und Computer");

  // 7. Zweite Lehrperson öffnet den Eintrag der ersten
  stand = merke();
  await sende(abmelden);
  await meldeAn("lp.e2e.zwei", pwZwei);
  muss((await ueberschrift()) === "Hallo, Zora Zwei", "Zweite Lehrperson angemeldet");
  await oeffne(freiPfad);
  pruefe((await ueberschrift()) === "Nicht gefunden", "Fremder Eintrag über die Adresse: «Nicht gefunden»");
  pruefe(!(await text()).includes("fett"), "Fremder Eintrag: kein Text der ersten Lehrperson");
  keineFehlerSeit(stand, "Fremder Eintrag", ["status of 404"]);
  stand = merke();
  await oeffne("/lehrperson/eintraege");
  pruefe((await js("document.querySelectorAll('a.karte--eintrag').length")) === 0, "Zweite Lehrperson: keine Einträge der ersten");
  await keinUeberlauf("Meine Einträge leer 390 px");
  keineFehlerSeit(stand, "Meine Einträge der zweiten");

  // 8. Auftraggeberin kann eine beantwortete Frage nicht löschen
  stand = merke();
  await sende(abmelden);
  await meldeAn("projektleitung", PW_AUFTRAGGEBERIN);
  await oeffne("/verwaltung/inhalte/runden/1");
  await sende("article[id^=frage-] a[href$='/loeschen']");
  t = await text();
  pruefe(/schon \d+-mal beantwortet/.test(t), "Verwaltung: beantwortete Frage zeigt die Erklärung «schon … beantwortet»");
  pruefe(!t.includes("Endgültig löschen") && !(await js("!!document.querySelector('form[action$=\"/loeschen\"] button')")), "Verwaltung: kein Knopf «Endgültig löschen»");
  await keinUeberlauf("Frage löschen gesperrt 390 px");
  await screenshot("29a-lp-loeschen-gesperrt");
  keineFehlerSeit(stand, "Beantwortete Frage löschen");
  pruefe(dialoge() === dialogeVorher, "Lehrperson-Ablauf: kein JavaScript-Dialog");
  await sende(abmelden);
}

async function ablaufAufnahmen() {
  // #17 füllt diese Funktion
}

async function ablaufEintraege() {
  const abmelden = ".seitenkopf form[action='/abmelden'] button";
  const NAME = "Ida Überlangernachnamebeispielperson";
  await handy();
  await farbschema("light");

  // 1. Vorbereitung: eigener Zugang mit langem Namen, mehrzeiliger freier Eintrag
  await meldeAn("projektleitung", PW_AUFTRAGGEBERIN);
  muss((await text()).includes("Abmelden"), "Einträge: Auftraggeberin angemeldet");
  const pwIda = await legeZugangAn(NAME, "lp.e2e.export");
  await sende(abmelden);
  await meldeAn("lp.e2e.export", pwIda);
  await oeffne("/lehrperson/tagebuch/neu/frei");
  await tippe("#text", "Erste Zeile\nZweite Zeile");
  await sende("form.formular button[type=submit]");
  muss(/^\/lehrperson\/tagebuch\/\d+$/.test(await pfad()), "Einträge: freier Eintrag der Testperson gespeichert");
  await sende(abmelden);
  await meldeAn("projektleitung", PW_AUFTRAGGEBERIN);

  // 2. Verwaltung: Karte und Navigation
  let stand = merke();
  await oeffne("/verwaltung");
  pruefe(await js("!!document.querySelector('a.karte[href=\"/verwaltung/eintraege\"]')"), "Einträge: Karte «Einträge» auf der Verwaltung ist ein Link");
  pruefe(await js("[...document.querySelectorAll('.verwaltungsnavigation a')].some((a) => a.innerText.trim() === 'Einträge')"), "Einträge: Navigation enthält «Einträge»");
  await keinUeberlauf("Verwaltung mit Navigation 390 px");
  keineFehlerSeit(stand, "Verwaltung mit Einträgen");

  // 3. Seite Einträge, Filter
  stand = merke();
  await sende("a.karte[href='/verwaltung/eintraege']");
  muss((await pfad()) === "/verwaltung/eintraege", "Einträge: Karte führt auf die Seite Einträge");
  const idaKarte = `[...document.querySelectorAll('a.karte--person')].find((a) => a.innerText.includes('Ida'))`;
  pruefe(await js(`!!(${idaKarte})?.innerText.includes('1 Tagebucheintrag')`), "Einträge: Karte von Ida zeigt «1 Tagebucheintrag»");
  await keinUeberlauf("Einträge 390 px");
  await screenshot("40-eintraege");
  await screenshot("44-export-karte");
  const knoepfe = await js(
    `[...document.querySelectorAll('#export a.knopf')].map((e) => { const r = e.getBoundingClientRect(); return r.height >= 43.5 && r.left >= 0 && r.right <= ${sollBreite}; })`,
  );
  pruefe(knoepfe.length === 2 && knoepfe.every(Boolean), "Einträge: beide Export-Knöpfe ganz im Bild und tippbar hoch");
  const alleKarten = await js("document.querySelectorAll('article.karte--eintrag').length");
  const idaHref = await js(`(${idaKarte}).getAttribute("href")`);
  await sende(`a.karte--person[href='${idaHref}']`);
  muss((await js("location.search")).startsWith("?lehrperson="), "Einträge: Karte von Ida filtert");
  pruefe(await js("document.querySelector('nav.chips .chip[aria-current]')?.innerText.includes('Ida')"), "Einträge: Chip von Ida ist aktiv");
  pruefe(
    await js("[...document.querySelectorAll('article.karte--eintrag')].every((a) => !a.innerText.includes('Erika') && !a.innerText.includes('Zora'))"),
    "Einträge: gefilterte Liste ohne Einträge anderer Personen",
  );
  await keinUeberlauf("Einträge gefiltert 390 px");
  await screenshot("43-eintraege-gefiltert");

  // 4. Zeilenumbruch im Eintrag
  const umbruch = await js(
    `(() => { const el = [...document.querySelectorAll('article.karte--eintrag .antwort__text')].find((e) => e.textContent.includes('Erste Zeile')); return el ? { ws: getComputedStyle(el).whiteSpace, t: el.innerText } : null; })()`,
  );
  muss(umbruch !== null, "Einträge: Eintrag von Ida steht in der Liste");
  pruefe(umbruch.ws === "pre-wrap", "Einträge: Text mit white-space pre-wrap");
  pruefe(/Erste Zeile\s*\n\s*Zweite Zeile/.test(umbruch.t), "Einträge: Zeilenumbruch bleibt sichtbar");

  // «Alle» zeigt wieder alle
  await sende("nav.chips a.chip:first-child");
  pruefe((await js("document.querySelectorAll('article.karte--eintrag').length")) >= alleKarten && !(await js("location.search")), "Einträge: «Alle» zeigt wieder alle Einträge");

  // 5. Downloads im Seitenkontext
  const dl = await js(
    `(async () => {
      const t = await fetch("/verwaltung/eintraege/tabelle.csv");
      const tb = new Uint8Array(await t.arrayBuffer());
      const z = await fetch("/verwaltung/eintraege/gesamtexport.zip");
      const zb = new Uint8Array(await z.arrayBuffer());
      return { ts: t.status, kopf: [...tb.slice(0, 3)], zs: z.status, pk: String.fromCharCode(zb[0], zb[1]) };
    })()`,
  );
  pruefe(dl.ts === 200 && dl.kopf.join() === "239,187,191", "Einträge: Tabelle 200 und beginnt mit EF BB BF");
  pruefe(dl.zs === 200 && dl.pk === "PK", "Einträge: Gesamtexport 200 und beginnt mit PK");

  // 6. Aufnahme (nur wenn eine auf der Seite steht)
  const audio = await js("document.querySelector('audio')?.src ?? null");
  if (audio) {
    const a = await js(`(async () => { const r = await fetch(${JSON.stringify(audio)}); return { s: r.status, t: r.headers.get("content-type") }; })()`);
    pruefe(a.s === 200 && a.t.startsWith("audio/"), "Einträge: Aufnahme lädt mit Typ audio/…");
  }
  keineFehlerSeit(stand, "Seite Einträge");

  // 7. Dunkel und Desktop
  await oeffne("/verwaltung/eintraege");
  await farbschema("dark");
  await keinUeberlauf("Einträge 390 px dunkel");
  await screenshot("41-eintraege-dunkel");
  await farbschema("light");
  await desktop();
  await oeffne("/verwaltung/eintraege");
  await keinUeberlauf("Einträge 1280 px");
  await screenshot("42-eintraege-desktop");
  await handy();
  await sende(abmelden);
}

async function ablaufGast() {
  const inhalt = JSON.parse(readFileSync(new URL("./platzhalter/inhalte.json", import.meta.url), "utf8"));
  const titel = inhalt.runden.map((r) => r.titel);
  const frageText = (runde, nr) => inhalt.runden[runde - 1].fragen[nr].text;
  const abmelden = ".seitenkopf form[action='/abmelden'] button";
  const dialoge = () => ereignisse.filter((e) => e === "Page.javascriptDialogOpening").length;
  const dialogeVorher = dialoge();
  const tag = (basisTag, plus) => {
    const [j, m, t] = basisTag.split("-").map(Number);
    return new Date(Date.UTC(j, m - 1, t + plus)).toISOString().slice(0, 10);
  };
  const heute = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Zurich" }).format(new Date());
  const tag3 = tag(heute, 14);
  const tag3Anzeige = tag3.split("-").reverse().join(".");
  let stand;
  let t;

  // 0. Vorbereitung: erster Tag wieder auf heute (der Ablauf von #15 hat ihn in die Zukunft gesetzt)
  await handy();
  await farbschema("light");
  stand = merke();
  await meldeAn("projektleitung", PW_AUFTRAGGEBERIN);
  muss((await text()).includes("Abmelden"), "Gast-Ablauf: Auftraggeberin angemeldet");
  await oeffne("/verwaltung/inhalte/allgemein");
  await tippe("#projektstart", heute);
  await sende("form.formular button[type=submit]");
  muss((await js("document.querySelector('#projektstart').value")) === heute, "Gast-Ablauf: erster Tag auf heute gesetzt");
  await sende(abmelden);
  await cdp("Network.clearBrowserCookies");
  keineFehlerSeit(stand, "Gast-Vorbereitung");

  // 1. Login-Seite mit Gast-Karte
  stand = merke();
  await oeffne("/");
  pruefe(await js("document.querySelector(\"a[href='/gast']\")?.offsetHeight > 0"), "Gast: Login-Seite zeigt den Link «Ansehen ohne Konto»");
  pruefe((await text()).includes("Ansehen ohne Konto"), "Gast: Login-Seite nennt «Ansehen ohne Konto»");
  await keinUeberlauf("Gast: Login-Seite 390 px");
  await screenshot("70-gast-login");
  keineFehlerSeit(stand, "Gast: Login-Seite");

  // 2. Gast-Start
  stand = merke();
  await sende("a[href='/gast']");
  muss((await pfad()) === "/gast", "Gast: Link führt auf /gast");
  t = await text();
  pruefe(t.includes("Ansicht ohne Speichern"), "Gast-Start: Band «Ansicht ohne Speichern»");
  pruefe(t.includes("Willkommen"), "Gast-Start: «Willkommen»");
  pruefe(t.includes(titel[0]), "Gast-Start: Runde 1 sichtbar");
  pruefe(t.includes("Nächste Runde ab"), "Gast-Start: «Nächste Runde ab»");
  pruefe(!t.includes(titel[1]), "Gast-Start: Runde 2 noch nicht sichtbar");
  pruefe((await js("document.querySelectorAll('.tabs a').length")) === 3, "Gast-Start: Navigation mit drei Einträgen");
  pruefe(!t.includes("Abmelden"), "Gast-Start: kein «Abmelden»");
  await keinUeberlauf("Gast-Start 390 px");
  await screenshot("73-gast-start");
  keineFehlerSeit(stand, "Gast-Start");

  // 3. Runde 1: Speichern zeigt nur eine Meldung
  stand = merke();
  await sende("a[href='/gast/runden/1']");
  muss((await ueberschrift()) === titel[0], "Gast: Runde 1 geöffnet");
  const antwort = "Gast-Test: Dieser Text wird nicht gespeichert.";
  await tippe("textarea", antwort);
  await sende("form.formular > button.knopf");
  pruefe((await text()).includes("Nicht gespeichert."), "Gast-Runde: «Nicht gespeichert.» sichtbar");
  pruefe((await js("document.querySelector('textarea').value")).includes(antwort), "Gast-Runde: Text steht noch im Feld");
  await keinUeberlauf("Gast-Runde nach Speichern 390 px");
  await screenshot("74-gast-runde-nicht-gespeichert");
  keineFehlerSeit(stand, "Gast-Runde speichern");

  // 4. Tagebuch und Info
  stand = merke();
  await sende(".tabs a[href='/gast/tagebuch/neu']");
  await sende("a[href='/gast/tagebuch/neu/frei']");
  muss((await pfad()) === "/gast/tagebuch/neu/frei", "Gast: Tagebuch «Frei schreiben» geöffnet");
  await tippe("textarea", "Gast-Test: freier Eintrag.");
  await sende("form.formular > button.knopf");
  pruefe((await text()).includes("Nicht gespeichert."), "Gast-Tagebuch: «Nicht gespeichert.» sichtbar");
  await keinUeberlauf("Gast-Tagebuch 390 px");
  await sende(".tabs a[href='/gast/info']");
  pruefe((await js("document.querySelectorAll('details').length")) >= 2, "Gast-Info: Infoblock mit Abschnitten vorhanden");
  await klick("details:not([open]) summary");
  pruefe((await js("document.querySelectorAll('details[open]').length")) >= 2, "Gast-Info: weiterer Abschnitt lässt sich öffnen");
  await keinUeberlauf("Gast-Info 390 px");
  keineFehlerSeit(stand, "Gast-Tagebuch und Info");

  // 5. Noch nicht freigeschaltete Runde: «Nicht gefunden»
  stand = merke();
  await oeffne("/gast/runden/2");
  pruefe((await ueberschrift()) === "Nicht gefunden", "Gast: Runde 2 über die Adresse ist «Nicht gefunden»");
  pruefe(!(await text()).includes(frageText(2, 0)), "Gast: Fragen von Runde 2 nicht sichtbar");
  await keinUeberlauf("Gast: Nicht gefunden 390 px");
  await screenshot("75-gast-nicht-gefunden");
  keineFehlerSeit(stand, "Gast: Nicht gefunden", ["status of 404"]);

  // 6. «Anmelden» im Kopf
  stand = merke();
  await oeffne("/gast");
  await sende("a.knopf--kopf");
  pruefe((await pfad()) === "/", "Gast: «Anmelden» im Kopf führt zur Login-Seite");
  keineFehlerSeit(stand, "Gast: Anmelden");

  // 7. Vorschau als Auftraggeberin
  stand = merke();
  await meldeAn("projektleitung", PW_AUFTRAGGEBERIN);
  await oeffne("/verwaltung");
  await keinUeberlauf("Verwaltung-Start 390 px");
  await sende("a.karte--link[href='/verwaltung/vorschau']");
  muss((await pfad()) === "/verwaltung/vorschau", "Vorschau: Karte «Vorschau» öffnet die Auswahlseite");
  pruefe(await js("!!document.querySelector('.verwaltungsnavigation')"), "Vorschau: Verwaltungsnavigation sichtbar");
  await keinUeberlauf("Vorschau-Auswahl 390 px");
  await screenshot("76-vorschau-auswahl");
  await sende(`a.karte--link[href='/verwaltung/vorschau/${tag3}']`);
  t = await text();
  pruefe(t.includes(titel[2]), "Vorschau: Titel von Runde 3 sichtbar");
  pruefe(t.includes("Woche 3") && t.includes(tag3Anzeige), "Vorschau: Band nennt «Woche 3» und das Datum");
  pruefe(t.includes("Es wird nichts gespeichert"), "Vorschau: Band «Es wird nichts gespeichert»");
  await keinUeberlauf("Vorschau Woche 3 390 px");
  await screenshot("77-vorschau-woche-3");
  await oeffne("/verwaltung/inhalte/runden/4");
  await sende("main a[href^='/verwaltung/vorschau/'][href$='/runden/4']");
  t = await text();
  pruefe(t.includes(frageText(4, 0)) && t.includes(frageText(4, 1)), "Vorschau: Fragen von Runde 4 sichtbar");
  await keinUeberlauf("Vorschau Runde 4 390 px");
  await screenshot("78-vorschau-kuenftige-runde");
  await sende("a.knopf--kopf");
  pruefe((await pfad()) === "/verwaltung/vorschau", "Vorschau: «Vorschau beenden» führt zur Auswahl");
  await sende(abmelden);
  keineFehlerSeit(stand, "Vorschau");

  // 8. Dunkel und Desktop
  stand = merke();
  await farbschema("dark");
  await oeffne("/");
  await keinUeberlauf("Login-Seite 390 px dunkel (Gast)");
  await screenshot("71-gast-login-dunkel");
  await oeffne("/gast");
  await keinUeberlauf("Gast-Start 390 px dunkel");
  await farbschema("light");
  await desktop();
  await oeffne("/");
  await keinUeberlauf("Login-Seite 1280 px (Gast)");
  await screenshot("72-gast-login-desktop");
  await oeffne("/gast");
  await keinUeberlauf("Gast-Start 1280 px");
  await meldeAn("projektleitung", PW_AUFTRAGGEBERIN);
  await oeffne("/verwaltung/vorschau");
  await keinUeberlauf("Vorschau-Auswahl 1280 px");
  await sende(abmelden);
  await handy();
  keineFehlerSeit(stand, "Gast: Dunkel und Desktop");
  pruefe(dialoge() === dialogeVorher, "Gast-Ablauf: kein JavaScript-Dialog");
}

async function ablaeufe() {
  const PW_FALSCH = "falsches-passwort";

  // 1. Login-Seite in Handy-Breite, hell und dunkel
  await handy();
  await farbschema("light");
  let stand = merke();
  await oeffne("/");
  muss((await ueberschrift()) === "Anmelden", "Login-Seite: Titel «Anmelden» sichtbar");
  pruefe(await js("document.querySelector('h1').offsetHeight > 0"), "Login-Seite: Titel hat eine sichtbare Fläche");
  pruefe(await js("!!document.querySelector('#benutzername') && !!document.querySelector('#passwort')"), "Login-Seite: Felder für Benutzername und Passwort vorhanden");
  await keinUeberlauf("Login-Seite 390 px");
  await screenshot("01-login-hell");

  await farbschema("dark");
  await screenshot("02-login-dunkel");
  await keinUeberlauf("Login-Seite 390 px dunkel");
  keineFehlerSeit(stand, "Login-Seite Handy");
  await farbschema("light");

  // Login-Seite in Desktop-Breite
  await desktop();
  stand = merke();
  await oeffne("/");
  pruefe((await ueberschrift()) === "Anmelden", "Login-Seite Desktop: Titel sichtbar");
  await keinUeberlauf("Login-Seite 1280 px");
  await screenshot("03-login-desktop");
  keineFehlerSeit(stand, "Login-Seite Desktop");

  // 2. Falsches Passwort
  await handy();
  stand = merke();
  await oeffne("/");
  await tippe("#benutzername", "projektleitung");
  await tippe("#passwort", PW_FALSCH);
  await sende("form[action='/anmelden'] button[type=submit]");
  pruefe((await text()).includes("Benutzername oder Passwort stimmt nicht."), "Falsches Passwort: Meldung sichtbar");
  pruefe((await pfad()) !== "/verwaltung", "Falsches Passwort: nicht angemeldet");
  await keinUeberlauf("Login-Fehler 390 px");
  await screenshot("04-login-fehler");
  keineFehlerSeit(stand, "Login-Fehler", ["status of 400"]); // 400 ist die Antwort auf falsche Zugangsdaten

  // 3. Auftraggeberin meldet sich an, legt einen Zugang an, sieht das Passwort, meldet sich ab
  stand = merke();
  await oeffne("/");
  await tippe("#benutzername", "projektleitung");
  await tippe("#passwort", PW_AUFTRAGGEBERIN);
  await sende("form[action='/anmelden'] button[type=submit]");
  muss((await text()).includes("Projektleitung") && (await text()).includes("Abmelden"), "Auftraggeberin ist angemeldet (Name und Abmelden im Kopf)");
  keineFehlerSeit(stand, "Anmeldung Auftraggeberin");

  stand = merke();
  await oeffne("/verwaltung");
  muss((await ueberschrift()) === "Verwaltung", "Auftraggeberin sieht die Verwaltung");
  await keinUeberlauf("Verwaltung 390 px");
  await oeffne("/verwaltung/zugaenge");
  muss((await ueberschrift()) === "Zugänge", "Auftraggeberin sieht die Zugänge");
  pruefe((await js("document.querySelector('#passwort').value.length")) >= 8, "Zugang anlegen: Passwort ist vorbelegt");
  await keinUeberlauf("Zugänge 390 px");
  await screenshot("05-zugaenge");
  await tippe("#anzeigename", "Anna Muster");
  await tippe("#benutzername", "lp.anna");
  await sende("form[action='/verwaltung/zugaenge'] button[type=submit]");
  const bestaetigung = await text();
  muss(bestaetigung.includes("lp.anna") && (await js("document.querySelector('dl.zugangsdaten dd:last-of-type')?.innerText.length > 0")), "Zugang angelegt: Benutzername und Passwort werden angezeigt");
  const pwLehrperson = await js("document.querySelector('dl.zugangsdaten dd:last-of-type').innerText.trim()");
  await keinUeberlauf("Zugang angelegt 390 px");
  await screenshot("06-zugang-angelegt");
  await oeffne("/verwaltung/zugaenge");
  pruefe((await text()).includes("Anna Muster"), "Zugänge: neuer Zugang steht in der Liste");
  keineFehlerSeit(stand, "Verwaltung");

  await sende(".seitenkopf form[action='/abmelden'] button");
  pruefe((await ueberschrift()) === "Anmelden", "Abmelden führt zur Login-Seite");
  await oeffne("/verwaltung");
  pruefe((await ueberschrift()) === "Anmelden", "Nach dem Abmelden: Verwaltung nicht mehr zugänglich");

  // 4. Lehrperson meldet sich mit dem gelesenen Passwort an, sieht ihre Startseite, hat keinen Zugriff auf die Verwaltung
  stand = merke();
  await oeffne("/");
  await tippe("#benutzername", "lp.anna");
  await tippe("#passwort", pwLehrperson);
  await sende("form[action='/anmelden'] button[type=submit]");
  muss((await ueberschrift()) === "Hallo, Anna Muster", "Lehrperson ist angemeldet: Startseite mit Anzeigename");
  await keinUeberlauf("Lehrperson-Start 390 px");
  await screenshot("07-lehrperson-start");
  await oeffne("/verwaltung");
  pruefe((await ueberschrift()) === "Kein Zugriff", "Lehrperson: /verwaltung zeigt «Kein Zugriff»");
  await keinUeberlauf("Kein Zugriff 390 px");
  await screenshot("08-kein-zugriff");
  keineFehlerSeit(stand, "Lehrperson", ["status of 403"]); // 403 ist die Antwort auf /verwaltung
  await sende(".seitenkopf form[action='/abmelden'] button");
  pruefe((await ueberschrift()) === "Anmelden", "Lehrperson: Abmelden führt zur Login-Seite");

  // ------------------------------------------------------------ Eingabemaske für Inhalte (#15)
  const INH = "/verwaltung/inhalte";
  const dialoge = () => ereignisse.filter((e) => e === "Page.javascriptDialogOpening").length;
  const dialogeVorher = dialoge();
  const SPEICHERN = "form.formular button[type=submit]";
  const sichtbar = (sel) => js(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); return !!e && e.offsetHeight > 0; })()`);
  /** Füllt Felder (Selektor → Wert) und schickt das Formular ab. */
  async function fuelle(felder) {
    for (const [sel, wert] of Object.entries(felder)) await tippe(sel, wert);
    await sende(SPEICHERN);
  }
  /** Titel der Karten (h2 oder strong) einer Liste in der Reihenfolge der Seite. */
  const kartenTexte = (sel) => js(`[...document.querySelectorAll(${JSON.stringify(sel)})].map((e) => e.innerText.trim())`);
  /** Tippflächen und Knöpfe liegen ganz im Bild und sind mindestens 44 px hoch. */
  const knoepfeOk = (sel) =>
    js(`[...document.querySelectorAll(${JSON.stringify(sel)})].every((e) => { const r = e.getBoundingClientRect(); return r.height >= 43.5 && r.left >= 0 && r.right <= ${sollBreite}; })`);

  // Auftraggeberin wieder anmelden (am Ende von Ablauf 4 abgemeldet).
  await handy();
  await farbschema("light");
  stand = merke();
  await oeffne("/");
  await tippe("#benutzername", "projektleitung");
  await tippe("#passwort", PW_AUFTRAGGEBERIN);
  await sende("form[action='/anmelden'] button[type=submit]");
  muss((await text()).includes("Abmelden"), "Inhalte: Auftraggeberin angemeldet");

  // 5. Übersicht: sechs Bereiche, Platzhalter geladen, Hinweise noch unbestätigt
  await oeffne(INH);
  muss((await ueberschrift()) === "Inhalte", "Inhalte-Übersicht: Titel «Inhalte»");
  pruefe((await js("document.querySelectorAll('a.karte--link').length")) === 6, "Inhalte-Übersicht: sechs Bereiche");
  pruefe((await text()).includes("0 von 5 Hinweisen bestätigt"), "Inhalte-Übersicht: «0 von 5 Hinweisen bestätigt»");
  pruefe((await text()).includes("Noch offen"), "Inhalte-Übersicht: Marke «Noch offen» sichtbar");
  pruefe(await knoepfeOk("a.karte--link"), "Inhalte-Übersicht: Karten ganz im Bild und tippbar hoch");
  await keinUeberlauf("Inhalte-Übersicht 390 px");
  await screenshot("10-inhalte-uebersicht");
  await farbschema("dark");
  await keinUeberlauf("Inhalte-Übersicht 390 px dunkel");
  await screenshot("11-inhalte-uebersicht-dunkel");
  await farbschema("light");
  await desktop();
  await keinUeberlauf("Inhalte-Übersicht 1280 px");
  await handy();
  keineFehlerSeit(stand, "Inhalte-Übersicht");

  // 6. Allgemein: Titel mit 60 Zeichen, Begrüssung mit Liste und fett
  stand = merke();
  await oeffne(`${INH}/allgemein`);
  const langerTitel = "Reflexionsinstrument ".repeat(3).slice(0, 60);
  await fuelle({
    "#titel": langerTitel,
    "#begruessung": "Willkommen!\r\n\r\n- erster Punkt\r\n- zweiter Punkt\r\n\r\nDas ist **wichtig**.",
    "#projektstart": "2030-01-14",
  });
  muss((await pfad()) === `${INH}/allgemein`, "Allgemein: nach dem Speichern wieder auf der Seite");
  pruefe((await js("document.querySelector('.seitenkopf__titel').innerText")) === langerTitel, "Allgemein: Titel mit 60 Zeichen steht im Kopf");
  pruefe(
    await js(`(() => { const t = document.querySelector('.seitenkopf__titel'); return t.scrollWidth <= t.clientWidth + 1 && t.getBoundingClientRect().right <= ${sollBreite}; })()`),
    "Allgemein: Titel mit 60 Zeichen bricht im Kopf um, ragt nicht heraus",
  );
  pruefe(await js("document.querySelectorAll('#begruessung-anzeige ul li').length === 2 && !!document.querySelector('#begruessung-anzeige strong')"), "Allgemein: Begrüssung zeigt Liste und fett");
  await keinUeberlauf("Allgemein 390 px");
  // Härtefall: 60 Zeichen ohne Leerzeichen
  await fuelle({ "#titel": "W".repeat(60) });
  await keinUeberlauf("Allgemein, Titel aus 60 Zeichen ohne Leerzeichen, 390 px");
  pruefe(
    await js(`(() => { const t = document.querySelector('.seitenkopf__titel'); return t.scrollWidth <= t.clientWidth + 1 && t.getBoundingClientRect().right <= ${sollBreite}; })()`),
    "Allgemein: Titel ohne Leerzeichen bricht um, Text ragt nicht aus dem Kopf",
  );
  await screenshot("12a-allgemein-langer-titel");
  await fuelle({ "#titel": "Reflexionsinstrument" });
  keineFehlerSeit(stand, "Allgemein");

  // 7. Infoblock: Skript-Text, langes Wort, aus Word eingefügt, Nach oben
  stand = merke();
  await oeffne(INH + "/info");
  muss((await ueberschrift()) === "Infoblock", "Infoblock: Titel");
  await sende("a[href='/verwaltung/inhalte/info/neu']");
  await fuelle({ "#titel": "Skript-Test", "#inhalt": "<script>alert(1)</script> bleibt Text" });
  pruefe((await text()).includes("<script>alert(1)</script> bleibt Text"), "Infoblock: Skript steht als sichtbarer Text");
  await sende("a[href='/verwaltung/inhalte/info/neu']");
  await fuelle({ "#titel": "Langes Wort", "#inhalt": `Vor ${"a".repeat(300)} nach` });
  await keinUeberlauf("Infoblock mit 300 Zeichen langem Wort 390 px");
  await sende("a[href='/verwaltung/inhalte/info/neu']");
  await fuelle({ "#titel": "Aus Word", "#inhalt": "Einleitung\r\n\r\n  •\tErster Punkt\r\n•\tZweiter Punkt\r\n•\tDritter Punkt" });
  pruefe(
    await js("(() => { const a = [...document.querySelectorAll('article')].find((x) => x.querySelector('h2')?.innerText === 'Aus Word'); return !!a && a.querySelectorAll('ul li').length === 3; })()"),
    "Infoblock: aus Word eingefügte Zeilen erscheinen als Liste mit drei Punkten",
  );
  await keinUeberlauf("Infoblock mit Word-Text 390 px");
  await screenshot("12-infoblock");
  const titelVorher = await kartenTexte("article h2");
  const wordId = await js("[...document.querySelectorAll('article')].find((x) => x.querySelector('h2')?.innerText === 'Aus Word').id");
  await sende(`#${wordId} form[action$='/verschieben'] button[aria-label*='nach oben']`);
  pruefe((await js("location.hash")) === `#${wordId}`, "Infoblock: Nach oben springt zum verschobenen Abschnitt (Anker)");
  pruefe(await js(`document.getElementById(${JSON.stringify(wordId)}).getBoundingClientRect().top < innerHeight`), "Infoblock: verschobener Abschnitt liegt im sichtbaren Bereich");
  const titelNachher = await kartenTexte("article h2");
  const iw = titelVorher.indexOf("Aus Word");
  pruefe(titelNachher.indexOf("Aus Word") === iw - 1 && titelNachher.indexOf("Langes Wort") === titelVorher.indexOf("Langes Wort") + 1, "Infoblock: Reihenfolge der Titel ist getauscht");
  await keinUeberlauf("Infoblock nach Verschieben 390 px");
  pruefe(dialoge() === dialogeVorher, "Infoblock: kein Dialog durch den Skript-Text");
  keineFehlerSeit(stand, "Infoblock");

  // 8. Runde ohne Fallbeispiel, Fragen (Text, Skala mit Fehler), umsortieren
  stand = merke();
  await oeffne(INH + "/runden");
  await sende("a[href='/verwaltung/inhalte/runden/neu']");
  await keinUeberlauf("Formular Runde 390 px");
  await fuelle({ "#titel": "E2E-Runde", "#freischaltdatum": "2030-01-14" });
  muss(/^\/verwaltung\/inhalte\/runden\/\d+$/.test(await pfad()), "Runde: nach dem Anlegen auf der Seite der Runde");
  pruefe((await text()).includes("Kein Fallbeispiel."), "Runde: ohne Fallbeispiel angelegt");
  pruefe((await text()).includes("Diese Runde hat noch keine Fragen."), "Runde: noch ohne Fragen");
  const langeFrage = "Woran hast du in dieser Woche gemerkt, dass sich dein Blick auf die Situation in der Klasse verändert hat, und was hat dich dazu gebracht, anders zu reagieren als sonst? Beschreibe bitte, was du konkret getan hast und wie die Klasse darauf reagiert hat.";
  await sende("a[href$='/fragen/neu']");
  await fuelle({ "#text": langeFrage });
  pruefe((await js("document.querySelectorAll('article[id^=frage-]').length")) === 1, "Runde: erste Frage (Text) steht in der Liste");
  // Skala ohne Beschriftung: Fehler am Feld
  stand = merke();
  await sende("a[href$='/fragen/neu']");
  await klick("input[name=typ][value=skala]");
  await tippe("#text", "Wie sicher fühlst du dich im Umgang mit schwierigen Gesprächen mit Eltern oder Kollegen?");
  await sende(SPEICHERN);
  pruefe(await sichtbar(".fehler[id^=fehler-skala]"), "Frage Skala ohne Beschriftung: Fehlertext am Feld sichtbar");
  pruefe(await sichtbar("p.hinweis.fehler"), "Frage Skala ohne Beschriftung: Hinweis über dem Formular");
  const markiert = await js(`(() => {
    const rot = getComputedStyle(document.querySelector(".fehler[id^=fehler-skala]")).color;
    const felder = [...document.querySelectorAll("[aria-invalid=true]")];
    return felder.length > 0 && felder.every((f) => getComputedStyle(f).borderColor === rot);
  })()`);
  pruefe(markiert === true, "Frage Skala ohne Beschriftung: Feld rot markiert (aria-invalid)");
  await keinUeberlauf("Frage mit Fehler 390 px");
  await screenshot("14-frage-fehler");
  keineFehlerSeit(stand, "Frage mit Fehler", ["status of 400"]);
  stand = merke();
  await fuelle({ "#skala_min_text": "gar nicht sicher", "#skala_max_text": "sehr sicher" });
  pruefe((await js("document.querySelectorAll('article[id^=frage-]').length")) === 2, "Frage Skala mit Beschriftung gespeichert");
  await sende("a[href$='/fragen/neu']");
  await fuelle({ "#text": "Was nimmst du dir für die nächste Woche vor?" });
  muss((await js("document.querySelectorAll('article[id^=frage-]').length")) === 3, "Runde: drei Fragen");
  // mittlere Frage hat zwei Verschiebe-Knöpfe
  pruefe((await js("document.querySelectorAll('article[id^=frage-]')[1].querySelectorAll('.verschieben button').length")) === 2, "Runde: mittlere Frage hat zwei Verschiebe-Knöpfe");
  pruefe(await knoepfeOk("main .verschieben button, main .aktionen a, main .knopf"), "Runde: Knöpfe ganz im Bild und mindestens 44 px hoch");
  await keinUeberlauf("Seite einer Runde 390 px");
  await screenshot("13-runde");
  const frageVorher = await kartenTexte("article[id^=frage-] strong");
  await sende("article[id^=frage-]:nth-of-type(1) form[action$='/verschieben'] button[aria-label*='nach unten']");
  const frageNachher = await kartenTexte("article[id^=frage-] strong");
  pruefe(frageNachher[1] === frageVorher[0] && frageNachher[0] === frageVorher[1], "Runde: Fragen umsortiert");
  await keinUeberlauf("Runde nach Umsortieren 390 px");
  keineFehlerSeit(stand, "Runde und Fragen");
  const rundenPfad = await pfad();
  await desktop();
  await oeffne(rundenPfad);
  await keinUeberlauf("Seite einer Runde 1280 px");
  await screenshot("17-runde-desktop");
  await oeffne(rundenPfad + "/fragen/neu");
  await keinUeberlauf("Formular Frage 1280 px");
  await screenshot("17a-frage-formular-desktop");
  await handy();

  // 9. Leitfrage und Impuls, Impuls über die Bestätigungsseite löschen
  stand = merke();
  await oeffne(INH + "/leitfragen");
  await sende("a[href='/verwaltung/inhalte/leitfragen/neu']");
  await fuelle({ "#text": "Was hat mich heute beschäftigt?" });
  pruefe((await text()).includes("Was hat mich heute beschäftigt?"), "Leitfrage angelegt");
  await keinUeberlauf("Leitfragen 390 px");
  await oeffne(INH + "/impulse");
  await sende("a[href='/verwaltung/inhalte/impulse/neu']");
  await fuelle({ "#text": "E2E-Impuls zum Löschen", "#sichtbar_ab": "2030-01-20" });
  muss((await text()).includes("E2E-Impuls zum Löschen"), "Impuls angelegt");
  await keinUeberlauf("Impulse 390 px");
  const impulsId = await js("[...document.querySelectorAll('article[id^=impuls-]')].find((x) => x.innerText.includes('E2E-Impuls zum Löschen')).id");
  await sende(`#${impulsId} a[href$='/loeschen']`);
  pruefe((await ueberschrift()).length > 0 && (await sichtbar("form[action$='/loeschen'] button")), "Impuls löschen: Bestätigungsseite mit Knopf");
  await keinUeberlauf("Löschen-Seite 390 px");
  await screenshot("16-loeschen");
  await sende("form[action$='/loeschen'] button[type=submit]");
  pruefe(!(await text()).includes("E2E-Impuls zum Löschen"), "Impuls nach Bestätigung gelöscht");
  keineFehlerSeit(stand, "Leitfrage und Impuls");

  // 10. Hinweise: Vorschlag unverändert speichern
  stand = merke();
  await oeffne(INH + "/hinweise");
  muss((await js("document.querySelectorAll('article[id^=hinweis-]').length")) === 5, "Hinweise: fünf Texte");
  await sende("#hinweis-hinweis_datenspeicherung a[href$='/hinweis_datenspeicherung']");
  pruefe((await text()).includes("Bestätigen und speichern"), "Hinweis: Knopf «Bestätigen und speichern» bei Vorschlag");
  await sende(SPEICHERN);
  pruefe(await js("!!document.querySelector('#hinweis-hinweis_datenspeicherung .marke--erledigt')"), "Hinweise: Text als «Bestätigt» markiert");
  await keinUeberlauf("Hinweise 390 px");
  await screenshot("15-hinweise");
  await oeffne(INH);
  pruefe((await text()).includes("1 von 5 Hinweisen bestätigt"), "Inhalte-Übersicht: «1 von 5 Hinweisen bestätigt»");
  keineFehlerSeit(stand, "Hinweise");

  // 11. Lehrperson hat keinen Zugriff auf die Inhalte
  stand = merke();
  await sende(".seitenkopf form[action='/abmelden'] button");
  await oeffne("/");
  await tippe("#benutzername", "lp.anna");
  await tippe("#passwort", pwLehrperson);
  await sende("form[action='/anmelden'] button[type=submit]");
  await oeffne(INH);
  pruefe((await ueberschrift()) === "Kein Zugriff", "Inhalte: Lehrperson sieht «Kein Zugriff»");
  await oeffne(INH + "/info/neu");
  pruefe((await ueberschrift()) === "Kein Zugriff", "Inhalte: Lehrperson kann keinen Abschnitt anlegen");
  keineFehlerSeit(stand, "Lehrperson und Inhalte", ["status of 403"]);
  pruefe(dialoge() === dialogeVorher, "Inhalte: kein JavaScript-Dialog im ganzen Ablauf");
}

// ---------------------------------------------------------------- Ablauf des Skripts

let abbruch = false;
try {
  rmSync(HIER + "daten-pilot", { recursive: true, force: true });
  rmSync(HIER + "profil-pilot", { recursive: true, force: true });
  rmSync(BILDER, { recursive: true, force: true });
  mkdirSync(BILDER, { recursive: true });
  mkdirSync(DATEN, { recursive: true });
  // Konto der Auftraggeberin wie im Betrieb per Kommando anlegen (Passwort über stdin).
  const anlegen = spawnSync(
    "uv",
    ["run", "python", "-m", "app.kommandos", "auftraggeberin-anlegen", "--benutzername", "projektleitung", "--anzeigename", "Projektleitung"],
    { cwd: PROJEKT, env: { ...process.env, DATEN_VERZEICHNIS: DATEN }, input: `${PW_AUFTRAGGEBERIN}\n`, encoding: "utf8" },
  );
  if (anlegen.status !== 0) throw new Error(`Konto der Auftraggeberin nicht angelegt (Exit ${anlegen.status}): ${anlegen.stdout}${anlegen.stderr}`);
  // Erfundene Platzhalter-Inhalte wie im Betrieb per Kommando laden.
  const platzhalter = spawnSync("uv", ["run", "python", "-m", "app.kommandos", "platzhalter-laden"], {
    cwd: PROJEKT,
    env: { ...process.env, DATEN_VERZEICHNIS: DATEN },
    encoding: "utf8",
  });
  if (platzhalter.status !== 0) throw new Error(`Platzhalter nicht geladen (Exit ${platzhalter.status}): ${platzhalter.stdout}${platzhalter.stderr}`);
  await starteApp();
  await starteChrome();
  await ablaeufe();
  await ablaufLehrperson();
  await ablaufAufnahmen();
  await ablaufEintraege();
  await ablaufGast();
} catch (e) {
  abbruch = true;
  console.log(`FEHLER ${e.stack || e}`);
} finally {
  aufraeumen();
}
console.log(`\n${ok} bestanden, ${probleme.length} fehlgeschlagen${abbruch ? ", Abbruch durch Ausnahme" : ""}`);
process.exit(probleme.length || abbruch ? 1 : 0);
