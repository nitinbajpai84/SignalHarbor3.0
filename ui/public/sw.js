/* Signal Harbor service worker (G5). Three jobs and nothing more:
 * 1. keep the app shell, so the app opens with no network;
 * 2. keep the last Desk, Consume answer, note and family portal this person read, so they can still be read offline (network first: a fresh answer
 *    always wins, the kept one is used only when the network fails);
 * 3. show a notification when the push service wakes us. The push carries no words: we ask /api/v3/push/inbox for them.
 * Kept answers belong to one person: signing in or out empties them. Nothing that is not a GET of the lists below is ever kept, except the last Ask answer. */
const SHELL = "sh-shell-v1";
const DATA = "sh-data-v1";
const SHELL_URLS = ["/", "/manifest.webmanifest", "/brand/pwa-192.png", "/brand/pwa-512.png", "/brand/signal-harbor-mark-64.png"];
const KEEP = ["/api/v3/desk", "/api/v3/consume", "/api/v3/note", "/api/v3/board", "/api/v3/portal", "/api/auth/me"];
const LAST_ASK = "/__last-ask";

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_URLS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== SHELL && k !== DATA).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  );
});

const json = (body) => new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json", "X-Offline": "1" } });

async function networkFirst(req, cacheName, fallbackKey) {
  const cache = await caches.open(cacheName);
  try {
    const res = await fetch(req);
    if (res.ok) await cache.put(fallbackKey || req, res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(fallbackKey || req);
    if (hit) return hit;
    throw err;
  }
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  const path = url.pathname;

  // Signing in or out: the next person must not see the last person's kept answers.
  if (req.method === "POST" && (path === "/api/auth/logout" || path === "/api/auth/login")) {
    e.respondWith(fetch(req).finally(() => caches.delete(DATA)));
    return;
  }
  // The Ask answer: keep the last one; offline, say so and show it.
  if (req.method === "POST" && path === "/api/v3/ask") {
    e.respondWith((async () => {
      try {
        const res = await fetch(req);
        if (res.ok) await (await caches.open(DATA)).put(new Request(LAST_ASK), res.clone());
        return res;
      } catch (err) {
        const hit = await (await caches.open(DATA)).match(new Request(LAST_ASK));
        if (!hit) throw err;
        const last = await hit.json();
        return json({ ...last, answer: `You are offline. This is the last answer you saw, not an answer to this question: ${last.answer}`, trace: [], cached: true });
      }
    })());
    return;
  }
  if (req.method !== "GET") return;

  if (KEEP.includes(path)) {
    e.respondWith(networkFirst(req, DATA, new Request(path)));
    return;
  }
  if (path.startsWith("/api/")) return; // everything else in the API is always live
  if (req.mode === "navigate") {
    e.respondWith(networkFirst(req, SHELL, new Request("/")).catch(() => caches.match("/"))); // one shell for every in-app address
    return;
  }
  if (path.startsWith("/assets/") || path.startsWith("/brand/") || path === "/manifest.webmanifest") {
    // built files carry a hash in their name, so a kept copy is the right copy
    e.respondWith(caches.open(SHELL).then(async (c) => (await c.match(req)) || fetch(req).then((res) => { if (res.ok) c.put(req, res.clone()); return res; })));
  }
});

self.addEventListener("push", (e) => {
  e.waitUntil((async () => {
    let items = [];
    try {
      const res = await fetch("/api/v3/push/inbox", { credentials: "include" });
      if (res.ok) items = await res.json();
    } catch (err) { /* offline or signed out: the generic words below */ }
    if (!items.length) items = [{ title: "Signal Harbor", body: "Something new is waiting for you.", url: "/v3/desk" }];
    await Promise.all(items.slice(0, 3).map((i) => self.registration.showNotification(i.title, {
      body: i.body, icon: "/brand/pwa-192.png", badge: "/brand/signal-harbor-mark-64.png", tag: i.url, data: { url: i.url },
    })));
  })());
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/v3/desk";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((all) => {
    const open = all.find((c) => new URL(c.url).origin === self.location.origin);
    return open ? open.focus().then((c) => c.navigate(url)) : self.clients.openWindow(url);
  }));
});
