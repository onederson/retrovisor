// Vendel: o bichinho da tela 8. Cada janela (sessao) do Claude Code vira um Vendel que mostra o que
// ela esta fazendo. Os dados chegam pelo WebSocket em dados.mini (server/mini.py) e o app.js repassa
// com window.Vendel.atualizar(mini, dados). Sem toque por 2 min, o painel vem sozinho para esta tela.
// Ele tambem tem humor (server/humor.py), conversa por voz e faz perguntas para melhorar a memoria
// (cerebro do Vendel, projeto Vendel, via /vendel/* em server/cerebro.py).
(() => {
  'use strict';

  const G = {
    corpo: '#000000', bordaPreto: '#263B28', branco: '#FFFFFF', bordaBranco: '#000000',
    sombraBranco: '#D5D9DD', luz: '#76FF03', forte: '#CCFF90', fraca: '#2E7D1B',
    omniAnel: '#9EA7AD', omniEscuro: '#6E777D', coracao: '#FF4081', gota: '#7FC8FF',
    amarelo: '#FFD54A'
  };
  const OLHO_CLI = {
    claude: { luz: '#FF8A00', forte: '#FFD180', fraca: '#8C4600' },   // laranja
    agy: { luz: '#2998FF', forte: '#A6D8FF', fraca: '#104A8A' },      // azul
    opencode: { luz: '#B366FF', forte: '#E5CCFF', fraca: '#5A248F' }, // roxo
    gemini: { luz: '#00E5FF', forte: '#B2F5FF', fraca: '#006878' },   // ciano
    codex: { luz: '#FF4D94', forte: '#FFB3D1', fraca: '#8C1D4A' },    // rosa/magenta
    ollama: { luz: '#E2E8F0', forte: '#FFFFFF', fraca: '#64748B' }    // prata
  };
  function paletaOlho(cli) {
    if (!cli) return null;
    return OLHO_CLI[String(cli).trim().toLowerCase()] || null;
  }
  const ATIVOS = new Set(['pensando', 'digitando', 'lendo', 'executando', 'delegando', 'trabalhando']);
  const ROTULO = {
    ocioso: 'à toa', pensando: 'pensando', digitando: 'escrevendo', lendo: 'lendo',
    executando: 'rodando comando', delegando: 'chamou ajudante', trabalhando: 'trabalhando',
    precisa: 'precisa de você', concluido: 'terminou!', dormindo: 'dormindo',
    testando: 'rodando testes', teste_ok: 'testes passaram!', pescando: 'buscando dados',
    enviando: 'enviando git', arquiteto: 'planejando', bibliotecario: 'carregando contexto',
    academia: 'treinando pesado', erro: 'ops, erro!', cooldown: 'pausa pro café'
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

  // ---------- renderizacao vetorial 2D (Ultra T / Upgrade) ----------
  let W = 0, H = 0, dpr = 1, base = 30, ultimoSlotW = 100;
  function dimensionar() {
    const r = (secao.querySelector('.vendel-palco') || secao).getBoundingClientRect();
    if (!r.width || !r.height) return false;
    dpr = Math.min(window.devicePixelRatio || 1, 3);
    W = Math.round(r.width);
    H = Math.round(r.height);
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    base = H - Math.max(36, Math.round(H * 0.14));
    return true;
  }

  let ox = 0, oy = 0;          // deslocamento lento da cena inteira (OLED)
  let mascara = 1, semente = 1; // mascara < 1: o Vendel esta se montando/desfazendo
  function ruido(x, y) {
    let n = (Math.imul(x, 374761393) + Math.imul(y, 668265263)) ^ semente;
    n = Math.imul(n ^ (n >>> 13), 1274126177);
    return ((n ^ (n >>> 16)) >>> 0) / 4294967296;
  }

  function desenharOmnitrix(ctx, ox, oy) {
    ctx.save();
    ctx.translate(ox, oy);

    const R = 6.2;
    ctx.fillStyle = G.omniAnel;
    ctx.strokeStyle = G.bordaBranco;
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.arc(0, 0, R, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.strokeStyle = G.omniEscuro;
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.arc(0, 0, 5.0, 0, Math.PI * 2);
    ctx.stroke();

    ctx.save();
    ctx.beginPath();
    ctx.arc(0, 0, 4.4, 0, Math.PI * 2);
    ctx.fillStyle = G.branco;
    ctx.fill();
    ctx.clip();

    ctx.fillStyle = G.corpo;
    ctx.beginPath();
    ctx.moveTo(-4.8, -3.6);
    ctx.lineTo(0, 0);
    ctx.lineTo(-4.8, 3.6);
    ctx.closePath();
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(4.8, -3.6);
    ctx.lineTo(0, 0);
    ctx.lineTo(4.8, 3.6);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    ctx.fillStyle = G.omniEscuro;
    ctx.fillRect(-0.6, -6.0, 1.2, 1.0);
    ctx.fillRect(-0.6, 5.0, 1.2, 1.0);
    ctx.fillRect(-6.0, -0.6, 1.0, 1.2);
    ctx.fillRect(5.0, -0.6, 1.0, 1.2);

    ctx.restore();
  }

  function desenharBraco(ctx, s, st, p, t) {
    if (st === 'hide') return;

    ctx.save();
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';

    const tArm = t - 0.08; // Follow-through / movimento secundario

    if (st === 'down') {
      // Parte interna branca do braco + palma/parte interna dos 3 dedos curvados
      const tracoBracoBranco = () => {
        ctx.beginPath();
        ctx.moveTo(s * 18, -60);
        ctx.lineTo(s * 17, -36);
        ctx.lineTo(s * 16, -15);
        // Dedo interno 1 (curvado suavemente para dentro, ponta arredondada)
        ctx.quadraticCurveTo(s * 14.5, -9, s * 15.5, -4);
        ctx.quadraticCurveTo(s * 16.5, -2.5, s * 17.8, -4.5);
        ctx.lineTo(s * 18.6, -12);
        // Dedo medio 2 (mais longo)
        ctx.quadraticCurveTo(s * 18.4, -6, s * 19.4, -1.5);
        ctx.quadraticCurveTo(s * 20.6, 0, s * 21.6, -2);
        ctx.lineTo(s * 22.0, -12);
        // Dedo externo 3 (palma)
        ctx.quadraticCurveTo(s * 22.2, -6.5, s * 23.0, -3.5);
        ctx.quadraticCurveTo(s * 24.0, -2, s * 24.6, -4.5);
        ctx.lineTo(s * 24.2, -15);
        ctx.lineTo(s * 23.5, -36);
        ctx.lineTo(s * 25, -63);
        ctx.closePath();
      };

      ctx.fillStyle = G.branco;
      tracoBracoBranco();
      ctx.fill();

      // Sombreamento cel-shaded sutil na parte interna do braco
      ctx.fillStyle = G.sombraBranco;
      ctx.beginPath();
      ctx.moveTo(s * 18, -60);
      ctx.lineTo(s * 17, -36);
      ctx.lineTo(s * 16, -15);
      ctx.lineTo(s * 18.2, -15);
      ctx.lineTo(s * 19, -36);
      ctx.lineTo(s * 20, -60);
      ctx.closePath();
      ctx.fill();

      // Contorno preto nitido do braco branco
      ctx.strokeStyle = G.bordaBranco;
      ctx.lineWidth = 1.6;
      tracoBracoBranco();
      ctx.stroke();

      // Parte externa preta do braco + dorso da mao e 3 dedos
      ctx.fillStyle = G.corpo;
      ctx.strokeStyle = G.bordaPreto;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(s * 25, -63);
      ctx.lineTo(s * 32, -61);
      ctx.lineTo(s * 30.5, -36);
      ctx.lineTo(s * 27.5, -14);
      // Dorso do dedo externo 3
      ctx.quadraticCurveTo(s * 27.2, -6, s * 25.6, -3);
      ctx.quadraticCurveTo(s * 24.6, -1.8, s * 24.0, -3.8);
      ctx.lineTo(s * 23.6, -12.5);
      // Dorso do dedo medio 2
      ctx.quadraticCurveTo(s * 23.0, -5, s * 21.8, -1.8);
      ctx.quadraticCurveTo(s * 20.8, -0.6, s * 20.4, -2.8);
      ctx.lineTo(s * 20.6, -13);
      ctx.lineTo(s * 22.8, -36);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

    } else if (st === 'mid') {
      const bal = Math.sin(tArm * 3) * 1.5;

      ctx.fillStyle = G.branco;
      ctx.strokeStyle = G.bordaBranco;
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      ctx.moveTo(s * 18, -60);
      ctx.lineTo(s * 24, -50);
      ctx.lineTo(s * 20, -42 + bal);
      ctx.lineTo(s * 17, -40 + bal);
      ctx.lineTo(s * 19, -46 + bal);
      ctx.lineTo(s * 23, -56);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = G.corpo;
      ctx.strokeStyle = G.bordaPreto;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(s * 23, -56);
      ctx.lineTo(s * 32, -61);
      ctx.lineTo(s * 35, -48);
      ctx.lineTo(s * 26, -38 + bal);
      ctx.lineTo(s * 20, -42 + bal);
      ctx.lineTo(s * 24, -50);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

    } else if (st === 'up') {
      const aceno = Math.sin(tArm * 6) * 3;

      ctx.fillStyle = G.branco;
      ctx.strokeStyle = G.bordaBranco;
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      ctx.moveTo(s * 18, -60);
      ctx.lineTo(s * 24, -72);
      ctx.lineTo(s * 22 + aceno, -96);
      ctx.lineTo(s * 26 + aceno, -98);
      ctx.lineTo(s * 27, -76);
      ctx.lineTo(s * 25, -63);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = G.corpo;
      ctx.strokeStyle = G.bordaPreto;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(s * 25, -63);
      ctx.lineTo(s * 32, -61);
      ctx.lineTo(s * 36, -74);
      ctx.lineTo(s * 30 + aceno, -96);
      ctx.lineTo(s * 26 + aceno, -98);
      ctx.lineTo(s * 27, -76);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    }

    ctx.restore();
  }

  function desenharCircuitos(ctx, p, t) {
    const ach = p.dorme;
    const tt = t + (p.fase || 0);

    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    const corCircuito = p.luzes >= 1 ? G.forte : (ach ? G.fraca : G.luz);
    ctx.strokeStyle = corCircuito;
    ctx.lineWidth = 1.8;
    if (ach) ctx.globalAlpha = 0.35;
    else if (p.luzes >= 1) {
      ctx.shadowColor = G.luz;
      ctx.shadowBlur = 6;
    }

    // 1. Linha vertical central: base do olho ate a ponta em V do peito
    ctx.beginPath();
    ctx.moveTo(0, -78);
    ctx.lineTo(0, -48);
    ctx.stroke();

    // 2. Linhas simetricas no pescoco e ombros
    for (const s of [-1, 1]) {
      ctx.beginPath();
      ctx.moveTo(s * 8, -86);
      ctx.lineTo(s * 12, -74);
      ctx.lineTo(s * 24, -66);
      ctx.lineTo(s * 28, -61);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(s * 16, -70);
      ctx.lineTo(s * 20, -62);
      ctx.stroke();
    }

    // 3. Circuitos nos bracos
    for (const [s, st] of [[-1, p.armL], [1, p.armR]]) {
      if (st === 'down') {
        ctx.beginPath();
        ctx.moveTo(s * 28, -52);
        ctx.lineTo(s * 26, -34);
        ctx.lineTo(s * 23, -31);
        ctx.lineTo(s * 23, -16);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(s * 25, -14);
        ctx.lineTo(s * 18, -14);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(s * 29, -44);
        ctx.lineTo(s * 26, -44);
        ctx.moveTo(s * 28, -26);
        ctx.lineTo(s * 25, -26);
        ctx.stroke();
      } else if (st === 'mid') {
        ctx.beginPath();
        ctx.moveTo(s * 28, -52);
        ctx.lineTo(s * 32, -46);
        ctx.lineTo(s * 25, -40);
        ctx.stroke();
      } else if (st === 'up') {
        ctx.beginPath();
        ctx.moveTo(s * 28, -66);
        ctx.lineTo(s * 32, -78);
        ctx.lineTo(s * 28, -90);
        ctx.stroke();
      }
    }

    // Pulsos animados percorrendo os circuitos quando velPulso > 0
    if (p.velPulso > 0 && !ach) {
      const f = (tt * p.velPulso * 0.4) % 1;
      ctx.fillStyle = G.forte;
      ctx.shadowColor = G.forte;
      ctx.shadowBlur = 6;

      const yVert = -78 + f * 30;
      ctx.beginPath();
      ctx.arc(0, yVert, 2.2, 0, Math.PI * 2);
      ctx.fill();

      for (const s of [-1, 1]) {
        const xOmbro = s * (10 + f * 16);
        const yOmbro = -80 + f * 18;
        ctx.beginPath();
        ctx.arc(xOmbro, yOmbro, 2, 0, Math.PI * 2);
        ctx.fill();
      }

      for (const [s, st] of [[-1, p.armL], [1, p.armR]]) {
        if (st === 'down') {
          const yBraco = -50 + f * 34;
          ctx.beginPath();
          ctx.arc(s * 25, yBraco, 2, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }

    ctx.restore();
  }

  function desenharOlho(ctx, p, t) {
    const ach = p.dorme;
    const tt = t + (p.fase || 0);
    const ey = -84;

    ctx.save();
    ctx.translate(0, ey);

    if (p.vendado && !ach) {
      ctx.fillStyle = '#080E0A';
      ctx.strokeStyle = G.fraca;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(-16, -5, 32, 10, 3);
      else ctx.rect(-16, -5, 32, 10);
      ctx.fill();
      ctx.stroke();
      ctx.strokeStyle = '#050906';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(-16, 0); ctx.lineTo(-20, 3);
      ctx.moveTo(16, 0); ctx.lineTo(20, 3);
      ctx.stroke();
      ctx.restore();
      return;
    }

    const lx = (p.lx || 0) * 1.5;
    const ly = (p.ly || 0) * 1.5;

    const falando = p.mouth === 'open' || p.mouth === 'big';
    const pulsoFala = falando ? Math.abs(Math.sin(tt * 12)) * 1.8 : 0;

    const pal = p.olho || G;
    const corOlho = p.luzes >= 1 ? pal.forte : (ach ? pal.fraca : pal.luz);
    ctx.shadowColor = corOlho;
    ctx.shadowBlur = (ach ? 2 : (falando ? 12 : 7));

    if (p.eyes === 'closed' || ach) {
      ctx.strokeStyle = corOlho;
      ctx.lineWidth = 2.2;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(-6, 0);
      ctx.lineTo(6, 0);
      ctx.stroke();
    } else if (p.eyes === 'sleepy') {
      ctx.strokeStyle = corOlho;
      ctx.lineWidth = 2.4;
      ctx.beginPath();
      ctx.arc(0, 0, 5.5, 0, Math.PI);
      ctx.stroke();
    } else if (p.eyes === 'happy') {
      ctx.strokeStyle = corOlho;
      ctx.lineWidth = 2.8;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.arc(0, 3, 6, Math.PI * 1.15, Math.PI * 1.85);
      ctx.stroke();
    } else if (p.eyes === 'wide') {
      const rOut = 8.0 + pulsoFala, rIn = 3.6;
      ctx.fillStyle = pal.forte;
      ctx.beginPath();
      ctx.arc(lx, ly, rOut, 0, Math.PI * 2);
      ctx.arc(lx, ly, rIn, 0, Math.PI * 2, true);
      ctx.fill();

      ctx.fillStyle = G.corpo;
      ctx.beginPath();
      ctx.arc(lx, ly, rIn, 0, Math.PI * 2);
      ctx.fill();
    } else if (p.eyes === 'spiral') {
      ctx.strokeStyle = corOlho;
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      for (let a = 0; a < Math.PI * 4; a += 0.25) {
        const r = 1.0 + a * 1.3;
        const x = Math.cos(a + tt * 6) * r;
        const y = Math.sin(a + tt * 6) * r;
        if (a === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    } else {
      const rOut = 6.2 + pulsoFala, rIn = 3.0;

      ctx.fillStyle = corOlho;
      ctx.beginPath();
      ctx.arc(lx, ly, rOut, 0, Math.PI * 2);
      ctx.arc(lx, ly, rIn, 0, Math.PI * 2, true);
      ctx.fill();

      ctx.fillStyle = G.corpo;
      ctx.beginPath();
      ctx.arc(lx, ly, rIn, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = '#FFFFFF';
      ctx.shadowBlur = 0;
      ctx.beginPath();
      ctx.arc(lx - 2, ly - 2, 1.2, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }

  // ---------- corpo (Ultra T / Upgrade) ----------
  function corpo(p, t) {
    const ach = p.dorme;
    const tt = t + (p.fase || 0);

    const balancoX = p.balanca ? Math.sin(tt * p.velBalanco) * 1.5 : 0;
    const respiracaoY = p.balanca ? Math.sin(tt * p.velBalanco * 0.7) * 0.8 : 0;

    ctx.save();
    if (p.pose === 'deitado' || ach) {
      ctx.translate(balancoX, 4);
      if (p.pose === 'deitado') {
        ctx.translate(-8, 6);
        ctx.rotate(0.35);
      } else {
        ctx.scale(1.02, 0.94);
      }
    } else {
      ctx.translate(balancoX, respiracaoY);
    }
    if (p.rot) ctx.rotate(p.rot);
    if (p.sx != null || p.sy != null) {
      ctx.scale(p.sx ?? 1, p.sy ?? 1);
    }

    // 1. Pernas (Brancas, retas e grossas, com cel-shading cinza e contorno preto)
    ctx.fillStyle = G.branco;
    ctx.strokeStyle = G.bordaBranco;
    ctx.lineWidth = 1.6;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';

    const tap = p.peImpaciente ? Math.max(0, Math.sin(tt * 14) * 4) : 0;
    const tracoPernas = () => {
      if (p.pose === 'lotus') {
        ctx.beginPath();
        ctx.moveTo(-17, -24);
        ctx.quadraticCurveTo(-26, -18, -24, -8);
        ctx.quadraticCurveTo(-22, -2, -10, -2);
        ctx.quadraticCurveTo(0, -4, 10, -2);
        ctx.quadraticCurveTo(22, -2, 24, -8);
        ctx.quadraticCurveTo(26, -18, 17, -24);
        ctx.closePath();
        return;
      }
      if (p.pose === 'sentado') {
        ctx.beginPath();
        ctx.moveTo(-17, -24);
        ctx.lineTo(-17, -12);
        ctx.lineTo(8, -12);
        ctx.lineTo(8, 0);
        ctx.quadraticCurveTo(9, 1, 14, 0);
        ctx.lineTo(14, -14);
        ctx.lineTo(-3, -14);
        ctx.lineTo(-3, -24);
        ctx.closePath();
        return;
      }
      ctx.beginPath();
      ctx.moveTo(-17, -24);
      ctx.lineTo(-17, -1);
      ctx.quadraticCurveTo(-18, 0, -16, 0);
      ctx.lineTo(-4, 0);
      ctx.quadraticCurveTo(-3, 0, -3, -2);
      ctx.lineTo(-3, -22);
      ctx.quadraticCurveTo(0, -20, 3, -22);
      ctx.lineTo(3, -2);
      ctx.quadraticCurveTo(3, 0, 4, 0);
      ctx.lineTo(16, 0 - tap);
      ctx.quadraticCurveTo(18, 0 - tap, 17, -1 - tap);
      ctx.lineTo(17, -24);
      ctx.closePath();
    };
    tracoPernas();
    ctx.fill();

    // Sombreamento cel-shaded cinza (#D5D9DD)
    ctx.fillStyle = G.sombraBranco;
    if (p.pose === 'lotus') {
      ctx.beginPath();
      ctx.moveTo(-14, -8);
      ctx.quadraticCurveTo(0, -2, 14, -8);
      ctx.lineTo(10, -2);
      ctx.quadraticCurveTo(0, -4, -10, -2);
      ctx.closePath();
      ctx.fill();
    } else if (p.pose === 'sentado') {
      ctx.beginPath();
      ctx.moveTo(-17, -14);
      ctx.lineTo(-3, -14);
      ctx.lineTo(8, -14);
      ctx.lineTo(8, -12);
      ctx.lineTo(-17, -12);
      ctx.closePath();
      ctx.fill();
    } else {
      ctx.beginPath();
      ctx.moveTo(-6, -22);
      ctx.lineTo(-3, -22);
      ctx.lineTo(-3, 0);
      ctx.lineTo(-16, 0);
      ctx.lineTo(-16, -2);
      ctx.lineTo(-6, -2);
      ctx.closePath();
      ctx.fill();

      ctx.beginPath();
      ctx.moveTo(3, -22);
      ctx.lineTo(6, -22);
      ctx.lineTo(6, -2);
      ctx.lineTo(16, -2 - tap);
      ctx.lineTo(16, 0 - tap);
      ctx.lineTo(3, 0);
      ctx.closePath();
      ctx.fill();
    }

    tracoPernas();
    ctx.stroke();

    // 2. Peitoral e Barriga (Brancos, encaixam no "V" dos ombros pretos)
    ctx.fillStyle = G.branco;
    ctx.beginPath();
    ctx.moveTo(-17, -24);
    ctx.lineTo(-18, -48);
    ctx.lineTo(-18, -66);
    ctx.lineTo(0, -48);
    ctx.lineTo(18, -66);
    ctx.lineTo(18, -48);
    ctx.lineTo(17, -24);
    ctx.closePath();
    ctx.fill();

    // Sombreamento cel-shaded no tronco
    ctx.fillStyle = G.sombraBranco;
    ctx.beginPath();
    ctx.moveTo(-17, -24);
    ctx.lineTo(17, -24);
    ctx.lineTo(17, -27);
    ctx.lineTo(-17, -27);
    ctx.closePath();
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(14, -27);
    ctx.lineTo(17, -27);
    ctx.lineTo(18, -48);
    ctx.lineTo(15, -48);
    ctx.closePath();
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(-17, -24);
    ctx.lineTo(-18, -48);
    ctx.lineTo(-18, -66);
    ctx.moveTo(18, -66);
    ctx.lineTo(18, -48);
    ctx.lineTo(17, -24);
    ctx.stroke();

    // 3. Bracos e Maos (Tres dedos grandes, dorso preto, palma branca)
    desenharBraco(ctx, -1, p.armL, p, t);
    desenharBraco(ctx, 1, p.armR, p, t);

    // 4. Cabeca e Ombros (Preto solido com V agudo no peito)
    ctx.fillStyle = G.corpo;
    ctx.strokeStyle = G.bordaPreto;
    ctx.lineWidth = 1.4;

    ctx.beginPath();
    ctx.moveTo(0, -48);
    ctx.lineTo(-18, -66);
    ctx.lineTo(-32, -61);
    ctx.quadraticCurveTo(-33, -64, -28, -67);
    ctx.quadraticCurveTo(-17, -72, -15, -84);
    ctx.quadraticCurveTo(-12, -98, 0, -100);
    ctx.quadraticCurveTo(12, -98, 15, -84);
    ctx.quadraticCurveTo(17, -72, 28, -67);
    ctx.quadraticCurveTo(33, -64, 32, -61);
    ctx.lineTo(18, -66);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Contorno do decote em V no peito
    ctx.strokeStyle = G.bordaBranco;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(-18, -66);
    ctx.lineTo(0, -48);
    ctx.lineTo(18, -66);
    ctx.stroke();

    // 5. Omnitrix
    desenharOmnitrix(ctx, 0, -38);

    // 6. Padrao de Circuitos Neon
    desenharCircuitos(ctx, p, t);

    // 7. Olho Unico do Ultra T
    desenharOlho(ctx, p, t);

    ctx.restore();
  }

  // ---------- o que o corpo vira / efeitos vetoriais ----------
  function teclado(px, py, t, s) {
    ctx.save();
    ctx.translate(px, py - 20 * s);
    ctx.scale(s, s);

    ctx.fillStyle = 'rgba(10, 20, 14, 0.88)';
    ctx.strokeStyle = G.luz;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(-24, 0);
    ctx.lineTo(24, 0);
    ctx.lineTo(28, 12);
    ctx.lineTo(-28, 12);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    for (let row = 0; row < 2; row++) {
      for (let col = 0; col < 8; col++) {
        const kx = -20 + col * 5 + row * 1.5;
        const ky = 2 + row * 5;
        const ativa = (Math.floor(t * 12 + col * 3 + row * 7) % 5) === 0;
        ctx.fillStyle = ativa ? G.forte : G.fraca;
        ctx.fillRect(kx, ky, 3.5, 3.5);
      }
    }
    ctx.restore();
  }

  function olhoLupa(px, py, t, s, largo) {
    ctx.save();
    ctx.translate(px, py - 84 * s);
    ctx.scale(s, s);

    ctx.strokeStyle = G.luz;
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.arc(0, 0, 10 + Math.sin(t * 6) * 1.5, 0, Math.PI * 2);
    ctx.stroke();

    const alcance = largo ? 55 : 35;
    const osc = Math.sin(t * 4) * 6;
    const grad = ctx.createLinearGradient(0, 0, alcance, osc);
    grad.addColorStop(0, 'rgba(118, 255, 3, 0.6)');
    grad.addColorStop(1, 'rgba(118, 255, 3, 0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(6, 0);
    ctx.lineTo(alcance, osc - 12);
    ctx.lineTo(alcance, osc + 12);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = G.forte;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(alcance * 0.7, osc - 8);
    ctx.lineTo(alcance * 0.7, osc + 8);
    ctx.stroke();
    ctx.restore();
  }

  function engrenagem(gx, gy, t, s) {
    ctx.save();
    ctx.translate(gx, gy);
    ctx.scale(s, s);
    const ang = t * 3;
    ctx.rotate(ang);

    ctx.fillStyle = 'rgba(10, 24, 16, 0.9)';
    ctx.strokeStyle = G.luz;
    ctx.lineWidth = 1.6;

    const dentes = 8, rIn = 9, rOut = 13;
    ctx.beginPath();
    for (let i = 0; i < dentes * 2; i++) {
      const a = (i * Math.PI) / dentes;
      const r = i % 2 === 0 ? rOut : rIn;
      const x = Math.cos(a) * r, y = Math.sin(a) * r;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = G.luz;
    ctx.beginPath();
    ctx.arc(0, 0, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = G.forte;
    ctx.beginPath();
    ctx.arc(0, 0, 2, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
    ctx.save();
    ctx.translate(gx, gy);
    ctx.scale(s, s);
    const fSpark = Math.floor(t * 8) % 3;
    ctx.fillStyle = G.forte;
    if (fSpark === 0) { ctx.fillRect(-14, -14, 2, 2); ctx.fillRect(15, -8, 2, 2); }
    else if (fSpark === 1) { ctx.fillRect(12, -15, 2, 2); ctx.fillRect(-12, 14, 2, 2); }
    ctx.restore();
  }

  function ajudante(px, py, t, s, olho) {
    ctx.save();
    ctx.translate(px + 40 * s, py - 45 * s + Math.sin(t * 5) * (4 * s));
    ctx.scale(s * 0.42, s * 0.42);

    const pMini = { eyes: 'happy', lx: 0, ly: 0, armL: 'down', armR: 'up', mouth: 'smile', luzes: 1, velPulso: 8, dorme: false, fase: 0, olho };
    corpo(pMini, t);

    ctx.fillStyle = G.luz;
    ctx.globalAlpha = 0.6;
    for (let i = 0; i < 3; i++) {
      const f = ((t * 2 + i * 0.33) % 1);
      ctx.beginPath();
      ctx.arc(Math.sin(t * 8 + i) * 6, 6 + f * 14, 2 * (1 - f), 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function balaoPensando(px, py, t, s, lado) {
    ctx.save();
    const bx = lado === 'direita' ? px + 36 * s : px - 18 * s;
    const by = py - 118 * s;
    ctx.translate(bx, by);
    ctx.scale(s, s);

    ctx.fillStyle = 'rgba(12, 18, 14, 0.92)';
    ctx.strokeStyle = G.luz;
    ctx.lineWidth = 1.5;

    const bw = 32, bh = 18;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(-bw / 2, -bh / 2, bw, bh, 6);
    else ctx.rect(-bw / 2, -bh / 2, bw, bh);
    ctx.fill();
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(lado === 'direita' ? -18 : 18, 12, 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(lado === 'direita' ? -23 : 23, 18, 1.8, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    const n = Math.floor(t * 2.5) % 4;
    for (let i = 0; i < 3; i++) {
      ctx.fillStyle = i < n ? G.forte : G.fraca;
      ctx.beginPath();
      ctx.arc(-8 + i * 8, 0, 2.2, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function balaoSinal(px, py, sinal, s) {
    ctx.save();
    ctx.translate(px, py - 120 * s);
    ctx.scale(s, s);

    const cor = sinal === '!' ? G.amarelo : G.luz;
    ctx.fillStyle = cor;
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 1.4;

    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(-12, -14, 24, 20, 5);
    else ctx.rect(-12, -14, 24, 20);
    ctx.moveTo(-3, 6);
    ctx.lineTo(0, 12);
    ctx.lineTo(3, 6);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = '#000000';
    ctx.font = 'bold 15px monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(sinal, 0, -4);
    ctx.restore();
  }

  function ondasSom(px, py, t, s) {
    ctx.save();
    ctx.translate(px + 24 * s, py - 84 * s);
    ctx.scale(s, s);
    ctx.strokeStyle = G.luz;
    ctx.lineWidth = 1.8;
    ctx.lineCap = 'round';
    const f = Math.floor(t * 6) % 3;
    for (let i = 0; i <= f; i++) {
      ctx.beginPath();
      ctx.arc(0, 0, 8 + i * 7, -Math.PI * 0.35, Math.PI * 0.35);
      ctx.stroke();
    }
    ctx.restore();
  }

  function gotas(px, py, t, n, s) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);
    for (let i = 0; i < n; i++) {
      const f = ((t * 0.8 + i * 0.5) % 1);
      const gx = i ? -24 : 24, gy = -90 + f * 20;
      ctx.globalAlpha = 1 - f * 0.7;
      ctx.fillStyle = G.gota;
      ctx.beginPath();
      ctx.arc(gx, gy, 2.5, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function confete(px, py, t, largura, s) {
    ctx.save();
    ctx.translate(px, py);
    for (let i = 0; i < 16; i++) {
      const x = ((i * 47) % largura) - largura / 2;
      const y = -130 * s + ((t * 60 + i * 23) % (130 * s));
      const cor = i % 3 === 0 ? G.branco : (i % 3 === 1 ? G.luz : G.amarelo);
      ctx.fillStyle = cor;
      ctx.fillRect(x, y, 3 * s, 4 * s);
    }
    ctx.restore();
  }

  function visto(px, py, s) {
    ctx.save();
    ctx.translate(px, py - 116 * s);
    ctx.scale(s, s);
    ctx.strokeStyle = G.luz;
    ctx.lineWidth = 3.2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(-10, 0);
    ctx.lineTo(-3, 7);
    ctx.lineTo(11, -7);
    ctx.stroke();
    ctx.restore();
  }

  function zzz(px, py, t, s) {
    ctx.save();
    ctx.translate(px + 18 * s, py - 85 * s);
    ctx.scale(s, s);
    for (let i = 0; i < 3; i++) {
      const f = (t * 0.5 + i / 3) % 1;
      const zx = f * 18 + Math.sin(f * 8 + i) * 5, zy = -f * 38;
      ctx.globalAlpha = 0.75 * (1 - f);
      ctx.fillStyle = G.luz;
      ctx.font = `bold ${Math.round(8 + i * 3)}px sans-serif`;
      ctx.fillText('Z', zx, zy);
    }
    ctx.restore();
  }

  function coracao(px, py, f, s) {
    ctx.save();
    ctx.translate(px, py - (40 + f * 35) * s);
    ctx.scale(s * (0.8 + 0.3 * Math.sin(f * Math.PI * 4)), s * (0.8 + 0.3 * Math.sin(f * Math.PI * 4)));
    ctx.globalAlpha = 1 - f;
    ctx.fillStyle = G.coracao;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.bezierCurveTo(-5, -6, -10, -3, -10, 3);
    ctx.bezierCurveTo(-10, 8, -5, 12, 0, 16);
    ctx.bezierCurveTo(5, 12, 10, 8, 10, 3);
    ctx.bezierCurveTo(10, -3, 5, -6, 0, 0);
    ctx.fill();
    ctx.restore();
  }

  // ---------- helper timing assimetrico e animacoes do Ultra T ----------
  function faseAssimetrica(t, fases) {
    let duracaoTotal = 0;
    for (let i = 0; i < fases.length; i++) duracaoTotal += fases[i][0];
    if (duracaoTotal <= 0) return { nome: '', prog: 0, idx: 0 };
    let tMod = ((t % duracaoTotal) + duracaoTotal) % duracaoTotal;
    let acumulado = 0;
    for (let i = 0; i < fases.length; i++) {
      const [dur, nome] = fases[i];
      if (tMod < acumulado + dur || i === fases.length - 1) {
        const prog = dur > 0 ? (tMod - acumulado) / dur : 0;
        return { nome, prog, idx: i };
      }
      acumulado += dur;
    }
    return { nome: fases[0][1], prog: 0, idx: 0 };
  }

  function achouLampada(px, py, progresso, s) {
    ctx.save();
    ctx.translate(px, py - 122 * s);
    ctx.scale(s, s);
    const f = Math.min(1, Math.max(0, progresso / 450));
    const escala = 1 + Math.sin(f * Math.PI) * 0.35;
    ctx.scale(escala, escala);
    ctx.shadowColor = G.luz;
    ctx.shadowBlur = 12;

    ctx.fillStyle = G.luz;
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.arc(0, -6, 10, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = G.omniEscuro;
    ctx.fillRect(-4, 3, 8, 4);

    ctx.strokeStyle = G.forte;
    ctx.lineWidth = 1.8;
    for (let i = 0; i < 6; i++) {
      const a = (i * Math.PI) / 3;
      ctx.beginPath();
      ctx.moveTo(Math.cos(a) * 13, -6 + Math.sin(a) * 13);
      ctx.lineTo(Math.cos(a) * 18, -6 + Math.sin(a) * 18);
      ctx.stroke();
    }

    ctx.fillStyle = '#000000';
    ctx.font = 'bold 12px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('!', 0, -6);
    ctx.restore();
  }

  function tokenMalabarismo(px, py, tempo, s) {
    ctx.save();
    const f = (tempo * 2.2) % 1;
    const x = px + Math.cos(tempo * 4.4) * (20 * s);
    const y = py - (25 + Math.sin(f * Math.PI) * 45) * s;
    ctx.translate(x, y);
    ctx.scale(s, s);
    ctx.shadowColor = G.luz;
    ctx.shadowBlur = 10;
    ctx.fillStyle = G.luz;
    ctx.beginPath();
    ctx.arc(0, 0, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.arc(-1.5, -1.5, 1.8, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function prancheta(px, py, tt, s) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);
    ctx.fillStyle = '#1A241E';
    ctx.strokeStyle = G.bordaBranco;
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(-12, -18, 24, 30, 3);
    else ctx.rect(-12, -18, 24, 30);
    ctx.fill(); ctx.stroke();

    ctx.fillStyle = G.omniAnel;
    ctx.fillRect(-6, -21, 12, 4);

    ctx.fillStyle = '#E8F5E9';
    ctx.fillRect(-9, -15, 18, 24);
    const pulso = 1 + Math.sin(tt * 8) * 0.15;
    ctx.save();
    ctx.translate(0, -3);
    ctx.scale(pulso, pulso);
    ctx.fillStyle = G.luz;
    ctx.shadowColor = G.luz;
    ctx.shadowBlur = 6;
    ctx.font = 'bold 15px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('?', 0, 0);
    ctx.restore();
    ctx.restore();
  }

  function aneisImpacto(px, py, tt, s) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);
    for (let i = 0; i < 3; i++) {
      const f = ((tt * 3 + i * 0.33) % 1);
      const r = 3 + f * 16;
      ctx.globalAlpha = Math.max(0, 1 - f);
      ctx.strokeStyle = G.luz;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(0, 0, r, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }

  function chapeuDetetive(px, py, tt, s) {
    ctx.save();
    ctx.translate(px, py - 96 * s);
    ctx.scale(s, s);
    const inclinacao = Math.sin((tt - 0.08) * 2) * 0.06;
    ctx.rotate(inclinacao);
    ctx.fillStyle = '#1A231F';
    ctx.strokeStyle = G.bordaPreto;
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.ellipse(0, 4, 18, 5, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(-11, 4);
    ctx.quadraticCurveTo(-12, -10, 0, -12);
    ctx.quadraticCurveTo(12, -10, 11, 4);
    ctx.closePath();
    ctx.fill(); ctx.stroke();

    ctx.strokeStyle = G.luz;
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.moveTo(-10, 3);
    ctx.lineTo(10, 3);
    ctx.stroke();
    ctx.restore();
  }

  function particulasMeditacao(px, py, tt, s) {
    ctx.save();
    const rx = 36 * s, ry = 12 * s;
    for (let i = 0; i < 6; i++) {
      const ang = tt * 2.2 + (i * Math.PI) / 3;
      const x = px + Math.cos(ang) * rx;
      const y = py + Math.sin(ang) * ry;
      const tipo = i % 4;
      ctx.save();
      ctx.translate(x, y);
      ctx.scale(s, s);
      ctx.shadowColor = G.luz;
      ctx.shadowBlur = 6;
      if (tipo === 0 || tipo === 1) {
        ctx.fillStyle = tipo === 0 ? G.luz : G.forte;
        ctx.font = 'bold 11px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(tipo === 0 ? '0' : '1', 0, 0);
      } else if (tipo === 2) {
        engrenagem(0, 0, tt * 2, 0.4);
      } else {
        ctx.fillStyle = G.forte;
        ctx.fillRect(-2, -2, 4, 4);
      }
      ctx.restore();
    }
    ctx.restore();
  }

  function anelEnergiaChao(px, py, tt, s, flut) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);
    const fator = Math.max(0.6, 1 - (flut || 0) / (60 * s));
    ctx.fillStyle = 'rgba(0, 0, 0, 0.35)';
    ctx.beginPath();
    ctx.ellipse(0, 0, 24 * fator, 6 * fator, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = G.luz;
    ctx.shadowColor = G.luz;
    ctx.shadowBlur = 8;
    ctx.lineWidth = 1.6;
    ctx.globalAlpha = 0.5 + Math.sin(tt * 4) * 0.2;
    ctx.beginPath();
    ctx.ellipse(0, 0, (26 + Math.sin(tt * 5) * 2) * fator, 7 * fator, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  function pilhaLivros(px, py, tt, s) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);
    const cores = [G.luz, '#1E88E5', G.amarelo, '#B366FF', '#FFFFFF'];
    const larguras = [30, 28, 26, 24, 22];
    for (let i = 0; i < 5; i++) {
      const bal = Math.sin((tt - 0.08) * 4 + i * 0.4) * (1.2 + i * 1.8);
      const ly = -i * 8;
      ctx.save();
      ctx.translate(bal, ly);
      ctx.fillStyle = cores[i % cores.length];
      ctx.strokeStyle = G.bordaBranco;
      ctx.lineWidth = 1.2;
      ctx.fillRect(-larguras[i] / 2, -7, larguras[i], 7);
      ctx.strokeRect(-larguras[i] / 2, -7, larguras[i], 7);
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect(-larguras[i] / 2 + 2, -5, larguras[i] - 4, 3);
      ctx.restore();
    }
    ctx.restore();
  }

  function bigornaFerreiro(px, py, tt, s, fase) {
    ctx.save();
    const vibraX = fase.nome === 'impacto' ? (Math.sin(tt * 60) * 2.5 * s) : 0;
    ctx.translate(px + vibraX, py);
    ctx.scale(s, s);
    ctx.fillStyle = '#1B2620';
    ctx.strokeStyle = G.luz;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(-16, 0);
    ctx.lineTo(16, 0);
    ctx.lineTo(12, -10);
    ctx.lineTo(20, -18);
    ctx.lineTo(14, -18);
    ctx.lineTo(12, -14);
    ctx.lineTo(-14, -14);
    ctx.lineTo(-22, -18);
    ctx.lineTo(-24, -14);
    ctx.lineTo(-12, -10);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    if (fase.nome === 'impacto') {
      const fSpark = fase.prog;
      for (let i = 0; i < 5; i++) {
        const ang = -Math.PI * 0.15 - (i * Math.PI * 0.7) / 4;
        const dist = 6 + fSpark * 28;
        const sx = Math.cos(ang) * dist;
        const sy = -14 + Math.sin(ang) * dist;
        ctx.fillStyle = i % 2 === 0 ? G.amarelo : G.forte;
        ctx.shadowColor = G.luz;
        ctx.shadowBlur = 6;
        ctx.fillRect(sx, sy, 2.5, 2.5);
      }
    }
    ctx.restore();
  }

  function marteloFerreiro(px, py, tt, s, fase) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);
    let ang = 0;
    if (fase.nome === 'erguendo') {
      ang = -0.4 - fase.prog * 0.8;
    } else if (fase.nome === 'antecipacao') {
      ang = -1.2 + Math.sin(tt * 35) * 0.05;
    } else if (fase.nome === 'descendo') {
      ang = -1.2 + fase.prog * 1.5;
      ctx.strokeStyle = 'rgba(118, 255, 3, 0.45)';
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(10, -35, 32, -1.2, ang);
      ctx.stroke();
    } else if (fase.nome === 'impacto') {
      ang = 0.3;
    } else {
      ang = 0.3 - fase.prog * 0.7;
    }

    ctx.translate(14, -40);
    ctx.rotate(ang);
    ctx.fillStyle = '#6D4C41';
    ctx.fillRect(-2, -32, 4, 38);
    ctx.fillStyle = '#263238';
    ctx.strokeStyle = G.luz;
    ctx.lineWidth = 1.4;
    ctx.fillRect(-10, -42, 20, 12);
    ctx.strokeRect(-10, -42, 20, 12);
    ctx.restore();
  }

  function levantamentoPeso(px, py, tt, s, fase) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);
    let barraY = -50;
    if (fase.nome === 'forca') {
      barraY = -48 + Math.sin(tt * 40) * 1.2;
    } else if (fase.nome === 'ergue') {
      barraY = -48 - fase.prog * 58;
    } else {
      barraY = -106 + fase.prog * 58;
    }
    ctx.strokeStyle = G.omniAnel;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(-36, barraY);
    ctx.lineTo(36, barraY);
    ctx.stroke();
    for (const sx of [-34, 34]) {
      ctx.fillStyle = '#1A1A1A';
      ctx.strokeStyle = G.luz;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(sx - 4, barraY - 14, 8, 28, 2);
      else ctx.rect(sx - 4, barraY - 14, 8, 28);
      ctx.fill(); ctx.stroke();
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(sx - (sx > 0 ? -4 : 10), barraY - 10, 6, 20, 2);
      else ctx.rect(sx - (sx > 0 ? -4 : 10), barraY - 10, 6, 20);
      ctx.fill(); ctx.stroke();
    }
    ctx.restore();
  }

  function faixaCorrida(px, py, tt, s) {
    ctx.save();
    ctx.translate(px, py - 86 * s);
    ctx.scale(s, s);
    ctx.fillStyle = G.luz;
    ctx.fillRect(-16, -4, 32, 5);
    const osc = Math.sin(tt * 16) * 4;
    ctx.beginPath();
    ctx.moveTo(-16, -2);
    ctx.lineTo(-28, -6 + osc);
    ctx.lineTo(-24, 0 + osc);
    ctx.lineTo(-16, 1);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  function poeiraCorrida(px, py, tt, s) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);
    for (let i = 0; i < 3; i++) {
      const f = ((tt * 3 + i * 0.33) % 1);
      ctx.fillStyle = 'rgba(213, 217, 221, ' + (1 - f) * 0.7 + ')';
      ctx.beginPath();
      ctx.arc(-i * 8 - f * 12, -f * 8, 2 + f * 4, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function oculosProtecao(px, py, tt, s) {
    ctx.save();
    ctx.translate(px, py - 84 * s);
    ctx.scale(s, s);
    ctx.strokeStyle = '#1C2520';
    ctx.lineWidth = 2.4;
    ctx.beginPath();
    ctx.moveTo(-18, 0); ctx.lineTo(18, 0); ctx.stroke();
    ctx.fillStyle = 'rgba(0, 229, 255, 0.35)';
    ctx.strokeStyle = G.luz;
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(-10, -7, 20, 14, 4);
    else ctx.rect(-10, -7, 20, 14);
    ctx.fill(); ctx.stroke();
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(-6, -4); ctx.lineTo(6, 4); ctx.stroke();
    ctx.restore();
  }

  function frascosCiencia(px, py, tt, s, testeOk) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);
    // Frasco 1 (verde)
    ctx.save();
    ctx.translate(-22, -38);
    ctx.strokeStyle = G.bordaBranco;
    ctx.fillStyle = testeOk ? G.forte : G.luz;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(-3, -12); ctx.lineTo(3, -12); ctx.lineTo(3, -6);
    ctx.lineTo(8, 6); ctx.lineTo(-8, 6); ctx.lineTo(-3, -6);
    ctx.closePath();
    ctx.fill(); ctx.stroke();
    const fb = (tt * 3) % 1;
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.arc(0, 2 - fb * 14, 1.4, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // Frasco 2 (inclinado despejando)
    ctx.save();
    ctx.translate(22, -42);
    ctx.rotate(-0.55);
    ctx.strokeStyle = G.bordaBranco;
    ctx.fillStyle = testeOk ? G.amarelo : '#B366FF';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(-3, -12); ctx.lineTo(3, -12); ctx.lineTo(3, -6);
    ctx.lineTo(8, 6); ctx.lineTo(-8, 6); ctx.lineTo(-3, -6);
    ctx.closePath();
    ctx.fill(); ctx.stroke();
    ctx.restore();

    if (testeOk) {
      for (let i = 0; i < 6; i++) {
        const ang = (i * Math.PI) / 3 + tt * 2;
        const d = 16 + ((tt * 20 + i * 8) % 20);
        ctx.fillStyle = i % 2 === 0 ? G.amarelo : G.luz;
        ctx.fillRect(Math.cos(ang) * d, -40 + Math.sin(ang) * d, 2.5, 2.5);
      }
    }
    ctx.restore();
  }

  function capaceteObra(px, py, tt, s) {
    ctx.save();
    ctx.translate(px, py - 96 * s);
    ctx.scale(s, s);
    ctx.fillStyle = G.amarelo;
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.arc(0, 0, 15, Math.PI, 0);
    ctx.closePath();
    ctx.fill(); ctx.stroke();
    ctx.fillRect(-18, -1, 36, 4);
    ctx.strokeRect(-18, -1, 36, 4);
    ctx.restore();
  }

  function blueprint(px, py, tt, s) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);
    ctx.fillStyle = '#1E88E5';
    ctx.strokeStyle = '#90CAF9';
    ctx.lineWidth = 1.2;
    ctx.fillRect(-24, -14, 48, 28);
    ctx.strokeRect(-24, -14, 48, 28);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.lineWidth = 0.8;
    for (let gx = -18; gx <= 18; gx += 6) {
      ctx.beginPath(); ctx.moveTo(gx, -12); ctx.lineTo(gx, 12); ctx.stroke();
    }
    for (let gy = -10; gy <= 10; gy += 5) {
      ctx.beginPath(); ctx.moveTo(-22, gy); ctx.lineTo(22, gy); ctx.stroke();
    }
    const rabisco = Math.sin(tt * 8) * 6;
    ctx.save();
    ctx.translate(rabisco, -2);
    ctx.rotate(-0.6);
    ctx.fillStyle = '#D32F2F';
    ctx.fillRect(-2, -18, 4, 18);
    ctx.fillStyle = '#FFD54A';
    ctx.beginPath(); ctx.moveTo(-2, 0); ctx.lineTo(2, 0); ctx.lineTo(0, 4); ctx.closePath(); ctx.fill();
    ctx.restore();
    ctx.restore();
  }

  function varaPesca(px, py, tt, s, fase) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);
    ctx.strokeStyle = '#8D6E63';
    ctx.lineWidth = 2.4;
    ctx.beginPath();
    ctx.moveTo(10, -40);
    const curva = fase.nome === 'mordeu' || fase.nome === 'puxando' ? 24 : 12;
    ctx.quadraticCurveTo(24, -65, 38 + curva, -75);
    ctx.stroke();

    ctx.strokeStyle = G.luz;
    ctx.lineWidth = 1;
    const pontaX = 38 + curva, pontaY = -75;
    let chumboX = 45, chumboY = -4;
    if (fase.nome === 'puxando') {
      chumboX = 20 + (1 - fase.prog) * 25;
      chumboY = -35 - Math.sin(fase.prog * Math.PI) * 30;
    } else if (fase.nome === 'comemorando') {
      chumboX = 20; chumboY = -35;
    }
    ctx.beginPath();
    ctx.moveTo(pontaX, pontaY);
    ctx.lineTo(chumboX, chumboY);
    ctx.stroke();

    if (fase.nome === 'puxando' || fase.nome === 'comemorando') {
      ctx.fillStyle = G.luz;
      ctx.shadowColor = G.luz;
      ctx.shadowBlur = 8;
      ctx.fillRect(chumboX - 5, chumboY - 5, 10, 10);
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect(chumboX - 2, chumboY - 2, 4, 4);
    } else {
      const fOnda = (tt * 2) % 1;
      ctx.strokeStyle = 'rgba(118, 255, 3, ' + (1 - fOnda) + ')';
      ctx.beginPath();
      ctx.ellipse(45, 0, 4 + fOnda * 12, 1.5 + fOnda * 4, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }

  function mensageiroFoguete(px, py, tt, s, fase) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);
    if (fase.nome === 'embalando') {
      ctx.fillStyle = '#8D6E63';
      ctx.strokeStyle = '#5D4037';
      ctx.lineWidth = 1.2;
      ctx.fillRect(14, -18, 20, 18);
      ctx.strokeRect(14, -18, 20, 18);
      ctx.fillStyle = G.luz;
      ctx.fillRect(22, -18, 4, 18);
      ctx.fillRect(14, -10, 20, 4);
    } else {
      const subida = fase.prog * 140;
      const fy = -18 - subida;
      const fx = 24;
      ctx.save();
      ctx.translate(fx, fy);
      ctx.fillStyle = '#FF5722';
      ctx.beginPath();
      ctx.moveTo(-4, 10); ctx.lineTo(4, 10); ctx.lineTo(0, 18 + Math.sin(tt * 20) * 4);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = '#EEEEEE';
      ctx.strokeStyle = G.luz;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(-6, 10); ctx.lineTo(-6, -6); ctx.lineTo(0, -18); ctx.lineTo(6, -6); ctx.lineTo(6, 10);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
      ctx.restore();
    }
    ctx.restore();
  }

  function nuvemCinza(px, py, tt, s) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);
    ctx.fillStyle = '#455A64';
    ctx.beginPath();
    ctx.arc(-10, 0, 10, 0, Math.PI * 2);
    ctx.arc(6, -4, 12, 0, Math.PI * 2);
    ctx.arc(18, 2, 8, 0, Math.PI * 2);
    ctx.fill();

    const fR = (tt * 3) % 1;
    ctx.strokeStyle = G.luz;
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.moveTo(2, 10); ctx.lineTo(-2, 16); ctx.lineTo(3, 17); ctx.lineTo(0, 24);
    ctx.stroke();
    ctx.restore();
  }

  function fogoExtintor(px, py, tt, s) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);

    const fx = 38, fy = 0;
    for (let i = 0; i < 4; i++) {
      const h = 14 + Math.sin(tt * 15 + i * 1.5) * 6;
      ctx.fillStyle = i % 2 === 0 ? '#FF5722' : G.amarelo;
      ctx.beginPath();
      ctx.moveTo(fx - 10 + i * 5, fy);
      ctx.lineTo(fx - 7 + i * 5, fy - h);
      ctx.lineTo(fx - 4 + i * 5, fy);
      ctx.closePath();
      ctx.fill();
    }

    ctx.fillStyle = '#D32F2F';
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 1.2;
    ctx.fillRect(8, -32, 10, 24);
    ctx.strokeRect(8, -32, 10, 24);
    ctx.strokeStyle = '#212121';
    ctx.lineWidth = 2.4;
    ctx.beginPath();
    ctx.moveTo(13, -32); ctx.lineTo(13, -36); ctx.lineTo(24, -30);
    ctx.stroke();

    for (let i = 0; i < 5; i++) {
      const fEspuma = ((tt * 4 + i * 0.2) % 1);
      const ex = 24 + fEspuma * 16;
      const ey = -30 + fEspuma * 26 + Math.sin(fEspuma * Math.PI) * 4;
      ctx.fillStyle = 'rgba(255, 255, 255, ' + (1 - fEspuma * 0.5) + ')';
      ctx.beginPath();
      ctx.arc(ex, ey, 2 + fEspuma * 3, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function cafeCooldown(px, py, tt, s) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);

    ctx.fillStyle = '#5D4037';
    ctx.strokeStyle = '#3E2723';
    ctx.lineWidth = 1.2;
    ctx.fillRect(-16, -10, 32, 4);
    ctx.fillRect(-14, -6, 4, 6);
    ctx.fillRect(10, -6, 4, 6);

    const cx = 14, cy = -26;
    ctx.fillStyle = '#ECEFF1';
    ctx.strokeStyle = G.bordaBranco;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(cx - 6, cy - 8, 12, 10, 2);
    else ctx.rect(cx - 6, cy - 8, 12, 10);
    ctx.fill(); ctx.stroke();
    ctx.beginPath();
    ctx.arc(cx + 6, cy - 3, 3, -Math.PI / 2, Math.PI / 2);
    ctx.stroke();

    for (let i = 0; i < 2; i++) {
      const fVapor = ((tt * 0.8 + i * 0.5) % 1);
      const vy = cy - 10 - fVapor * 16;
      const vx = cx + Math.sin(tt * 4 + i) * 3;
      ctx.strokeStyle = 'rgba(255, 255, 255, ' + (1 - fVapor) * 0.7 + ')';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(vx, vy, 2, 0, Math.PI);
      ctx.stroke();
    }

    const ax = -26, ay = -12;
    ctx.strokeStyle = G.luz;
    ctx.fillStyle = G.amarelo;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(ax - 6, ay - 8); ctx.lineTo(ax + 6, ay - 8);
    ctx.lineTo(ax - 6, ay + 8); ctx.lineTo(ax + 6, ay + 8);
    ctx.closePath();
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(ax, ay + 5, 2.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function bolhaSono(px, py, tt, s) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);
    const f = Math.sin((tt * 1.4) % Math.PI);
    const r = (2.5 + f * 5.5);
    ctx.fillStyle = 'rgba(118, 255, 3, 0.4)';
    ctx.strokeStyle = G.luz;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.arc(-r * 0.3, -r * 0.3, r * 0.25, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function estrelinhasVitoria(px, py, tt, s) {
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);
    for (let i = 0; i < 6; i++) {
      const f = ((tt * 1.5 + i / 6) % 1);
      const ang = (i * Math.PI) / 3;
      const dist = 15 + f * 35;
      const sx = Math.cos(ang) * dist;
      const sy = Math.sin(ang) * dist;
      ctx.fillStyle = i % 2 === 0 ? G.amarelo : G.forte;
      ctx.shadowColor = G.luz;
      ctx.shadowBlur = 6;
      ctx.globalAlpha = 1 - f;
      ctx.fillRect(sx, sy, 3, 3);
    }
    ctx.restore();
  }

  // ---------- aura das formas do Megabrain ----------
  const OURO = { luz: '#FFD54A', forte: '#FFF3B0', fraca: '#B8860B', bordaPreto: '#4A3B10' };
  function trocarPaleta(nova) {
    const antes = {};
    for (const k of Object.keys(nova)) { antes[k] = G[k]; G[k] = nova[k]; }
    return antes;
  }

  function aura(px, py, t, nivel, achata, s) {
    if (nivel <= 0) return;
    ctx.save();
    ctx.translate(px, py);
    ctx.scale(s, s);

    const cor = nivel === 3 ? '#FFD54A' : (nivel === 2 ? G.luz : G.fraca);
    ctx.strokeStyle = cor;
    ctx.shadowColor = cor;
    ctx.shadowBlur = nivel >= 2 ? 16 : 8;
    ctx.lineWidth = nivel >= 2 ? 3 : 1.8;
    ctx.globalAlpha = nivel === 1 ? 0.45 : (0.6 + 0.2 * Math.sin(t * 6));

    ctx.beginPath();
    ctx.moveTo(-20, 2);
    ctx.lineTo(-20, -64);
    ctx.quadraticCurveTo(-22, -104, 0, -104);
    ctx.quadraticCurveTo(22, -104, 20, -64);
    ctx.lineTo(20, 2);
    ctx.closePath();
    ctx.stroke();

    if (nivel === 3) {
      ctx.fillStyle = '#FFF3B0';
      for (let i = 0; i < 6; i++) {
        const f = ((t * 1.2 + i / 6) % 1);
        const sx = -24 + ((i * 13) % 49);
        const sy = 4 - f * 110;
        ctx.globalAlpha = 1 - f;
        ctx.fillRect(sx, sy, 2.5, 2.5);
      }
    }
    ctx.restore();
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
    const ativ = v.dados && v.dados.atividade;

    let cx = Math.round(v.cx), cy = base;
    const p = { eyes: 'open', lx: 0, ly: 0, armL: 'down', armR: 'down', mouth: 'none', luzes: 0, velPulso: 4,
                balanca: false, velBalanco: 2.5, dorme: false, lupa: false, fase: v.fase,
                olho: paletaOlho(v.dados && v.dados.cli), sx: 1, sy: 1, rot: 0, pose: 'em_pe',
                peImpaciente: false };
    const tt = t + v.fase;
    const pisca = (tt % 3.4) < 0.15;
    let alfa = 1;
    const hEst = humor.estado;
    const altura = Math.min(H * 0.66, slotW * 0.78, 250);
    const s = Math.max(0.4, altura / 100);

    if (ativ === 'erro') {
      p.velPulso = 16;
      if (v.errosSeguidos >= 2) {
        p.eyes = 'wide'; p.armL = 'mid'; p.armR = 'mid';
      } else {
        p.rot = 0.28; cy += Math.round(5 * s);
        p.eyes = 'spiral'; p.armL = 'mid'; p.armR = 'mid';
      }
    } else if (ativ === 'cooldown') {
      p.pose = 'sentado'; p.armL = 'mid'; p.armR = 'mid'; p.eyes = 'sleepy';
    } else if (ativ === 'testando' || ativ === 'teste_ok') {
      p.eyes = 'wide'; p.armL = 'mid'; p.armR = 'mid'; p.velPulso = 10;
      p.sy = 1 + Math.sin(tt * 4) * 0.02;
    } else if (ativ === 'arquiteto') {
      p.eyes = 'open'; p.armL = 'mid'; p.armR = 'mid'; p.velPulso = 8;
    } else if (ativ === 'pescando') {
      const fasePesca = faseAssimetrica(tt, [[2.2, 'aguardando'], [0.4, 'mordeu'], [0.8, 'puxando'], [1.2, 'comemorando']]);
      p.armL = 'down'; p.armR = 'mid';
      if (fasePesca.nome === 'comemorando') { p.eyes = 'happy'; p.mouth = 'smile'; }
      else if (fasePesca.nome === 'mordeu' || fasePesca.nome === 'puxando') { p.eyes = 'wide'; }
    } else if (ativ === 'enviando') {
      const faseEnvio = faseAssimetrica(tt, [[1.4, 'embalando'], [1.6, 'lancamento'], [1.0, 'tchau']]);
      if (faseEnvio.nome === 'embalando') { p.armL = 'mid'; p.armR = 'mid'; p.sy = 0.95; }
      else { p.armR = 'up'; p.eyes = 'happy'; }
    } else if (ativ === 'bibliotecario' && sit === 'lendo') {
      cx += Math.round(Math.sin(tt * 3.5) * 8);
      p.rot = Math.sin(tt * 3.5) * 0.04;
      p.armL = 'mid'; p.armR = 'mid';
      p.ly = -1; p.eyes = 'wide';
    } else {
      switch (sit) {
        case 'ocioso': {
          const parado = hEst === 'carente' || hEst === 'sonolento';
          const maxWander = Math.min(24, slotW * 0.15);
          const amp = parado ? 0 : maxWander;
          cx += Math.round(Math.sin(tt * 0.5) * amp);
          const vel = Math.cos(tt * 0.5);
          p.lx = amp && Math.abs(vel) >= 0.2 ? Math.sign(vel) : 0;
          p.balanca = true; p.mouth = 'smile';
          p.sy = 1 + Math.sin(tt * 2.2) * 0.03;
          p.sx = 1 - Math.sin(tt * 2.2) * 0.02;
          if (pisca) p.eyes = 'closed';
          if ((tt % 7) > 6) p.ly = -1;
          if (hEst === 'animado') {
            p.velPulso = 9; p.velBalanco = 5;
            if ((tt % 4) < 0.7) { cy -= Math.round(Math.abs(Math.sin(tt * 9)) * 3 * s); p.eyes = 'happy'; }
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

          const tempoCiclo = tt % 10;
          if (tempoCiclo < 2.4) {
            const acao = Math.floor(tt / 10) % 4;
            if (acao === 0) { if ((tempoCiclo % 0.6) < 0.18) p.eyes = 'closed'; }
            else if (acao === 1) { p.lx = Math.sin(tempoCiclo * 4) > 0 ? 1 : -1; p.ly = 0; }
            else if (acao === 2) { p.armL = 'up'; p.armR = 'up'; p.sy = 1.08; p.sx = 0.93; }
            else if (acao === 3) {
              p.armL = Math.sin(tempoCiclo * 8) > 0 ? 'mid' : 'up';
              p.armR = Math.sin(tempoCiclo * 8) <= 0 ? 'mid' : 'up';
            }
          }
          break;
        }
        case 'pensando': case 'pensandoVoz': {
          const flut = Math.sin(tt * 2.8) * 7 * s;
          cy -= Math.round(18 * s + flut);
          p.pose = 'lotus'; p.eyes = 'closed'; p.armL = 'mid'; p.armR = 'mid';
          p.velPulso = 12;
          break;
        }
        case 'digitando': {
          const faseFerr = faseAssimetrica(tt, [[0.12, 'erguendo'], [0.28, 'antecipacao'], [0.06, 'descendo'], [0.15, 'impacto'], [0.12, 'recuperacao']]);
          p.armL = 'mid'; p.armR = 'hide'; p.velPulso = 12;
          if (faseFerr.nome === 'impacto') { p.sx = 1.07; p.sy = 0.94; }
          else if (faseFerr.nome === 'descendo') { p.sx = 0.94; p.sy = 1.06; }
          break;
        }
        case 'lendo': {
          cx += Math.round(Math.sin(tt * 2) * 16);
          p.rot = Math.sin(tt * 2) * 0.07 + 0.08;
          p.lupa = true; p.lx = 1; p.armR = 'mid'; p.velPulso = 6;
          break;
        }
        case 'executando': case 'trabalhando': {
          p.velPulso = 14;
          const exIdx = Math.floor(tt / 6) % 3;
          if (exIdx === 0) {
            const fasePeso = faseAssimetrica(tt, [[1.1, 'forca'], [1.2, 'ergue'], [0.7, 'desce']]);
            if (fasePeso.nome === 'forca') {
              p.sy = 0.91; p.sx = 1.09; p.armL = 'mid'; p.armR = 'mid'; p.eyes = 'wide';
              gotas(cx + ox, cy + oy, tt, 2, s);
            } else if (fasePeso.nome === 'ergue') {
              p.sy = 1.13; p.sx = 0.91; p.armL = 'up'; p.armR = 'up'; p.eyes = 'happy';
            } else {
              p.armL = 'mid'; p.armR = 'mid';
            }
          } else if (exIdx === 1) {
            p.sy = 1 + Math.abs(Math.sin(tt * 14)) * 0.06;
            p.sx = 1 - Math.abs(Math.sin(tt * 14)) * 0.05;
            p.armL = Math.sin(tt * 14) > 0 ? 'mid' : 'down';
            p.armR = Math.sin(tt * 14) <= 0 ? 'mid' : 'down';
          } else {
            p.pose = 'flexao'; p.rot = -1.25;
            cx -= Math.round(20 * s);
            cy += Math.round(12 * s + Math.sin(tt * 5) * 6 * s);
            p.armL = 'mid'; p.armR = 'mid';
            gotas(cx + ox + 15 * s, cy + oy - 15 * s, tt, 2, s);
          }
          break;
        }
        case 'delegando': p.lx = 1; p.velPulso = 10; p.armR = 'mid'; break;
        case 'precisa': {
          p.sx = 1.08; p.sy = 1.08;
          p.eyes = 'wide'; p.mouth = 'open'; p.peImpaciente = true;
          p.armL = 'mid'; p.armR = 'up';
          p.luzes = Math.floor(tt * 4) % 2; p.velPulso = 0;
          const tempoPrecisa = (agora - (v.entrouEstadoEm || agora)) / 1000;
          if (tempoPrecisa > 6) {
            const pulo = Math.abs(Math.sin(tt * 8)) * 9 * s;
            cy -= Math.round(pulo);
            p.armL = 'up'; p.armR = 'up';
          }
          break;
        }
        case 'concluido': {
          const fPulo = (tt * 3) % 1;
          if (fPulo < 0.2) { p.sy = 0.88; p.sx = 1.10; }
          else if (fPulo < 0.7) { cy -= Math.round(Math.sin((fPulo - 0.2) / 0.5 * Math.PI) * 16 * s); p.sy = 1.15; p.sx = 0.90; }
          else { p.sy = 0.92; p.sx = 1.08; }
          cx += Math.round(Math.sin(tt * 6) * 4);
          p.eyes = 'happy'; p.mouth = 'smile'; p.armL = 'up'; p.armR = 'up'; p.luzes = 1; p.velPulso = 0;
          break;
        }
        case 'dormindo': {
          const tempoDorm = (agora - (v.entrouEstadoEm || agora)) / 1000;
          if (tempoDorm < 1.8) {
            p.eyes = 'closed'; p.mouth = 'big';
            p.sx = 1.08; p.sy = 0.88;
            p.armL = 'up'; p.armR = 'up';
            p.rot = Math.sin((tempoDorm / 1.8) * Math.PI) * 0.18;
          } else {
            p.eyes = 'closed'; p.dorme = true; p.pose = 'deitado';
            p.armL = 'hide'; p.armR = 'hide'; alfa = 0.6;
            p.sx = 1.05 + Math.sin(tt * 1.4) * 0.04;
            p.sy = 0.93 - Math.sin(tt * 1.4) * 0.03;
            if (Math.floor(tt / 15) % 2 === 1) p.sx = -p.sx;
          }
          break;
        }
        case 'ouvindo':
          p.eyes = 'wide'; p.ly = -1; p.velPulso = 16; p.armR = 'mid'; break;
        case 'falando':
          p.mouth = Math.floor(tt * 7) % 2 ? 'open' : 'smile'; p.velPulso = 8; p.armR = Math.floor(tt * 2) % 2 ? 'mid' : 'down'; break;
        case 'perguntando':
          p.eyes = 'wide'; p.ly = -1; p.armR = 'up'; p.velPulso = 6; break;
      }
    }

    if (agora < v.sustoAte) {
      p.eyes = 'wide';
      p.sx = 0.92;
      p.sy = 1.10;
    }

    const carinho = v.carinhoAte > agora ? 1 - (v.carinhoAte - agora) / 1400 : -1;
    if (carinho >= 0 && sit !== 'dormindo') {
      p.eyes = 'happy'; p.mouth = 'smile'; cy -= Math.round(Math.abs(Math.sin(carinho * Math.PI * 3)) * 3 * s);
    }
    p.cx = cx; p.cy = cy;
    v.cxDesenho = cx;

    // montar/desfazer (teletransporte)
    semente = v.semente;
    mascara = Math.min(1, (agora - v.nasc) / 700);
    if (v.morte) mascara = Math.min(mascara, Math.max(0, 1 - (agora - v.morte) / 600));
    if (mascara <= 0) { mascara = 1; return; }

    const largo = slotW >= 120;
    if (sit === 'concluido') confete(cx + ox, cy + oy, t, Math.min(180, slotW * 0.9), s);
    p.vendado = principal && cego;
    const nivelForma = principal ? forma : 0;
    const transformando = principal && agora < transformandoAte;
    if (transformando) p.luzes = Math.floor(t * 10) % 2;
    if (nivelForma > 0 || transformando) aura(cx + ox, cy + oy, t, Math.max(nivelForma, transformando ? 3 : 0), p.dorme, s);
    const original = nivelForma === 3 ? trocarPaleta(OURO) : null;  // forma suprema: circuitos dourados

    ctx.save();
    ctx.translate(cx + ox, cy + oy);
    ctx.scale(s, s);
    ctx.globalAlpha = alfa * mascara;
    corpo(p, t);
    ctx.restore();

    if (mascara < 1) {
      ctx.save();
      ctx.translate(cx + ox, cy + oy);
      ctx.scale(s, s);
      const corteY = -105 + (1 - mascara) * 110;
      ctx.strokeStyle = G.luz;
      ctx.lineWidth = 2;
      ctx.shadowColor = G.luz;
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(-35, corteY);
      ctx.lineTo(35, corteY);
      ctx.stroke();
      ctx.restore();
    }

    if (original) trocarPaleta(original);

    // Efeitos e acessorios correspondentes a cada estado/atividade
    if (ativ === 'erro') {
      if (v.errosSeguidos >= 2) fogoExtintor(cx + ox, cy + oy, tt, s);
      else nuvemCinza(cx + ox, cy + oy - 120 * s, tt, s);
    } else if (ativ === 'cooldown') {
      cafeCooldown(cx + ox, cy + oy, tt, s);
    } else if (ativ === 'testando' || ativ === 'teste_ok') {
      oculosProtecao(cx + ox, cy + oy, tt, s);
      frascosCiencia(cx + ox, cy + oy, tt, s, ativ === 'teste_ok');
    } else if (ativ === 'arquiteto') {
      capaceteObra(cx + ox, cy + oy, tt, s);
      blueprint(cx + ox, cy + oy - 25 * s, tt, s);
    } else if (ativ === 'pescando') {
      const fasePesca = faseAssimetrica(tt, [[2.2, 'aguardando'], [0.4, 'mordeu'], [0.8, 'puxando'], [1.2, 'comemorando']]);
      varaPesca(cx + ox, cy + oy, tt, s, fasePesca);
    } else if (ativ === 'enviando') {
      const faseEnvio = faseAssimetrica(tt, [[1.4, 'embalando'], [1.6, 'lancamento'], [1.0, 'tchau']]);
      mensageiroFoguete(cx + ox, cy + oy, tt, s, faseEnvio);
    } else if (ativ === 'bibliotecario' && sit === 'lendo') {
      pilhaLivros(cx + ox, cy + oy - 28 * s, tt, s);
    } else if (sit === 'digitando') {
      const faseFerr = faseAssimetrica(tt, [[0.12, 'erguendo'], [0.28, 'antecipacao'], [0.06, 'descendo'], [0.15, 'impacto'], [0.12, 'recuperacao']]);
      bigornaFerreiro(cx + ox + 22 * s, cy + oy, tt, s, faseFerr);
      marteloFerreiro(cx + ox, cy + oy, tt, s, faseFerr);
    } else if (sit === 'lendo') {
      chapeuDetetive(cx + ox, cy + oy, tt, s);
      olhoLupa(cx + ox, cy + oy, tt, s, largo);
    } else if (sit === 'executando' || sit === 'trabalhando') {
      const exIdx = Math.floor(tt / 6) % 3;
      if (exIdx === 0) {
        const fasePeso = faseAssimetrica(tt, [[1.1, 'forca'], [1.2, 'ergue'], [0.7, 'desce']]);
        levantamentoPeso(cx + ox, cy + oy, tt, s, fasePeso);
      } else if (exIdx === 1) {
        faixaCorrida(cx + ox, cy + oy, tt, s);
        poeiraCorrida(cx + ox - 20 * s, cy + oy - 2 * s, tt, s);
      }
    } else if (sit === 'delegando') {
      ajudante(cx + ox, cy + oy, t, s, p.olho);
    } else if (sit === 'pensando' || sit === 'pensandoVoz') {
      const flut = Math.sin(tt * 2.8) * 7 * s;
      anelEnergiaChao(cx + ox, base + oy, tt, s, flut);
      particulasMeditacao(cx + ox, cy + oy - 84 * s, tt, s);
      balaoPensando(cx + ox, cy + oy, tt, s, largo && cx + 40 < W ? 'direita' : 'cima');
    } else if (sit === 'precisa') {
      aneisImpacto(cx + ox + 18 * s, cy + oy - 55 * s, tt, s);
      prancheta(cx + ox - 20 * s, cy + oy - 38 * s, tt, s);
      if (Math.floor(t * 2.5) % 3 !== 2) balaoSinal(cx + ox, cy + oy, '!', s);
    } else if (sit === 'perguntando') {
      balaoSinal(cx + ox, cy + oy, '?', s);
    } else if (sit === 'ouvindo') {
      ondasSom(cx + ox, cy + oy, t, s);
    } else if (sit === 'concluido') {
      visto(cx + ox, cy + oy, s);
      estrelinhasVitoria(cx + ox, cy + oy - 80 * s, tt, s);
    } else if (sit === 'dormindo') {
      const tempoDorm = (agora - (v.entrouEstadoEm || agora)) / 1000;
      if (tempoDorm >= 1.8) {
        bolhaSono(cx + ox - 20 * s, cy + oy - 42 * s, tt, s);
        zzz(cx + ox, cy + oy, t, s);
      }
    } else if (sit === 'ocioso') {
      const tempoCiclo = tt % 10;
      if (tempoCiclo < 2.4 && Math.floor(tt / 10) % 4 === 3) {
        tokenMalabarismo(cx + ox, cy + oy, tempoCiclo, s);
      }
      const ex = humor.extras || [];
      const n = (ex.includes('cansado') ? 1 : 0) + (ex.includes('calor') ? 1 : 0);
      if (n) gotas(cx + ox, cy + oy, t, n, s);
    }

    if (agora < v.sustoAte) balaoSinal(cx + ox, cy + oy, '!', s);
    if (agora < v.achouAte) achouLampada(cx + ox, cy + oy, agora - (v.achouAte - 450), s);
    if (carinho >= 0) coracao(cx + ox, cy + oy, carinho, s);
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
    const agora = Date.now();
    return { id, dados, cx: null, nasc: agora, morte: null, fase: (Math.abs(h) % 100) / 17,
             semente: h || 7, carinhoAte: 0, mostra: dados.estado, ultimoMostra: dados.estado,
             entrouEstadoEm: agora, sustoAte: 0, achouAte: 0, errosSeguidos: 0,
             ultimaAtividade: (dados && dados.atividade) || '',
             ativoDesde: ATIVOS.has(dados.estado) ? agora : null };
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
    const nome = v.dados.projeto || v.dados.cli || 'IA';
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
          <div><b>${duracao(resumo.trabalhando_s || 0)}</b><span>de IA</span></div>
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
    const x = e.clientX - r.left - ox;
    const tolerancia = Math.max(44, Math.min(90, ultimoSlotW * 0.4));
    let melhor = null, dist = tolerancia;
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
    const ativ = v.dados && v.dados.atividade;
    const desde = Date.parse(v.dados.desde || '');
    const ha = Number.isFinite(desde) ? ` · ${duracao((Date.now() - desde) / 1000)}` : '';
    const nome = (v.dados.tipo === 'ajudante' ? 'ajudante · ' : '') + (v.dados.projeto || '?');
    const extra = mostra === 'concluido' || mostra === 'dormindo' ? '' : ha;
    const rotuloTexto = (ativ && ROTULO[ativ]) ? ROTULO[ativ] : (ROTULO[mostra] || mostra);
    return { nome, linha: rotuloTexto + extra };
  }

  let visivel = false;
  const calmo = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const QUADRO_MS = calmo ? 300 : 40;
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
    ultimoSlotW = slotW;
    lista.forEach((v, i) => {
      const alvo = slotW * (i + 0.5);
      v.cx = v.cx == null ? alvo : v.cx + (alvo - v.cx) * 0.15;
    });

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    for (const v of vendels.values()) {
      if (v.morte && relogio - v.morte > 650) { vendels.delete(v.id); continue; }
      if (v.cx == null) continue;
      if (!v.morte && !lista.includes(v)) continue;
      const novoMostra = dormir && !ATIVOS.has(v.dados.estado) ? 'dormindo' : v.dados.estado;
      if (novoMostra !== v.mostra) {
        const antes = v.mostra;
        if ((antes === 'dormindo' || antes === 'ocioso') && (ATIVOS.has(novoMostra) || novoMostra === 'precisa')) {
          v.sustoAte = relogio + 200;
        }
        if (antes === 'lendo' && (ATIVOS.has(novoMostra) || novoMostra === 'concluido')) {
          v.achouAte = relogio + 450;
        }
        v.ultimoMostra = antes;
        v.mostra = novoMostra;
        v.entrouEstadoEm = relogio;
      }
      const ativAtual = v.dados && v.dados.atividade;
      if (ativAtual !== v.ultimaAtividade) {
        if (ativAtual === 'erro') {
          v.errosSeguidos = (v.errosSeguidos || 0) + 1;
        } else if (ativAtual && ativAtual !== 'erro') {
          v.errosSeguidos = 0;
        }
        v.ultimaAtividade = ativAtual;
      }
      if (novoMostra === 'concluido' || novoMostra === 'ocioso') {
        v.errosSeguidos = 0;
      }
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
      el.style.left = `${(v.cx / W) * 100}%`;
    }
    for (const [id, el] of rotulos) if (!presentes.has(id)) { el.remove(); rotulos.delete(id); }
    const extras = ativos.length - lista.length;
    rotulosEl.dataset.extras = extras > 0 ? `+${extras}` : '';

    if (resumoEl) {
      const n = resumo.concluidas || 0, s = resumo.trabalhando_s || 0;
      const txt = n || s ? `hoje: ${n} ${n === 1 ? 'tarefa' : 'tarefas'} · ${duracao(s)} de IA` : '';
      if (resumoEl.textContent !== txt) resumoEl.textContent = txt;
    }
    if (horaEl) {
      const d = new Date();
      const txt = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
      if (horaEl.textContent !== txt) horaEl.textContent = txt;
    }
    camada.style.transform = `translate(${ox}px, ${oy}px)`;
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
