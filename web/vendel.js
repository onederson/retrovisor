// Vendel: o bichinho da tela 8. Cada janela (sessao) do Claude Code vira um Vendel que mostra o que
// ela esta fazendo. Os dados chegam pelo WebSocket em dados.mini (server/mini.py) e o app.js repassa
// com window.Vendel.atualizar(mini). Sem toque por 2 min, o painel vem sozinho para esta tela.
(() => {
  'use strict';

  const G = {
    corpo: '#0C120E', sombra: '#050806', brilho: '#2B3A30', borda: '#1C6B28',
    luz: '#5CFF4A', forte: '#D2FFC4', fraca: '#1F8A2C', w: '#F2FFF0', yel: '#F2E14E',
    tinta: '#061008', coracao: '#FF6B9A'
  };
  const ATIVOS = new Set(['pensando', 'digitando', 'lendo', 'executando', 'delegando', 'trabalhando']);
  const ROTULO = {
    ocioso: 'à toa', pensando: 'pensando', digitando: 'escrevendo', lendo: 'lendo',
    executando: 'rodando comando', delegando: 'chamou ajudante', trabalhando: 'trabalhando',
    precisa: 'precisa de você', concluido: 'terminou!', dormindo: 'dormindo'
  };
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
  const faixa = document.getElementById('vendel-faixa');

  // ---------- grade de pixels ----------
  let W = 0, H = 0, escala = 6, base = 40;
  function dimensionar() {
    const r = secao.getBoundingClientRect();
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
      const balanco = p.balanca && y < -4 ? Math.round(Math.sin(t * 2.5 + y * 0.35 + p.fase) * 0.7) : 0;
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
    [cx - 6, cx + 3].forEach((x, i) => {
      if (p.lupa && i === 1) return;
      const lx = p.lx, ly = p.ly;
      if (p.eyes === 'closed') P(x, ey + 2, 4, 1, G.fraca);
      else if (p.eyes === 'happy') { P(x, ey + 2, 1, 1, G.luz); P(x + 1, ey + 1, 2, 1, G.luz); P(x + 3, ey + 2, 1, 1, G.luz); }
      else if (p.eyes === 'wide') { P(x, ey - 1, 4, 4, G.luz); P(x, ey - 1, 1, 1, G.w); P(x + 1, ey, 2, 2, G.forte); }
      else { P(x + lx, ey + ly, 4, 3, G.luz); P(x + lx, ey + ly, 1, 1, G.w); P(x + 2 + lx, ey + 1 + ly, 1, 1, G.forte); }
    });
    const my = cy + fy(-1);
    if (p.mouth === 'smile') { P(cx - 2, my - 1, 1, 1, G.luz); P(cx - 1, my, 3, 1, G.luz); P(cx + 2, my - 1, 1, 1, G.luz); }
    if (p.mouth === 'open') P(cx - 1, my - 1, 2, 2, G.luz);
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
  function balaoExclamacao(cx, cy) {
    P(cx - 3, cy - 28, 7, 9, G.yel); P(cx - 4, cy - 27, 9, 7, G.yel);
    P(cx - 1, cy - 19, 3, 1, G.yel); P(cx, cy - 18, 1, 1, G.yel);
    P(cx, cy - 26, 1, 4, G.tinta); P(cx, cy - 21, 1, 1, G.tinta);
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

  // ---------- um Vendel num quadro ----------
  function desenhar(v, t, agora, slotW) {
    const sit = v.mostra;
    let cx = Math.round(v.cx), cy = base;
    const p = { eyes: 'open', lx: 0, ly: 0, armL: 'down', armR: 'down', mouth: 'none',
                luzes: 0, velPulso: 4, balanca: false, dorme: false, lupa: false, fase: v.fase };
    const tt = t + v.fase;
    const pisca = (tt % 3.4) < 0.15;
    let alfa = 1;
    switch (sit) {
      case 'ocioso': {
        const amp = Math.max(0, Math.min(8, slotW / 2 - 14));
        cx += Math.round(Math.sin(tt * 0.5) * amp);
        const vel = Math.cos(tt * 0.5);
        p.lx = amp && Math.abs(vel) >= 0.2 ? Math.sign(vel) : 0;
        p.balanca = true; p.mouth = 'smile';
        if (pisca) p.eyes = 'closed';
        if ((tt % 7) > 6) p.ly = -1;
        break;
      }
      case 'pensando':
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
    ctx.globalAlpha = alfa;
    corpo(p, t);
    ctx.globalAlpha = 1;
    if (sit === 'digitando') teclado(cx, cy, t);
    if (sit === 'lendo') olhoLupa(cx, cy, t, largo ? 12 : 5);
    if (sit === 'executando' || sit === 'trabalhando') engrenagem(cx + 16, cy + 1, t);
    if (sit === 'delegando') ajudante(cx, cy, t);
    if (sit === 'pensando') balaoPensando(cx, cy, t, largo ? 'direita' : 'cima');
    if (sit === 'precisa' && Math.floor(t * 2.5) % 3 !== 2) balaoExclamacao(cx, cy);
    if (sit === 'concluido') visto(Math.round(v.cx), base);
    if (sit === 'dormindo') zzz(cx, cy, t);
    if (carinho >= 0) coracao(cx, cy, carinho);
    mascara = 1;
  }

  // ---------- estado vindo do servidor ----------
  const vendels = new Map(); // id -> {dados, cx, nasc, morte, fase, semente, carinhoAte, estadoAnterior}
  let resumo = { concluidas: 0, trabalhando_s: 0 };
  let ultimaMudanca = Date.now();
  let assinatura = '';
  let ultimoToque = Date.now();

  function novoVendel(id, dados) {
    let h = 0;
    for (const ch of id) h = (Math.imul(h, 31) + ch.charCodeAt(0)) | 0;
    return { id, dados, cx: null, nasc: Date.now(), morte: null, fase: (Math.abs(h) % 100) / 17,
             semente: h || 7, carinhoAte: 0, mostra: dados.estado };
  }

  function atualizar(mini) {
    if (!mini || !Array.isArray(mini.sessoes)) return;
    resumo = mini.hoje || resumo;
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
    // sem nenhuma janela: o Vendel fica sozinho
    if (!sessoes.length) {
      vistos.add('_eu');
      if (!vendels.has('_eu') || vendels.get('_eu').morte) {
        vendels.set('_eu', novoVendel('_eu', { id: '_eu', projeto: '', estado: 'ocioso', tipo: 'eu' }));
      }
    }
    for (const v of vendels.values()) {
      if (!vistos.has(v.id) && !v.morte) v.morte = agora;
    }
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
    if (depois === 'precisa') {
      vibrar([80, 60, 80]);
      if (!naTelaVendel()) mostrarFaixa(`${nome} precisa de você`, 'precisa', 0);
    } else if (depois === 'concluido' && ATIVOS.has(antes)) {
      if (!naTelaVendel()) mostrarFaixa(`${nome} terminou`, 'ok', 6000);
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
  const marcarToque = () => { ultimoToque = Date.now(); };
  document.addEventListener('pointerdown', marcarToque, true);
  document.addEventListener('touchstart', marcarToque, { capture: true, passive: true });
  setInterval(() => {
    if (Date.now() - ultimoToque > REPOUSO_MS && podePular()) { irParaVendel(); ultimoToque = Date.now(); }
    conferirFaixa();
  }, 3000);

  // carinho: tocar num Vendel
  secao.addEventListener('pointerdown', (e) => {
    const r = canvas.getBoundingClientRect();
    if (!r.width) return;
    const x = (e.clientX - r.left) / (r.width / W) - ox;
    let melhor = null, dist = 15;
    for (const v of vendels.values()) {
      if (v.morte) continue;
      const d = Math.abs((v.cxDesenho ?? v.cx) - x);
      if (d < dist) { dist = d; melhor = v; }
    }
    if (melhor) { melhor.carinhoAte = Date.now() + 1400; vibrar(15); }
  });

  // ---------- desenho ----------
  const rotulos = new Map(); // id -> div
  function duracao(s) {
    if (s < 60) return `${Math.max(0, Math.round(s))} s`;
    if (s < 3600) return `${Math.floor(s / 60)} min`;
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
    return `${h}h${String(m).padStart(2, '0')}`;
  }
  function textoRotulo(v, mostra) {
    if (v.id === '_eu') return { nome: 'Vendel', linha: mostra === 'dormindo' ? 'dormindo' : 'nenhuma janela do Claude aberta' };
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
    const noite = hora >= 23 || hora < 6;

    // OLED: a cena inteira passeia 2 px a cada minuto
    const minuto = Math.floor(relogio / 60000);
    ox = [0, 1, 2, 1, 0, -1, -2, -1][minuto % 8];
    oy = [0, -1, 0, 1][Math.floor(minuto / 8) % 4];

    const ativos = [...vendels.values()].filter((v) => !v.morte);
    const algumAtivo = ativos.some((v) => ATIVOS.has(v.dados.estado) || v.dados.estado === 'precisa');
    const parado = relogio - Math.max(ultimaMudanca, ultimoToque);
    const dormir = !algumAtivo && (parado > DORMIR_MS || (noite && parado > REPOUSO_MS));

    // posicoes: cada um no centro da sua faixa (os que somem saem do calculo)
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
      desenhar(v, t, relogio, slotW);
    }

    // rotulos em HTML (texto nitido), embaixo de cada um
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
    secao.classList.toggle('noite', noite || dormir);
  }

  if ('IntersectionObserver' in window) {
    new IntersectionObserver((itens) => {
      for (const it of itens) visivel = it.intersectionRatio > 0.3;
    }, { threshold: [0, 0.3, 1] }).observe(secao);
  } else visivel = true;
  window.addEventListener('resize', () => { W = 0; });

  atualizar({ sessoes: [], hoje: resumo });
  requestAnimationFrame(quadro);
  window.Vendel = { atualizar, irPara: irParaVendel };
})();
