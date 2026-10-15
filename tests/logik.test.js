const { test } = require("node:test");
const assert = require("node:assert/strict");

const INHALTE = require("../prototyp/js/inhalte.js");
const L = require("../prototyp/js/logik.js");

const anfang = INHALTE.runden.find((r) => r.id === "anfang");
const mitte = INHALTE.runden.find((r) => r.id === "mitte");

function runde(personId, rundeId, antworten, erstellt) {
  return {
    id: `${personId}-${rundeId}`,
    personId,
    typ: "runde",
    rundeId,
    fallId: rundeId === "anfang" ? "hausaufgaben" : null,
    antworten,
    erstellt,
  };
}

function notiz(personId, antworten, erstellt, impulsId = null) {
  return { id: `${personId}-${erstellt}`, personId, typ: "notiz", impulsId, antworten, erstellt };
}

test("Runde ist gesperrt, bevor ihre Woche erreicht ist", () => {
  assert.equal(L.rundenStatus(mitte, 1, [], "lp1"), "gesperrt");
});

test("Runde ist offen ab ihrer Woche und bleibt offen, wenn nicht erledigt", () => {
  assert.equal(L.rundenStatus(mitte, 2, [], "lp1"), "offen");
  assert.equal(L.rundenStatus(mitte, 4, [], "lp1"), "offen");
});

test("Runde ist erledigt, sobald die Person einen Eintrag dazu hat", () => {
  const e = [runde("lp1", "anfang", { erster_gedanke: "x" }, "2026-11-30T08:00:00Z")];
  assert.equal(L.rundenStatus(anfang, 1, e, "lp1"), "erledigt");
});

test("Der Eintrag einer anderen Person erledigt die Runde nicht", () => {
  const e = [runde("lp2", "anfang", { erster_gedanke: "x" }, "2026-11-30T08:00:00Z")];
  assert.equal(L.rundenStatus(anfang, 1, e, "lp1"), "offen");
});

test("eintraegeVon liefert nur eigene Einträge, neueste zuerst", () => {
  const e = [
    notiz("lp1", { frei: "alt" }, "2026-11-01T08:00:00Z"),
    notiz("lp2", { frei: "fremd" }, "2026-11-02T08:00:00Z"),
    notiz("lp1", { frei: "neu" }, "2026-11-03T08:00:00Z"),
  ];
  const eigene = L.eintraegeVon(e, "lp1");
  assert.deepEqual(
    eigene.map((x) => x.antworten.frei),
    ["neu", "alt"],
  );
});

test("aktuellerImpuls nimmt den Impuls der Woche, sonst den letzten davor", () => {
  const impulse = [
    { id: "a", woche: 1, text: "A" },
    { id: "c", woche: 3, text: "C" },
  ];
  assert.equal(L.aktuellerImpuls(impulse, 1).id, "a");
  assert.equal(L.aktuellerImpuls(impulse, 2).id, "a");
  assert.equal(L.aktuellerImpuls(impulse, 4).id, "c");
  assert.equal(L.aktuellerImpuls([], 1), null);
});

test("csvZelle setzt Anführungszeichen und verdoppelt innere", () => {
  assert.equal(L.csvZelle('Er sagte "nein"; dann'), '"Er sagte ""nein""; dann"');
});

test("csvZelle entschärft Formeln gegen CSV-Injection", () => {
  assert.equal(L.csvZelle("=SUMME(A1)"), "\"'=SUMME(A1)\"");
  assert.equal(L.csvZelle("+41 79"), "\"'+41 79\"");
  assert.equal(L.csvZelle("@x"), "\"'@x\"");
});

test("csvExport: BOM, Semikolon, Kopfzeile, eine Zeile pro Antwort", () => {
  const e = [
    runde(
      "lp1",
      "anfang",
      { erster_gedanke: "Zeile 1\nZeile 2", vertraut: 4 },
      "2026-11-30T08:00:00Z",
    ),
    notiz("lp2", { frei: "Beobachtung" }, "2026-12-01T09:30:00Z", "moment"),
  ];
  const csv = L.csvExport(e, INHALTE);
  assert.ok(csv.startsWith("﻿"), "BOM für Excel");
  const zeilen = csv.slice(1).split("\r\n");
  assert.equal(zeilen[0], '"Lehrperson";"Datum";"Art";"Fallbeispiel / Impuls";"Frage";"Antwort"');
  // 2 Antworten aus der Runde + 1 aus der Notiz
  assert.equal(zeilen.filter((z) => z.length > 0).length, 4);
  assert.ok(csv.includes('"Lehrperson 1"'));
  assert.ok(csv.includes('"Die Hausaufgaben"'));
  assert.ok(csv.includes('"Zeile 1\nZeile 2"'), "Zeilenumbruch bleibt in der Zelle");
  assert.ok(csv.includes('"4"'));
  assert.ok(csv.includes('"Notiz"'));
  assert.ok(csv.includes('"Freie Notiz"'));
});

test("csvExport lässt leere Antworten weg", () => {
  const e = [runde("lp1", "anfang", { erster_gedanke: "  ", annahmen: "ja" }, "2026-11-30T08:00:00Z")];
  const zeilen = L.csvExport(e, INHALTE).slice(1).split("\r\n").filter(Boolean);
  assert.equal(zeilen.length, 2);
});

test("zusammenfassung zählt pro Person Runden und Notizen", () => {
  const e = [
    runde("lp1", "anfang", { erster_gedanke: "x" }, "2026-11-30T08:00:00Z"),
    notiz("lp1", { frei: "a" }, "2026-12-01T08:00:00Z"),
    notiz("lp1", { frei: "b" }, "2026-12-02T08:00:00Z"),
  ];
  const z = L.zusammenfassung(e, INHALTE);
  assert.equal(z.length, 4);
  const lp1 = z.find((p) => p.person.id === "lp1");
  assert.equal(lp1.runden, 1);
  assert.equal(lp1.notizen, 2);
  assert.equal(lp1.letzter, "2026-12-02T08:00:00Z");
  const lp3 = z.find((p) => p.person.id === "lp3");
  assert.equal(lp3.runden, 0);
  assert.equal(lp3.letzter, null);
});

test("hatInhalt erkennt leere Antworten", () => {
  assert.equal(L.hatInhalt({ a: "", b: "  " }), false);
  assert.equal(L.hatInhalt({ a: "", b: 3 }), true);
  assert.equal(L.hatInhalt({ a: "x" }), true);
});
