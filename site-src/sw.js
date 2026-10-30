/* Service worker: makes the serverless build installable and playable with no connection.
 *
 * The cache name and the asset list below are filled in by `scripts/make_site.py`. Every asset URL
 * carries the build's content hash, so a cached asset never goes stale — a new build asks
 * for new URLs. That is also why this file changes on every build, which is what makes the
 * browser install the new worker at all.
 *
 * The page itself is the one URL without a hash. It goes to the network first, so a deploy
 * reaches anyone online; the cache only answers when the network does not. Serving a cached
 * page first would pair an old page with a cache the new worker has already deleted.
 */

const CACHE = "krass-jass-__VERSION__";
const ASSETS = __ASSETS__;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET" || new URL(request.url).origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put("./", copy));
          }
          return response;
        })
        .catch(() => caches.match("./")),
    );
    return;
  }

  event.respondWith(caches.match(request).then((hit) => hit || fetch(request)));
});
