/*
 * Reine Logik ohne DOM: Freischaltung, Filter, Export.
 * Läuft im Browser und unter Node (für die Tests).
 */
(function (root) {
  "use strict";

  function hatInhalt(antworten) {
    return Object.values(antworten).some((w) =>
      typeof w === "number" ? true : String(w ?? "").trim() !== "",
    );
  }

  function rundenEintrag(eintraege, personId, rundeId) {
    return (
      eintraege.find((e) => e.typ === "runde" && e.personId === personId && e.rundeId === rundeId) ||
      null
    );
  }

  function rundenStatus(runde, woche, eintraege, personId) {
    if (rundenEintrag(eintraege, personId, runde.id)) return "erledigt";
    return woche >= runde.ab ? "offen" : "gesperrt";
  }

  function eintraegeVon(eintraege, personId) {
    return eintraege
      .filter((e) => e.personId === personId)
      .sort((a, b) => b.erstellt.localeCompare(a.erstellt));
  }

  function aktuellerImpuls(impulse, woche) {
    const bisher = impulse.filter((i) => i.woche <= woche);
    return bisher.length ? bisher[bisher.length - 1] : null;
  }

  function formatDatum(iso, mitZeit = true) {
    const optionen = { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Zurich" };
    if (mitZeit) Object.assign(optionen, { hour: "2-digit", minute: "2-digit" });
    return new Intl.DateTimeFormat("de-CH", optionen).format(new Date(iso));
  }

  function personName(inhalte, personId) {
    const p = inhalte.personen.find((x) => x.id === personId);
    return p ? p.name : personId;
  }

  // Beschriftung eines Eintrags: Art, Fallbeispiel/Impuls und die Frage zu jeder Antwort.
  function beschreibe(eintrag, inhalte) {
    if (eintrag.typ === "runde") {
      const runde = inhalte.runden.find((r) => r.id === eintrag.rundeId);
      const fallId = eintrag.fallId || runde?.fall || null;
      const fall = fallId ? inhalte.fallbeispiele[fallId] : null;
      return {
        art: runde ? runde.titel : eintrag.rundeId,
        bezug: fall ? fall.titel : "",
        frage: (id) => runde?.fragen.find((f) => f.id === id)?.frage || id,
      };
    }
    const impuls = inhalte.impulse.find((i) => i.id === eintrag.impulsId);
    return {
      art: "Notiz",
      bezug: impuls ? impuls.text : "",
      frage: (id) =>
        id === "frei" ? "Freie Notiz" : inhalte.notiz.leitfragen.find((l) => l.id === id)?.frage || id,
    };
  }

  function csvZelle(wert) {
    let s = String(wert ?? "");
    // Formel-Zeichen am Anfang entschärfen, damit Excel nichts ausführt (CSV-Injection).
    if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
    return '"' + s.replace(/"/g, '""') + '"';
  }

  function csvExport(eintraege, inhalte) {
    const zeilen = [["Lehrperson", "Datum", "Art", "Fallbeispiel / Impuls", "Frage", "Antwort"]];
    const sortiert = [...eintraege].sort(
      (a, b) => a.personId.localeCompare(b.personId) || a.erstellt.localeCompare(b.erstellt),
    );
    for (const e of sortiert) {
      const b = beschreibe(e, inhalte);
      for (const [frageId, antwort] of Object.entries(e.antworten)) {
        if (typeof antwort !== "number" && String(antwort ?? "").trim() === "") continue;
        zeilen.push([
          personName(inhalte, e.personId),
          formatDatum(e.erstellt),
          b.art,
          b.bezug,
          b.frage(frageId),
          antwort,
        ]);
      }
    }
    return "﻿" + zeilen.map((z) => z.map(csvZelle).join(";")).join("\r\n") + "\r\n";
  }

  function zusammenfassung(eintraege, inhalte) {
    return inhalte.personen.map((person) => {
      const eigene = eintraegeVon(eintraege, person.id);
      return {
        person,
        runden: eigene.filter((e) => e.typ === "runde").length,
        notizen: eigene.filter((e) => e.typ === "notiz").length,
        letzter: eigene.length ? eigene[0].erstellt : null,
      };
    });
  }

  const LOGIK = {
    hatInhalt,
    rundenEintrag,
    rundenStatus,
    eintraegeVon,
    aktuellerImpuls,
    formatDatum,
    personName,
    beschreibe,
    csvZelle,
    csvExport,
    zusammenfassung,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = LOGIK;
  } else {
    root.LOGIK = LOGIK;
  }
})(this);
