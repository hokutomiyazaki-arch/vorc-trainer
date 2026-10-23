// Service Worker ─ VORC トレーニング（Functional Neuro Training）。手本：~/FNT-Apps/pinto-8/sw.js
// 戦略：Network First（新しいコードを最優先で拾う）。オフライン時のみキャッシュへ。
// index.html 側で controllerchange を検知して location.reload() する。
// 🔴 index.html や voice/ を変えたら CACHE_NAME の版を上げる（古いキャッシュが消える）
const CACHE_NAME = 'vorc-trainer-v1.12.0';

const ASSETS_TO_CACHE = [
  './',
  './index.html',
  './manifest.json',
  './FNT512.png',
  './FNT512-transparent.png',
  './icons/icon-192.png',
  './voice/index.json',
  './voice/unlock.mp3'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(ASSETS_TO_CACHE))
      .then(() => self.skipWaiting())
      .catch((err) => console.error('[SW] precache failed', err))
  );
});

// 古いキャッシュを削除して即 claim
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names.map((name) => (name !== CACHE_NAME) ? caches.delete(name) : null)))
      .then(() => self.clients.claim())
  );
});

// Network First。対象は同一オリジン＋Google Fonts（顔の読み取りの部品＝jsdelivr・googleapis の大きいファイルはブラウザに任せる）
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = req.url;
  const sameOrigin = url.startsWith(self.location.origin);
  const isFont = url.startsWith('https://fonts.');
  if (!sameOrigin && !isFont) return;
  if (sameOrigin && /[?&]sig=/.test(url)) return;   // 公開中の版と比べる取得（index.html の pageSig）はキャッシュしない
  if (req.headers.has('range')) return;              // 音声の部分取得はそのまま通す
  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.status === 200 && (res.type === 'basic' || res.type === 'cors')) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
        }
        return res;
      })
      .catch(() =>
        caches.match(req).then((cached) => {
          if (cached) return cached;
          if (req.mode === 'navigate') return caches.match('./index.html');
          return new Response('Offline', { status: 503, statusText: 'Offline' });
        })
      )
  );
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});
