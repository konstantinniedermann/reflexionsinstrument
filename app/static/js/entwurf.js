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

  // Wie auf dem Server: Zeilenenden vereinheitlichen, Rand abschneiden.
  function norm(text) {
    return text.replace(/\r\n/g, "\n").trim();
  }

  function schuetze(formular) {
    var vorsatz = PRAEFIX + formular.getAttribute("data-entwurf") + ":";
    var felder = formular.querySelectorAll("textarea[name]");
    var hinweis = formular.querySelector("[data-entwurf-hinweis]");
    var wiederhergestellt = false;

    felder.forEach(function (feld) {
      var schluessel = vorsatz + feld.name;
      var entwurf = lies(schluessel);
      if (entwurf !== null) {
        if (norm(entwurf) === norm(feld.defaultValue)) {
          schreibe(schluessel, null);
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

  document.querySelectorAll("form[data-entwurf-verwerfen]").forEach(function (formular) {
    loescheAlle(PRAEFIX + formular.getAttribute("data-entwurf-verwerfen") + ":");
  });
  document.querySelectorAll("form[data-entwurf]").forEach(schuetze);
  document.querySelectorAll("form[action='/abmelden']").forEach(function (formular) {
    formular.addEventListener("submit", function () {
      loescheAlle(PRAEFIX);
    });
  });
})();
