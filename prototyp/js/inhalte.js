/*
 * Inhalte des Prototyps. Alle Texte sind neutrale Platzhalter zu einem allgemeinen Thema.
 * Echte Inhalte der Auftraggeberin gehören nicht in dieses öffentliche Repo.
 */
(function (root) {
  "use strict";

  const INHALTE = {
    titel: "Reflexionsheft",

    personen: [
      { id: "lp1", name: "Lehrperson 1" },
      { id: "lp2", name: "Lehrperson 2" },
      { id: "lp3", name: "Lehrperson 3" },
      { id: "lp4", name: "Lehrperson 4" },
    ],

    wochen: 4,

    info: [
      {
        titel: "Worum es geht",
        text: [
          "Platzhalter: Hier steht später eine kurze Einführung ins Thema. Sie erklärt, worum es im Heft geht und warum es sich lohnt, darüber nachzudenken.",
          "Im Unterricht entscheiden wir vieles schnell und aus dem Bauch heraus. Dieses Heft lädt dich ein, solche Momente im Nachhinein in Ruhe anzuschauen. Es geht nicht um richtig oder falsch.",
        ],
      },
      {
        titel: "Hintergrund",
        text: [
          "Platzhalter: Hier können Texte aus dem Theorieteil stehen, kurz und verständlich aufbereitet. Zum Beispiel Begriffe, die im Heft vorkommen, oder ein kurzes Beispiel aus der Praxis.",
        ],
      },
      {
        titel: "Warum reflektieren?",
        text: [
          "Wer die eigenen Gewohnheiten kennt, kann bewusster entscheiden: im Unterricht, in der Planung und im Gespräch mit dem Team. Reflexion braucht dafür Zeit und einen geschützten Rahmen.",
        ],
      },
      {
        titel: "So funktioniert das Heft",
        text: [
          "Während vier Wochen gibt es drei angeleitete Runden: am Anfang, in der Mitte und am Schluss. Jede Runde dauert etwa 15 Minuten.",
          "Dazwischen kannst du jederzeit Beobachtungen aus deinem Alltag ins Notizbüchlein schreiben. Ab und zu bekommst du einen kurzen Impuls als Anregung.",
        ],
      },
      {
        titel: "Wer sieht deine Einträge?",
        text: [
          "Deine Einträge sieht ausser dir nur die Projektleiterin. Die anderen Lehrpersonen sehen sie nicht.",
          "Bitte schreibe keine Namen von Kindern, Eltern oder Kolleg:innen auf. Nach Abschluss der Arbeit werden alle Einträge gelöscht.",
        ],
      },
    ],

    fallbeispiele: {
      hausaufgaben: {
        titel: "Die Hausaufgaben",
        kurz: "Ein Kind bringt die Hausaufgaben nicht mit.",
        text: [
          "Platzhalter-Fallbeispiel. Ein Kind bringt zum dritten Mal in Folge die Hausaufgaben nicht mit. Es sagt, es habe sie vergessen.",
          "Eine Kollegin meint: «Da musst du jetzt konsequent sein, sonst machen es bald alle so.»",
        ],
      },
      stille: {
        titel: "Das stille Kind",
        kurz: "Ein Kind meldet sich nie.",
        text: [
          "Platzhalter-Fallbeispiel. Ein Kind meldet sich im Unterricht nie von sich aus. Wenn du es aufrufst, antwortet es leise und knapp.",
          "Im Zeugnisgespräch steht die Frage im Raum, wie die mündliche Beteiligung bewertet werden soll.",
        ],
      },
      wandertag: {
        titel: "Der Wandertag",
        kurz: "Wer übernimmt welche Aufgabe?",
        text: [
          "Platzhalter-Fallbeispiel. Für den Wandertag verteilst du Aufgaben: Karte lesen, Znüni organisieren, Fotos machen.",
          "Später fällt dir auf, dass du die Aufgaben fast genau gleich verteilt hast wie im letzten Jahr, ohne die Kinder zu fragen.",
        ],
      },
      rueckmeldung: {
        titel: "Die Rückmeldung",
        kurz: "Wie formuliere ich eine Rückmeldung?",
        text: [
          "Platzhalter-Fallbeispiel. Nach einer Prüfung schreibst du kurze Rückmeldungen. Beim Durchlesen merkst du, dass einige ausführlich und ermutigend sind, andere knapp.",
          "Du fragst dich, woran das liegt.",
        ],
      },
    },

    runden: [
      {
        id: "anfang",
        titel: "Runde 1: Einstieg",
        ab: 1,
        einleitung:
          "Wähle eines der drei Fallbeispiele aus. Lies es in Ruhe und beantworte danach die Fragen. Es gibt keine falschen Antworten.",
        auswahl: ["hausaufgaben", "stille", "wandertag"],
        fragen: [
          {
            id: "erster_gedanke",
            typ: "text",
            frage: "Was ist dein erster Gedanke zu dieser Situation?",
            hilfe: "Schreib spontan auf, was dir durch den Kopf geht.",
          },
          {
            id: "annahmen",
            typ: "text",
            frage: "Welche Annahmen stecken in der Situation?",
            hilfe: "Und welche davon teilst du vielleicht selbst?",
          },
          {
            id: "handeln",
            typ: "text",
            frage: "Wie würdest du handeln? Was wäre eine Alternative?",
          },
          {
            id: "vertraut",
            typ: "skala",
            frage: "Wie vertraut sind dir solche Situationen aus deinem Alltag?",
            pole: ["gar nicht", "sehr"],
          },
        ],
      },
      {
        id: "mitte",
        titel: "Runde 2: Unterwegs",
        ab: 2,
        einleitung:
          "In dieser Runde gibt es ein Fallbeispiel für alle. Danach schaust du kurz auf deine letzten zwei Wochen zurück.",
        fall: "rueckmeldung",
        fragen: [
          {
            id: "erster_gedanke",
            typ: "text",
            frage: "Was löst diese Situation bei dir aus?",
          },
          {
            id: "eigene_situation",
            typ: "text",
            frage: "Kennst du einen ähnlichen Moment aus deinem eigenen Unterricht?",
            hilfe: "Ohne Namen. Beschreibe nur die Situation.",
          },
          {
            id: "rueckblick",
            typ: "text",
            frage: "Was hast du in den letzten zwei Wochen bei dir beobachtet?",
          },
          {
            id: "aufmerksamkeit",
            typ: "skala",
            frage: "Wie bewusst achtest du zurzeit auf solche Momente?",
            pole: ["kaum", "sehr"],
          },
        ],
      },
      {
        id: "ende",
        titel: "Runde 3: Rückblick",
        ab: 4,
        einleitung:
          "Zum Abschluss liest du nochmals, was du in der ersten Runde geschrieben hast. Danach schaust du auf die ganzen vier Wochen zurück.",
        rueckblickAuf: "anfang",
        fragen: [
          {
            id: "wiedergelesen",
            typ: "text",
            frage: "Wenn du deine Antworten von damals liest: Was fällt dir auf?",
          },
          {
            id: "veraenderung",
            typ: "text",
            frage: "Hat sich in deinem Unterricht oder deiner Planung etwas verändert?",
          },
          {
            id: "mitnehmen",
            typ: "text",
            frage: "Was nimmst du mit?",
          },
          {
            id: "anregung",
            typ: "skala",
            frage: "Wie sehr hat dich das Heft zum Nachdenken angeregt?",
            pole: ["gar nicht", "sehr"],
          },
        ],
      },
    ],

    notiz: {
      einleitung:
        "Halte fest, was dir im Alltag auffällt: eine Situation, eine Bemerkung, ein eigener Gedanke.",
      leitfragen: [
        { id: "passiert", frage: "Was ist passiert?" },
        { id: "gedacht", frage: "Was habe ich gedacht oder gefühlt?" },
        { id: "mitnehmen", frage: "Was nehme ich mit?" },
      ],
    },

    impulse: [
      {
        id: "moment",
        woche: 1,
        text: "Gab es heute einen Moment im Unterricht, über den du noch nachdenkst?",
      },
      {
        id: "gewohnheit",
        woche: 2,
        text: "Welche Entscheidung hast du diese Woche aus Gewohnheit getroffen?",
      },
      {
        id: "ueberrascht",
        woche: 3,
        text: "Hat dich diese Woche ein Kind überrascht? Was hattest du vorher erwartet?",
      },
      {
        id: "ausblick",
        woche: 4,
        text: "Welche Situation aus diesen vier Wochen wirst du nicht so schnell vergessen?",
      },
    ],
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = INHALTE;
  } else {
    root.INHALTE = INHALTE;
  }
})(this);
