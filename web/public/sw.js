// Home hub service worker (plan.md M15): the app opens without the hub, showing
// the last data it saw, marked stale. Browsers only run it over HTTPS, so it is
// active on the Tailscale address (*.ts.net) and not on the plain LAN address.
//
// - Pages: network first, the cached page when the hub cannot be reached.
// - /assets/*: cache first; their names change with every build.
// - /api/* GETs: network first, and every good JSON answer is kept. Offline the
//   kept answer is served with "stale": true, so the cards say so.
// - /kiosk/ and anything not a GET are left alone.

const VERSION = 'v1'
const SHELL = `home-hub-shell-${VERSION}`
const ASSETS = `home-hub-assets-${VERSION}`
const API = `home-hub-api-${VERSION}`

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(SHELL).then((cache) => cache.add('/')).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (event) => {
  const keep = [SHELL, ASSETS, API]
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(names.filter((n) => !keep.includes(n)).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  const url = new URL(request.url)
  if (request.method !== 'GET' || url.origin !== self.location.origin) return
  if (url.pathname === '/kiosk' || url.pathname.startsWith('/kiosk/')) return

  if (request.mode === 'navigate') event.respondWith(page(request))
  else if (url.pathname.startsWith('/assets/')) event.respondWith(asset(request))
  else if (url.pathname.startsWith('/api/')) event.respondWith(api(request))
})

async function page(request) {
  try {
    const response = await fetch(request)
    if (response.ok) (await caches.open(SHELL)).put('/', response.clone())
    return response
  } catch {
    return (await caches.match('/', { cacheName: SHELL })) ?? Response.error()
  }
}

async function asset(request) {
  const cached = await caches.match(request, { cacheName: ASSETS })
  if (cached) return cached
  const response = await fetch(request)
  if (response.ok) (await caches.open(ASSETS)).put(request, response.clone())
  return response
}

async function api(request) {
  try {
    const response = await fetch(request)
    const json = (response.headers.get('content-type') ?? '').includes('application/json')
    if (response.ok && json) (await caches.open(API)).put(request, response.clone())
    return response
  } catch (error) {
    const cached = await caches.match(request, { cacheName: API })
    if (!cached) throw error
    return markStale(cached)
  }
}

// The kept answer, flagged stale when it is one of the hub's payloads.
async function markStale(response) {
  try {
    const body = await response.clone().json()
    if (body && typeof body === 'object' && !Array.isArray(body) && 'stale' in body) {
      return new Response(JSON.stringify({ ...body, stale: true }), {
        headers: { 'Content-Type': 'application/json', 'X-Served-By': 'service-worker' },
      })
    }
  } catch {
    // not JSON after all: serve it as kept
  }
  return response
}
