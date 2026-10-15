/*
 * Oberfläche des Prototyps: einfacher Hash-Router und Ansichten als HTML-Strings.
 * Alle Nutzereingaben laufen durch esc(), bevor sie ins HTML kommen.
 */
(function () {
  "use strict";

  const I = window.INHALTE;
  const L = window.LOGIK;
  const S = window.SPEICHER;

  let zustand = S.laden();
  const app = document.getElementById("app");
  const tabs = document.getElementById("tabs");

  // ---------- Hilfsfunktionen ----------

  function esc(wert) {
    return String(wert ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function absaetze(liste) {
    return liste.map((t) => `<p>${esc(t)}</p>`).join("");
  }

  function sichern() {
    S.speichern(zustand);
  }

  function gehe(pfad) {
    if (location.hash === pfad) zeichne();
    else location.hash = pfad;
  }

  function istLp() {
    return zustand.rolle && zustand.rolle.typ === "lp";
  }

  function istAdmin() {
    return zustand.rolle && zustand.rolle.typ === "admin";
  }

  function ich() {
    return istLp() ? zustand.rolle.personId : null;
  }

  // Immer gerendert, Ein- und Ausblenden per Klasse am <body>, damit Getipptes erhalten bleibt.
  function besprechen(punkte) {
    return `
      <aside class="besprechen" aria-label="Zum Besprechen">
        <p class="besprechen__titel">Zum Besprechen</p>
        <ul>${punkte.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>
      </aside>`;
  }

  function zurueck(href, text) {
    return `<a class="zurueck" href="${href}">‹ ${esc(text)}</a>`;
  }

  function vorschau(eintrag) {
    const text = Object.values(eintrag.antworten).find(
      (w) => typeof w === "string" && w.trim() !== "",
    );
    return text ? text.trim() : "";
  }

  // ---------- Ansichten ----------

  function ansichtWahl() {
    const lps = I.personen
      .map((p) => `<button class="knopf knopf--zweit" data-rolle-lp="${esc(p.id)}">${esc(p.name)}</button>`)
      .join("");
    return `
      <h1 tabindex="-1">So könnte das Reflexionsheft aussehen</h1>
      <p class="lead">Dies ist ein Prototyp zum Ausprobieren. Alle Texte sind Platzhalter. Was du hier eingibst, bleibt nur in diesem Browser.</p>
      <section class="karte">
        <h2>Als Lehrperson ansehen</h2>
        <p class="gedaempft">Jede Lehrperson sieht nur ihre eigenen Einträge. Lehrperson 1 ist noch leer, die anderen haben schon etwas geschrieben.</p>
        <div class="raster-2">${lps}</div>
      </section>
      <section class="karte">
        <h2>Als Projektleiterin ansehen</h2>
        <p class="gedaempft">Du siehst alle Einträge und kannst sie als Tabelle herunterladen.</p>
        <button class="knopf" data-rolle-admin>Zur Übersicht</button>
      </section>
      ${besprechen([
        "Später bekommt jede Lehrperson einen persönlichen Link. Sie muss sich kein Passwort merken.",
        "Oben unter «Prototyp-Steuerung» kannst du die Woche wechseln und so die Runden freischalten.",
      ])}`;
  }

  function rundenKarte(runde) {
    const status = L.rundenStatus(runde, zustand.woche, zustand.eintraege, ich());
    const eintrag = L.rundenEintrag(zustand.eintraege, ich(), runde.id);
    const marke =
      status === "erledigt"
        ? `<span class="marke marke--erledigt">erledigt am ${esc(L.formatDatum(eintrag.erstellt, false))}</span>`
        : status === "offen"
          ? `<span class="marke marke--offen">jetzt ausfüllen</span>`
          : `<span class="marke">ab Woche ${runde.ab}</span>`;
    const inhalt = `
      <span class="runde__titel">${esc(runde.titel)}</span>
      ${marke}`;
    if (status === "gesperrt") {
      return `<li class="runde runde--gesperrt" aria-disabled="true">${inhalt}</li>`;
    }
    const ziel = status === "erledigt" ? `#/eintrag/${esc(eintrag.id)}` : `#/runde/${esc(runde.id)}`;
    return `<li><a class="runde runde--${status}" href="${ziel}">${inhalt}<span class="pfeil" aria-hidden="true">›</span></a></li>`;
  }

  function ansichtStart() {
    const impuls = L.aktuellerImpuls(I.impulse, zustand.woche);
    const notizen = L.eintraegeVon(zustand.eintraege, ich()).filter((e) => e.typ === "notiz").length;
    return `
      <p class="ueberzeile">Woche ${zustand.woche} von ${I.wochen}</p>
      <h1 tabindex="-1">Guten Tag</h1>
      ${
        impuls
          ? `<section class="karte karte--impuls">
              <p class="ueberzeile">Impuls dieser Woche</p>
              <p class="impuls__text">${esc(impuls.text)}</p>
              <a class="knopf" href="#/notiz?impuls=${esc(impuls.id)}">Dazu notieren</a>
            </section>`
          : ""
      }
      <section class="karte">
        <h2>Angeleitete Runden</h2>
        <ul class="runden">${I.runden.map(rundenKarte).join("")}</ul>
      </section>
      <section class="karte">
        <h2>Notizbüchlein</h2>
        <p class="gedaempft">${notizen === 0 ? "Noch keine Notizen." : notizen === 1 ? "1 Notiz" : `${notizen} Notizen`} · Halte fest, was dir im Alltag auffällt.</p>
        <a class="knopf knopf--zweit" href="#/notiz">Neue Notiz</a>
      </section>
      <a class="karte karte--link" href="#/info">
        <span><strong>Worum geht es?</strong><br><span class="gedaempft">Hier kannst du dich jederzeit einlesen.</span></span>
        <span class="pfeil" aria-hidden="true">›</span>
      </a>
      ${besprechen([
        "Wie sollen die Impulse ankommen: hier im Heft, per E-Mail oder schickst du sie selbst per WhatsApp?",
        "Passt der Rhythmus: Runde 1 in Woche 1, Runde 2 in Woche 2, Runde 3 in Woche 4?",
      ])}`;
  }

  function ansichtInfo() {
    const teile = I.info
      .map(
        (t, i) => `
        <details class="karte aufklapp"${i === 0 ? " open" : ""}>
          <summary>${esc(t.titel)}</summary>
          <div class="aufklapp__inhalt">${absaetze(t.text)}</div>
        </details>`,
      )
      .join("");
    return `
      <h1 tabindex="-1">Worum es geht</h1>
      <p class="lead">Hier kannst du dich ins Thema einlesen, so oft du möchtest.</p>
      ${teile}
      ${besprechen([
        "Welche Themen gehören in den Infoblock? Hier könnten Texte aus deinem Theorieteil stehen.",
        "Lieber kurze Abschnitte zum Aufklappen oder ein durchgehender Text?",
      ])}`;
  }

  function ansichtFallwahl(runde) {
    const karten = runde.auswahl
      .map((id) => {
        const f = I.fallbeispiele[id];
        return `<li><a class="karte karte--link" href="#/runde/${esc(runde.id)}/${esc(id)}">
          <span><strong>${esc(f.titel)}</strong><br><span class="gedaempft">${esc(f.kurz)}</span></span>
          <span class="pfeil" aria-hidden="true">›</span></a></li>`;
      })
      .join("");
    return `
      ${zurueck("#/start", "Start")}
      <h1 tabindex="-1">${esc(runde.titel)}</h1>
      <p class="lead">${esc(runde.einleitung)}</p>
      <ul class="liste-ohne">${karten}</ul>
      ${besprechen([
        "Variante A: Die Lehrperson wählt aus drei Fällen (wie hier in Runde 1).",
        "Variante B: Alle bekommen denselben Fall (wie in Runde 2). Was passt besser zu deiner Arbeit?",
      ])}`;
  }

  function frageFeld(frage, rundeId) {
    const name = `f_${frage.id}`;
    if (frage.typ === "skala") {
      const optionen = [1, 2, 3, 4, 5]
        .map(
          (n) => `<label class="skala__wert"><input type="radio" name="${name}" value="${n}"><span>${n}</span></label>`,
        )
        .join("");
      return `
        <fieldset class="feld">
          <legend>${esc(frage.frage)}</legend>
          <div class="skala">${optionen}</div>
          <div class="skala__pole"><span>${esc(frage.pole[0])}</span><span>${esc(frage.pole[1])}</span></div>
        </fieldset>`;
    }
    const id = `${rundeId}-${frage.id}`;
    return `
      <div class="feld">
        <label for="${id}">${esc(frage.frage)}</label>
        ${frage.hilfe ? `<p class="hilfe" id="${id}-hilfe">${esc(frage.hilfe)}</p>` : ""}
        <textarea id="${id}" name="${name}" rows="4"${frage.hilfe ? ` aria-describedby="${id}-hilfe"` : ""}></textarea>
      </div>`;
  }

  function antwortenBlock(eintrag, beschreibung) {
    return Object.entries(eintrag.antworten)
      .filter(([, w]) => typeof w === "number" || String(w ?? "").trim() !== "")
      .map(([id, w]) => {
        const runde = I.runden.find((r) => r.id === eintrag.rundeId);
        const frage = runde?.fragen.find((f) => f.id === id);
        const wert =
          typeof w === "number" && frage?.pole
            ? `${w} von 5 <span class="gedaempft">(1 = ${esc(frage.pole[0])}, 5 = ${esc(frage.pole[1])})</span>`
            : esc(w);
        return `<div class="antwort"><p class="antwort__frage">${esc(beschreibung.frage(id))}</p><p class="antwort__text">${wert}</p></div>`;
      })
      .join("");
  }

  function fallKarte(fall) {
    return `
      <section class="fall">
        <p class="ueberzeile">Fallbeispiel</p>
        <h2>${esc(fall.titel)}</h2>
        ${absaetze(fall.text)}
      </section>`;
  }

  function ansichtRunde(rundeId, fallId) {
    const runde = I.runden.find((r) => r.id === rundeId);
    if (!runde) return ansichtNichtGefunden();
    const status = L.rundenStatus(runde, zustand.woche, zustand.eintraege, ich());
    if (status === "erledigt") {
      const e = L.rundenEintrag(zustand.eintraege, ich(), runde.id);
      return { umleiten: `#/eintrag/${e.id}` };
    }
    if (status === "gesperrt") {
      return `
        ${zurueck("#/start", "Start")}
        <h1 tabindex="-1">${esc(runde.titel)}</h1>
        <p class="lead">Diese Runde ist ab Woche ${runde.ab} offen.</p>`;
    }
    if (runde.auswahl && !fallId) return ansichtFallwahl(runde);
    if (runde.auswahl && !runde.auswahl.includes(fallId)) return ansichtNichtGefunden();
    if (!runde.auswahl && fallId) return ansichtNichtGefunden();

    const fall = I.fallbeispiele[fallId || runde.fall] || null;
    let rueckblick = "";
    if (runde.rueckblickAuf) {
      const frueher = L.rundenEintrag(zustand.eintraege, ich(), runde.rueckblickAuf);
      const frueherRunde = I.runden.find((r) => r.id === runde.rueckblickAuf);
      rueckblick = frueher
        ? `<section class="karte karte--rueckblick">
            <p class="ueberzeile">Deine Antworten aus ${esc(frueherRunde.titel)}</p>
            ${frueher.fallId ? `<h2>${esc(I.fallbeispiele[frueher.fallId].titel)}</h2>` : ""}
            ${antwortenBlock(frueher, L.beschreibe(frueher, I))}
          </section>`
        : `<section class="karte karte--rueckblick"><p class="gedaempft">Du hast ${esc(frueherRunde.titel)} nicht ausgefüllt. Schau trotzdem auf die letzten Wochen zurück.</p></section>`;
    }

    return `
      ${zurueck(runde.auswahl ? `#/runde/${esc(runde.id)}` : "#/start", runde.auswahl ? "Andere Wahl" : "Start")}
      <h1 tabindex="-1">${esc(runde.titel)}</h1>
      ${runde.auswahl ? "" : `<p class="lead">${esc(runde.einleitung)}</p>`}
      ${fall ? fallKarte(fall) : ""}
      ${rueckblick}
      <form class="formular" data-form="runde" data-runde="${esc(runde.id)}" data-fall="${esc(fallId || "")}" novalidate>
        ${runde.fragen.map((f) => frageFeld(f, runde.id)).join("")}
        <p class="fehler" role="alert" hidden>Bitte beantworte mindestens eine Frage.</p>
        <button class="knopf" type="submit">Speichern</button>
      </form>
      ${besprechen([
        "Sollen Antworten nach dem Speichern noch änderbar sein?",
        "Braucht es ein Zwischenspeichern, falls man unterbrochen wird?",
        "Passen Freitext und Skala, oder lieber nur Freitext?",
      ])}`;
  }

  function ansichtNotiz(impulsId) {
    const impuls = I.impulse.find((i) => i.id === impulsId) || null;
    const leit = I.notiz.leitfragen
      .map(
        (l) => `<div class="feld"><label for="n-${esc(l.id)}">${esc(l.frage)}</label>
          <textarea id="n-${esc(l.id)}" name="f_${esc(l.id)}" rows="3"></textarea></div>`,
      )
      .join("");
    return `
      ${zurueck("#/start", "Start")}
      <h1 tabindex="-1">Neue Notiz</h1>
      <p class="lead">${esc(I.notiz.einleitung)}</p>
      ${impuls ? `<section class="karte karte--impuls"><p class="ueberzeile">Zum Impuls</p><p class="impuls__text">${esc(impuls.text)}</p></section>` : ""}
      <p class="hinweis">Bitte schreibe keine Namen von Kindern, Eltern oder Kolleg:innen auf.</p>
      <form class="formular" data-form="notiz" data-impuls="${esc(impuls ? impuls.id : "")}" novalidate>
        <div class="feld">
          <label for="n-frei">Deine Notiz</label>
          <textarea id="n-frei" name="f_frei" rows="6"></textarea>
        </div>
        <details class="aufklapp aufklapp--innen">
          <summary>Lieber mit Leitfragen schreiben</summary>
          <div class="aufklapp__inhalt">${leit}</div>
        </details>
        <p class="fehler" role="alert" hidden>Die Notiz ist noch leer.</p>
        <button class="knopf" type="submit">Speichern</button>
      </form>
      ${besprechen([
        "Freies Schreiben, Leitfragen oder beides?",
        "Wäre eine Sprachaufnahme statt Tippen hilfreich, z. B. direkt nach dem Unterricht?",
      ])}`;
  }

  function ansichtDanke(typ) {
    const text =
      typ === "runde"
        ? "Danke für deine Reflexion. Du kannst deine Antworten jederzeit unter «Meine Einträge» nachlesen."
        : "Deine Notiz ist gespeichert.";
    return `
      <div class="danke">
        <h1 tabindex="-1">Gespeichert</h1>
        <p class="lead">${esc(text)}</p>
        <div class="raster-2">
          <a class="knopf" href="#/start">Zur Startseite</a>
          <a class="knopf knopf--zweit" href="#/eintraege">Meine Einträge</a>
        </div>
      </div>`;
  }

  function eintragsKarte(e, href, mitPerson) {
    const b = L.beschreibe(e, I);
    const impuls = I.impulse.find((i) => i.id === e.impulsId);
    const titel = e.typ === "runde" ? b.art : impuls ? `Zum Impuls aus Woche ${impuls.woche}` : "Freie Notiz";
    return `
      <li><a class="karte karte--eintrag" href="${href}">
        <span class="eintrag__kopf">
          <span class="marke ${e.typ === "runde" ? "marke--runde" : ""}">${e.typ === "runde" ? "Runde" : "Notiz"}</span>
          <span class="gedaempft">${mitPerson ? esc(L.personName(I, e.personId)) + " · " : ""}${esc(L.formatDatum(e.erstellt))}</span>
        </span>
        <strong>${esc(titel)}${e.typ === "runde" && b.bezug ? ` · ${esc(b.bezug)}` : ""}</strong>
        <span class="eintrag__vorschau">${esc(vorschau(e))}</span>
      </a></li>`;
  }

  function ansichtEintraege() {
    const eigene = L.eintraegeVon(zustand.eintraege, ich());
    const liste = eigene.length
      ? `<ul class="liste-ohne">${eigene.map((e) => eintragsKarte(e, `#/eintrag/${esc(e.id)}`, false)).join("")}</ul>`
      : `<section class="karte"><p>Noch keine Einträge.</p><a class="knopf knopf--zweit" href="#/notiz">Erste Notiz schreiben</a></section>`;
    return `
      <h1 tabindex="-1">Meine Einträge</h1>
      <p class="lead">Alles, was du geschrieben hast. Nur du und die Projektleiterin sehen es.</p>
      ${liste}
      ${besprechen([
        "Liste wie hier, oder eher wie ein Tagebuch mit dem Datum als Überschrift?",
      ])}`;
  }

  function ansichtEintrag(id) {
    const e = zustand.eintraege.find((x) => x.id === id);
    // Eine Lehrperson darf nur eigene Einträge öffnen.
    if (!e || (istLp() && e.personId !== ich())) return ansichtNichtGefunden();
    const b = L.beschreibe(e, I);
    const fallId = e.fallId || I.runden.find((r) => r.id === e.rundeId)?.fall;
    const fall = e.typ === "runde" && fallId ? I.fallbeispiele[fallId] : null;
    const back = istAdmin() ? zurueck("#/admin", "Übersicht") : zurueck("#/eintraege", "Meine Einträge");
    return `
      ${back}
      <p class="ueberzeile">${istAdmin() ? esc(L.personName(I, e.personId)) + " · " : ""}${esc(L.formatDatum(e.erstellt))}</p>
      <h1 tabindex="-1">${esc(e.typ === "runde" ? b.art : "Notiz")}</h1>
      ${
        fall
          ? `<details class="karte aufklapp"><summary>Fallbeispiel: ${esc(fall.titel)}</summary><div class="aufklapp__inhalt">${absaetze(fall.text)}</div></details>`
          : ""
      }
      ${e.typ === "notiz" && b.bezug ? `<section class="karte karte--impuls"><p class="ueberzeile">Zum Impuls</p><p class="impuls__text">${esc(b.bezug)}</p></section>` : ""}
      <section class="karte">${antwortenBlock(e, b)}</section>`;
  }

  function ansichtAdmin(filter) {
    const uebersicht = L.zusammenfassung(zustand.eintraege, I);
    const personKarten = uebersicht
      .map(
        (z) => `
        <a class="karte karte--person${filter === z.person.id ? " ist-aktiv" : ""}" href="#/admin?person=${esc(z.person.id)}">
          <strong>${esc(z.person.name)}</strong>
          <span>Runden ${z.runden} von ${I.runden.length}</span>
          <span>${z.notizen} ${z.notizen === 1 ? "Notiz" : "Notizen"}</span>
          <span class="gedaempft">${z.letzter ? "zuletzt " + esc(L.formatDatum(z.letzter, false)) : "noch nichts"}</span>
        </a>`,
      )
      .join("");
    const alle = [...zustand.eintraege].sort((a, b) => b.erstellt.localeCompare(a.erstellt));
    const gefiltert = filter ? alle.filter((e) => e.personId === filter) : alle;
    const chips = [{ id: "", name: "Alle" }, ...I.personen]
      .map(
        (p) =>
          `<a class="chip${(filter || "") === p.id ? " ist-aktiv" : ""}" href="#/admin${p.id ? `?person=${esc(p.id)}` : ""}">${esc(p.name)}</a>`,
      )
      .join("");
    const impulse = I.impulse
      .map(
        (i) =>
          `<li class="${i.woche === zustand.woche ? "ist-aktuell" : ""}"><span class="marke">Woche ${i.woche}</span> ${esc(i.text)}</li>`,
      )
      .join("");
    return `
      <p class="ueberzeile">Projektleiterin · Woche ${zustand.woche} von ${I.wochen}</p>
      <h1 tabindex="-1">Übersicht</h1>
      <div class="raster-personen">${personKarten}</div>
      <section class="karte">
        <h2>Auswertung</h2>
        <p class="gedaempft">Alle Antworten als Tabelle, eine Zeile pro Antwort. Öffnet sich direkt in Excel.</p>
        <button class="knopf" data-export>Tabelle herunterladen</button>
      </section>
      <h2 class="abschnitt">Einträge</h2>
      <nav class="chips" aria-label="Nach Lehrperson filtern">${chips}</nav>
      ${
        gefiltert.length
          ? `<ul class="liste-ohne">${gefiltert.map((e) => eintragsKarte(e, `#/admin/eintrag/${esc(e.id)}`, true)).join("")}</ul>`
          : `<p class="gedaempft">Noch keine Einträge.</p>`
      }
      <section class="karte">
        <h2>Geplante Impulse</h2>
        <ul class="impulsliste">${impulse}</ul>
      </section>
      ${besprechen([
        "Möchtest du sehen, wer was geschrieben hat, oder reichen Kürzel?",
        "Liest du schon während der vier Wochen mit oder erst am Schluss? Das sollten die Lehrpersonen wissen.",
        "Brauchst du ausser der Tabelle noch etwas für die Auswertung?",
      ])}`;
  }

  function ansichtNichtGefunden() {
    return `
      <h1 tabindex="-1">Nicht gefunden</h1>
      <p class="lead">Diese Seite gibt es nicht.</p>
      <a class="knopf knopf--zweit" href="#/">Zum Anfang</a>`;
  }

  // ---------- Prototyp-Steuerung ----------

  function zeichneSteuerung() {
    const rolle = istLp()
      ? L.personName(I, ich())
      : istAdmin()
        ? "Projektleiterin"
        : "noch nicht gewählt";
    document.getElementById("steuerung-rolle").textContent = rolle;
    const wochen = document.getElementById("steuerung-wochen");
    wochen.innerHTML = Array.from({ length: I.wochen }, (_, i) => i + 1)
      .map(
        (w) =>
          `<button type="button" class="segment${w === zustand.woche ? " ist-aktiv" : ""}" data-woche="${w}" aria-pressed="${w === zustand.woche}">${w}</button>`,
      )
      .join("");
    document.getElementById("steuerung-hinweise").checked = zustand.hinweise;
  }

  // ---------- Router ----------

  function zerlege() {
    const roh = location.hash.replace(/^#/, "") || "/";
    const [pfad, query = ""] = roh.split("?");
    return { teile: pfad.split("/").filter(Boolean), params: new URLSearchParams(query) };
  }

  function route() {
    const { teile, params } = zerlege();
    const [a, b, c] = teile;

    if (!a || a === "wahl") {
      if (!a && istLp()) return { umleiten: "#/start" };
      if (!a && istAdmin()) return { umleiten: "#/admin" };
      return ansichtWahl();
    }
    if (a === "admin") {
      if (!istAdmin()) return { umleiten: "#/wahl" };
      if (b === "eintrag" && c) return ansichtEintrag(c);
      return ansichtAdmin(params.get("person"));
    }
    if (!istLp()) return { umleiten: "#/wahl" };
    switch (a) {
      case "start":
        return ansichtStart();
      case "info":
        return ansichtInfo();
      case "runde":
        return ansichtRunde(b, c);
      case "notiz":
        return ansichtNotiz(params.get("impuls"));
      case "danke":
        return ansichtDanke(b);
      case "eintraege":
        return ansichtEintraege();
      case "eintrag":
        return ansichtEintrag(b);
      default:
        return ansichtNichtGefunden();
    }
  }

  function zeichne() {
    const ergebnis = route();
    if (ergebnis && ergebnis.umleiten) {
      location.replace(ergebnis.umleiten);
      return;
    }
    app.innerHTML = ergebnis;
    document.body.classList.toggle("ohne-hinweise", !zustand.hinweise);
    tabs.hidden = !istLp();
    const aktiv = zerlege().teile[0] || "";
    tabs.querySelectorAll("a").forEach((t) => {
      const ziel = t.getAttribute("href").replace("#/", "");
      const an = ziel === aktiv || (ziel === "eintraege" && aktiv === "eintrag");
      t.classList.toggle("ist-aktiv", an);
      if (an) t.setAttribute("aria-current", "page");
      else t.removeAttribute("aria-current");
    });
    zeichneSteuerung();
    window.scrollTo(0, 0);
    const h1 = app.querySelector("h1");
    if (h1) h1.focus({ preventScroll: true });
  }

  // ---------- Ereignisse ----------

  function antwortenAus(form) {
    const antworten = {};
    for (const el of form.elements) {
      if (!el.name || !el.name.startsWith("f_")) continue;
      const id = el.name.slice(2);
      if (el.type === "radio") {
        if (el.checked) antworten[id] = Number(el.value);
      } else {
        antworten[id] = el.value;
      }
    }
    return antworten;
  }

  app.addEventListener("submit", (ev) => {
    const form = ev.target;
    ev.preventDefault();
    const antworten = antwortenAus(form);
    const fehler = form.querySelector(".fehler");
    if (!L.hatInhalt(antworten)) {
      fehler.hidden = false;
      return;
    }
    const basis = { id: S.neueId(), personId: ich(), antworten, erstellt: new Date().toISOString() };
    if (form.dataset.form === "runde") {
      zustand.eintraege.push({
        ...basis,
        typ: "runde",
        rundeId: form.dataset.runde,
        fallId: form.dataset.fall || null,
      });
      sichern();
      gehe("#/danke/runde");
    } else {
      zustand.eintraege.push({ ...basis, typ: "notiz", impulsId: form.dataset.impuls || null });
      sichern();
      gehe("#/danke/notiz");
    }
  });

  app.addEventListener("click", (ev) => {
    const ziel = ev.target.closest("button");
    if (!ziel) return;
    if (ziel.dataset.rolleLp) {
      zustand.rolle = { typ: "lp", personId: ziel.dataset.rolleLp };
      sichern();
      gehe("#/start");
    } else if ("rolleAdmin" in ziel.dataset) {
      zustand.rolle = { typ: "admin" };
      sichern();
      gehe("#/admin");
    } else if ("export" in ziel.dataset) {
      const blob = new Blob([L.csvExport(zustand.eintraege, I)], { type: "text/csv;charset=utf-8" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "reflexionsheft-eintraege.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    }
  });

  document.getElementById("steuerung").addEventListener("click", (ev) => {
    const knopf = ev.target.closest("button");
    if (!knopf) return;
    if (knopf.dataset.woche) {
      zustand.woche = Number(knopf.dataset.woche);
      sichern();
      // Ein offenes Formular nicht neu zeichnen, sonst ginge Getipptes verloren.
      if (app.querySelector("form")) zeichneSteuerung();
      else zeichne();
    } else if (knopf.id === "steuerung-wechseln") {
      zustand.rolle = null;
      sichern();
      gehe("#/wahl");
    } else if (knopf.id === "steuerung-reset") {
      zustand = S.zuruecksetzen();
      gehe("#/wahl");
    }
  });

  document.getElementById("steuerung-hinweise").addEventListener("change", (ev) => {
    zustand.hinweise = ev.target.checked;
    sichern();
    document.body.classList.toggle("ohne-hinweise", !zustand.hinweise);
  });

  window.addEventListener("hashchange", zeichne);
  zeichne();
})();
