// Service worker de Gregal Trace: lo que hace falta para poder instalar la web como app.
// No guarda páginas de la aplicación (cambian a cada momento y son privadas de cada usuario):
// solo guarda la página «Sin conexión» para enseñarla si no hay cobertura.
const CACHE = 'gregal-trace-v1';
const SIN_CONEXION = '{% url "sin_conexion" %}';

self.addEventListener('install', function (evento) {
    evento.waitUntil(caches.open(CACHE).then(function (cache) { return cache.add(SIN_CONEXION); }));
    self.skipWaiting();
});

self.addEventListener('activate', function (evento) {
    // Borra cachés de versiones anteriores
    evento.waitUntil(caches.keys().then(function (claves) {
        return Promise.all(claves.filter(function (c) { return c !== CACHE; }).map(function (c) { return caches.delete(c); }));
    }));
    self.clients.claim();
});

self.addEventListener('fetch', function (evento) {
    // Solo las páginas (navegación): si falla la red, «Sin conexión». El resto va directo a internet.
    if (evento.request.mode === 'navigate') {
        evento.respondWith(fetch(evento.request).catch(function () { return caches.match(SIN_CONEXION); }));
    }
});
