/*
 * Speicher des Prototyps: alles nur im Browser (localStorage).
 * Fällt auf einen Zwischenspeicher zurück, falls localStorage gesperrt ist.
 */
(function (root) {
  "use strict";

  const SCHLUESSEL = "reflexionsheft-prototyp-v1";
  let fluechtig = null;

  function vorTagen(tage, stunde) {
    const d = new Date();
    d.setDate(d.getDate() - tage);
    d.setHours(stunde, 15, 0, 0);
    return d.toISOString();
  }

  // Beispiel-Einträge der anderen Lehrpersonen, damit die Übersicht nicht leer ist.
  // Lehrperson 1 startet leer: Mit ihr probiert man selbst aus.
  function demoEintraege() {
    return [
      {
        id: "demo-1",
        personId: "lp2",
        typ: "runde",
        rundeId: "anfang",
        fallId: "hausaufgaben",
        antworten: {
          erster_gedanke: "Ich habe sofort gedacht: Das kenne ich. Und auch, dass ich in solchen Momenten schnell streng werde.",
          annahmen: "Dass das Kind es nicht ernst nimmt. Dabei weiss ich nicht, wie sein Nachmittag aussieht.",
          handeln: "Zuerst in Ruhe nachfragen, bevor ich eine Konsequenz ausspreche.",
          vertraut: 4,
        },
        erstellt: vorTagen(3, 19),
      },
      {
        id: "demo-2",
        personId: "lp2",
        typ: "notiz",
        impulsId: "moment",
        antworten: {
          frei: "In der Mathestunde habe ich eine Frage zweimal demselben Kind gestellt, weil ich die richtige Antwort erwartet habe.",
        },
        erstellt: vorTagen(2, 12),
      },
      {
        id: "demo-3",
        personId: "lp2",
        typ: "notiz",
        impulsId: null,
        antworten: {
          passiert: "Bei der Planung der Gruppen habe ich zwei Kinder automatisch getrennt.",
          gedacht: "Erst später gemerkt, dass ich das nur wegen einer Situation vom letzten Herbst gemacht habe.",
          mitnehmen: "Gruppen einmal bewusst anders zusammensetzen.",
        },
        erstellt: vorTagen(1, 17),
      },
      {
        id: "demo-4",
        personId: "lp3",
        typ: "runde",
        rundeId: "anfang",
        fallId: "stille",
        antworten: {
          erster_gedanke: "Schriftlich zeigt das Kind viel mehr, als es mündlich sagt.",
          annahmen: "Dass nur zählt, wer sich meldet.",
          handeln: "",
          vertraut: 3,
        },
        erstellt: vorTagen(2, 20),
      },
      {
        id: "demo-5",
        personId: "lp4",
        typ: "notiz",
        impulsId: null,
        antworten: {
          frei: "Beim Lesen des Infoblocks ist mir aufgefallen, wie viele Entscheidungen ich jeden Tag ohne Nachdenken treffe.",
        },
        erstellt: vorTagen(1, 8),
      },
    ];
  }

  function neuerZustand() {
    return { rolle: null, woche: 1, hinweise: true, eintraege: demoEintraege() };
  }

  function laden() {
    try {
      const roh = root.localStorage.getItem(SCHLUESSEL);
      if (roh) return JSON.parse(roh);
    } catch (_) {
      if (fluechtig) return fluechtig;
    }
    return neuerZustand();
  }

  function speichern(zustand) {
    fluechtig = zustand;
    try {
      root.localStorage.setItem(SCHLUESSEL, JSON.stringify(zustand));
    } catch (_) {
      // Privater Modus o. Ä.: Daten bleiben bis zum Neuladen erhalten.
    }
  }

  function zuruecksetzen() {
    const z = neuerZustand();
    speichern(z);
    return z;
  }

  function neueId() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  }

  root.SPEICHER = { laden, speichern, zuruecksetzen, neueId };
})(this);
