// Terry AI Agent — Service Worker v2
// Caching strategies: Cache-First for static assets, Network-First for API, Stale-While-Revalidate for pages

const CACHE_VERSION = 'terry-sw-v2';
const STATIC_CACHE = `static-${CACHE_VERSION}`;
const API_CACHE = `api-${CACHE_VERSION}`;
const PAGE_CACHE = `pages-${CACHE_VERSION}`;
const MAX_STATIC_ITEMS = 50;
const MAX_PAGE_ITEMS = 20;
const MAX_API_ITEMS = 30;

// Assets to pre-cache on install
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/install.html',
  '/manifest.json',
  '/offline.html',
];

// ── Install: Pre-cache critical assets ──
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: Clean old caches ──
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((name) => name !== STATIC_CACHE && name !== API_CACHE && name !== PAGE_CACHE)
          .map((name) => caches.delete(name))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Fetch: Route-based caching ──
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  // SSE stream: Never cache (must check before /api/ prefix)
  if (url.pathname === '/api/stream') {
    event.respondWith(fetch(event.request));
    return;
  }

  // API requests: Network-First (always try fresh, fallback to cache)
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(event.request, API_CACHE));
    return;
  }

  // Static assets (JS, CSS, images, fonts): Cache-First
  if (isStaticAsset(url.pathname)) {
    event.respondWith(cacheFirst(event.request, STATIC_CACHE));
    return;
  }

  // Pages (HTML): Stale-While-Revalidate
  event.respondWith(staleWhileRevalidate(event.request, PAGE_CACHE));
});

// ── Strategy: Network-First ──
async function networkFirst(request, cacheName) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      await updateCache(cacheName, request, networkResponse, MAX_API_ITEMS);
    }
    return networkResponse;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    // For API failures, return a JSON error
    return new Response(
      JSON.stringify({ error: 'Offline — Terry server not reachable', offline: true }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

// ── Strategy: Cache-First ──
async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      await updateCache(cacheName, request, networkResponse, MAX_STATIC_ITEMS);
    }
    return networkResponse;
  } catch {
    return new Response('Offline', { status: 503 });
  }
}

// ── Strategy: Stale-While-Revalidate ──
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  // Start background update (don't await - let it run in background)
  const fetchPromise = fetch(request)
    .then((networkResponse) => {
      if (networkResponse.ok) {
        updateCache(cacheName, request, networkResponse, MAX_PAGE_ITEMS);
      }
      return networkResponse;
    })
    .catch(() => cached || offlinePage());

  // Return cache immediately if available, update in background
  if (cached) {
    fetchPromise.catch(() => {}); // Prevent unhandled rejection
    return cached;
  }

  // No cache: wait for network or offline page
  return fetchPromise;
}

// ── Offline fallback page ──
async function offlinePage() {
  const cached = await caches.match('/offline.html');
  if (cached) return cached;
  return new Response(
    '<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Terry — Offline</title>'
    + '<style>body{font-family:-apple-system,sans-serif;background:#1a1a2e;color:#e0e0e0;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;padding:20px}'
    + '.c{max-width:400px}.icon{font-size:64px;margin-bottom:16px}h1{color:#00d4aa;font-size:20px}p{color:#a0a0b0;font-size:14px;line-height:1.6}'
    + 'button{background:#00d4aa;color:#1a1a2e;border:none;padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;margin-top:16px}'
    + '</style></head><body><div class="c"><div class="icon">🤖</div><h1>Terry is Offline</h1>'
    + '<p>The Terry server is not reachable right now. Check your network connection or restart the server with <code>terry webui</code>.</p>'
    + '<button onclick="location.reload()">Retry</button></div></body></html>',
    { status: 200, headers: { 'Content-Type': 'text/html' } }
  );
}

// ── Helpers ──
function isStaticAsset(pathname) {
  return /\.(js|css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot|webp)(\?.*)?$/.test(pathname);
}

// Enforce cache size limits to prevent unbounded growth
async function trimCache(cacheName, maxItems) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  if (keys.length > maxItems) {
    const toDelete = keys.slice(0, keys.length - maxItems);
    for (const key of toDelete) {
      cache.delete(key);
    }
  }
}

async function updateCache(cacheName, request, response, maxItems) {
  const cache = await caches.open(cacheName);
  await cache.put(request, response.clone());
  await trimCache(cacheName, maxItems);
}

// ── Push Notifications (optional, opt-in) ──
self.addEventListener('push', (event) => {
  if (!event.data) return;
  const data = event.data.json();

  const notificationOptions = {
    body: data.body || 'Task completed',
    data: { url: data.url || '/' },
  };

  // Only add icon/badge if provided in push data
  if (data.icon) {
    notificationOptions.icon = data.icon;
  }
  if (data.badge) {
    notificationOptions.badge = data.badge;
  }

  event.waitUntil(
    self.registration.showNotification(data.title || 'Terry', notificationOptions)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes(url) && 'focus' in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
