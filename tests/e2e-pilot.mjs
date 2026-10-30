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
const handy = () => cdp("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
const desktop = () => cdp("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
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
  const [scroll, breite] = await js("[document.documentElement.scrollWidth, window.innerWidth]");
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
  await starteApp();
  await starteChrome();
  await ablaeufe();
} catch (e) {
  abbruch = true;
  console.log(`FEHLER ${e.stack || e}`);
} finally {
  aufraeumen();
}
console.log(`\n${ok} bestanden, ${probleme.length} fehlgeschlagen${abbruch ? ", Abbruch durch Ausnahme" : ""}`);
process.exit(probleme.length || abbruch ? 1 : 0);
