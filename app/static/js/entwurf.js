// Entwurfsschutz: Text, der noch nicht gespeichert ist, bleibt im Browser-Tab erhalten.
// sessionStorage endet mit dem Tab. Die Seiten funktionieren auch ohne dieses Skript.
(function () {
  "use strict";
  var PRAEFIX = "entwurf:";

  function lies(schluessel) {
    try {
      return sessionStorage.getItem(schluessel);
    } catch (e) {
      return null;
    }
  }

  function schreibe(schluessel, wert) {
    try {
      if (wert === null) sessionStorage.removeItem(schluessel);
      else sessionStorage.setItem(schluessel, wert);
    } catch (e) {
      // Speicher gesperrt oder voll: dann gibt es eben keinen Schutz.
    }
  }

  function loescheAlle(vorsatz) {
    try {
      for (var i = sessionStorage.length - 1; i >= 0; i--) {
        var k = sessionStorage.key(i);
        if (k && k.indexOf(vorsatz) === 0) sessionStorage.removeItem(k);
      }
    } catch (e) {}
  }

  // Wie auf dem Server (app/eingaben.py): Zeilenenden vereinheitlichen, Rand abschneiden.
  function norm(text) {
    return text.replace(/\r\n?/g, "\n").trim();
  }

  function schuetze(formular) {
    var vorsatz = PRAEFIX + formular.getAttribute("data-entwurf") + ":";
    var felder = formular.querySelectorAll("textarea[name]");
    var hinweis = formular.querySelector("[data-entwurf-hinweis]");
    // Auf einer Fehlerseite ist der Feldwert der abgelehnte Text, nicht der gespeicherte.
    var mitFehler = !!formular.querySelector(".fehler");
    var wiederhergestellt = false;

    felder.forEach(function (feld) {
      var schluessel = vorsatz + feld.name;
      var entwurf = lies(schluessel);
      if (entwurf !== null) {
        if (norm(entwurf) === norm(feld.defaultValue)) {
          if (!mitFehler) schreibe(schluessel, null);
        } else {
          feld.value = entwurf;
          wiederhergestellt = true;
        }
      }
      feld.addEventListener("input", function () {
        var gleich = norm(feld.value) === norm(feld.defaultValue);
        schreibe(schluessel, gleich ? null : feld.value);
      });
    });

    if (!hinweis) return;
    hinweis.hidden = !wiederhergestellt;
    var knopf = hinweis.querySelector("button");
    if (knopf) {
      knopf.addEventListener("click", function () {
        loescheAlle(vorsatz);
        felder.forEach(function (feld) {
          feld.value = feld.defaultValue;
        });
        hinweis.hidden = true;
      });
    }
  }

  // Nach dem Anlegen: Den Entwurf des Formulars «neu» nur löschen, wenn er dem gespeicherten
  // Text dieser Seite entspricht. Ein anderer, noch nicht gespeicherter Entwurf bleibt.
  document.querySelectorAll("form[data-entwurf-verwerfen]").forEach(function (formular) {
    var feld = formular.querySelector("textarea[name='text']");
    if (!feld || formular.querySelector(".fehler")) return;
    var schluessel = PRAEFIX + formular.getAttribute("data-entwurf-verwerfen") + ":text";
    var entwurf = lies(schluessel);
    if (entwurf !== null && norm(entwurf) === norm(feld.defaultValue)) schreibe(schluessel, null);
  });
  document.querySelectorAll("form[data-entwurf]").forEach(schuetze);
  document.querySelectorAll("form[action='/abmelden']").forEach(function (formular) {
    formular.addEventListener("submit", function () {
      loescheAlle(PRAEFIX);
    });
  });
})();
