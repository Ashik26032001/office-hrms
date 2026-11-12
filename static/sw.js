/**
 * SmartHR Attendance — Service Worker
 * Handles caching, offline support and background sync
 */

const CACHE_NAME    = 'smarthr-v1';
const OFFLINE_URL   = '/offline/';

// Files to cache immediately on install
const PRECACHE = [
    '/',
    '/accounts/login/',
    '/offline/',
    '/static/manifest.json',
    '/static/icons/icon-192x192.png',
    '/static/icons/icon-512x512.png',
    // Bootstrap + Chart.js from CDN cached locally
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js',
    'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js',
];

// ─── INSTALL ──────────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                // Cache what we can — ignore failures for CDN files
                return Promise.allSettled(
                    PRECACHE.map(url =>
                        cache.add(url).catch(e => console.warn('Cache miss:', url))
                    )
                );
            })
            .then(() => self.skipWaiting())
    );
});

// ─── ACTIVATE ─────────────────────────────────────────────────────────────────
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
            )
        ).then(() => self.clients.claim())
    );
});

// ─── FETCH ────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET and non-http requests
    if (request.method !== 'GET') return;
    if (!request.url.startsWith('http')) return;

    // API calls — network only (never cache scan results)
    const apiPaths = ['/attendance/scan/', '/attendance/face-scan/', '/attendance/fp/', '/attendance/api/'];
    if (apiPaths.some(p => url.pathname.startsWith(p))) {
        event.respondWith(
            fetch(request).catch(() =>
                new Response(JSON.stringify({ success: false, message: 'You are offline. Connect to network.' }),
                    { headers: { 'Content-Type': 'application/json' } })
            )
        );
        return;
    }

    // HTML pages — network first, fall back to cache, then offline page
    if (request.headers.get('Accept') && request.headers.get('Accept').includes('text/html')) {
        event.respondWith(
            fetch(request)
                .then(response => {
                    // Cache successful page loads
                    if (response.ok) {
                        const clone = response.clone();
                        caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
                    }
                    return response;
                })
                .catch(() =>
                    caches.match(request)
                        .then(cached => cached || caches.match(OFFLINE_URL))
                )
        );
        return;
    }

    // Static assets — cache first, then network
    event.respondWith(
        caches.match(request).then(cached => {
            if (cached) return cached;
            return fetch(request).then(response => {
                if (response.ok) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
                }
                return response;
            }).catch(() => new Response('', { status: 404 }));
        })
    );
});

// ─── PUSH NOTIFICATIONS ───────────────────────────────────────────────────────
self.addEventListener('push', event => {
    let data = { title: 'SmartHR', body: 'You have a new notification' };
    try {
        data = event.data ? event.data.json() : data;
    } catch (e) {}

    event.waitUntil(
        self.registration.showNotification(data.title, {
            body:    data.body,
            icon:    '/static/icons/icon-192x192.png',
            badge:   '/static/icons/icon-72x72.png',
            vibrate: [200, 100, 200],
            data:    { url: data.url || '/' },
            actions: [
                { action: 'view',    title: 'View' },
                { action: 'dismiss', title: 'Dismiss' },
            ]
        })
    );
});

self.addEventListener('notificationclick', event => {
    event.notification.close();
    if (event.action !== 'dismiss') {
        const url = event.notification.data?.url || '/';
        event.waitUntil(clients.openWindow(url));
    }
});
