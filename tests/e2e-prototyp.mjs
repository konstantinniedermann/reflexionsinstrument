// End-to-End-Prüfung des Prototyps über das Chrome DevTools Protocol (nur Node-Bordmittel).
// Aufruf: node tests/e2e-prototyp.mjs  (braucht Google Chrome unter /Applications)
// Screenshots landen in tests/.e2e/bilder/.
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFileSync, writeFileSync, mkdirSync, rmSync, existsSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { setTimeout as warte } from "node:timers/promises";

const WURZEL = new URL("../prototyp/", import.meta.url).pathname;
const AUS = new URL("./.e2e/bilder/", import.meta.url).pathname;
const PROFIL = new URL("./.e2e/profil/", import.meta.url).pathname;

// Kleiner statischer Server für den Prototyp-Ordner.
const TYPEN = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript" };
const server = createServer((req, res) => {
  const pfad = normalize(decodeURIComponent(new URL(req.url, "http://x").pathname)).replace(/^([/\\])+/, "");
  const datei = join(WURZEL, pfad || "index.html");
  if (!datei.startsWith(WURZEL) || !existsSync(datei)) {
    res.writeHead(404).end();
    return;
  }
  res.writeHead(200, { "content-type": `${TYPEN[extname(datei)] || "application/octet-stream"}; charset=utf-8` });
  res.end(readFileSync(datei));
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASIS = `http://127.0.0.1:${server.address().port}/`;
rmSync(AUS, { recursive: true, force: true });
mkdirSync(AUS, { recursive: true });
rmSync(PROFIL, { recursive: true, force: true });

const chrome = spawn(
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  [
    "--headless=new",
    "--remote-debugging-port=9333",
    `--user-data-dir=${PROFIL}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--hide-scrollbars",
    "about:blank",
  ],
  { stdio: "ignore" },
);

let ziel;
for (let i = 0; i < 50 && !ziel; i++) {
  await warte(200);
  try {
    const liste = await (await fetch("http://127.0.0.1:9333/json")).json();
    ziel = liste.find((t) => t.type === "page");
  } catch {}
}
const ws = new WebSocket(ziel.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let nr = 0;
const offen = new Map();
const fehler = [];
ws.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.id && offen.has(d.id)) {
    offen.get(d.id)(d);
    offen.delete(d.id);
  } else if (d.method === "Runtime.exceptionThrown") {
    fehler.push(d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text);
  } else if (d.method === "Runtime.consoleAPICalled" && d.params.type === "error") {
    fehler.push(d.params.args.map((a) => a.value).join(" "));
  }
};
const cdp = (method, params = {}) =>
  new Promise((r) => {
    const id = ++nr;
    offen.set(id, r);
    ws.send(JSON.stringify({ id, method, params }));
  });

async function js(ausdruck) {
  const r = await cdp("Runtime.evaluate", { expression: ausdruck, awaitPromise: true, returnByValue: true });
  if (r.result.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description);
  return r.result.result.value;
}

async function bild(name) {
  await warte(150);
  const r = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
  writeFileSync(`${AUS}${name}.png`, Buffer.from(r.result.data, "base64"));
}

async function gehe(hash) {
  await js(`location.hash = ${JSON.stringify(hash)}`);
  await warte(120);
}

const klick = (sel) => js(`document.querySelector(${JSON.stringify(sel)}).click()`);
const text = () => js(`document.getElementById('app').textContent`);

let ok = 0;
const probleme = [];
function pruefe(bedingung, name) {
  if (bedingung) ok++;
  else probleme.push(name);
  console.log(`${bedingung ? "✔" : "✖"} ${name}`);
}
async function keinUeberlauf(name) {
  const w = await js(`[document.documentElement.scrollWidth, document.documentElement.clientWidth]`);
  pruefe(w[0] <= w[1], `kein horizontales Scrollen: ${name} (${w[0]} ≤ ${w[1]})`);
}

await cdp("Runtime.enable");
await cdp("Page.enable");
await cdp("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });

// --- Start, Rollenwahl ---
await cdp("Page.navigate", { url: BASIS });
await warte(600);
await js(`localStorage.clear(); location.hash = ''; location.reload()`);
await warte(600);
pruefe((await text()).includes("Als Lehrperson ansehen"), "Rollenwahl erscheint beim ersten Besuch");
await keinUeberlauf("Rollenwahl");
await bild("01-wahl");

await klick('[data-rolle-lp="lp1"]');
await warte(150);
pruefe((await js("location.hash")) === "#/start", "Lehrperson 1 landet auf der Startseite");
const status = await js(`[...document.querySelectorAll('.runden li')].map(li => li.innerText.replace(/\\s+/g,' '))`);
pruefe(status[0].includes("jetzt ausfüllen") && status[1].includes("ab Woche 2") && status[2].includes("ab Woche 4"), `Woche 1: nur Runde 1 offen (${status.join(" | ")})`);
pruefe(!(await js(`document.getElementById('tabs').hidden`)), "Tab-Leiste sichtbar für Lehrperson");
await keinUeberlauf("Start");
await bild("02-start");

// --- Gesperrte Runde direkt aufrufen ---
await gehe("#/runde/ende");
pruefe((await text()).includes("ab Woche 4 offen"), "Gesperrte Runde lässt sich nicht ausfüllen");

// --- Runde 1 ---
await gehe("#/runde/anfang");
pruefe((await js(`document.querySelectorAll('.liste-ohne a').length`)) === 3, "Runde 1 bietet drei Fallbeispiele");
await bild("03-fallwahl");
await gehe("#/runde/anfang/gibtsnicht");
pruefe((await text()).includes("Nicht gefunden"), "Unbekanntes Fallbeispiel → Nicht gefunden");
await gehe("#/runde/anfang/hausaufgaben");
pruefe((await text()).includes("Die Hausaufgaben"), "Fallbeispiel wird angezeigt");
await klick('form button[type=submit]');
pruefe(!(await js(`document.querySelector('.fehler').hidden`)), "Leeres Formular zeigt Fehlermeldung");
await keinUeberlauf("Runde 1 Formular");
await bild("04-runde1");
await js(`document.querySelector('textarea[name=f_erster_gedanke]').value = 'Mein erster Gedanke\\nmit zweiter Zeile'`);
await js(`document.querySelector('input[name=f_vertraut][value="4"]').click()`);
await klick('form button[type=submit]');
await warte(150);
pruefe((await js("location.hash")) === "#/danke/runde", "Speichern führt zur Danke-Seite");
const gespeichert = await js(`JSON.parse(localStorage.getItem('reflexionsheft-prototyp-v1')).eintraege.filter(e => e.personId === 'lp1')`);
pruefe(gespeichert.length === 1 && gespeichert[0].antworten.vertraut === 4 && gespeichert[0].fallId === "hausaufgaben", "Eintrag ist mit Skala und Fallbeispiel gespeichert");
await gehe("#/start");
pruefe((await js(`document.querySelector('.runden li').innerText`)).includes("erledigt"), "Runde 1 ist danach erledigt");
await gehe("#/runde/anfang");
pruefe((await js("location.hash")).startsWith("#/eintrag/"), "Erledigte Runde öffnet den gespeicherten Eintrag");

// --- Notiz mit Impuls, inkl. XSS-Versuch ---
await gehe("#/start");
await klick(".karte--impuls a");
await warte(120);
pruefe((await js("location.hash")) === "#/notiz?impuls=moment", "Impuls öffnet Notiz mit Bezug");
pruefe((await text()).includes("keine Namen"), "Notiz zeigt Hinweis «keine Namen»");
await bild("05-notiz");
await js(`document.querySelector('textarea[name=f_frei]').value = '<img src=x onerror="window.__xss=1"> Beobachtung'`);
await klick('form button[type=submit]');
await warte(150);
await gehe("#/eintraege");
await warte(300);
pruefe((await js("window.__xss")) === undefined, "Eingegebenes HTML wird nicht ausgeführt (XSS)");
pruefe((await text()).includes("<img src=x"), "Eingegebenes HTML erscheint als Text");
const eigene = await js(`document.querySelectorAll('.karte--eintrag').length`);
pruefe(eigene === 2, `Meine Einträge zeigt nur die 2 eigenen (${eigene})`);
await keinUeberlauf("Meine Einträge");
await bild("06-eintraege");

// --- Datenschutz: fremden Eintrag direkt aufrufen ---
await gehe("#/eintrag/demo-1");
pruefe((await text()).includes("Nicht gefunden"), "Fremder Eintrag ist für Lehrperson 1 nicht sichtbar");
await gehe("#/admin");
pruefe((await js("location.hash")) === "#/wahl", "Lehrperson kommt nicht in die Übersicht der Projektleiterin");
await js(`document.querySelector('[data-rolle-lp="lp1"]').click()`);
await warte(120);

// --- Infoblock ---
await gehe("#/info");
pruefe((await js(`document.querySelectorAll('details.aufklapp').length`)) === 5, "Infoblock hat fünf Abschnitte");
await bild("07-info");

// --- Woche 4: Rückblick ---
await js(`document.querySelector('#steuerung-wochen [data-woche="4"]').click()`);
await gehe("#/start");
const status4 = await js(`[...document.querySelectorAll('.runden li')].map(li => li.innerText.replace(/\\s+/g,' '))`);
pruefe(status4[1].includes("jetzt ausfüllen") && status4[2].includes("jetzt ausfüllen"), "Woche 4: Runden 2 und 3 offen");
pruefe((await js(`document.querySelector('.impuls__text').innerText`)).includes("nicht so schnell vergessen"), "Woche 4 zeigt den Impuls der Woche 4");
await gehe("#/runde/ende");
const rb = await text();
pruefe(rb.includes("Deine Antworten aus Runde 1") && rb.includes("Mein erster Gedanke"), "Runde 3 zeigt die eigenen Antworten aus Runde 1");
await bild("08-runde3");
await gehe("#/runde/mitte");
pruefe((await text()).includes("Die Rückmeldung"), "Runde 2 zeigt das gemeinsame Fallbeispiel");

// --- Hinweise ausschalten ---
const sichtbareHinweise = () => js(`[...document.querySelectorAll('.besprechen')].filter(b => b.offsetParent !== null).length`);
pruefe((await sichtbareHinweise()) === 1, "Hinweis «Zum Besprechen» sichtbar");
await js(`document.querySelector('textarea').value = 'angefangen'`);
await js(`{ const c = document.getElementById('steuerung-hinweise'); c.checked = false; c.dispatchEvent(new Event('change')) }`);
pruefe((await sichtbareHinweise()) === 0, "Hinweise lassen sich ausblenden");
await js(`document.querySelector('#steuerung-wochen [data-woche="3"]').click()`);
pruefe((await js(`document.querySelector('textarea').value`)) === "angefangen", "Getipptes bleibt beim Umschalten von Hinweisen und Woche erhalten");
await js(`document.querySelector('#steuerung-wochen [data-woche="4"]').click()`);
await gehe("#/runde/mitte/gibtsnicht");
pruefe((await text()).includes("Nicht gefunden"), "Runde ohne Auswahl lehnt Fall-ID in der URL ab");
await gehe("#/runde/mitte");
await js(`{ const c = document.getElementById('steuerung-hinweise'); c.checked = true; c.dispatchEvent(new Event('change')) }`);

// --- Projektleiterin ---
await js(`document.getElementById('steuerung-wechseln').click()`);
await warte(120);
await klick("[data-rolle-admin]");
await warte(150);
pruefe((await js("location.hash")) === "#/admin", "Projektleiterin landet in der Übersicht");
pruefe(await js(`document.getElementById('tabs').hidden`), "Keine Tab-Leiste für Projektleiterin");
const karten = await js(`[...document.querySelectorAll('.karte--person')].map(k => k.innerText.replace(/\\s+/g,' '))`);
pruefe(karten.length === 4 && karten[0].includes("Runden 1 von 3") && karten[0].includes("1 Notiz"), `Übersicht pro Lehrperson (${karten[0]})`);
const alleEintraege = await js(`document.querySelectorAll('.karte--eintrag').length`);
pruefe(alleEintraege === 7, `Projektleiterin sieht alle 7 Einträge (${alleEintraege})`);
await keinUeberlauf("Übersicht");
await bild("09-admin");
await gehe("#/admin?person=lp2");
pruefe((await js(`document.querySelectorAll('.karte--eintrag').length`)) === 3, "Filter auf Lehrperson 2 zeigt 3 Einträge");
await gehe("#/admin/eintrag/demo-1");
pruefe((await text()).includes("Lehrperson 2") && (await text()).includes("4 von 5"), "Projektleiterin öffnet fremden Eintrag mit Skala");
const csv = await js(`LOGIK.csvExport(SPEICHER.laden().eintraege, INHALTE)`);
pruefe(csv.includes("Mein erster Gedanke") && csv.includes("Die Hausaufgaben") && csv.startsWith("﻿"), "CSV enthält die neuen Einträge");
await js(`{ window.__dl = null; const orig = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function(){ if (this.download) { window.__dl = this.download; return; } return orig.call(this); } }`);
await gehe("#/admin");
await klick("[data-export]");
pruefe((await js("window.__dl")) === "reflexionsheft-eintraege.csv", "Export-Knopf löst Download aus");

// --- Dunkles Farbschema ---
await cdp("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
await bild("10-admin-dunkel");
await js(`document.getElementById('steuerung-wechseln').click()`);
await warte(100);
await klick('[data-rolle-lp="lp1"]');
await warte(150);
await bild("11-start-dunkel");
await cdp("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }] });

// --- Zurücksetzen ---
await js(`document.getElementById('steuerung-reset').click()`);
await warte(150);
const nachReset = await js(`JSON.parse(localStorage.getItem('reflexionsheft-prototyp-v1'))`);
pruefe(nachReset.eintraege.length === 5 && nachReset.rolle === null, "Zurücksetzen stellt die Demo-Daten wieder her");

// --- Breiter Bildschirm ---
await cdp("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
await klick("[data-rolle-admin]");
await warte(150);
await bild("12-admin-desktop");

pruefe(fehler.length === 0, `keine JavaScript-Fehler (${fehler.join("; ")})`);
console.log(`\n${ok} bestanden, ${probleme.length} fehlgeschlagen`);
ws.close();
chrome.kill();
server.close();
process.exit(probleme.length ? 1 : 0);
