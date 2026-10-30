// End-to-End-Prüfung der Pilot-Version (FastAPI-App) über das Chrome DevTools Protocol.
// Nur Node-Bordmittel, keine Pakete. Aufruf: make e2e  (oder: node tests/e2e-pilot.mjs)
// Umgebung: CHROME_PFAD (Standard: Google Chrome unter /Applications).
// Screenshots landen in tests/.e2e/bilder-pilot/.
//
// Aufbau: Abschnitt «Gerüst» (Hilfsfunktionen für alle Abläufe) und Abschnitt «Abläufe».
// Spätere Issues ergänzen ihre Abläufe im Abschnitt «Abläufe» mit oeffne(), js(), klick(),
// screenshot() und pruefe().
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { setTimeout as warte } from "node:timers/promises";

const HIER = new URL("./.e2e/", import.meta.url).pathname;
const BILDER = `${HIER}bilder-pilot/`;
const DATEN = `${HIER}daten-pilot/`;
const PROFIL = `${HIER}profil-pilot/`;
const PROJEKT = new URL("../", import.meta.url).pathname;
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

async function warteBis(pruefung, text, versuche = 100) {
  for (let i = 0; i < versuche; i++) {
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
  basis = `http://127.0.0.1:${port}`;
  await warteBis(async () => (await fetch(`${basis}/healthz`)).status === 200, "App antwortet nicht auf /healthz");
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
  const ziel = await warteBis(async () => {
    const liste = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
    return liste.find((t) => t.type === "page");
  }, "Chrome startet nicht");
  ws = new WebSocket(ziel.webSocketDebuggerUrl);
  await new Promise((r, f) => {
    ws.onopen = r;
    ws.onerror = f;
  });
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && offen.has(d.id)) {
      offen.get(d.id)(d);
      offen.delete(d.id);
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
  new Promise((r) => {
    const id = ++nr;
    offen.set(id, r);
    ws.send(JSON.stringify({ id, method, params }));
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

async function keinUeberlauf(name) {
  const [scroll, breite] = await js("[document.documentElement.scrollWidth, window.innerWidth]");
  pruefe(scroll <= breite, `kein horizontales Scrollen: ${name} (${scroll} <= ${breite})`);
}

/** Prüft, dass seit dem Aufruf von merke() keine Konsolenfehler oder CSP-Verstösse dazukamen. */
const merke = () => konsolenfehler.length;
function keineFehlerSeit(stand, name) {
  const neu = konsolenfehler.slice(stand);
  pruefe(neu.length === 0, `keine Konsolenfehler und CSP-Verstösse: ${name}${neu.length ? ` (${neu.join("; ")})` : ""}`);
}

async function aufraeumen() {
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

// ---------------------------------------------------------------- Abläufe

async function ablaeufe() {
  // Startseite in Handy-Breite, hell und dunkel
  await handy();
  await farbschema("light");
  let stand = merke();
  await oeffne("/");
  pruefe((await js("document.querySelector('h1')?.innerText")) === "Reflexionsinstrument", "Startseite: Titel «Reflexionsinstrument» sichtbar");
  pruefe(await js("document.querySelector('h1').offsetHeight > 0"), "Startseite: Titel hat eine sichtbare Fläche");
  await keinUeberlauf("Startseite 390 px");
  await screenshot("01-start-hell");

  await farbschema("dark");
  await screenshot("02-start-dunkel");
  await keinUeberlauf("Startseite 390 px dunkel");
  keineFehlerSeit(stand, "Startseite Handy");
  await farbschema("light");

  // Startseite in Desktop-Breite
  await desktop();
  stand = merke();
  await oeffne("/");
  pruefe((await text()).includes("Reflexionsinstrument"), "Startseite Desktop: Titel sichtbar");
  await screenshot("03-start-desktop");
  keineFehlerSeit(stand, "Startseite Desktop");
}

// ---------------------------------------------------------------- Ablauf des Skripts

let abbruch = false;
try {
  rmSync(HIER + "daten-pilot", { recursive: true, force: true });
  rmSync(HIER + "profil-pilot", { recursive: true, force: true });
  rmSync(BILDER, { recursive: true, force: true });
  mkdirSync(BILDER, { recursive: true });
  mkdirSync(DATEN, { recursive: true });
  await starteApp();
  await starteChrome();
  await ablaeufe();
} catch (e) {
  abbruch = true;
  console.log(`FEHLER ${e.stack || e}`);
} finally {
  await aufraeumen();
}
console.log(`\n${ok} bestanden, ${probleme.length} fehlgeschlagen${abbruch ? ", Abbruch durch Ausnahme" : ""}`);
process.exit(probleme.length || abbruch ? 1 : 0);
