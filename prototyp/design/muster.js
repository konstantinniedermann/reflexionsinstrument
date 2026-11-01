/*
 * Gestaltungsmuster A/B/C zum Ausprobieren (Wegwerf-Prototyp).
 * Siehe docs/superpowers/specs/2026-11-01-design-muster-design.md
 * Alle Texte sind Platzhalter. Es wird nichts gespeichert.
 */
(function () {
  "use strict";

  const MUSTER = {
    a: "Spielplan",
    b: "Register",
    c: "Plakat",
  };

  // Seite -> Register (Farbe des Hintergrunds) und aktiver Navigationspunkt
  const SEITEN = {
    start: { reg: "start", nav: "start", titel: "Start" },
    runde: { reg: "runden", nav: "start", titel: "Runde 2" },
    tagebuch: { reg: "tagebuch", nav: "tagebuch", titel: "Tagebuch" },
    schreiben: { reg: "tagebuch", nav: "tagebuch", titel: "Frei schreiben" },
    eintraege: { reg: "eintraege", nav: "eintraege", titel: "Meine Einträge" },
    info: { reg: "info", nav: "info", titel: "Info" },
  };

  const pfeil = '<span class="pfeil" aria-hidden="true">›</span>';

  function etikett(text) {
    return `<p class="etikett">${text}</p>`;
  }

  const VORLAGEN = {
    start: () => `
      <header class="kopf">
        <p class="ueberzeile">Woche 2</p>
        <h1 tabindex="-1">Willkommen zurück</h1>
        <p class="lead">Schön, dass du da bist. Hier siehst du, was diese Woche ansteht.</p>
      </header>

      <section class="block flaeche reg-tagebuch" aria-labelledby="impuls-titel">
        <p class="ueberzeile" id="impuls-titel">Impuls dieser Woche</p>
        <p class="impuls">Wann hast du heute bewusst gewartet, bevor du reagiert hast?</p>
        <a class="knopf" href="#schreiben">Dazu schreiben</a>
      </section>

      <section class="block flaeche reg-runden" aria-labelledby="runden-titel">
        <h2 id="runden-titel">Runden</h2>
        <ul class="liste">
          <li><span class="zeile zeile--still"><span class="zeile__titel">Runde 1</span><span class="marke">Erledigt</span></span></li>
          <li><a class="zeile" href="#runde"><span class="zeile__titel">Runde 2</span><span class="marke marke--offen">Offen</span>${pfeil}</a></li>
          <li><span class="zeile zeile--gesperrt"><span class="zeile__titel">Runde 3</span><span class="meta">ab 16. November</span></span></li>
        </ul>
      </section>

      <section class="block flaeche reg-tagebuch" aria-labelledby="tagebuch-titel">
        <h2 id="tagebuch-titel">Tagebuch</h2>
        <p class="meta">3 Einträge · Halte fest, was dir auffällt.</p>
        <a class="knopf" href="#tagebuch">Neuer Tagebucheintrag</a>
      </section>

      <a class="block block--link flaeche reg-info" href="#info">
        <span class="zeile__titel">Worum es geht</span>${pfeil}
      </a>`,

    runde: () => `
      <header class="kopf">
        ${etikett("Runden")}
        <h1 tabindex="-1">Runde 2</h1>
        <p class="lead">Ein Fall für alle. Nimm dir etwa 15 Minuten Zeit.</p>
      </header>

      <section class="block flaeche reg-runden" aria-labelledby="fall-titel">
        <p class="ueberzeile">Fallbeispiel</p>
        <h2 id="fall-titel">Die Gruppenarbeit</h2>
        <p>Platzhalter: In einer Gruppenarbeit übernimmt ein Kind alle Aufgaben, die anderen schauen zu. Die Lehrperson bemerkt es erst kurz vor Schluss.</p>
        <p>Hier steht später das echte Fallbeispiel der Projektleiterin.</p>
      </section>

      <form class="block formular" data-speichern>
        <label class="feld">
          <span class="feld__frage">Was fällt dir an dieser Situation auf?</span>
          <textarea rows="5"></textarea>
        </label>
        <fieldset class="feld">
          <legend class="feld__frage">Wie vertraut ist dir eine solche Situation?</legend>
          <div class="skala">
            ${[1, 2, 3, 4, 5]
              .map(
                (n) =>
                  `<label><input type="radio" name="skala" value="${n}" /><span>${n}</span></label>`,
              )
              .join("")}
          </div>
          <div class="skala__enden"><span>gar nicht</span><span>sehr</span></div>
        </fieldset>
        <div class="knoepfe">
          <button class="knopf knopf--haupt" type="submit">Speichern</button>
          <a class="knopf knopf--leise" href="#start">Später weitermachen</a>
        </div>
      </form>`,

    tagebuch: () => `
      <header class="kopf">
        <h1 class="etikett etikett--titel" tabindex="-1">Tagebuch</h1>
        <p class="lead">Was möchtest du festhalten?</p>
      </header>

      <a class="block block--link flaeche reg-tagebuch" href="#schreiben">
        <span class="zeile__titel">Frei schreiben</span>${pfeil}
      </a>
      <a class="block block--link flaeche reg-tagebuch" href="#schreiben">
        <span>
          <span class="zeile__titel">Frei sprechen</span>
          <span class="meta">Eintrag einsprechen, zum Beispiel direkt nach dem Unterricht.</span>
        </span>${pfeil}
      </a>
      <a class="block block--link flaeche reg-tagebuch" href="#schreiben">
        <span>
          <span class="zeile__titel">Zum Impuls dieser Woche</span>
          <span class="meta">Wann hast du heute bewusst gewartet, bevor du reagiert hast?</span>
        </span>${pfeil}
      </a>

      <h2 class="zwischentitel">Zu einer Leitfrage schreiben</h2>
      <a class="block block--link flaeche reg-tagebuch" href="#schreiben">
        <span>Welche Situation ist dir heute besonders in Erinnerung geblieben?</span>${pfeil}
      </a>
      <a class="block block--link flaeche reg-tagebuch" href="#schreiben">
        <span>Was würdest du beim nächsten Mal anders machen?</span>${pfeil}
      </a>`,

    schreiben: () => `
      <header class="kopf">
        ${etikett("Tagebuch")}
        <h1 tabindex="-1">Frei schreiben</h1>
      </header>
      <p class="hinweis">Bitte schreibe keine Namen von Kindern, Eltern oder Kolleginnen und Kollegen auf.</p>
      <form class="block formular" data-speichern>
        <label class="feld">
          <span class="feld__frage">Was ist dir aufgefallen?</span>
          <textarea rows="8"></textarea>
        </label>
        <div class="knoepfe">
          <button class="knopf knopf--haupt" type="submit">Speichern</button>
          <a class="knopf knopf--leise" href="#tagebuch">Abbrechen</a>
        </div>
      </form>`,

    eintraege: () => {
      const eintraege = [
        ["tagebuch", "Tagebuch", "Heute, 16:20", "Frei geschrieben", "Platzhalter: In der Pause kam ein Kind zu mir und …"],
        ["tagebuch", "Impuls", "Gestern, 12:05", "Wann hast du heute bewusst gewartet …", "Platzhalter: Beim Morgenkreis habe ich …"],
        ["runden", "Runde", "28. Oktober", "Runde 1 · Der Pausenplatz", "Platzhalter: Mir fällt auf, dass …"],
        ["tagebuch", "Tagebuch", "27. Oktober", "Aufnahme, 1:42", ""],
      ];
      return `
      <header class="kopf">
        <h1 class="etikett etikett--titel" tabindex="-1">Meine Einträge</h1>
        <p class="lead">Nur du und die Projektleiterin sehen sie.</p>
      </header>
      <ul class="eintraege">
        ${eintraege
          .map(
            ([reg, art, wann, titel, vorschau]) => `
          <li>
            <a class="block block--eintrag" href="#eintraege">
              <span class="eintrag__kopf"><span class="marke flaeche reg-${reg}">${art}</span><span class="meta">${wann}</span></span>
              <span class="zeile__titel">${titel}</span>
              ${vorschau ? `<span class="meta">${vorschau}</span>` : ""}
            </a>
          </li>`,
          )
          .join("")}
      </ul>`;
    },

    info: () => `
      <header class="kopf">
        <h1 class="etikett etikett--titel" tabindex="-1">Info</h1>
        <p class="lead">Worum es geht und wer deine Einträge sieht.</p>
      </header>
      <article class="block lesetext">
        <h2>Worum es geht</h2>
        <p>Platzhalter: Im Unterricht entscheiden wir vieles schnell und aus dem Bauch heraus. Dieses Heft lädt dich ein, solche Momente im Nachhinein in Ruhe anzuschauen. Es geht nicht um richtig oder falsch.</p>
        <h2>So funktioniert das Heft</h2>
        <p>Während vier Wochen gibt es drei angeleitete Runden. Dazwischen kannst du jederzeit ins Tagebuch schreiben oder sprechen.</p>
        <h2>Wer sieht deine Einträge?</h2>
        <p>Ausser dir nur die Projektleiterin. Nach Abschluss der Arbeit werden alle Einträge gelöscht.</p>
      </article>
      <p class="abmelden"><button class="knopf knopf--leise" type="button" data-hinweis>Abmelden</button><span class="meta">Nur nötig auf einem geteilten Gerät.</span></p>`,
  };

  const app = document.getElementById("app");
  const nav = document.getElementById("tabs");
  const schalter = document.getElementById("muster-schalter");
  const meldung = document.getElementById("meldung");

  function aktuellesMuster() {
    const m = new URLSearchParams(location.search).get("m");
    return MUSTER[m] ? m : "a";
  }

  function setzeMuster(m) {
    document.body.dataset.muster = m;
    document.title = `Muster ${m.toUpperCase()} «${MUSTER[m]}» – Reflexionsheft`;
    schalter.querySelectorAll("a").forEach((a) => {
      const aktiv = a.dataset.m === m;
      if (aktiv) a.setAttribute("aria-current", "true");
      else a.removeAttribute("aria-current");
    });
  }

  function zeigeMeldung(text) {
    meldung.textContent = text;
    meldung.hidden = false;
    clearTimeout(zeigeMeldung.t);
    zeigeMeldung.t = setTimeout(() => (meldung.hidden = true), 3500);
  }

  function render() {
    const name = location.hash.replace("#", "") || "start";
    const seite = SEITEN[name] ? name : "start";
    const info = SEITEN[seite];
    document.body.dataset.reg = info.reg;
    app.innerHTML = VORLAGEN[seite]();
    nav.querySelectorAll("a").forEach((a) => {
      if (a.dataset.nav === info.nav) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    // Musterwechsel behält die aktuelle Seite
    schalter.querySelectorAll("a").forEach((a) => {
      a.href = `?m=${a.dataset.m}#${seite}`;
    });
    window.scrollTo(0, 0);
    const h1 = app.querySelector("h1");
    if (h1 && render.schonGerendert) h1.focus({ preventScroll: true });
    render.schonGerendert = true;
  }

  app.addEventListener("submit", (e) => {
    if (!e.target.matches("[data-speichern]")) return;
    e.preventDefault();
    location.hash = "eintraege";
    zeigeMeldung("Im Muster wird nichts gespeichert.");
  });
  app.addEventListener("click", (e) => {
    if (e.target.closest("[data-hinweis]")) zeigeMeldung("Im Muster nicht verfügbar.");
  });

  setzeMuster(aktuellesMuster());
  window.addEventListener("hashchange", render);
  render();
})();
