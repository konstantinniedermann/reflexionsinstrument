// Benachrichtigungen auf diesem Gerät ein- und ausschalten (#37).
// Zeigt in [data-benachrichtigung] den passenden Zustand; Abo und Kündigung gehen per
// Formular-POST (mit CSRF-Feld der Seite) an den Server.
(() => {
  const box = document.querySelector("[data-benachrichtigung]");
  if (!box) return;

  const ort = box.dataset.ort;
  const schluessel = box.dataset.pushSchluessel;
  const csrf = box.querySelector('input[name="csrf"]').value;
  const meldung = box.querySelector("[data-meldung]");
  const SPAETER = "benachrichtigung-spaeter";

  const agent = navigator.userAgent;
  // iPadOS meldet sich als Mac; erkennbar an der Touch-Bedienung.
  const istIos = /iPhone|iPad|iPod/.test(agent) || (/Macintosh/.test(agent) && navigator.maxTouchPoints > 1);
  const installiert = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const moeglich = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

  function spaeterGewaehlt() {
    try {
      return localStorage.getItem(SPAETER) === "1";
    } catch {
      return false;
    }
  }

  function zeige(zustand, sichtbar) {
    for (const teil of box.querySelectorAll("[data-zustand]")) {
      teil.hidden = teil.dataset.zustand !== zustand;
    }
    // Auf der Startseite nur als Einladung, sonst immer.
    const einladung = (zustand === "aus" || zustand === "ios") && !spaeterGewaehlt();
    box.hidden = !(sichtbar || ort !== "start" || einladung);
  }

  function fehler(text) {
    meldung.textContent = text;
    meldung.hidden = false;
  }

  function base64url(bytes) {
    return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function bytesAus(wert) {
    const roh = atob(wert.replace(/-/g, "+").replace(/_/g, "/"));
    return Uint8Array.from(roh, (z) => z.charCodeAt(0));
  }

  async function melde(pfad, felder) {
    const daten = new FormData();
    daten.append("csrf", csrf);
    for (const [name, wert] of Object.entries(felder)) daten.append(name, wert);
    // redirect: "manual" – eine abgelaufene Anmeldung leitet um und darf nicht als Erfolg gelten.
    const antwort = await fetch(pfad, { method: "POST", body: daten, credentials: "same-origin", redirect: "manual" });
    if (!antwort.ok) throw new Error(`Status ${antwort.status}`);
  }

  function anmelden(abo) {
    const { endpoint, keys } = abo.toJSON();
    return melde("/benachrichtigung/abo", { endpunkt: endpoint, p256dh: keys.p256dh, auth: keys.auth });
  }

  function passenderSchluessel(abo) {
    const k = abo.options && abo.options.applicationServerKey;
    return !k || base64url(new Uint8Array(k)) === schluessel;
  }

  // Ist der Push-Dienst nicht erreichbar, kann das Abo ohne Antwort hängen bleiben.
  const ZEITLIMIT = 20000;

  function mitZeitlimit(versprechen) {
    let uhr;
    const ablauf = new Promise((_, ablehnen) => {
      uhr = setTimeout(() => ablehnen(new Error("Zeitüberschreitung")), ZEITLIMIT);
    });
    return Promise.race([versprechen, ablauf]).finally(() => clearTimeout(uhr));
  }

  async function abschliessen(registrierung) {
    await navigator.serviceWorker.ready;
    return mitZeitlimit(
      registrierung.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: bytesAus(schluessel) }),
    );
  }

  async function einschalten() {
    meldung.hidden = true;
    try {
      // Die Erlaubnis muss direkt im Tippen angefragt werden (iOS).
      const erlaubnis = await Notification.requestPermission();
      if (erlaubnis !== "granted") {
        zeige(erlaubnis === "denied" ? "abgelehnt" : "aus", true);
        return;
      }
      const registrierung = await navigator.serviceWorker.register("/sw.js");
      await anmelden(await abschliessen(registrierung));
      zeige("an", true);
    } catch {
      fehler("Das hat nicht geklappt. Bitte die Seite neu laden und nochmals versuchen.");
    }
  }

  async function ausschalten() {
    meldung.hidden = true;
    try {
      const registrierung = await navigator.serviceWorker.getRegistration();
      const abo = registrierung && (await registrierung.pushManager.getSubscription());
      if (abo) {
        // Zuerst im Browser kündigen: Scheitert danach die Meldung an den Server, lehnt der
        // Push-Dienst das alte Abo beim nächsten Versand ab, und der Server entfernt es.
        await abo.unsubscribe();
        await melde("/benachrichtigung/abo/loeschen", { endpunkt: abo.endpoint });
      }
      zeige("aus", true);
    } catch {
      fehler("Das hat nicht geklappt. Bitte die Seite neu laden und nochmals versuchen.");
    }
  }

  async function pruefe() {
    if (!moeglich) {
      zeige(istIos && !installiert ? "ios" : "unmoeglich");
      return;
    }
    if (Notification.permission === "denied") {
      zeige("abgelehnt");
      return;
    }
    try {
      const registrierung = await navigator.serviceWorker.register("/sw.js");
      let abo = await registrierung.pushManager.getSubscription();
      // Neuer Schlüssel auf dem Server: altes Abo kündigen und ohne Rückfrage neu abschliessen.
      if (abo && !passenderSchluessel(abo)) {
        await abo.unsubscribe();
        abo = Notification.permission === "granted" ? await abschliessen(registrierung) : null;
      }
      if (abo) {
        // Erneut melden: deckt Kontowechsel und vom Server entfernte Abos ab.
        await anmelden(abo);
        zeige("an");
      } else {
        zeige("aus");
      }
    } catch {
      zeige("aus");
    }
  }

  // Während ein Vorgang läuft, sind die Knöpfe gesperrt (kein doppeltes Einschalten).
  async function gesperrt(vorgang) {
    const knoepfe = box.querySelectorAll("button");
    for (const k of knoepfe) k.disabled = true;
    try {
      await vorgang();
    } finally {
      for (const k of knoepfe) k.disabled = false;
    }
  }

  box.addEventListener("click", (ereignis) => {
    const aktion = ereignis.target.closest("[data-aktion]")?.dataset.aktion;
    if (aktion === "ein") gesperrt(einschalten);
    else if (aktion === "aus") gesperrt(ausschalten);
    else if (aktion === "spaeter") {
      try {
        localStorage.setItem(SPAETER, "1");
      } catch {
        // Ohne Speicher erscheint die Einladung beim nächsten Mal wieder.
      }
      box.hidden = true;
    }
  });

  pruefe();
})();
