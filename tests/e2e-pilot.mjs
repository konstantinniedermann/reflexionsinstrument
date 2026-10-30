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
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
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

async function ablaufLehrperson() {
  // #16 füllt diese Funktion
}

async function ablaufAufnahmen() {
  // #17 füllt diese Funktion
}

async function ablaufEintraege() {
  // #18 füllt diese Funktion
}

async function ablaufGast() {
  // #19 füllt diese Funktion
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
