// Service Worker für Benachrichtigungen (#37). Zeigt eingehende Nachrichten an und öffnet
// beim Tippen das Instrument. Bewusst ohne Zwischenspeicher und ohne fetch-Handler.

self.addEventListener("push", (ereignis) => {
  let daten = { titel: "Reflexionsinstrument", text: "" };
  try {
    daten = { ...daten, ...ereignis.data.json() };
  } catch {
    // Ohne lesbaren Inhalt trotzdem eine Benachrichtigung zeigen (Pflicht bei userVisibleOnly).
  }
  ereignis.waitUntil(
    self.registration.showNotification(daten.titel, {
      body: daten.text,
      icon: "/static/bilder/symbol-192.png",
      lang: "de",
    }),
  );
});

self.addEventListener("notificationclick", (ereignis) => {
  ereignis.notification.close();
  ereignis.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((fenster) => {
      const offen = fenster.find((f) => new URL(f.url).origin === self.location.origin);
      return offen ? offen.focus() : self.clients.openWindow("/");
    }),
  );
});
