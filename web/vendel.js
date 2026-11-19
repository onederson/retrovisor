// Vendel: o bichinho da tela 8. Cada janela (sessao) do Claude Code vira um Vendel que mostra o que
// ela esta fazendo. Os dados chegam pelo WebSocket em dados.mini (server/mini.py) e o app.js repassa
// com window.Vendel.atualizar(mini, dados). Sem toque por 2 min, o painel vem sozinho para esta tela.
// Ele tambem tem humor (server/humor.py), conversa por voz e faz perguntas para melhorar a memoria
// (cerebro do Vendel, projeto Vendel, via /vendel/* em server/cerebro.py).
(() => {
  'use strict';

  const G = {
    corpo: '#0C120E', sombra: '#050806', brilho: '#2B3A30', borda: '#1C6B28',
    luz: '#5CFF4A', forte: '#D2FFC4', fraca: '#1F8A2C', w: '#F2FFF0', yel: '#F2E14E',
    tinta: '#061008', coracao: '#FF6B9A', gota: '#7FC8FF'
  };
  const ATIVOS = new Set(['pensando', 'digitando', 'lendo', 'executando', 'delegando', 'trabalhando']);
  const ROTULO = {
    ocioso: 'à toa', pensando: 'pensando', digitando: 'escrevendo', lendo: 'lendo',
    executando: 'rodando comando', delegando: 'chamou ajudante', trabalhando: 'trabalhando',
    precisa: 'precisa de você', concluido: 'terminou!', dormindo: 'dormindo'
  };
  const HUMOR_ROTULO = { animado: 'animado', curioso: 'curioso', tranquilo: 'tranquilo', sonolento: 'com sono', carente: 'carente' };
  const REPOUSO_MS = 120000;   // sem toque: o painel vem para o Vendel
  const DORMIR_MS = 600000;    // sem nada acontecendo: ele dorme
  const MAX_VISIVEIS = 4;

  const secao = document.getElementById('tela-vendel');
  if (!secao) return;
  const canvas = secao.querySelector('.vendel-canvas');
  const ctx = canvas.getContext('2d');
  const camada = secao.querySelector('.vendel-camada');
  const rotulosEl = secao.querySelector('.vendel-rotulos');
  const resumoEl = secao.querySelector('.vendel-resumo');
  const horaEl = secao.querySelector('.vendel-hora');
  const falaEl = secao.querySelector('.vendel-fala');
  const perguntaEl = secao.querySelector('.vendel-pergunta');
  const digitarEl = secao.querySelector('.vendel-digitar');
  const painelEl = secao.querySelector('.vendel-painel');
  const faixa = document.getElementById('vendel-faixa');

  const guardado = (chave, padrao) => { try { return localStorage.getItem(chave) ?? padrao; } catch (e) { return padrao; } };
  const guardar = (chave, valor) => { try { localStorage.setItem(chave, valor); } catch (e) {} };
  const enviarWs = (obj) => { if (window.painelEnviar) window.painelEnviar(obj); };
  function urlPainel(rota) {
    const t = new URLSearchParams(location.search).get('t');
    return t ? `${rota}${rota.includes('?') ? '&' : '?'}t=${encodeURIComponent(t)}` : rota;
  }

  // ---------- grade de pixels ----------
  let W = 0, H = 0, escala = 6, base = 30;
  function dimensionar() {
    const r = (secao.querySelector('.vendel-palco') || secao).getBoundingClientRect();
    if (!r.width || !r.height) return false;
    escala = Math.max(3, Math.floor(r.height / 52)); // ~52 px de altura: o Vendel ocupa metade da tela
    W = Math.floor(r.width / escala);
    H = Math.floor(r.height / escala);
    canvas.width = W; canvas.height = H;
    base = H - 22; // pes em base+10, sobra espaco para os rotulos embaixo
    return true;
  }

  let ox = 0, oy = 0;          // deslocamento lento da cena inteira (OLED)
  let mascara = 1, semente = 1; // mascara < 1: o Vendel esta se montando/desfazendo
  function ruido(x, y) {
    let n = (Math.imul(x, 374761393) + Math.imul(y, 668265263)) ^ semente;
    n = Math.imul(n ^ (n >>> 13), 1274126177);
    return ((n ^ (n >>> 16)) >>> 0) / 4294967296;
  }
  function P(x, y, w, h, col) {
    x = Math.round(x) + ox; y = Math.round(y) + oy;
    ctx.fillStyle = col;
    if (mascara >= 1) { ctx.fillRect(x, y, w, h); return; }
    for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
      if (ruido(x + i, y + j) < mascara) ctx.fillRect(x + i, y + j, 1, 1);
    }
  }

  // ---------- corpo ----------
  function expandir(pts) {
    const out = [];
    for (let i = 0; i < pts.length - 1; i++) {
      let [x, y] = pts[i]; const [x2, y2] = pts[i + 1];
      const dx = Math.sign(x2 - x), dy = Math.sign(y2 - y);
      while (x !== x2 || y !== y2) {  // cada eixo para ao chegar (diagonal torta nao vira laco infinito)
        out.push([x, y]);
        if (x !== x2) x += dx;
        if (y !== y2) y += dy;
      }
    }
    out.push(pts[pts.length - 1]);
    return out;
  }
  const CIRCUITOS = [
    expandir([[-4, -11], [4, -11]]),
    expandir([[-9, -3], [-7, -3], [-7, 1], [-3, 1]]),
    expandir([[9, -3], [7, -3], [7, 1], [3, 1]]),
    expandir([[0, 5], [0, 8]]),
    expandir([[-5, -11], [-6, -9]]),
    expandir([[5, -11], [6, -9]])
  ];

  function dentro(x, y, achata) {
    let ys = y;
    if (achata && y < 6) ys = 6 + (y - 6) * 2.2;
    const cabeca = (x * x) / 100 + ((ys + 5) * (ys + 5)) / 64 <= 1;
    const tronco = ys >= 0 && ys <= 8 && Math.abs(x) <= 7 - (ys >= 7 ? ys - 6 : 0);
    const pes = !achata && ys >= 9 && ys <= 10 && Math.abs(x) >= 2 && Math.abs(x) <= 5;
    const poca = achata && y >= 8 && y <= 10 && Math.abs(x) <= 12 - (y - 8) * 2;
    return cabeca || tronco || pes || poca;
  }

  function corpo(p, t) {
    const { cx, cy } = p;
    const ach = p.dorme;
    const fy = (y) => (ach && y < 6 ? Math.round(6 + (y - 6) / 2.2) : y);
    for (let y = -14; y <= 10; y++) {
      const balanco = p.balanca && y < -4 ? Math.round(Math.sin(t * p.velBalanco + y * 0.35 + p.fase) * 0.7) : 0;
      for (let x = -13; x <= 13; x++) {
        if (!dentro(x, y, ach)) continue;
        const borda = !dentro(x - 1, y, ach) || !dentro(x + 1, y, ach) || !dentro(x, y - 1, ach) || !dentro(x, y + 1, ach);
        let col = (x * 0.5 + y * 0.5 > 4) ? G.sombra : G.corpo;
        if (borda) col = G.borda;
        P(cx + x + balanco, cy + y, 1, 1, col);
      }
    }
    if (!ach) { P(cx - 6, cy - 11, 3, 1, G.brilho); P(cx - 7, cy - 10, 1, 2, G.brilho); }

    const alfa = ctx.globalAlpha;
    ctx.globalAlpha = alfa * (ach ? 0.35 : 1);
    for (const linha of CIRCUITOS) for (const [x, y] of linha) P(cx + x, cy + fy(y), 1, 1, p.luzes >= 1 ? G.luz : G.fraca);
    ctx.globalAlpha = alfa;
    if (p.velPulso > 0) {
      CIRCUITOS.forEach((linha, k) => {
        const i = Math.floor(t * p.velPulso + k * 3 + p.fase * 5) % (linha.length + 4);
        if (i < linha.length) { const [x, y] = linha[i]; P(cx + x, cy + fy(y), 1, 1, G.forte); }
      });
    }
    ctx.globalAlpha = alfa * (ach ? 0.3 : 0.55 + 0.45 * Math.sin(t * 3 + p.fase));
    P(cx - 2, cy + 1, 5, 3, G.luz); P(cx - 1, cy + 2, 3, 1, G.forte);
    ctx.globalAlpha = alfa;

    for (const s of [-1, 1]) {
      const st = s < 0 ? p.armL : p.armR;
      if (st === 'down') { const bx = s < 0 ? cx - 9 : cx + 8; P(bx, cy + 1, 2, 4, G.borda); P(bx, cy + 4, 2, 1, G.luz); }
      else if (st === 'mid') { const bx = s < 0 ? cx - 12 : cx + 11; P(bx, cy - 1, 2, 3, G.borda); P(bx, cy - 1, 2, 1, G.luz); }
      else if (st === 'up') { const bx = s < 0 ? cx - 12 : cx + 11; P(bx, cy - 7, 2, 5, G.borda); P(bx, cy - 7, 2, 1, G.luz); }
    }

    const ey = cy + fy(-6);
    if (p.vendado && !ach) {  // modo cego: venda nos olhos (a camera esta desligada)
      P(cx - 10, ey - 1, 21, 4, G.borda); P(cx - 9, ey, 19, 2, '#123d19');
      P(cx + 10, ey, 2, 1, G.borda); P(cx + 11, ey + 1, 2, 2, G.borda); P(cx + 12, ey + 3, 1, 2, G.borda);
    }
    if (!p.vendado || ach) [cx - 6, cx + 3].forEach((x, i) => {
      if (p.lupa && i === 1) return;
      const lx = p.lx, ly = p.ly;
      if (p.eyes === 'closed') P(x, ey + 2, 4, 1, G.fraca);
      else if (p.eyes === 'sleepy') { P(x, ey + 1, 4, 1, G.fraca); P(x, ey + 2, 4, 1, G.luz); }
      else if (p.eyes === 'happy') { P(x, ey + 2, 1, 1, G.luz); P(x + 1, ey + 1, 2, 1, G.luz); P(x + 3, ey + 2, 1, 1, G.luz); }
      else if (p.eyes === 'wide') { P(x, ey - 1, 4, 4, G.luz); P(x, ey - 1, 1, 1, G.w); P(x + 1, ey, 2, 2, G.forte); }
      else { P(x + lx, ey + ly, 4, 3, G.luz); P(x + lx, ey + ly, 1, 1, G.w); P(x + 2 + lx, ey + 1 + ly, 1, 1, G.forte); }
    });
    const my = cy + fy(-1);
    if (p.mouth === 'smile') { P(cx - 2, my - 1, 1, 1, G.luz); P(cx - 1, my, 3, 1, G.luz); P(cx + 2, my - 1, 1, 1, G.luz); }
    if (p.mouth === 'open') P(cx - 1, my - 1, 2, 2, G.luz);
    if (p.mouth === 'big') { P(cx - 2, my - 1, 4, 2, G.luz); P(cx - 1, my, 2, 1, G.tinta); }
  }

  // ---------- o que o corpo vira ----------
  function teclado(cx, cy, t) {
    const y = cy + 7;
    P(cx - 12, y, 25, 1, G.borda); P(cx - 12, y + 1, 25, 4, G.corpo); P(cx - 12, y + 4, 25, 1, G.borda);
    for (let i = 0; i < 11; i++) { P(cx - 11 + i * 2, y + 2, 1, 1, G.fraca); P(cx - 10 + i * 2, y + 3, 1, 1, G.fraca); }
    const k = Math.floor(t * 11) % 11, k2 = (k * 7 + 4) % 11;
    P(cx - 11 + k * 2, y + 2, 1, 1, G.forte); P(cx - 10 + k2 * 2, y + 3, 1, 1, G.forte);
    const f = Math.floor(t * 8) % 2;
    P(cx - 7, y - 2 + f, 2, 2, G.borda); P(cx + 5, y - 1 - f, 2, 2, G.borda);
  }
  function olhoLupa(cx, cy, t, alcance) {
    const lx = cx + 5, ly = cy - 5, r = 3 + (Math.floor(t * 2) % 2);
    for (let y = -r - 1; y <= r + 1; y++) for (let x = -r - 1; x <= r + 1; x++) {
      const d = Math.sqrt(x * x + y * y);
      if (d <= r + 0.5 && d >= r - 0.5) P(lx + x, ly + y, 1, 1, G.luz);
      else if (d < r - 0.5) P(lx + x, ly + y, 1, 1, G.tinta);
    }
    P(lx - 1, ly, 3, 1, G.forte);
    const linha = Math.floor(t * 6) % 7 - 3;
    const alfa = ctx.globalAlpha;
    ctx.globalAlpha = alfa * 0.6;
    for (let i = 1; i <= alcance; i++) P(lx + r + 1 + i, ly + linha + Math.round(i * linha * 0.15), 1, 1, G.luz);
    ctx.globalAlpha = alfa;
  }
  function engrenagem(gx, gy, t) {
    const s = Math.floor(t * 6) % 2;
    for (let y = -3; y <= 3; y++) for (let x = -3; x <= 3; x++) if (x * x + y * y <= 10) P(gx + x, gy + y, 1, 1, G.borda);
    const dentes = s ? [[0, -4], [0, 4], [-4, 0], [4, 0]] : [[-3, -3], [3, -3], [-3, 3], [3, 3]];
    for (const [x, y] of dentes) P(gx + x - (x < 0 ? 1 : 0), gy + y - (y < 0 ? 1 : 0), 2, 2, G.borda);
    P(gx - 1, gy - 1, 3, 3, G.luz); P(gx, gy, 1, 1, G.forte);
    P(gx - 7, gy, 4, 1, G.borda);
    const fase = Math.floor(t * 8) % 3;
    if (fase === 0) { P(gx - 4, gy - 6, 1, 1, G.forte); P(gx + 6, gy - 3, 1, 1, G.forte); }
    if (fase === 1) P(gx + 4, gy - 6, 1, 1, G.forte);
  }
  function ajudante(cx, cy, t) {
    const x = cx + 15, y = cy + 5 - (Math.floor(t * 4) % 2);
    P(x - 3, y - 2, 7, 5, G.borda); P(x - 2, y - 3, 5, 1, G.borda);
    P(x - 2, y - 1, 5, 3, G.corpo);
    P(x - 1, y - 1, 1, 1, G.luz); P(x + 1, y - 1, 1, 1, G.luz);
    P(x - 7, y, 3, 1, G.fraca);
  }
  function balaoPensando(cx, cy, t, lado) {
    const n = Math.floor(t * 2.5) % 4;
    if (lado === 'direita') {
      P(cx + 10, cy - 13, 1, 1, G.borda); P(cx + 12, cy - 16, 2, 2, G.borda);
      P(cx + 15, cy - 24, 11, 6, G.borda); P(cx + 14, cy - 23, 13, 4, G.borda); P(cx + 15, cy - 23, 11, 4, G.corpo);
      for (let i = 0; i < n; i++) P(cx + 16 + i * 3, cy - 22, 2, 2, G.luz);
    } else {
      P(cx + 3, cy - 16, 1, 1, G.borda);
      P(cx - 5, cy - 24, 11, 6, G.borda); P(cx - 6, cy - 23, 13, 4, G.borda); P(cx - 5, cy - 23, 11, 4, G.corpo);
      for (let i = 0; i < n; i++) P(cx - 4 + i * 3, cy - 22, 2, 2, G.luz);
    }
  }
  function balaoSinal(cx, cy, sinal) {
    const cor = sinal === '!' ? G.yel : G.luz;
    P(cx - 3, cy - 28, 7, 9, cor); P(cx - 4, cy - 27, 9, 7, cor);
    P(cx - 1, cy - 19, 3, 1, cor); P(cx, cy - 18, 1, 1, cor);
    if (sinal === '!') { P(cx, cy - 26, 1, 4, G.tinta); P(cx, cy - 21, 1, 1, G.tinta); }
    else { P(cx - 1, cy - 26, 3, 1, G.tinta); P(cx + 1, cy - 25, 1, 1, G.tinta); P(cx, cy - 24, 1, 1, G.tinta); P(cx, cy - 21, 1, 1, G.tinta); }
  }
  function ondasSom(cx, cy, t) {
    const f = Math.floor(t * 6) % 3;
    for (let i = 0; i <= f; i++) {
      const x = cx + 12 + i * 2;
      P(x, cy - 8 - i, 1, 1, G.luz); P(x + 1, cy - 7 - i, 1, 3 + i * 2, G.luz); P(x, cy - 3 + i, 1, 1, G.luz);
    }
  }
  function gotas(cx, cy, t, n) {
    for (let i = 0; i < n; i++) {
      const f = ((t * 0.8 + i * 0.5) % 1);
      const x = cx + (i ? -10 : 9), y = cy - 12 + Math.round(f * 8);
      const alfa = ctx.globalAlpha;
      ctx.globalAlpha = alfa * (1 - f * 0.6);
      P(x, y, 1, 2, G.gota); P(x, y + 2, 1, 1, '#BFE4FF');
      ctx.globalAlpha = alfa;
    }
  }
  function confete(cx, cy, t, largura) {
    for (let i = 0; i < 14; i++) {
      const x = cx + ((i * 37) % largura) - largura / 2, y = cy - 34 + ((t * 14 + i * 11) % 34);
      P(x, y, 1, (i % 2) + 1, i % 3 === 0 ? G.w : (i % 3 === 1 ? G.luz : G.forte));
    }
  }
  function visto(cx, cy) {
    const pts = [[0, 3], [1, 4], [2, 5], [3, 4], [4, 3], [5, 2], [6, 1], [7, 0]];
    for (const [x, y] of pts) P(cx - 4 + x, cy - 30 + y, 1, 2, G.luz);
  }
  function zzz(cx, cy, t) {
    const alfa = ctx.globalAlpha;
    for (let i = 0; i < 3; i++) {
      const f = (t * 0.5 + i / 3) % 1, zx = cx + 8 + f * 6, zy = cy + 4 - f * 14;
      ctx.globalAlpha = alfa * 0.5 * (1 - f);
      P(zx, zy, 3, 1, G.luz); P(zx + 1, zy + 1, 1, 1, G.luz); P(zx, zy + 2, 3, 1, G.luz);
    }
    ctx.globalAlpha = alfa;
  }
  function coracao(cx, cy, f) {
    const y = cy - 18 - Math.round(f * 8);
    const alfa = ctx.globalAlpha;
    ctx.globalAlpha = alfa * (1 - f);
    P(cx - 2, y, 1, 1, G.coracao); P(cx, y, 1, 1, G.coracao);
    P(cx - 3, y + 1, 5, 1, G.coracao); P(cx - 2, y + 2, 3, 1, G.coracao); P(cx - 1, y + 3, 1, 1, G.coracao);
    ctx.globalAlpha = alfa;
  }

  // ---------- aura das formas do Megabrain ----------
  const OURO = { luz: '#FFD54A', forte: '#FFF3B0', fraca: '#B8860B', borda: '#8A6A10' };
  function trocarPaleta(nova) {
    const antes = {};
    for (const k of Object.keys(nova)) { antes[k] = G[k]; G[k] = nova[k]; }
    return antes;
  }
  // nivel 1: brilho verde fraco; 2: chama verde forte; 3: chama dourada com faiscas
  function aura(cx, cy, t, nivel, achata) {
    const raio = nivel >= 2 ? 2 : 1;
    const dens = [0, 0.3, 0.5, 0.65][nivel];
    const cor = nivel === 3 ? '#FFC93C' : (nivel === 2 ? G.luz : G.fraca);
    const quadro = Math.floor(t * 8);
    const alfa = ctx.globalAlpha;
    ctx.globalAlpha = alfa * (nivel === 1 ? 0.5 : 0.8);
    for (let y = -17; y <= 11; y++) for (let x = -16; x <= 16; x++) {
      if (dentro(x, y, achata)) continue;
      let perto = false;
      for (let dy = -raio; dy <= raio && !perto; dy++) for (let dx = -raio; dx <= raio; dx++) {
        if (dx * dx + dy * dy <= raio * raio + 1 && dentro(x + dx, y + dy, achata)) { perto = true; break; }
      }
      if (!perto) continue;
      if (ruido(x * 7, y * 13 + quadro) < dens) P(cx + x, cy + y - (y < -6 ? quadro % 2 : 0), 1, 1, cor);
    }
    if (nivel === 3) for (let i = 0; i < 4; i++) {
      const f = ((t * 0.9 + i / 4) % 1);
      P(cx - 12 + ((i * 7) % 25), cy + 6 - Math.round(f * 24), 1, 1, f < 0.7 ? '#FFF3B0' : '#FFC93C');
    }
    ctx.globalAlpha = alfa;
  }

  // ---------- estado de vida (humor) e interacao ----------
  let humor = { estado: 'tranquilo', extras: [], motivo: '' };
  let vida = {};
  let especial = null, especialAte = 0; // 'ouvindo' | 'falando' | 'perguntando' | 'pensandoVoz' no Vendel principal
  function marcarEspecial(nome, ms) { especial = nome; especialAte = nome ? Date.now() + (ms || 60000) : 0; }

  // ---------- um Vendel num quadro ----------
  function desenhar(v, t, agora, slotW, principal) {
    let sit = v.mostra;
    const esp = principal && especial && agora < especialAte ? especial : null;
    if (esp && !ATIVOS.has(sit) && sit !== 'precisa') sit = esp;
    let cx = Math.round(v.cx), cy = base;
    const p = { eyes: 'open', lx: 0, ly: 0, armL: 'down', armR: 'down', mouth: 'none', luzes: 0, velPulso: 4,
                balanca: false, velBalanco: 2.5, dorme: false, lupa: false, fase: v.fase };
    const tt = t + v.fase;
    const pisca = (tt % 3.4) < 0.15;
    let alfa = 1;
    const hEst = humor.estado;
    switch (sit) {
      case 'ocioso': {
        const parado = hEst === 'carente' || hEst === 'sonolento';
        const amp = parado ? 0 : Math.max(0, Math.min(8, slotW / 2 - 14));
        cx += Math.round(Math.sin(tt * 0.5) * amp);
        const vel = Math.cos(tt * 0.5);
        p.lx = amp && Math.abs(vel) >= 0.2 ? Math.sign(vel) : 0;
        p.balanca = true; p.mouth = 'smile';
        if (pisca) p.eyes = 'closed';
        if ((tt % 7) > 6) p.ly = -1;
        if (hEst === 'animado') {
          p.velPulso = 9; p.velBalanco = 5;
          if ((tt % 4) < 0.7) { cy -= Math.round(Math.abs(Math.sin(tt * 9)) * 2); p.eyes = 'happy'; }
        } else if (hEst === 'curioso') {
          p.lx = Math.floor(tt / 1.5) % 2 ? 1 : -1; if ((tt % 5) < 1) p.ly = -1;
        } else if (hEst === 'sonolento') {
          p.balanca = false; p.velPulso = 2; p.mouth = 'none';
          p.eyes = (tt % 6) < 4.5 ? 'sleepy' : 'open';
          if ((tt % 9) < 1.3) { p.mouth = 'big'; p.eyes = 'closed'; }
        } else if (hEst === 'carente') {
          p.lx = 0; p.ly = 0; p.mouth = 'none';
          if ((tt % 15) < 2) p.armR = Math.floor(tt * 4) % 2 ? 'up' : 'mid';
        }
        if ((humor.extras || []).includes('calor')) p.armL = Math.floor(tt * 6) % 2 ? 'up' : 'mid';
        break;
      }
      case 'pensando': case 'pensandoVoz':
        p.lx = 1; p.ly = -1; p.armR = 'mid'; p.velPulso = 12; cy += Math.floor(tt) % 2;
        if (pisca) p.eyes = 'closed';
        break;
      case 'digitando': p.ly = 1; p.armL = p.armR = 'hide'; p.velPulso = 12; break;
      case 'lendo': p.lupa = true; p.lx = 1; p.armR = 'mid'; p.velPulso = 6; break;
      case 'executando': case 'trabalhando':
        p.lx = 1; p.ly = 1; p.armR = 'hide'; p.velPulso = 14; cy += Math.floor(tt * 4) % 2; break;
      case 'delegando': p.lx = 1; p.velPulso = 10; p.armR = 'mid'; break;
      case 'precisa':
        p.eyes = 'wide'; p.mouth = 'open'; p.armR = Math.floor(tt * 4) % 2 ? 'up' : 'mid';
        p.luzes = Math.floor(tt * 4) % 2; p.velPulso = 0; cy -= Math.floor(tt * 4) % 2; break;
      case 'concluido':
        p.eyes = 'happy'; p.mouth = 'smile'; p.armL = p.armR = 'up'; p.luzes = 1; p.velPulso = 0;
        cy -= Math.round(Math.abs(Math.sin(tt * 5)) * 3); break;
      case 'dormindo':
        p.eyes = 'closed'; p.dorme = true; p.velPulso = 1.5; p.armL = p.armR = 'hide'; alfa = 0.6; break;
      case 'ouvindo':
        p.eyes = 'wide'; p.ly = -1; p.velPulso = 16; p.armR = 'mid'; break;
      case 'falando':
        p.mouth = Math.floor(tt * 7) % 2 ? 'open' : 'smile'; p.velPulso = 8; p.armR = Math.floor(tt * 2) % 2 ? 'mid' : 'down'; break;
      case 'perguntando':
        p.eyes = 'wide'; p.ly = -1; p.armR = 'up'; p.velPulso = 6; break;
    }
    const carinho = v.carinhoAte > agora ? 1 - (v.carinhoAte - agora) / 1400 : -1;
    if (carinho >= 0 && sit !== 'dormindo') {
      p.eyes = 'happy'; p.mouth = 'smile'; cy -= Math.round(Math.abs(Math.sin(carinho * Math.PI * 3)) * 2);
    }
    p.cx = cx; p.cy = cy;
    v.cxDesenho = cx;

    // montar/desfazer (teletransporte)
    semente = v.semente;
    mascara = Math.min(1, (agora - v.nasc) / 700);
    if (v.morte) mascara = Math.min(mascara, Math.max(0, 1 - (agora - v.morte) / 600));
    if (mascara <= 0) { mascara = 1; return; }

    const largo = slotW >= 56;
    if (sit === 'concluido') confete(Math.round(v.cx), base, t, Math.min(40, Math.floor(slotW)));
    p.vendado = principal && cego;
    const nivelForma = principal ? forma : 0;
    const transformando = principal && agora < transformandoAte;
    if (transformando) p.luzes = Math.floor(t * 10) % 2;
    if (nivelForma > 0 || transformando) aura(cx, cy, t, Math.max(nivelForma, transformando ? 3 : 0), p.dorme);
    const original = nivelForma === 3 ? trocarPaleta(OURO) : null;  // forma suprema: circuitos dourados
    ctx.globalAlpha = alfa;
    corpo(p, t);
    ctx.globalAlpha = 1;
    if (original) trocarPaleta(original);
    if (sit === 'digitando') teclado(cx, cy, t);
    if (sit === 'lendo') olhoLupa(cx, cy, t, largo ? 12 : 5);
    if (sit === 'executando' || sit === 'trabalhando') engrenagem(cx + 16, cy + 1, t);
    if (sit === 'delegando') ajudante(cx, cy, t);
    if (sit === 'pensando' || sit === 'pensandoVoz') balaoPensando(cx, cy, t, largo && cx + 28 < W ? 'direita' : 'cima');
    if (sit === 'precisa' && Math.floor(t * 2.5) % 3 !== 2) balaoSinal(cx, cy, '!');
    if (sit === 'perguntando') balaoSinal(cx, cy, '?');
    if (sit === 'ouvindo') ondasSom(cx, cy, t);
    if (sit === 'concluido') visto(Math.round(v.cx), base);
    if (sit === 'dormindo') zzz(cx, cy, t);
    if (sit === 'ocioso') {
      const ex = humor.extras || [];
      const n = (ex.includes('cansado') ? 1 : 0) + (ex.includes('calor') ? 1 : 0);
      if (n) gotas(cx, cy, t, n);
    }
    if (carinho >= 0) coracao(cx, cy, carinho);
    mascara = 1;
  }

  // ---------- estado vindo do servidor ----------
  const vendels = new Map(); // id -> {dados, cx, nasc, morte, fase, semente, carinhoAte, ativoDesde}
  let resumo = { concluidas: 0, trabalhando_s: 0, por_projeto: {} };
  let ultimoDados = null;
  let ultimaMudanca = Date.now();
  let assinatura = '';
  let ultimoToque = Date.now();

  function novoVendel(id, dados) {
    let h = 0;
    for (const ch of id) h = (Math.imul(h, 31) + ch.charCodeAt(0)) | 0;
    return { id, dados, cx: null, nasc: Date.now(), morte: null, fase: (Math.abs(h) % 100) / 17,
             semente: h || 7, carinhoAte: 0, mostra: dados.estado,
             ativoDesde: ATIVOS.has(dados.estado) ? Date.now() : null };
  }

  function atualizar(mini, dados) {
    if (dados) ultimoDados = dados;
    if (!mini || !Array.isArray(mini.sessoes)) return;
    resumo = mini.hoje || resumo;
    if (mini.humor) humor = mini.humor;
    if (mini.vida) vida = mini.vida;
    if (typeof mini.pc_parado_s === "number") { pcParadoS = mini.pc_parado_s; pcParadoEm = Date.now(); }
    const agora = Date.now();
    const sessoes = mini.sessoes.slice(0, 20);
    const assin = sessoes.map((s) => s.id + ':' + s.estado).join('|');
    if (assin !== assinatura) { assinatura = assin; ultimaMudanca = agora; }

    const vistos = new Set();
    for (const s of sessoes) {
      vistos.add(s.id);
      let v = vendels.get(s.id);
      if (!v || v.morte) {
        v = novoVendel(s.id, s); vendels.set(s.id, v);
        if (s.estado === 'precisa') avisar(v, '', 'precisa');
      }
      const antes = v.dados.estado;
      v.dados = s;
      if (s.estado !== antes) avisar(v, antes, s.estado);
    }
    if (!sessoes.length) {
      vistos.add('_eu');
      if (!vendels.has('_eu') || vendels.get('_eu').morte) {
        vendels.set('_eu', novoVendel('_eu', { id: '_eu', projeto: '', estado: 'ocioso', tipo: 'eu' }));
      }
    }
    for (const v of vendels.values()) {
      if (!vistos.has(v.id) && !v.morte) v.morte = agora;
    }
    if (dados) conferirSaude(dados);
  }

  // ---------- formas, privacidade e voz ----------
  // Formas do Megabrain: base (Ollama pequeno) -> 2 (Ollama grande) -> 3 (agy, nuvem) -> suprema (Claude, nuvem).
  // Cansa: 10 min sem conversa numa forma alta e ele volta sozinho para a base.
  const FORMAS = [
    { modo: 'local', nome: 'Base', curto: 'Base' },
    { modo: 'local2', nome: 'Forma 2', curto: 'Forma 2' },
    { modo: 'agy', nome: 'Forma 3 (nuvem)', curto: 'Forma 3' },
    { modo: 'claude', nome: 'Forma suprema (Claude)', curto: 'Suprema' }
  ];
  let forma = Math.min(3, Math.max(0, Number(guardado('vendel_forma', '0')) || 0));
  let formaUsoEm = Date.now();
  let transformandoAte = 0;
  let vozLigada = guardado('vendel_voz', '1') === '1';
  let silencio = guardado('vendel_silencio', '0') === '1';
  let mudo = guardado('vendel_mudo', '0') === '1';   // microfone desligado de verdade
  let cego = guardado('vendel_cego', '0') === '1';   // camera desligada de verdade
  const noite = () => { const h = new Date().getHours(); return h >= 23 || h < 7; };
  const podeFalarSozinho = () => vozLigada && !silencio && !noite() && presente();

  // A voz vem do PC (vozes do Windows): o navegador do painel nao tem voz propria.
  let audioAtual = null;
  function falarAlto(texto, forcar) {
    if (!texto || (!forcar && !vozLigada)) return;
    try {
      if (audioAtual) audioAtual.pause();
      const a = new Audio(urlPainel('/vendel/voz?texto=' + encodeURIComponent(texto.slice(0, 1500))));
      audioAtual = a;
      a.onplay = () => marcarEspecial('falando', 60000);
      a.onended = a.onerror = () => { if (especial === 'falando') marcarEspecial(null); };
      a.play().catch(() => {});
    } catch (e) {}
  }
  const espera = (ms) => new Promise((r) => setTimeout(r, ms));

  // ---------- presenca: o dono mexeu no teclado/mouse do PC ha pouco (sem camera) ----------
  let pcParadoS = 0, pcParadoEm = Date.now();
  function presente() {
    const pc = pcParadoS + (Date.now() - pcParadoEm) / 1000;
    return pc < 240 || Date.now() - ultimoToque < 240000;
  }
  let ausenteDesde = null;
  function conferirPresenca() {
    if (presente()) {
      if (ausenteDesde && Date.now() - ausenteDesde > 20 * 60000) {   // voltou depois de 20 min fora
        const v = [...vendels.values()].find((x) => !x.morte);
        if (v) v.carinhoAte = Date.now() + 1400;
        ultimaMudanca = Date.now();
        if (vozLigada && !silencio && !noite()) falarAlto('Oi! Que bom que você voltou.');
      }
      ausenteDesde = null;
    } else if (!ausenteDesde) ausenteDesde = Date.now();
  }
  const enviarPrivacidade = () => enviarWs({ tipo: 'privacidade', mudo, cego });
  setInterval(enviarPrivacidade, 20000);
  setTimeout(enviarPrivacidade, 3000);

  let falaAte = 0;
  function mostrarFala(texto, ms) {
    if (!falaEl) return;
    falaEl.textContent = texto;
    falaEl.hidden = false;
    falaAte = Date.now() + (ms || 8000);
  }
  function aviso(texto) {
    if (podeFalarSozinho()) falarAlto(texto);
    if (naTelaVendel()) mostrarFala(texto, 6000);
  }

  // ---------- avisos fora da tela do Vendel ----------
  let faixaAte = 0;
  function vibrar(padrao) { if (navigator.vibrate) { try { navigator.vibrate(padrao); } catch (e) {} } }
  function mostrarFaixa(texto, tipo, ms) {
    if (!faixa) return;
    faixa.textContent = texto;
    faixa.dataset.tipo = tipo;
    faixa.hidden = false;
    faixaAte = ms ? Date.now() + ms : Infinity;
  }
  function esconderFaixa() { if (faixa) faixa.hidden = true; faixaAte = 0; }
  function avisar(v, antes, depois) {
    const nome = v.dados.projeto || 'Claude';
    if (ATIVOS.has(depois) && !ATIVOS.has(antes)) v.ativoDesde = Date.now();
    if (depois === 'precisa') {
      if (!silencio) vibrar([80, 60, 80]);
      if (!naTelaVendel()) mostrarFaixa(`${nome} precisa de você`, 'precisa', 0);
      aviso(`${nome} precisa de você`);
    } else if (depois === 'concluido' && ATIVOS.has(antes)) {
      const trabalhou = v.ativoDesde ? (Date.now() - v.ativoDesde) / 1000 : 0;
      v.ativoDesde = null;
      if (!naTelaVendel()) mostrarFaixa(`${nome} terminou`, 'ok', 6000);
      if (trabalhou >= 120) aviso(`Terminei no ${nome}`);
      if (Date.now() - ultimoToque < 600000) setTimeout(() => talvezPerguntar(), 8000);
    }
  }
  function conferirFaixa() {
    if (!faixa || faixa.hidden) return;
    if (naTelaVendel()) { esconderFaixa(); return; }
    if (faixa.dataset.tipo === 'precisa') {
      const algum = [...vendels.values()].some((v) => !v.morte && v.dados.estado === 'precisa');
      if (!algum) esconderFaixa();
    } else if (Date.now() > faixaAte) esconderFaixa();
  }
  if (faixa) faixa.addEventListener('click', () => { esconderFaixa(); irParaVendel(); });

  // uso alto e GPU quente: avisa uma vez quando passa do limite
  let avisouUso = false, avisoGpuEm = 0;
  function conferirSaude(dados) {
    try {
      const lim = ((dados.claude_usage || {}).limites || []).find((l) => String(l.nome || '').startsWith('Sessão'));
      const uso = lim ? Number(lim.usado_pct) : null;
      if (uso != null && uso >= 80 && !avisouUso) { avisouUso = true; aviso(`Sua janela de 5 horas do Claude passou de ${Math.round(uso)}%`); }
      if (uso != null && uso < 70) avisouUso = false;
      const gpu = (dados.hardware || {}).gpu_temp;
      if (gpu != null && gpu >= 85 && Date.now() - avisoGpuEm > 1800000) { avisoGpuEm = Date.now(); aviso(`A placa de vídeo está a ${Math.round(gpu)} graus`); }
    } catch (e) {}
  }

  // ---------- conversa (microfone do celular, ligado pelo PC so durante a escuta) ----------
  // vazioOk: sem fala, chama depois('') (ex.: foto sem pergunta = "o que voce esta vendo?")
  let escutando = false;
  async function ouvir(depois, vazioOk) {
    if (escutando) { fetch(urlPainel('/vendel/escutar/parar'), { method: 'POST' }).catch(() => {}); return; }
    if (mudo) { pedirTexto(depois); return; }
    escutando = true;
    mostrarFala('Preparando o ouvido…', 30000);
    marcarEspecial('pensandoVoz', 30000);
    try {
      const r = await (await fetch(urlPainel('/vendel/escutar/iniciar'), { method: 'POST' })).json();
      if (!r.ok) throw new Error(r.erro || 'sem microfone');
      const limite = Date.now() + 90000;
      let anterior = '';
      while (Date.now() < limite) {
        await espera(300);
        const e = await (await fetch(urlPainel('/vendel/escutar/estado'))).json();
        if (e.estado !== anterior) {
          anterior = e.estado;
          if (e.estado === 'ouvindo') { marcarEspecial('ouvindo', 20000); mostrarFala('Pode falar…', 20000); vibrar(20); }
          if (e.estado === 'transcrevendo') { marcarEspecial('pensandoVoz', 60000); mostrarFala('…', 60000); }
        }
        if (e.estado === 'pronto') { marcarEspecial(null); depois(e.texto); return; }
        if (e.estado === 'nada') { marcarEspecial(null); if (vazioOk) depois(''); else mostrarFala('Não ouvi nada.', 3000); return; }
        if (e.estado === 'erro') throw new Error(e.erro || 'erro');
      }
      throw new Error('demorou demais');
    } catch (err) {
      marcarEspecial(null);
      mostrarFala('Não consegui abrir o microfone do celular. Pode escrever.', 4000);
      pedirTexto(depois);
    } finally { escutando = false; }
  }
  let aoDigitar = null;
  function pedirTexto(depois) {
    if (!digitarEl) return;
    aoDigitar = depois;
    digitarEl.hidden = false;
    const campo = digitarEl.querySelector('input');
    campo.value = '';
    setTimeout(() => campo.focus(), 50);
  }
  if (digitarEl) {
    const campo = digitarEl.querySelector('input');
    const enviar = () => {
      const txt = campo.value.trim();
      digitarEl.hidden = true;
      campo.blur();
      if (txt && aoDigitar) aoDigitar(txt);
      aoDigitar = null;
    };
    digitarEl.querySelector('form').addEventListener('submit', (e) => { e.preventDefault(); enviar(); });
    digitarEl.querySelector('.vendel-cancelar').addEventListener('click', () => { digitarEl.hidden = true; aoDigitar = null; });
  }

  async function conversar(texto) {
    mostrarFala(`“${texto}”`, 240000);
    marcarEspecial('pensandoVoz', 240000);
    formaUsoEm = Date.now();
    try {
      const r = await fetch(urlPainel('/vendel/falar'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ texto, modo: FORMAS[forma].modo })
      });
      const d = await r.json();
      marcarEspecial(null);
      if (!r.ok || !d.resposta) throw new Error('sem resposta');
      mostrarFala(d.resposta, Math.max(8000, d.resposta.length * 90));
      falarAlto(d.resposta, true);
    } catch (e) {
      marcarEspecial(null);
      mostrarFala('Meu cérebro está desligado agora. Confira se o PC está ligado.', 6000);
    }
  }

  // ---------- perguntas para melhorar a memoria ----------
  let perguntaAtual = null, ultimaPerguntaEm = 0;
  async function talvezPerguntar() {
    if (silencio || noite() || perguntaAtual || Date.now() - ultimaPerguntaEm < 30 * 60000) return;
    ultimaPerguntaEm = Date.now();
    try {
      const d = await (await fetch(urlPainel('/vendel/pergunta'))).json();
      if (d && d.pergunta) mostrarPergunta(d.pergunta);
    } catch (e) {}
  }
  function mostrarPergunta(p) {
    if (!perguntaEl) return;
    perguntaAtual = p;
    perguntaEl.querySelector('.vendel-pergunta-texto').textContent = p.texto;
    perguntaEl.hidden = false;
    marcarEspecial('perguntando', 180000);
    if (naTelaVendel() || podeFalarSozinho()) falarAlto(p.texto);
  }
  function fecharPergunta() {
    if (perguntaEl) perguntaEl.hidden = true;
    perguntaAtual = null;
    if (especial === 'perguntando') marcarEspecial(null);
  }
  async function responderPergunta(texto) {
    const p = perguntaAtual;
    fecharPergunta();
    if (!p) return;
    try {
      await fetch(urlPainel('/vendel/responder'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: p.id, texto })
      });
      mostrarFala('Anotado! Obrigado.', 4000);
      falarAlto('Anotado! Obrigado.');
    } catch (e) { mostrarFala('Não consegui anotar agora.', 4000); }
  }
  if (perguntaEl) {
    perguntaEl.querySelector('.vendel-responder').addEventListener('click', () => ouvir(responderPergunta));
    perguntaEl.querySelector('.vendel-depois').addEventListener('click', fecharPergunta);
  }

  // ---------- botoes ----------
  function desenharBotoes() {
    const b = (cls) => secao.querySelector(cls);
    const marcar = (el, sim) => { if (el) el.setAttribute('aria-pressed', String(sim)); };
    const f = b('.vendel-forma');
    if (f) {
      f.dataset.forma = String(forma);
      f.setAttribute('aria-label', `Megabrain: ${FORMAS[forma].nome}. Toque para transformar`);
      const nome = f.querySelector('.vendel-forma-nome');
      if (nome) nome.textContent = FORMAS[forma].curto;
    }
    marcar(b('.vendel-voz'), vozLigada);
    marcar(b('.vendel-silencio'), silencio);
    marcar(b('.vendel-mudo'), mudo);
    marcar(b('.vendel-cego'), cego);
    secao.classList.toggle('mudo', mudo);
    secao.classList.toggle('cego', cego);
  }
  const clicar = (cls, fn) => { const el = secao.querySelector(cls); if (el) el.addEventListener('click', fn); };
  clicar('.vendel-mic', () => {
    if (audioAtual) { try { audioAtual.pause(); } catch (e) {} }
    if (mudo) { mostrarFala('Estou de ouvidos tapados. Pode escrever, ou tire o mudo.', 3000); }
    if (perguntaAtual) ouvir(responderPergunta); else ouvir(conversar);
  });
  clicar('.vendel-ver', async () => {
    if (cego) { mostrarFala('Estou de olhos vendados. Tire a venda no botão do olho.', 4000); return; }
    // primeiro a pergunta, depois a foto: da tempo de colocar a coisa na frente da camera
    ouvir(async (pergunta) => {
      marcarEspecial('pensandoVoz', 180000);
      mostrarFala('Segura na frente da câmera… olhando…', 180000);
      try {
        const r = await fetch(urlPainel('/vendel/olhar'), {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pergunta: pergunta || 'O que você está vendo?' })
        });
        const d = await r.json();
        marcarEspecial(null);
        if (!d.resposta) throw new Error('sem resposta');
        mostrarFala(d.resposta, Math.max(8000, d.resposta.length * 90));
        falarAlto(d.resposta, true);
      } catch (e) { marcarEspecial(null); mostrarFala('Não consegui olhar agora.', 4000); }
    }, true);
  });
  clicar('.vendel-forma', () => {
    forma = (forma + 1) % FORMAS.length;
    formaUsoEm = Date.now();
    transformandoAte = Date.now() + 1600;
    guardar('vendel_forma', String(forma)); desenharBotoes();
    vibrar(forma === 3 ? [40, 40, 40, 40, 120] : 30);
    if (forma >= 2) mostrarFala(`${FORMAS[forma].nome}: nesta forma eu penso na nuvem, e o pedacinho de memória da conversa sai do PC.`, 5000);
    else mostrarFala(`${FORMAS[forma].nome}: eu penso aqui no seu PC.`, 3000);
  });
  clicar('.vendel-voz', () => { vozLigada = !vozLigada; guardar('vendel_voz', vozLigada ? '1' : '0'); desenharBotoes(); });
  clicar('.vendel-silencio', () => { silencio = !silencio; guardar('vendel_silencio', silencio ? '1' : '0'); desenharBotoes(); });
  clicar('.vendel-mudo', () => {
    mudo = !mudo; guardar('vendel_mudo', mudo ? '1' : '0');
    desenharBotoes(); enviarPrivacidade();
  });
  clicar('.vendel-cego', () => {
    cego = !cego; guardar('vendel_cego', cego ? '1' : '0');
    desenharBotoes(); enviarPrivacidade();
  });
  // botoes e caixas nao contam como carinho nem abrem o resumo
  secao.querySelectorAll('.vendel-controle').forEach((el) => {
    el.addEventListener('pointerdown', (e) => e.stopPropagation());
  });
  desenharBotoes();

  // ---------- resumo do dia (segurar o dedo) ----------
  function duracao(s) {
    if (s < 60) return `${Math.max(0, Math.round(s))} s`;
    if (s < 3600) return `${Math.floor(s / 60)} min`;
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
    return `${h}h${String(m).padStart(2, '0')}`;
  }
  function abrirPainel() {
    if (!painelEl) return;
    const projetos = Object.entries(resumo.por_projeto || {}).sort((a, b) => b[1] - a[1]).slice(0, 5);
    const maior = projetos.length ? projetos[0][1] : 1;
    const d = ultimoDados || {};
    const claudeHoje = (d.claude || {}).hoje || {};
    const custo = (d.financeiro || {}).claude_equiv_hoje_usd;
    const tokens = (claudeHoje.input || 0) + (claudeHoje.output || 0) + (claudeHoje.cache_write || 0);
    const fmt = (n) => n >= 1e6 ? `${(n / 1e6).toFixed(1)} mi` : n >= 1e3 ? `${Math.round(n / 1e3)} mil` : String(n);
    painelEl.innerHTML = `
      <div class="vendel-painel-caixa">
        <div class="vendel-painel-topo"><b>Hoje</b><span>nível ${vida.nivel || 1} · ${HUMOR_ROTULO[humor.estado] || 'tranquilo'}</span></div>
        <div class="vendel-painel-numeros">
          <div><b>${resumo.concluidas || 0}</b><span>tarefas</span></div>
          <div><b>${duracao(resumo.trabalhando_s || 0)}</b><span>de Claude</span></div>
          <div><b>${fmt(tokens)}</b><span>tokens</span></div>
          <div><b>${custo != null ? '$' + Number(custo).toFixed(2) : '—'}</b><span>se fosse API</span></div>
        </div>
        <div class="vendel-painel-projetos">${projetos.map(([nome, s]) => `
          <div class="vendel-barra"><span></span><i style="width:${Math.max(4, (s / maior) * 100)}%"></i><em>${duracao(s)}</em></div>`).join('') || '<p>Nenhum projeto hoje ainda.</p>'}
        </div>
        <p class="vendel-painel-motivo"></p>
      </div>`;
    painelEl.querySelectorAll('.vendel-barra span').forEach((el, i) => { el.textContent = projetos[i][0]; });
    painelEl.querySelector('.vendel-painel-motivo').textContent = humor.motivo ? `Como estou: ${humor.motivo}.` : '';
    painelEl.hidden = false;
  }
  if (painelEl) painelEl.addEventListener('click', () => { painelEl.hidden = true; });

  // ---------- navegacao e repouso ----------
  const container = document.getElementById('container-horizontal');
  function indiceTela() {
    if (!container) return -1;
    return Math.round(container.scrollLeft / (container.clientWidth || window.innerWidth));
  }
  function indiceVendel() {
    return container ? [...container.querySelectorAll('.tela')].indexOf(secao) : -1;
  }
  function naTelaVendel() { return indiceTela() === indiceVendel(); }
  function irParaVendel() { secao.scrollIntoView({ behavior: 'smooth', inline: 'start' }); }

  function podePular() {
    const portao = document.getElementById('portao');
    if (!portao || !portao.classList.contains('aberto')) return false; // PC fora: o portao manda
    if (document.querySelector('.tela-bloqueio.ativa')) return false;
    const seletor = document.getElementById('seletor-app');
    if (seletor && !seletor.hidden) return false;
    const apagar = document.getElementById('overlay-apagar-tela');
    if (apagar && apagar.classList.contains('ativo')) return false;
    return !naTelaVendel();
  }
  let toqueEnviadoEm = 0;
  const marcarToque = () => {
    ultimoToque = Date.now();
    if (ultimoToque - toqueEnviadoEm > 30000) { toqueEnviadoEm = ultimoToque; enviarWs({ tipo: 'toque' }); }
  };
  document.addEventListener('pointerdown', marcarToque, true);
  document.addEventListener('touchstart', marcarToque, { capture: true, passive: true });
  setInterval(() => {
    if (Date.now() - ultimoToque > REPOUSO_MS && podePular()) { irParaVendel(); ultimoToque = Date.now(); }
    conferirFaixa();
    conferirPresenca();
    if (falaEl && !falaEl.hidden && Date.now() > falaAte && especial !== 'falando') falaEl.hidden = true;
    if (forma > 0 && Date.now() - formaUsoEm > 10 * 60000) {  // a transformacao cansa
      forma = 0; guardar('vendel_forma', '0'); desenharBotoes();
      if (naTelaVendel()) mostrarFala('Cansei… voltei para a forma base.', 4000);
    }
  }, 1000);

  // toque curto num Vendel = carinho; segurar = resumo do dia
  let segurar = null, inicioToque = null;
  secao.addEventListener('pointerdown', (e) => {
    inicioToque = { x: e.clientX, y: e.clientY, t: Date.now() };
    clearTimeout(segurar);
    segurar = setTimeout(() => { inicioToque = null; abrirPainel(); }, 650);
  });
  secao.addEventListener('pointermove', (e) => {
    if (inicioToque && Math.hypot(e.clientX - inicioToque.x, e.clientY - inicioToque.y) > 12) { clearTimeout(segurar); inicioToque = null; }
  });
  secao.addEventListener('pointerup', (e) => {
    clearTimeout(segurar);
    if (!inicioToque) return;
    inicioToque = null;
    const r = canvas.getBoundingClientRect();
    if (!r.width) return;
    const x = (e.clientX - r.left) / (r.width / W) - ox;
    let melhor = null, dist = 15;
    for (const v of vendels.values()) {
      if (v.morte) continue;
      const d = Math.abs((v.cxDesenho ?? v.cx) - x);
      if (d < dist) { dist = d; melhor = v; }
    }
    if (melhor) {
      melhor.carinhoAte = Date.now() + 1400; vibrar(15);
      enviarWs({ tipo: 'carinho' });
      setTimeout(() => talvezPerguntar(), 2500);
    }
  });
  secao.addEventListener('pointercancel', () => { clearTimeout(segurar); inicioToque = null; });

  // ---------- desenho ----------
  const rotulos = new Map(); // id -> div
  function textoRotulo(v, mostra) {
    if (v.id === '_eu') {
      const linha = mostra === 'dormindo' ? 'dormindo' : (HUMOR_ROTULO[humor.estado] || 'tranquilo');
      return { nome: 'Vendel', linha };
    }
    const desde = Date.parse(v.dados.desde || '');
    const ha = Number.isFinite(desde) ? ` · ${duracao((Date.now() - desde) / 1000)}` : '';
    const nome = (v.dados.tipo === 'ajudante' ? 'ajudante · ' : '') + (v.dados.projeto || '?');
    const extra = mostra === 'concluido' || mostra === 'dormindo' ? '' : ha;
    return { nome, linha: (ROTULO[mostra] || mostra) + extra };
  }

  let visivel = false;
  const calmo = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const QUADRO_MS = calmo ? 300 : 83;
  let ultimoQuadro = 0;

  function quadro(agora) {
    requestAnimationFrame(quadro);
    if (!visivel || document.hidden || agora - ultimoQuadro < QUADRO_MS) return;
    ultimoQuadro = agora;
    if (!W && !dimensionar()) return;
    const t = agora / 1000;
    const relogio = Date.now();
    const hora = new Date().getHours();
    const madrugada = hora >= 23 || hora < 6;

    // OLED: a cena inteira passeia 2 px a cada minuto
    const minuto = Math.floor(relogio / 60000);
    ox = [0, 1, 2, 1, 0, -1, -2, -1][minuto % 8];
    oy = [0, -1, 0, 1][Math.floor(minuto / 8) % 4];

    const ativos = [...vendels.values()].filter((v) => !v.morte);
    const algumAtivo = ativos.some((v) => ATIVOS.has(v.dados.estado) || v.dados.estado === 'precisa');
    const conversando = especial && relogio < especialAte;
    const parado = relogio - Math.max(ultimaMudanca, ultimoToque);
    const dormir = !algumAtivo && !conversando && (parado > DORMIR_MS || (madrugada && parado > REPOUSO_MS));

    const lista = ativos.slice(0, MAX_VISIVEIS);
    const slotW = W / Math.max(1, lista.length);
    lista.forEach((v, i) => {
      const alvo = slotW * (i + 0.5);
      v.cx = v.cx == null ? alvo : v.cx + (alvo - v.cx) * 0.15;
    });

    ctx.clearRect(0, 0, W, H);
    for (const v of vendels.values()) {
      if (v.morte && relogio - v.morte > 650) { vendels.delete(v.id); continue; }
      if (v.cx == null) continue;
      if (!v.morte && !lista.includes(v)) continue;
      v.mostra = dormir && !ATIVOS.has(v.dados.estado) ? 'dormindo' : v.dados.estado;
      desenhar(v, t, relogio, slotW, v === lista[0]);
    }

    const presentes = new Set();
    for (const v of lista) {
      presentes.add(v.id);
      let el = rotulos.get(v.id);
      if (!el) {
        el = document.createElement('div');
        el.className = 'vendel-rotulo';
        el.innerHTML = '<b></b><span></span>';
        rotulosEl.appendChild(el);
        rotulos.set(v.id, el);
      }
      const { nome, linha } = textoRotulo(v, v.mostra);
      if (el.firstChild.textContent !== nome) el.firstChild.textContent = nome;
      if (el.lastChild.textContent !== linha) el.lastChild.textContent = linha;
      el.dataset.estado = v.mostra;
      el.style.left = `${((v.cx + 0.5) / W) * 100}%`;
    }
    for (const [id, el] of rotulos) if (!presentes.has(id)) { el.remove(); rotulos.delete(id); }
    const extras = ativos.length - lista.length;
    rotulosEl.dataset.extras = extras > 0 ? `+${extras}` : '';

    if (resumoEl) {
      const n = resumo.concluidas || 0, s = resumo.trabalhando_s || 0;
      const txt = n || s ? `hoje: ${n} ${n === 1 ? 'tarefa' : 'tarefas'} · ${duracao(s)} de Claude` : '';
      if (resumoEl.textContent !== txt) resumoEl.textContent = txt;
    }
    if (horaEl) {
      const d = new Date();
      const txt = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
      if (horaEl.textContent !== txt) horaEl.textContent = txt;
    }
    camada.style.transform = `translate(${ox * escala}px, ${oy * escala}px)`;
    secao.classList.toggle('noite', (madrugada || dormir) && !conversando);
    const ouvindo = conversando && especial === 'ouvindo';
    const pensando = conversando && (especial === 'pensandoVoz' || especial === 'perguntando');
    secao.classList.toggle('ouvindo', ouvindo);
    secao.classList.toggle('pensando', pensando && !ouvindo);
    const nomeMic = secao.querySelector('.vendel-mic-nome');
    const txtMic = ouvindo ? 'Ouvindo…' : (escutando ? 'Preparando…' : (pensando ? 'Pensando…' : (especial === 'falando' && conversando ? 'Falando…' : 'Falar')));
    if (nomeMic && nomeMic.textContent !== txtMic) nomeMic.textContent = txtMic;
  }

  if ('IntersectionObserver' in window) {
    new IntersectionObserver((itens) => {
      for (const it of itens) visivel = it.intersectionRatio > 0.3;
    }, { threshold: [0, 0.3, 1] }).observe(secao);
  } else visivel = true;
  window.addEventListener('resize', () => { W = 0; });

  atualizar({ sessoes: [], hoje: resumo });
  requestAnimationFrame(quadro);
  window.Vendel = { atualizar, irPara: irParaVendel, falar: falarAlto };
})();
