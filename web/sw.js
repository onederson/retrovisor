// Service worker do painel: guarda a "casca" (HTML/CSS/JS) para o celular abrir o portao
// mesmo com o PC desligado; quando o PC volta, o WebSocket reconecta sozinho.
const CACHE = 'painel-v8';
const CASCA = ['/', '/static/style.css', '/static/app.js', '/static/manifest.json', '/static/icone-192.png', '/static/icone-512.png'];

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CASCA)).catch(() => {}));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== self.location.origin) return;
  const casca = url.pathname === '/' || url.pathname.startsWith('/static/');
  if (!casca) return; // /ws, /actions, /action: sempre rede

  // Rede primeiro (sempre a versao nova); sem PC, a copia guardada. A chave ignora ?v= e ?t=.
  const chave = url.pathname;
  // PC desligado: o firewall do Windows descarta a conexao em silencio, entao sem limite o
  // celular ficaria minutos esperando. Em 2,5 s sem resposta, usa a copia guardada.
  const ctrl = new AbortController();
  const limite = setTimeout(() => ctrl.abort(), 2500);
  e.respondWith(
    fetch(e.request, { signal: ctrl.signal })
      .then((resp) => {
        clearTimeout(limite);
        if (resp.ok) {
          const copia = resp.clone();
          caches.open(CACHE).then((c) => c.put(chave, copia));
        }
        return resp;
      })
      .catch(() => caches.match(chave).then((r) => r || Response.error()))
  );
});
