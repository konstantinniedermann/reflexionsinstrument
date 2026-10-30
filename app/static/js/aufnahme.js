// Aufnehmen im Browser: aufnehmen, anhoeren, mit einem POST speichern.
// Alle Texte stehen im Template; das Skript blendet nur ein und aus.
// Ohne dieses Skript (oder ohne Aufnahmefaehigkeit) bleibt das Dateifeld als Rueckfall.
(function () {
  "use strict";

  const wurzel = document.querySelector("[data-aufnehmen]");
  if (!wurzel) return;
  const formular = wurzel.closest("form");
  const maxDauer = Number(wurzel.dataset.maxDauer) * 1000;
  const maxBytes = Number(wurzel.dataset.maxBytes);
  const WARNUNG_VOR_ENDE = 60 * 1000;
  // Reihenfolge nach Design: AAC in MP4 spielt ueberall ab, WebM/Opus ist die Rueckfallstufe.
  const FORMATE = ["audio/mp4;codecs=mp4a.40.2", "audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"];
  const FEHLER = {
    NotAllowedError: "verweigert",
    SecurityError: "verweigert",
    NotFoundError: "kein-mikrofon",
    OverconstrainedError: "kein-mikrofon",
    NotReadableError: "besetzt",
    AbortError: "besetzt",
  };

  const teil = (name) => wurzel.querySelector(`[data-teil="${name}"]`);
  const knopf = (aktion) => wurzel.querySelector(`[data-aktion="${aktion}"]`);
  const player = wurzel.querySelector("[data-vorhoeren]");
  const zeit = wurzel.querySelector("[data-zeit]");
  const gesamt = zeit.textContent.split("/")[1]?.trim() ?? "";

  let strom = null;
  let recorder = null;
  let teile = [];
  let startZeit = 0;
  let dauer = 0;
  let uhr = null;
  let gewarnt = false;
  let stoppGrund = null; // null: unerwartetes Ende; "": Knopf «Stopp»; sonst Name der Meldung
  let sperre = null;
  let aufnahme = null;
  let adresse = null;
  let speichertGerade = false;

  function melde(name) {
    wurzel.querySelectorAll("[data-meldung]").forEach((e) => {
      e.hidden = e.dataset.meldung !== name;
    });
  }

  function zustand(name) {
    for (const n of ["bereit", "nimmt-auf", "fertig"]) teil(n).hidden = n !== name;
    player.hidden = name !== "fertig";
    knopf("speichern").hidden = name !== "fertig";
  }

  function zeige(ms) {
    const s = Math.floor(ms / 1000);
    zeit.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")} / ${gesamt}`;
  }

  function waehleFormat() {
    return FORMATE.find((typ) => MediaRecorder.isTypeSupported(typ)) ?? "";
  }

  function endung(typ) {
    if (typ.includes("mp4")) return ".m4a";
    if (typ.includes("ogg")) return ".ogg";
    return ".webm";
  }

  function beendeSpuren() {
    strom?.getTracks().forEach((spur) => spur.stop());
    strom = null;
  }

  async function bildschirmAn() {
    let neu = null;
    try {
      neu = (await navigator.wakeLock?.request("screen")) ?? null;
    } catch {
      return; // nicht erlaubt oder nicht vorhanden: dann eben ohne
    }
    // Die Aufnahme kann schon vorbei sein, bevor die Sperre kommt.
    if (recorder?.state === "recording") sperre = neu;
    else neu?.release().catch(() => {});
  }

  function bildschirmFrei() {
    sperre?.release().catch(() => {});
    sperre = null;
  }

  function verwirf() {
    if (adresse) URL.revokeObjectURL(adresse);
    adresse = null;
    aufnahme = null;
    player.removeAttribute("src");
    player.load();
  }

  function ticke() {
    const ms = performance.now() - startZeit;
    zeige(Math.min(ms, maxDauer));
    if (ms >= maxDauer) halte("hoechstdauer");
    else if (!gewarnt && ms >= maxDauer - WARNUNG_VOR_ENDE) {
      gewarnt = true;
      melde("noch-eine-minute");
    }
  }

  function halte(grund) {
    if (!recorder || recorder.state === "inactive") return;
    stoppGrund = grund;
    recorder.stop();
  }

  function beendet() {
    dauer = performance.now() - startZeit;
    clearInterval(uhr);
    beendeSpuren();
    bildschirmFrei();
    const typ = recorder.mimeType || teile[0]?.type || "";
    aufnahme = new Blob(teile, typ ? { type: typ } : {});
    teile = [];
    recorder = null;
    const grund = stoppGrund === null ? "angehalten" : stoppGrund;
    if (aufnahme.size === 0) {
      aufnahme = null;
      zustand("bereit");
      melde("ungueltig");
      return;
    }
    adresse = URL.createObjectURL(aufnahme);
    player.src = adresse;
    zustand("fertig");
    melde(grund || null);
    knopf("speichern").focus();
  }

  function brichStartAb(meldung) {
    beendeSpuren();
    recorder = null;
    knopf("start").disabled = false;
    zustand("bereit");
    melde(meldung);
  }

  async function starte() {
    melde(null);
    knopf("start").disabled = true;
    try {
      strom = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (fehler) {
      brichStartAb(FEHLER[fehler?.name] ?? "besetzt");
      return;
    }
    // Seite verlassen, waehrend der Browser nach dem Mikrofon fragte: nicht im Hintergrund aufnehmen.
    if (document.visibilityState === "hidden") {
      brichStartAb(null);
      return;
    }
    try {
      const mimeType = waehleFormat();
      const optionen = { audioBitsPerSecond: 64000 };
      if (mimeType) optionen.mimeType = mimeType;
      recorder = new MediaRecorder(strom, optionen);
    } catch {
      brichStartAb("nicht-unterstuetzt");
      return;
    }
    teile = [];
    gewarnt = false;
    stoppGrund = null;
    try {
      recorder.addEventListener("dataavailable", (e) => {
        if (e.data.size) teile.push(e.data);
      });
      recorder.addEventListener("start", () => {
        startZeit = performance.now();
      });
      recorder.addEventListener("stop", beendet);
      recorder.addEventListener("error", () => halte("angehalten"));
      strom.getTracks().forEach((spur) => spur.addEventListener("ended", () => halte("angehalten")));
      startZeit = performance.now();
      recorder.start(1000);
    } catch {
      // z. B. Mikrofon inzwischen von einem Anruf belegt, Strom schon beendet
      brichStartAb("besetzt");
      return;
    }
    zeige(0);
    uhr = setInterval(ticke, 250);
    knopf("start").disabled = false;
    zustand("nimmt-auf");
    knopf("stopp").focus();
    bildschirmAn();
  }

  function sperreKnoepfe(gesperrt) {
    wurzel.querySelectorAll("button").forEach((b) => {
      b.disabled = gesperrt;
    });
  }

  async function speichere() {
    if (!aufnahme || speichertGerade) return;
    if (aufnahme.size > maxBytes) {
      melde("zu-gross");
      return;
    }
    const daten = new FormData(formular);
    daten.set("aufnahme", aufnahme, "aufnahme" + endung(aufnahme.type));
    daten.set("dauer_sekunden", String(Math.ceil(dauer / 1000)));
    speichertGerade = true;
    sperreKnoepfe(true);
    melde("wird-gespeichert");
    let antwort;
    try {
      antwort = await fetch(formular.action, { method: "POST", body: daten, credentials: "same-origin" });
    } catch {
      antwort = null;
    }
    const ziel = antwort ? new URL(antwort.url).pathname : "";
    if (antwort?.ok && ziel.startsWith("/lehrperson/")) {
      location.assign(antwort.url + (formular.dataset.anker ? "#" + formular.dataset.anker : ""));
      return;
    }
    speichertGerade = false;
    sperreKnoepfe(false);
    if (!antwort) melde("keine-verbindung");
    else if (ziel === "/") melde("abgemeldet");
    else if (antwort.status === 413) melde("zu-gross");
    else if (antwort.status === 400) melde("ungueltig");
    else if (antwort.status === 403) melde("abgelaufen");
    else melde("serverfehler");
  }

  const verstecke = (sel) =>
    wurzel.querySelectorAll(sel).forEach((e) => {
      e.hidden = true;
    });
  // Satz und Link fuer den Fall ohne Skript; die Meldungen bringen ihren eigenen mit.
  verstecke("[data-nur-ohne-skript]");
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    melde("nicht-unterstuetzt"); // Dateifeld bleibt als Rueckfall
    return;
  }
  verstecke("[data-rueckfall]");
  zustand("bereit");

  knopf("start").addEventListener("click", starte);
  knopf("stopp").addEventListener("click", () => halte(""));
  knopf("neu").addEventListener("click", () => {
    verwirf();
    melde(null);
    zustand("bereit");
    knopf("start").focus();
  });
  formular.addEventListener("submit", (e) => {
    e.preventDefault();
    speichere();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") halte("angehalten");
  });
})();
