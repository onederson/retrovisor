// Aplicacao OLED Telemetria e Stream Deck para Galaxy S10+
// JS puro, sem bibliotecas externas

(function () {
  'use strict';

  // Parametros de URL e Token
  const paramsUrl = new URLSearchParams(window.location.search);
  const tokenUrl = paramsUrl.get('t');

  function comToken(url) {
    if (!tokenUrl) return url;
    const separador = url.includes('?') ? '&' : '?';
    return `${url}${separador}t=${encodeURIComponent(tokenUrl)}`;
  }

  // Historico de sparklines (ultimos 60 s, max 60 pontos)
  const historicoSparklines = {
    gpuUso: [],
    gpuTemp: [],
    gpuPower: [],
    cpuUso: [],
    cpuClock: []
  };

  // Formatadores de dados
  function formatarCurto(num) {
    if (num === null || num === undefined || isNaN(num)) return '—';
    const n = Math.abs(Number(num));
    const sinal = num < 0 ? '-' : '';
    if (n >= 1e6) {
      return sinal + (n / 1e6).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + 'M';
    }
    if (n >= 1e3) {
      return sinal + (n / 1e3).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 1 }) + 'k';
    }
    return sinal + Number(num).toLocaleString('pt-BR');
  }

  function formatarUsd(num) {
    if (num === null || num === undefined || isNaN(num)) return '$—';
    return '$' + Number(num).toFixed(2);
  }

  function formatarBrl(num) {
    if (num === null || num === undefined || isNaN(num)) return 'R$ —';
    return 'R$ ' + Number(num).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function formatarPct(pct) {
    if (pct === null || pct === undefined || isNaN(pct)) return '—%';
    return Number(pct).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 1 }) + '%';
  }

  function formatarMs(ms) {
    if (ms === null || ms === undefined || isNaN(ms)) return '—';
    return Math.round(Number(ms)).toLocaleString('pt-BR') + ' ms';
  }

  function formatarSegundosParaMmSs(segundos) {
    if (segundos === null || segundos === undefined || isNaN(segundos) || segundos < 0) return '00:00';
    const total = Math.floor(segundos);
    const m = Math.floor(total / 60);
    const s = total % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  function formatarIsoParaHhMm(isoStr) {
    if (!isoStr) return '—';
    try {
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) {
        const m = String(isoStr).match(/(\d{2}:\d{2})/);
        return m ? m[1] : String(isoStr).slice(0, 5);
      }
      return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return '—';
    }
  }

  function formatarTaxaRede(kbps) {
    if (kbps === null || kbps === undefined || isNaN(kbps)) return '—';
    const val = Number(kbps);
    if (val >= 1024) {
      return (val / 1024).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' MB/s';
    }
    return Math.round(val).toLocaleString('pt-BR') + ' KB/s';
  }

  function formatarTempoRestanteReset(isoStr) {
    if (!isoStr) return null;
    try {
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return null;
      const diffSeg = Math.floor((d.getTime() - Date.now()) / 1000);
      if (diffSeg <= 0) return '0m';
      const dias = Math.floor(diffSeg / 86400);
      const horas = Math.floor((diffSeg % 86400) / 3600);
      const minutos = Math.floor((diffSeg % 3600) / 60);
      if (dias > 0) {
        return `${dias}d${horas > 0 ? horas + 'h' : ''}`;
      }
      if (horas > 0) {
        return `${horas}h${minutos.toString().padStart(2, '0')}m`;
      }
      return `${minutos}m`;
    } catch (e) {
      return null;
    }
  }

  function formatarUptime(segundos) {
    if (segundos === null || segundos === undefined || isNaN(segundos) || segundos < 0) return '—';
    const total = Math.floor(segundos);
    const d = Math.floor(total / 86400);
    const h = Math.floor((total % 86400) / 3600);
    const m = Math.floor((total % 3600) / 60);
    return d > 0 ? `${d}d ${h}h` : `${h}h ${m}m`;
  }

  function formatarRamMb(ramMb) {
    if (ramMb === null || ramMb === undefined || isNaN(ramMb)) return '—';
    const val = Number(ramMb);
    if (val >= 1024) {
      return (val / 1024).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' GB';
    }
    return Math.round(val).toLocaleString('pt-BR') + ' MB';
  }

  // Icones SVG estilo Stream Deck (desenhados a mao, 1.75 stroke, sem preenchimento)
  function obterIconeSvg(id, micMutado, numero) {
    if (id === 'mic_mute') {
      if (micMutado) {
        return '<svg viewBox="0 0 24 24" class="icone-stream"><line x1="2" y1="2" x2="22" y2="22"/><path d="M18.89 13.23A7.12 7.12 0 0 0 19 11v-1"/><path d="M5 10v1a7 7 0 0 0 12 5"/><path d="M15 9.34V5a3 3 0 0 0-5.68-1.33"/><path d="M9 9v2a3 3 0 0 0 5.12 2.12"/><line x1="12" y1="19" x2="12" y2="22"/></svg>';
      }
      return '<svg viewBox="0 0 24 24" class="icone-stream"><path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v1a7 7 0 0 1-14 0v-1"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/></svg>';
    }
    if (id === 'ollama_ejetar') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><path d="M12 5L5 13h14L12 5z"/><line x1="5" y1="18" x2="19" y2="18"/></svg>';
    }
    if (id === 'omniroute_perfil') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="6" cy="6" r="2.5"/><path d="M6 8.5v7"/><path d="M18 8.5c0 4-4 5.5-12 5.5"/></svg>';
    }
    if (id === 'abrir_ia') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3z"/><path d="M19 4v4"/><path d="M21 6h-4"/></svg>';
    }
    if (id === 'sessao_reset') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>';
    }
    if (id === 'terminal_wsl') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><rect width="18" height="14" x="3" y="5" rx="2"/><path d="m7 10 3 2-3 2"/><path d="M13 14h4"/></svg>';
    }
    if (id === 'git_status') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="2.5"/><circle cx="6" cy="18" r="2.5"/><path d="M18 8.5a9 9 0 0 1-9 9"/><circle cx="6" cy="6" r="2.5"/></svg>';
    }
    if (id === 'liberar_portas') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><path d="M12 22v-5"/><path d="M9 8V3"/><path d="M15 3v5"/><path d="M18 8H6a2 2 0 0 0-2 2v2a5 5 0 0 0 5 5h6a5 5 0 0 0 5-5v-2a2 2 0 0 0-2-2z"/></svg>';
    }
    if (id === 'print') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3.5"/></svg>';
    }
    if (id === 'media_play') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><polygon points="6 4 14 12 6 20 6 4"/><line x1="18" y1="5" x2="18" y2="19"/></svg>';
    }
    if (id === 'vol_down') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15 9a4 4 0 0 1 0 6"/><line x1="18" y1="12" x2="22" y2="12"/></svg>';
    }
    if (id === 'vol_up') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15 9a4 4 0 0 1 0 6"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="20" y1="10" x2="20" y2="14"/></svg>';
    }
    if (String(id).startsWith('ollama_load_')) {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><rect width="14" height="14" x="5" y="5" rx="2"/><path d="M12 9v6"/><path d="m9 12 3 3 3-3"/><path d="M9 2v3"/><path d="M15 2v3"/><path d="M9 19v3"/><path d="M15 19v3"/><path d="M2 9h3"/><path d="M2 15h3"/><path d="M19 9h3"/><path d="M19 15h3"/></svg>';
    }
    if (id === 'tela_apagar' || id === 'apagar_tela') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>';
    }
    if (id === 'discord') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><path d="M7.5 7.5c3-1.3 6-1.3 9 0"/><path d="M7 16.5c3 1.5 7 1.5 10 0"/><path d="M15.5 17.5 17 20c2.2-.6 3.8-1.6 5-2.9-.2-4.3-1.3-8.2-3.4-11.5C17.2 4.8 15.8 4.3 14.5 4l-.6 1.4"/><path d="M8.5 17.5 7 20c-2.2-.6-3.8-1.6-5-2.9.2-4.3 1.3-8.2 3.4-11.5C6.8 4.8 8.2 4.3 9.5 4l.6 1.4"/><circle cx="9" cy="12.5" r="1.3"/><circle cx="15" cy="12.5" r="1.3"/></svg>';
    }
    if (id === 'tela_so' || id === 'tela_so_pc') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><rect width="16" height="11" x="4" y="4" rx="1.5"/><path d="M12 15v4"/><path d="M8 19h8"/><text x="12" y="12.5" font-size="7" text-anchor="middle" stroke="none" fill="currentColor">' + (numero || 1) + '</text></svg>';
    }
    if (id === 'tela_duplicar') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><rect width="9" height="7" x="1.5" y="6" rx="1"/><rect width="9" height="7" x="13.5" y="6" rx="1"/><path d="M6 13v3"/><path d="M18 13v3"/><path d="m10.5 9.5 3 0"/><path d="m12.3 8.3 1.2 1.2-1.2 1.2"/></svg>';
    }
    if (id === 'tela_estender') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><rect width="20" height="9" x="2" y="5" rx="1"/><path d="M12 5v9"/><path d="M7 14v4"/><path d="M17 14v4"/><path d="M5 18h4"/><path d="M15 18h4"/></svg>';
    }
    if (id === 'gerenciador') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><rect width="18" height="16" x="3" y="4" rx="2"/><path d="M6 15h2l2-5 3 7 2-4h3"/></svg>';
    }
    if (id === 'rocket_league') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><circle cx="16" cy="8" r="5"/><path d="M16 3v10"/><path d="M11.4 6h9.2"/><path d="M11.4 10h9.2"/><path d="M2 20h11l1.5-3H6.5L3.5 15H2z"/><circle cx="5.5" cy="20.5" r="1.3"/><circle cx="11" cy="20.5" r="1.3"/></svg>';
    }
    if (id === 'app_livre') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M17.5 14v7"/><path d="M14 17.5h7"/></svg>';
    }
    if (id === 'area_trabalho') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><rect width="20" height="14" x="2" y="3" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/><path d="M9 10l3 3 3-3"/></svg>';
    }
    if (id === 'media_proxima') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19"/></svg>';
    }
    if (id === 'som_mudo') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="22" y1="9" x2="16" y2="15"/><line x1="16" y1="9" x2="22" y2="15"/></svg>';
    }
    if (id === 'explorador') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.7-.9l-.8-1.2A2 2 0 0 0 7.9 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>';
    }
    if (id === 'app_brave') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><path d="M12 2 5 5l-1 7c0 4 3.5 8 8 10 4.5-2 8-6 8-10l-1-7-7-3z"/><path d="M9 10l3 2 3-2"/><path d="M10 15h4"/></svg>';
    }
    if (id === 'app_steam') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><circle cx="12" cy="12" r="10"/><circle cx="15.5" cy="9" r="2.5"/><circle cx="8.5" cy="15.5" r="1.8"/><path d="M10 14.5l3.7-3.7"/></svg>';
    }
    if (id === 'app_epicgames') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><path d="M5 2h14v16l-7 4-7-4z"/><path d="M10 7H8v7h2"/><path d="M8 10.5h2"/></svg>';
    }
    if (id === 'app_vscode') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><path d="m16 18 6-6-6-6"/><path d="m8 6-6 6 6 6"/></svg>';
    }
    if (id === 'app_obs') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/></svg>';
    }
    if (id === 'app_telegram') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/></svg>';
    }
    if (id === 'app_obsidian') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><path d="M12 2 5 9l2 9 5 4 5-4 2-9z"/><path d="M12 2v20"/><path d="M5 9h14"/></svg>';
    }
    if (id === 'app_vlc') {
      return '<svg viewBox="0 0 24 24" class="icone-stream"><path d="M12 2 4 20h16z"/><path d="M8.5 12h7"/><path d="M6.5 16h11"/></svg>';
    }
    // Generico
    return '<svg viewBox="0 0 24 24" class="icone-stream"><rect width="16" height="16" x="4" y="4" rx="3"/><circle cx="12" cy="12" r="2"/></svg>';
  }

  // Extracao resiliente de blocos do contrato
  function extrairBloco(dados, chave) {
    if (!dados) return { val: null, erro: false, msgErro: '' };
    const b = dados[chave];
    if (!b) return { val: null, erro: false, msgErro: '' };
    if (typeof b === 'object' && b !== null && 'erro' in b) {
      return {
        val: b.ultimo_ok || null,
        erro: true,
        msgErro: String(b.erro || 'Falha no coletor')
      };
    }
    return { val: b, erro: false, msgErro: '' };
  }

  function atualizarIndicadorErro(idEl, erro, msgErro) {
    const el = document.getElementById(idEl);
    if (!el) return;
    if (erro) {
      el.textContent = '[!]';
      el.title = msgErro || 'Aviso no coletor';
    } else {
      el.textContent = '';
      el.title = '';
    }
  }

  // Toast discreto
  let temporizadorToast = null;
  function exibirToast(msg, ok) {
    const toast = document.getElementById('toast-alerta');
    if (!toast) return;
    toast.textContent = msg || '';
    toast.className = 'toast-alerta visivel' + (ok === false ? ' falha' : '');
    if (temporizadorToast) clearTimeout(temporizadorToast);
    temporizadorToast = setTimeout(() => {
      toast.className = 'toast-alerta';
    }, 3000);
  }

  // Estado global do microfone e botoes
  let micMudo = false;
  function sincronizarBotoesMic() {
    const btns = document.querySelectorAll('.botao-stream[data-id="mic_mute"]');
    btns.forEach(btn => {
      const iconeContainer = btn.querySelector('.tecla-icone');
      if (micMudo) {
        btn.classList.add('mic-mudo');
        if (iconeContainer) iconeContainer.innerHTML = obterIconeSvg('mic_mute', true);
      } else {
        btn.classList.remove('mic-mudo');
        if (iconeContainer) iconeContainer.innerHTML = obterIconeSvg('mic_mute', false);
      }
    });
  }

  // Disparo de acao com feedback Stream Deck
  async function executarAcao(id, elementoBotao) {
    if (navigator.vibrate) {
      try { navigator.vibrate(25); } catch (e) {}
    }

    if (elementoBotao) {
      elementoBotao.classList.add('toque-ativo');
      elementoBotao.classList.add('executando');
      setTimeout(() => {
        elementoBotao.classList.remove('toque-ativo');
      }, 250);
    }

    const ehApagarTela = id === 'apagar_tela' || id === 'tela_apagar' ||
      (elementoBotao && elementoBotao.textContent.trim().toLowerCase().includes('apagar tela'));

    if (ehApagarTela) {
      ativarOverlayApagarTela();
    }

    try {
      const resp = await fetch(comToken(`/action/${encodeURIComponent(id)}`), {
        method: 'POST'
      });
      const dadosRetorno = await resp.json();
      if (elementoBotao) {
        elementoBotao.classList.remove('executando');
        if (dadosRetorno.ok) {
          elementoBotao.classList.add('flash-sucesso');
          setTimeout(() => elementoBotao.classList.remove('flash-sucesso'), 400);
        } else {
          elementoBotao.classList.add('flash-erro');
          setTimeout(() => elementoBotao.classList.remove('flash-erro'), 400);
        }
      }
      exibirToast(dadosRetorno.msg || (dadosRetorno.ok ? 'Ação concluída' : 'Erro na ação'), dadosRetorno.ok);
      if (dadosRetorno.estado && dadosRetorno.estado.mic_mudo !== undefined) {
        micMudo = Boolean(dadosRetorno.estado.mic_mudo);
        sincronizarBotoesMic();
      }
      return Boolean(dadosRetorno.ok);
    } catch (erro) {
      if (elementoBotao) {
        elementoBotao.classList.remove('executando');
        elementoBotao.classList.add('flash-erro');
        setTimeout(() => elementoBotao.classList.remove('flash-erro'), 400);
      }
      if (!ehApagarTela) {
        exibirToast('Falha na comunicação com o servidor', false);
      }
      return false;
    }
  }

  // Ligar / desligar Ollama e OmniRoute (Tela 1)
  // A barra anda sozinha ate ~95% pelo tempo esperado de subida e so chega a 100% quando o coletor ve o servico online.
  const SERVICO_TEMPO_ESPERADO_S = { ollama: 5, omniroute: 25 };
  const SERVICO_TIMEOUT_S = 150;
  const estadoServico = {
    ollama: { fase: null, inicio: 0, timer: null, online: false },
    omniroute: { fase: null, inicio: 0, timer: null, online: false }
  };

  function definirBarraServico(sv, pct, visivel) {
    const barra = document.getElementById(`${sv}-barra`);
    const preench = document.getElementById(`${sv}-barra-preench`);
    const rotulo = document.getElementById(`${sv}-barra-pct`);
    if (barra) barra.hidden = !visivel;
    if (preench) preench.style.width = `${pct}%`;
    if (rotulo) rotulo.textContent = `${Math.floor(pct)}%`;
  }

  function encerrarFaseServico(sv) {
    const est = estadoServico[sv];
    if (est.timer) clearInterval(est.timer);
    est.timer = null;
    est.fase = null;
  }

  function renderizarServico(sv) {
    const est = estadoServico[sv];
    const badge = document.getElementById(`${sv}-status`);
    const botao = document.getElementById(`${sv}-botao`);
    if (badge) {
      if (est.fase === 'ligando') {
        badge.textContent = 'LIGANDO';
        badge.className = 'distintivo-status status-ligando';
      } else if (est.fase === 'desligando') {
        badge.textContent = 'DESLIGANDO';
        badge.className = 'distintivo-status status-ligando';
      } else if (est.online) {
        badge.textContent = 'ONLINE';
        badge.className = 'distintivo-status status-online';
      } else {
        badge.textContent = 'OFFLINE';
        badge.className = 'distintivo-status status-offline';
      }
    }
    if (botao) {
      botao.disabled = Boolean(est.fase);
      botao.textContent = est.fase ? '…' : (est.online ? 'DESLIGAR' : 'LIGAR');
      botao.classList.toggle('desligar', !est.fase && est.online);
    }
  }

  // Chamado a cada pacote de telemetria com o estado real do servico
  function atualizarServico(sv, online) {
    const est = estadoServico[sv];
    est.online = Boolean(online);
    if (est.fase === 'ligando' && est.online) {
      encerrarFaseServico(sv);
      definirBarraServico(sv, 100, true);
      setTimeout(() => {
        if (!estadoServico[sv].fase) definirBarraServico(sv, 0, false);
      }, 900);
      exibirToast(`${sv === 'ollama' ? 'Ollama' : 'OmniRoute'} online`, true);
    } else if (est.fase === 'desligando' && !est.online) {
      encerrarFaseServico(sv);
    }
    renderizarServico(sv);
  }

  async function alternarServico(sv) {
    const est = estadoServico[sv];
    if (est.fase) return;
    const ligar = !est.online;
    if (navigator.vibrate) {
      try { navigator.vibrate(25); } catch (e) {}
    }
    est.fase = ligar ? 'ligando' : 'desligando';
    est.inicio = Date.now();
    if (ligar) {
      const tau = SERVICO_TEMPO_ESPERADO_S[sv] || 8;
      definirBarraServico(sv, 0, true);
      est.timer = setInterval(() => {
        const t = (Date.now() - est.inicio) / 1000;
        if (t > SERVICO_TIMEOUT_S) {
          encerrarFaseServico(sv);
          definirBarraServico(sv, 0, false);
          renderizarServico(sv);
          exibirToast(`${sv === 'ollama' ? 'Ollama' : 'OmniRoute'} não respondeu`, false);
          return;
        }
        definirBarraServico(sv, 95 * (1 - Math.exp(-t / tau)), true);
      }, 150);
    }
    renderizarServico(sv);
    try {
      const resp = await fetch(comToken(`/action/${sv}_${ligar ? 'ligar' : 'desligar'}`), { method: 'POST' });
      const ret = await resp.json();
      if (!ret.ok) {
        encerrarFaseServico(sv);
        definirBarraServico(sv, 0, false);
        renderizarServico(sv);
      }
      exibirToast(ret.msg || (ret.ok ? 'Ok' : 'Erro'), ret.ok);
    } catch (erro) {
      encerrarFaseServico(sv);
      definirBarraServico(sv, 0, false);
      renderizarServico(sv);
      exibirToast('Falha na comunicação com o servidor', false);
    }
    // Desligar: se o coletor demorar, libera o botao depois de 20 s
    if (!ligar) {
      setTimeout(() => {
        if (estadoServico[sv].fase === 'desligando') {
          encerrarFaseServico(sv);
          renderizarServico(sv);
        }
      }, 20000);
    }
  }

  document.querySelectorAll('.botao-servico').forEach(b => {
    b.addEventListener('click', (ev) => {
      ev.stopPropagation();
      alternarServico(b.dataset.servico);
    });
  });

  // Overlay Apagar Tela
  function ativarOverlayApagarTela() {
    const overlay = document.getElementById('overlay-apagar-tela');
    if (overlay) overlay.classList.add('ativo');
  }

  function desativarOverlayApagarTela() {
    const overlay = document.getElementById('overlay-apagar-tela');
    if (overlay) overlay.classList.remove('ativo');
  }

  // Tecla "Apagar Tela": um toque no preto volta ao painel
  function tocarNoPreto(e) {
    if (e) e.preventDefault(); // o toque nao atravessa para o botao embaixo
    desativarOverlayApagarTela();
  }

  const overlayEl = document.getElementById('overlay-apagar-tela');
  if (overlayEl) {
    overlayEl.addEventListener('click', tocarNoPreto);
    overlayEl.addEventListener('touchend', tocarNoPreto);
  }

  // Renderizacao das acoes recebidas do servidor
  let acoesCarregadas = false;
  async function carregarAcoes() {
    try {
      const resp = await fetch(comToken('/actions'));
      if (!resp.ok) return;
      const acoes = await resp.json();
      if (Array.isArray(acoes)) {
        renderizarListaAcoes(acoes);
        acoesCarregadas = true;
      }
    } catch (e) {
      // Servidor pode estar temporariamente sem endpoint de acoes
    }
  }


  function escaparHtml(t) {
    return String(t == null ? '' : t).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function vibrarCurto(ms) {
    if (navigator.vibrate) { try { navigator.vibrate(ms); } catch (e) {} }
  }

  // Tecla com varias opcoes (ex.: "Só tela 1/2/3"): arrastar para cima/baixo troca a opcao, tocar executa.
  function criarTeclaRolavel(acao) {
    const ops = acao.opcoes;
    const n = ops.length;
    const btn = document.createElement('button');
    btn.className = 'botao-stream tecla-rolavel';
    btn.dataset.id = acao.id;
    let idx = 0;
    try { idx = parseInt(localStorage.getItem('rolavel_' + acao.id) || '0', 10) || 0; } catch (e) {}
    idx = Math.min(n - 1, Math.max(0, idx));

    const faces = ops.map((op, i) => `
      <div class="rolavel-face">
        <div class="tecla-icone">${obterIconeSvg(acao.id, false, i + 1)}</div>
        <span class="rotulo-tecla">${escaparHtml(op.rotulo)}</span>
        <span class="desc-tecla">${escaparHtml(op.descricao)}</span>
      </div>`).join('');
    const pontos = ops.map(() => '<span class="rolavel-ponto"></span>').join('');
    btn.innerHTML = `
      <div class="rolavel-janela"><div class="rolavel-trilho" style="height:${n * 100}%">${faces}</div></div>
      <div class="rolavel-pontos">${pontos}</div>`;
    const trilho = btn.querySelector('.rolavel-trilho');
    const janela = btn.querySelector('.rolavel-janela');

    function mostrar(animar, desvioPx) {
      trilho.style.transition = animar ? 'transform 0.28s cubic-bezier(0.2, 0.8, 0.2, 1)' : 'none';
      trilho.style.transform = `translateY(calc(${-idx * 100 / n}% + ${desvioPx || 0}px))`;
      btn.querySelectorAll('.rolavel-ponto').forEach((p, i) => p.classList.toggle('ativo', i === idx));
      try { localStorage.setItem('rolavel_' + acao.id, String(idx)); } catch (e) {}
    }

    let y0 = null;
    let x0 = 0;
    let ultimoDy = 0;
    let arrastou = false;
    btn.addEventListener('pointerdown', (e) => {
      y0 = e.clientY; x0 = e.clientX; ultimoDy = 0; arrastou = false;
      try { btn.setPointerCapture(e.pointerId); } catch (err) {}
    });
    btn.addEventListener('pointermove', (e) => {
      if (y0 === null) return;
      if (btn.classList.contains('arrastando')) { arrastou = false; return; } // reordenando, nao rolar
      const dy = e.clientY - y0;
      ultimoDy = dy;
      if (!arrastou && Math.abs(dy) > 10 && Math.abs(dy) > Math.abs(e.clientX - x0)) arrastou = true;
      if (arrastou) mostrar(false, Math.max(-janela.clientHeight, Math.min(janela.clientHeight, dy)));
    });
    function concluir(dy) {
      y0 = null;
      if (!arrastou) return;
      if (dy < -30) idx = (idx + 1) % n;          // arrastou para cima: proxima tela
      else if (dy > 30) idx = (idx - 1 + n) % n;  // para baixo: anterior
      vibrarCurto(15);
      mostrar(true, 0);
    }
    btn.addEventListener('pointerup', (e) => { if (y0 !== null) concluir(e.clientY - y0); });
    // O WebView pode tomar o gesto no meio (pointercancel): conclui com a ultima posicao do dedo
    btn.addEventListener('pointercancel', () => { if (y0 !== null) concluir(ultimoDy); });
    btn.addEventListener('click', () => {
      if (arrastou) { arrastou = false; return; }
      executarAcao(ops[idx].id, btn);
    });
    mostrar(false, 0);
    return btn;
  }

  // ===== Reordenar teclas: segurar ~0,45 s e arrastar para o lugar de outra =====
  // A ordem fica salva no aparelho (localStorage), uma lista de ids por grade.
  // Segurar e soltar sem mover chama btn._aoSegurar (ex.: escolher o app da tecla livre).
  function ordenarPorSalvo(idGrade, lista) {
    let ordem = [];
    try { ordem = JSON.parse(localStorage.getItem('ordem_' + idGrade) || '[]'); } catch (e) {}
    if (!Array.isArray(ordem) || !ordem.length) return lista;
    const pos = id => { const i = ordem.indexOf(id); return i < 0 ? ordem.length : i; };
    return lista.map((a, i) => [a, i])
      .sort((x, y) => (pos(x[0].id) - pos(y[0].id)) || (x[1] - y[1]))
      .map(p => p[0]);
  }

  function ligarReordenar(grade) {
    if (!grade || grade.dataset.reordenar) return;
    grade.dataset.reordenar = '1';
    let alvo = null, timer = null, ativo = false, moveu = false, suprimirClique = false;
    let x0 = 0, y0 = 0, offX = 0, offY = 0;
    const teclas = () => Array.from(grade.children).filter(el => el.classList.contains('botao-stream'));

    function seguir(x, y) {
      alvo.style.transform = 'none';
      const r = alvo.getBoundingClientRect();
      alvo.style.transform = `translate(${x - offX - r.left}px, ${y - offY - r.top}px) scale(1.08)`;
    }

    // Move a tecla para o lugar da outra e anima as demais (FLIP)
    function mover(sobre) {
      const outras = teclas().filter(t => t !== alvo);
      const antes = new Map(outras.map(t => [t, t.getBoundingClientRect()]));
      const lista = teclas();
      if (lista.indexOf(alvo) < lista.indexOf(sobre)) sobre.after(alvo); else sobre.before(alvo);
      outras.forEach(t => {
        const a = antes.get(t);
        const d = t.getBoundingClientRect();
        if (a.left === d.left && a.top === d.top) return;
        t._animando = true;
        t.style.transition = 'none';
        t.style.transform = `translate(${a.left - d.left}px, ${a.top - d.top}px)`;
        requestAnimationFrame(() => {
          t.style.transition = 'transform 0.2s ease';
          t.style.transform = '';
        });
        setTimeout(() => { t._animando = false; t.style.transition = ''; }, 220);
      });
      moveu = true;
      vibrarCurto(10);
    }

    function soltar() {
      clearTimeout(timer); timer = null;
      if (!alvo) return;
      const b = alvo;
      alvo = null;
      if (!ativo) return;
      ativo = false;
      suprimirClique = true;
      setTimeout(() => { suprimirClique = false; }, 500);
      grade.classList.remove('reordenando');
      b.classList.remove('arrastando');
      b.style.transition = 'transform 0.18s ease';
      b.style.transform = '';
      setTimeout(() => { b.style.transition = ''; }, 200);
      if (moveu) {
        const ids = teclas().map(t => t.dataset.id).filter(Boolean);
        try { localStorage.setItem('ordem_' + grade.id, JSON.stringify(ids)); } catch (e) {}
      } else if (typeof b._aoSegurar === 'function') {
        b._aoSegurar();
      }
    }

    grade.addEventListener('contextmenu', (e) => e.preventDefault());
    grade.addEventListener('pointerdown', (e) => {
      if (e.button !== undefined && e.button !== 0) return;
      const b = e.target.closest('.botao-stream');
      if (!b || b.parentElement !== grade) return;
      alvo = b; ativo = false; moveu = false;
      x0 = e.clientX; y0 = e.clientY;
      clearTimeout(timer);
      timer = setTimeout(() => {
        timer = null;
        if (!alvo || !grade.contains(alvo)) return;
        ativo = true;
        vibrarCurto(40);
        alvo.style.transform = 'none';
        const r = alvo.getBoundingClientRect();
        offX = x0 - r.left; offY = y0 - r.top;
        alvo.classList.add('arrastando');
        grade.classList.add('reordenando');
        try { alvo.setPointerCapture(e.pointerId); } catch (err) {}
        seguir(x0, y0);
      }, 450);
    });
    grade.addEventListener('pointermove', (e) => {
      if (!alvo) return;
      if (!ativo) {
        // Mexeu antes do tempo: e swipe de tela ou rolagem da tecla, nao reordenar
        if (timer && Math.hypot(e.clientX - x0, e.clientY - y0) > 10) { clearTimeout(timer); timer = null; }
        return;
      }
      e.preventDefault();
      seguir(e.clientX, e.clientY);
      const sobre = teclas().find(t => {
        if (t === alvo || t._animando) return false;
        const r = t.getBoundingClientRect();
        return e.clientX > r.left && e.clientX < r.right && e.clientY > r.top && e.clientY < r.bottom;
      });
      if (sobre) mover(sobre);
    });
    grade.addEventListener('pointerup', soltar);
    grade.addEventListener('pointercancel', soltar);
    // Durante o arrasto o dedo nao pode rolar as telas
    grade.addEventListener('touchmove', (e) => { if (ativo) e.preventDefault(); }, { passive: false });
    // O toque que terminou um arrasto nao executa a acao da tecla
    grade.addEventListener('click', (e) => {
      if (suprimirClique) { suprimirClique = false; e.stopImmediatePropagation(); e.preventDefault(); }
    }, true);
  }

  // Seletor de app da tecla livre (lista do Menu Iniciar do PC)
  async function abrirSeletorApp() {
    const caixa = document.getElementById('seletor-app');
    const lista = document.getElementById('seletor-lista');
    const busca = document.getElementById('seletor-busca');
    if (!caixa || !lista) return;
    caixa.hidden = false;
    lista.innerHTML = '<div class="rotulo-secundario">carregando…</div>';
    let nomes = [];
    try {
      const resp = await fetch(comToken('/apps'));
      nomes = resp.ok ? await resp.json() : [];
    } catch (e) {}
    const desenhar = () => {
      const filtro = (busca && busca.value || '').trim().toLowerCase();
      lista.innerHTML = '';
      nomes.filter(nm => !filtro || nm.toLowerCase().includes(filtro)).forEach(nm => {
        const b = document.createElement('button');
        b.className = 'seletor-item';
        b.textContent = nm;
        b.addEventListener('click', () => escolherApp(nm));
        lista.appendChild(b);
      });
      if (!lista.children.length) lista.innerHTML = '<div class="rotulo-secundario">nada encontrado</div>';
    };
    if (busca) { busca.value = ''; busca.oninput = desenhar; }
    desenhar();
  }

  function fecharSeletorApp() {
    const caixa = document.getElementById('seletor-app');
    if (caixa) caixa.hidden = true;
  }

  async function escolherApp(nome) {
    try {
      const resp = await fetch(comToken('/app_slot'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nome })
      });
      const r = await resp.json();
      exibirToast(r.msg || 'ok', r.ok);
      if (r.ok) { fecharSeletorApp(); carregarAcoes(); }
    } catch (e) {
      exibirToast('Falha ao salvar o app', false);
    }
  }

  (function ligarSeletor() {
    const fechar = document.getElementById('seletor-fechar');
    if (fechar) fechar.addEventListener('click', fecharSeletorApp);
  })();

  function renderizarListaAcoes(acoes) {
    // Telas Windows (tela == 2) e Apps (tela == 4): grades 4x3 de teclas quadradas com icones SVG
    [['grade-stream-deck', 2], ['grade-apps', 4]].forEach(([idGrade, numTela]) => {
      const grade = document.getElementById(idGrade);
      if (!grade) return;
      grade.innerHTML = '';
      ligarReordenar(grade);
      ordenarPorSalvo(idGrade, acoes.filter(a => a.tela === numTela)).forEach(acao => {
        if (Array.isArray(acao.opcoes) && acao.opcoes.length) {
          grade.appendChild(criarTeclaRolavel(acao));
          return;
        }
        const btn = document.createElement('button');
        btn.className = 'botao-stream' + (acao.ativo === false ? ' desativado' : '');
        btn.dataset.id = acao.id;
        const estaMudo = acao.id === 'mic_mute' && micMudo;
        if (estaMudo) {
          btn.classList.add('mic-mudo');
        }
        btn.innerHTML = `
          <div class="tecla-icone">${obterIconeSvg(acao.id, estaMudo)}</div>
          <span class="rotulo-tecla">${escaparHtml(acao.rotulo || acao.id)}</span>
          <span class="desc-tecla">${escaparHtml(acao.descricao || '')}</span>
        `;
        if (acao.escolhivel) btn._aoSegurar = abrirSeletorApp;
        if (acao.ativo !== false) {
          btn.addEventListener('click', () => executarAcao(acao.id, btn));
        }
        grade.appendChild(btn);
      });
    });

    // Tela 6: Botoes superiores (tela == 3, mesmo componente de tecla menor)
    const containerTela3 = document.getElementById('topo-acoes-tela-3');
    if (containerTela3) {
      containerTela3.innerHTML = '';
      ligarReordenar(containerTela3);
      const acoesTela3 = ordenarPorSalvo('topo-acoes-tela-3', acoes.filter(a => a.tela === 3));

      if (acoesTela3.length === 0) {
        const btnApagar = document.createElement('button');
        btnApagar.className = 'botao-stream';
        btnApagar.dataset.id = 'tela_apagar';
        btnApagar.innerHTML = `
          <div class="tecla-icone">${obterIconeSvg('tela_apagar', false)}</div>
          <span class="rotulo-tecla">Apagar Tela</span>
        `;
        btnApagar.addEventListener('click', () => executarAcao('tela_apagar', btnApagar));
        containerTela3.appendChild(btnApagar);
      } else {
        acoesTela3.forEach(acao => {
          const btn = document.createElement('button');
          btn.className = 'botao-stream' + (acao.ativo === false ? ' desativado' : '');
          btn.dataset.id = acao.id;
          btn.innerHTML = `
            <div class="tecla-icone">${obterIconeSvg(acao.id, false)}</div>
            <span class="rotulo-tecla">${acao.rotulo || acao.id}</span>
          <span class="desc-tecla">${acao.descricao || ''}</span>
          `;
          if (acao.ativo !== false) {
            btn.addEventListener('click', () => executarAcao(acao.id, btn));
          }
          containerTela3.appendChild(btn);
        });
      }
    }
  }

  // Encurtador de nome de CPU
  function encurtarNomeCpu(nome) {
    if (!nome) return 'CPU: —';
    let s = String(nome);
    s = s.replace(/AMD\s+/gi, '');
    s = s.replace(/Intel\(R\)\s+/gi, '');
    s = s.replace(/Core\(TM\)\s+/gi, '');
    s = s.replace(/\s*Processor/gi, '');
    s = s.replace(/\s*\d+[\s-]*Core/gi, '');
    s = s.replace(/\s+/g, ' ').trim();
    return s || 'CPU';
  }

  let ultimoHardwareParaSparklines = null;

  // Desenho de Sparkline com gradiente vertical (alpha .18 a 0) e devicePixelRatio
  function desenharSparkline(canvasId, pontos, corLinha, corGradRgb, minFixo, maxFixo) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const parent = canvas.parentElement;
    const parentRect = parent ? parent.getBoundingClientRect() : null;
    const dpr = window.devicePixelRatio || 1;

    const w = (parentRect && parentRect.width > 0) ? Math.floor(parentRect.width) : (canvas.clientWidth || 70);
    const h = (canvas.clientHeight && canvas.clientHeight > 0) ? Math.floor(canvas.clientHeight) : 44;

    const tw = Math.round(w * dpr);
    const th = Math.round(h * dpr);
    if (canvas.width !== tw || canvas.height !== th) {
      canvas.width = tw;
      canvas.height = th;
    }

    ctx.save();
    ctx.clearRect(0, 0, tw, th);
    ctx.scale(dpr, dpr);

    if (!pontos || pontos.length === 0) {
      ctx.restore();
      return;
    }

    const minVal = minFixo !== null && minFixo !== undefined ? minFixo : 0;
    let maxVal = maxFixo !== null && maxFixo !== undefined ? maxFixo : Math.max(...pontos, 1);
    if (maxVal <= minVal) maxVal = minVal + 1;

    const pts = pontos.length === 1 ? [pontos[0], pontos[0]] : pontos;
    const n = pts.length;
    const stepX = (w - 2) / Math.max(n - 1, 1);
    const startX = 1;

    const coords = [];
    for (let i = 0; i < n; i++) {
      const x = Math.max(0, startX + i * stepX);
      const rawV = Number(pts[i]) || 0;
      const v = Math.max(minVal, Math.min(maxVal, rawV));
      const y = (h - 2) - ((v - minVal) / (maxVal - minVal)) * (h - 4);
      coords.push({ x, y });
    }

    // Preenchimento em gradiente vertical (alpha 0.18 ate 0)
    if (corGradRgb && coords.length > 0) {
      const grad = ctx.createLinearGradient(0, 0, 0, h);
      grad.addColorStop(0, `rgba(${corGradRgb}, 0.18)`);
      grad.addColorStop(1, `rgba(${corGradRgb}, 0)`);
      ctx.beginPath();
      ctx.moveTo(coords[0].x, h);
      for (let i = 0; i < coords.length; i++) {
        ctx.lineTo(coords[i].x, coords[i].y);
      }
      ctx.lineTo(coords[coords.length - 1].x, h);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();
    }

    // Traco da linha (1.5 px)
    ctx.beginPath();
    for (let i = 0; i < coords.length; i++) {
      if (i === 0) ctx.moveTo(coords[i].x, coords[i].y);
      else ctx.lineTo(coords[i].x, coords[i].y);
    }
    ctx.strokeStyle = corLinha;
    ctx.lineWidth = 1.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();

    ctx.restore();
  }

  function desenharTodasSparklines(hw) {
    if (!hw) return;
    // 1. GPU Uso (0–100)
    desenharSparkline('spark-gpu-uso', historicoSparklines.gpuUso, '#00E676', '0, 230, 118', 0, 100);

    // 2. GPU Temp (30–90 °C fixo)
    const tempLim = (hw.gpu_temp_limite !== null && hw.gpu_temp_limite !== undefined) ? Number(hw.gpu_temp_limite) : 90;
    desenharSparkline('spark-gpu-temp', historicoSparklines.gpuTemp, '#00E676', '0, 230, 118', 30, Math.max(90, tempLim));

    // 3. GPU Power (0 ate gpu_power_limite_w)
    const powerLim = (hw.gpu_power_limite_w !== null && hw.gpu_power_limite_w !== undefined && Number(hw.gpu_power_limite_w) > 0)
      ? Number(hw.gpu_power_limite_w)
      : 200;
    desenharSparkline('spark-gpu-power', historicoSparklines.gpuPower, '#00E676', '0, 230, 118', 0, powerLim);

    // 4. CPU Uso (0–100)
    desenharSparkline('spark-cpu-uso', historicoSparklines.cpuUso, '#00BFA5', '0, 191, 165', 0, 100);

    // 5. CPU Clock (0 ate cpu_base_mhz * 1.4)
    const cpuBase = (hw.cpu_base_mhz !== null && hw.cpu_base_mhz !== undefined && Number(hw.cpu_base_mhz) > 0)
      ? Number(hw.cpu_base_mhz)
      : 3700;
    desenharSparkline('spark-cpu-clock', historicoSparklines.cpuClock, '#00BFA5', '0, 191, 165', 0, cpuBase * 1.4);
  }

  function redesenharTodasSparklines() {
    if (ultimoHardwareParaSparklines) {
      desenharTodasSparklines(ultimoHardwareParaSparklines);
    }
  }

  function inicializarResizeSparklines() {
    const ids = ['spark-gpu-uso', 'spark-gpu-temp', 'spark-gpu-power', 'spark-cpu-uso', 'spark-cpu-clock'];
    if (typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver(() => {
        redesenharTodasSparklines();
      });
      ids.forEach(id => {
        const el = document.getElementById(id);
        if (el && el.parentElement) {
          ro.observe(el.parentElement);
        }
      });
    }
    window.addEventListener('resize', redesenharTodasSparklines);
  }

  // Atualizacao da Tela PC
  function atualizarTelaPC(dados) {
    const blocoHw = extrairBloco(dados, 'hardware');
    const hw = blocoHw.val || {};

    // 1. Barra superior: temperaturas CPU e GPU
    const cpuTempStr = hw.cpu_temp !== null && hw.cpu_temp !== undefined ? Math.round(hw.cpu_temp) + '°C' : '—';
    const gpuTempStr = hw.gpu_temp !== null && hw.gpu_temp !== undefined ? Math.round(hw.gpu_temp) + '°C' : '—';
    const elTopCpu = document.getElementById('topo-cpu');
    if (elTopCpu) {
      const cpuUsoTopo = hw.cpu_pct !== null && hw.cpu_pct !== undefined ? Math.round(hw.cpu_pct) + '%' : '—';
      elTopCpu.textContent = cpuTempStr !== '—' ? `CPU ${cpuTempStr}` : `CPU ${cpuUsoTopo}`;
    }
    const elTopGpu = document.getElementById('topo-gpu');
    if (elTopGpu) {
      elTopGpu.textContent = `GPU ${gpuTempStr}`;
    }

    // Armazenar no historico de sparklines se hardware recebido
    if (blocoHw.val) {
      if (hw.gpu_pct !== null && hw.gpu_pct !== undefined) {
        historicoSparklines.gpuUso.push(Number(hw.gpu_pct));
      } else {
        historicoSparklines.gpuUso.push(0);
      }
      if (historicoSparklines.gpuUso.length > 60) historicoSparklines.gpuUso.shift();

      if (hw.gpu_temp !== null && hw.gpu_temp !== undefined) {
        historicoSparklines.gpuTemp.push(Number(hw.gpu_temp));
      } else {
        historicoSparklines.gpuTemp.push(0);
      }
      if (historicoSparklines.gpuTemp.length > 60) historicoSparklines.gpuTemp.shift();

      if (hw.gpu_power_w !== null && hw.gpu_power_w !== undefined) {
        historicoSparklines.gpuPower.push(Number(hw.gpu_power_w));
      } else {
        historicoSparklines.gpuPower.push(0);
      }
      if (historicoSparklines.gpuPower.length > 60) historicoSparklines.gpuPower.shift();

      if (hw.cpu_pct !== null && hw.cpu_pct !== undefined) {
        historicoSparklines.cpuUso.push(Number(hw.cpu_pct));
      } else {
        historicoSparklines.cpuUso.push(0);
      }
      if (historicoSparklines.cpuUso.length > 60) historicoSparklines.cpuUso.shift();

      if (hw.cpu_clock_mhz !== null && hw.cpu_clock_mhz !== undefined) {
        historicoSparklines.cpuClock.push(Number(hw.cpu_clock_mhz));
      } else if (hw.cpu_base_mhz !== null && hw.cpu_base_mhz !== undefined) {
        historicoSparklines.cpuClock.push(Number(hw.cpu_base_mhz));
      } else {
        historicoSparklines.cpuClock.push(0);
      }
      if (historicoSparklines.cpuClock.length > 60) historicoSparklines.cpuClock.shift();
    }

    // Coluna GPU
    // Nome e Driver
    const elGpuNome = document.getElementById('pc-gpu-nome');
    if (elGpuNome) {
      elGpuNome.textContent = hw.gpu_nome || 'GPU: —';
    }

    const elGpuDriver = document.getElementById('pc-gpu-driver');
    if (elGpuDriver) {
      elGpuDriver.textContent = hw.gpu_driver ? `Driver ${hw.gpu_driver}` : 'Driver —';
    }

    // Uso GPU (numero grande com <small>%)
    const elGpuUso = document.getElementById('pc-gpu-uso');
    if (elGpuUso) {
      if (hw.gpu_pct !== null && hw.gpu_pct !== undefined) {
        elGpuUso.innerHTML = `${Math.round(hw.gpu_pct)}<small>%</small>`;
      } else {
        elGpuUso.innerHTML = '—<small>%</small>';
      }
    }

    // Temperatura GPU com alerta ambar e vermelho
    const elGpuTemp = document.getElementById('pc-gpu-temp');
    if (elGpuTemp) {
      if (hw.gpu_temp !== null && hw.gpu_temp !== undefined) {
        const t = Number(hw.gpu_temp);
        const lim = hw.gpu_temp_limite !== null && hw.gpu_temp_limite !== undefined ? Number(hw.gpu_temp_limite) : 89;
        elGpuTemp.innerHTML = `${Math.round(t)}<small>°C</small>`;
        if (t >= lim) {
          elGpuTemp.className = 'pc-stat-valor cor-alerta';
        } else if (t >= lim - 10) {
          elGpuTemp.className = 'pc-stat-valor cor-ambar';
        } else {
          elGpuTemp.className = 'pc-stat-valor';
        }
      } else {
        elGpuTemp.innerHTML = '—<small>°C</small>';
        elGpuTemp.className = 'pc-stat-valor';
      }
    }

    // Clocks GPU
    const elGpuClocks = document.getElementById('pc-gpu-clocks');
    if (elGpuClocks) {
      if (hw.gpu_clock_mhz !== null && hw.gpu_clock_mhz !== undefined) {
        const cur = hw.gpu_clock_mhz;
        const max = hw.gpu_clock_max_mhz ? ` / ${hw.gpu_clock_max_mhz}` : '';
        elGpuClocks.textContent = `${cur}${max} MHz`;
      } else {
        elGpuClocks.textContent = '— MHz';
      }
    }

    const elGpuMemClock = document.getElementById('pc-gpu-mem-clock');
    if (elGpuMemClock) {
      elGpuMemClock.textContent = hw.gpu_mem_clock_mhz !== null && hw.gpu_mem_clock_mhz !== undefined
        ? `${hw.gpu_mem_clock_mhz} MHz`
        : '— MHz';
    }

    // Power GPU
    const elGpuPower = document.getElementById('pc-gpu-power');
    const pAtual = hw.gpu_power_w !== null && hw.gpu_power_w !== undefined ? Number(hw.gpu_power_w) : null;
    const pLim = hw.gpu_power_limite_w !== null && hw.gpu_power_limite_w !== undefined ? Number(hw.gpu_power_limite_w) : null;
    if (elGpuPower) {
      const txtAtual = pAtual !== null ? pAtual.toFixed(1) : '—';
      const txtLim = pLim !== null ? Math.round(pLim) : '—';
      elGpuPower.innerHTML = `${txtAtual}<small>/ ${txtLim} W</small>`;
    }

    // Ventoinha (com 0 mostre "0% (parada)")
    const elGpuFan = document.getElementById('pc-gpu-fan');
    if (elGpuFan) {
      if (hw.gpu_fan_pct === 0) {
        elGpuFan.textContent = '0% (parada)';
      } else if (hw.gpu_fan_pct !== null && hw.gpu_fan_pct !== undefined) {
        elGpuFan.textContent = `${Math.round(hw.gpu_fan_pct)}%`;
      } else {
        elGpuFan.textContent = '—';
      }
    }

    // P-State
    const elGpuPstate = document.getElementById('pc-gpu-pstate');
    if (elGpuPstate) {
      elGpuPstate.textContent = hw.gpu_pstate !== null && hw.gpu_pstate !== undefined ? `P${hw.gpu_pstate}` : '—';
    }

    // Controlador de memória
    const elGpuMemCtrl = document.getElementById('pc-gpu-mem-ctrl');
    if (elGpuMemCtrl) {
      elGpuMemCtrl.textContent = formatarPct(hw.gpu_mem_ctrl_pct);
    }

    // ENC / DEC
    const elGpuEncDec = document.getElementById('pc-gpu-enc-dec');
    if (elGpuEncDec) {
      const enc = hw.gpu_enc_pct !== null && hw.gpu_enc_pct !== undefined ? `${hw.gpu_enc_pct}%` : '—';
      const dec = hw.gpu_dec_pct !== null && hw.gpu_dec_pct !== undefined ? `${hw.gpu_dec_pct}%` : '—';
      elGpuEncDec.textContent = `ENC ${enc} · DEC ${dec}`;
    }

    // PCIe rx/tx
    const elGpuPcie = document.getElementById('pc-gpu-pcie');
    if (elGpuPcie) {
      const rx = hw.gpu_pcie_rx_mbps !== null && hw.gpu_pcie_rx_mbps !== undefined ? Number(hw.gpu_pcie_rx_mbps).toFixed(1) : '—';
      const tx = hw.gpu_pcie_tx_mbps !== null && hw.gpu_pcie_tx_mbps !== undefined ? Number(hw.gpu_pcie_tx_mbps).toFixed(1) : '—';
      elGpuPcie.textContent = `↓ ${rx} · ↑ ${tx} MB/s`;
    }

    // Throttle (lista vazia = "sem limitação" em --texto-2)
    const containerThrottle = document.getElementById('pc-gpu-throttle');
    if (containerThrottle) {
      const thList = Array.isArray(hw.gpu_throttle) ? hw.gpu_throttle : [];
      if (thList.length === 0) {
        containerThrottle.innerHTML = '<span class="texto-sem-limitacao">sem limitação</span>';
      } else {
        containerThrottle.innerHTML = '';
        thList.forEach(m => {
          const sp = document.createElement('span');
          sp.className = 'etiqueta-throttle ativa';
          sp.textContent = m;
          containerThrottle.appendChild(sp);
        });
      }
    }

    // Coluna CPU
    // Nome encurtado
    const elCpuNome = document.getElementById('pc-cpu-nome');
    if (elCpuNome) {
      elCpuNome.textContent = encurtarNomeCpu(hw.cpu_nome);
      if (hw.cpu_nome) elCpuNome.title = hw.cpu_nome;
    }

    // Uso CPU (numero grande com <small>%)
    const elCpuUso = document.getElementById('pc-cpu-uso');
    if (elCpuUso) {
      if (hw.cpu_pct !== null && hw.cpu_pct !== undefined) {
        elCpuUso.innerHTML = `${Math.round(hw.cpu_pct)}<small>%</small>`;
      } else {
        elCpuUso.innerHTML = '—<small>%</small>';
      }
    }

    // Clock CPU (com null mostre base cpu_base_mhz com sufixo "base")
    const elCpuClock = document.getElementById('pc-cpu-clock');
    if (elCpuClock) {
      if (hw.cpu_clock_mhz !== null && hw.cpu_clock_mhz !== undefined) {
        elCpuClock.innerHTML = `${hw.cpu_clock_mhz}<small>MHz</small>`;
      } else if (hw.cpu_base_mhz !== null && hw.cpu_base_mhz !== undefined) {
        elCpuClock.innerHTML = `${hw.cpu_base_mhz}<small>MHz base</small>`;
      } else {
        elCpuClock.innerHTML = '—<small>MHz</small>';
      }
    }

    // Temperatura CPU (null = "—")
    const elCpuTemp = document.getElementById('pc-cpu-temp');
    if (elCpuTemp) {
      if (hw.cpu_temp !== null && hw.cpu_temp !== undefined) {
        elCpuTemp.innerHTML = `${Math.round(hw.cpu_temp)}<small>°C</small>`;
      } else {
        elCpuTemp.textContent = '—';
      }
    }

    // Grade de 12 mini barras verticais para cpu_nucleos
    const containerCores = document.getElementById('pc-cpu-cores');
    if (containerCores) {
      const nucleos = Array.isArray(hw.cpu_nucleos) ? hw.cpu_nucleos : [];
      if (nucleos.length > 0) {
        let bars = containerCores.children;
        if (bars.length !== nucleos.length) {
          containerCores.innerHTML = '';
          for (let i = 0; i < nucleos.length; i++) {
            const track = document.createElement('div');
            track.className = 'mini-trilho-v';
            track.title = `T${i + 1}`;
            const fill = document.createElement('div');
            fill.className = 'mini-barra-v';
            track.appendChild(fill);
            containerCores.appendChild(track);
          }
          bars = containerCores.children;
        }
        for (let i = 0; i < nucleos.length; i++) {
          const val = Math.max(0, Math.min(100, Number(nucleos[i]) || 0));
          const fillEl = bars[i].firstElementChild;
          if (fillEl) {
            fillEl.style.height = `${val}%`;
            fillEl.className = 'mini-barra-v ' + (val >= 90 ? 'barra-alerta' : (val >= 70 ? 'barra-ambar' : 'barra-verde'));
          }
        }
      } else {
        containerCores.innerHTML = '<span class="rotulo-secundario">—</span>';
      }
    }

    // Lista processos_top (Top 5 processos compacto)
    const containerProcessos = document.getElementById('pc-processos-lista');
    if (containerProcessos) {
      const procs = Array.isArray(hw.processos_top) ? hw.processos_top.slice(0, 5) : [];
      if (procs.length === 0) {
        containerProcessos.innerHTML = '<div class="linha-dado rotulo-secundario">Nenhum processo</div>';
      } else {
        containerProcessos.innerHTML = '';
        procs.forEach(p => {
          const nomeP = p.nome || 'processo';
          const cpuP = formatarPct(p.cpu_pct);
          const ramP = formatarRamMb(p.ram_mb);
          const divRow = document.createElement('div');
          divRow.className = 'pc-linha-processo';
          divRow.innerHTML = `
            <span class="pc-proc-nome" title="${nomeP}">${nomeP}</span>
            <span class="pc-proc-metricas">${cpuP} · ${ramP}</span>
          `;
          containerProcessos.appendChild(divRow);
        });
      }
    }

    // Faixa de baixo
    // RAM
    const elFaixaRam = document.getElementById('pc-faixa-ram');
    if (elFaixaRam) {
      const ramU = hw.ram_usado_gb !== null && hw.ram_usado_gb !== undefined ? Number(hw.ram_usado_gb).toFixed(1) : '—';
      const ramT = hw.ram_total_gb !== null && hw.ram_total_gb !== undefined ? Number(hw.ram_total_gb).toFixed(1) : '—';
      const ramP = hw.ram_pct !== null && hw.ram_pct !== undefined ? ` (${Math.round(hw.ram_pct)}%)` : '';
      elFaixaRam.textContent = `RAM ${ramU}/${ramT} GB`;
    }

    // VRAM
    const elFaixaVram = document.getElementById('pc-faixa-vram');
    if (elFaixaVram) {
      const vramU = hw.vram_usado_gb !== null && hw.vram_usado_gb !== undefined ? Number(hw.vram_usado_gb).toFixed(1) : '—';
      const vramT = hw.vram_total_gb !== null && hw.vram_total_gb !== undefined ? Number(hw.vram_total_gb).toFixed(1) : '—';
      let vramP = '';
      if (hw.vram_usado_gb !== null && hw.vram_total_gb && hw.vram_total_gb > 0) {
        vramP = ` (${Math.round((hw.vram_usado_gb / hw.vram_total_gb) * 100)}%)`;
      }
      elFaixaVram.textContent = `VRAM ${vramU}/${vramT} GB`;
    }

    // Swap %
    const elFaixaSwap = document.getElementById('pc-faixa-swap');
    if (elFaixaSwap) {
      const sw = hw.swap_pct !== null && hw.swap_pct !== undefined ? `${Math.round(hw.swap_pct)}%` : '—%';
      elFaixaSwap.textContent = `Swap ${sw}`;
    }

    // Disco L/E MB/s
    const elFaixaDisco = document.getElementById('pc-faixa-disco');
    if (elFaixaDisco) {
      const l = hw.disco_leitura_mbps !== null && hw.disco_leitura_mbps !== undefined ? Number(hw.disco_leitura_mbps).toFixed(1) : '—';
      const e = hw.disco_escrita_mbps !== null && hw.disco_escrita_mbps !== undefined ? Number(hw.disco_escrita_mbps).toFixed(1) : '—';
      elFaixaDisco.textContent = `Disco ${l}/${e} MB/s`;
    }

    // Rede ↓/↑
    const elFaixaRede = document.getElementById('pc-faixa-rede');
    if (elFaixaRede) {
      elFaixaRede.textContent = `Rede ↓${formatarTaxaRede(hw.rede_down_kbps)} ↑${formatarTaxaRede(hw.rede_up_kbps)}`;
    }

    // Uptime
    const elFaixaUptime = document.getElementById('pc-faixa-uptime');
    if (elFaixaUptime) {
      elFaixaUptime.textContent = `Ligado ${formatarUptime(hw.uptime_s)}`;
    }

    // Sparklines com escala fixa por metrica
    ultimoHardwareParaSparklines = hw;
    desenharTodasSparklines(hw);
  }

  // Atualizacao de elementos do DOM com base no snapshot recebido
  // PC bloqueado: tela com o botao de digital, que abre o Remote Fingerprint Unlock
  // Link intent: o Fully gratis abre outros apps com "Open Other URL Schemes" ligado (sem adb)
  const INTENT_DIGITAL = 'intent:#Intent;action=android.intent.action.MAIN;' +
    'category=android.intent.category.LAUNCHER;' +
    'component=ro.andreimircius.remotefingerauth/com.example.mircius.fingerprintauth.MainActivity;end';
  // Telas de anel (mesmo desenho da tela de Energia): normal -> aguardando (arco girando) -> ok (check) -> fade
  function criarTelaAnel(id, textos, esperaMs) {
    const el = document.getElementById(id);
    const t = { visivel: false, okPendente: false };
    let tAguardando = null, tSumir = null;
    t.estado = (estado) => {
      if (!el) return;
      el.dataset.estado = estado;
      const [nome, dica] = textos[estado];
      const elNome = el.querySelector('.energia-nome');
      const elDica = el.querySelector('.energia-desc');
      if (elNome) elNome.textContent = nome;
      if (elDica) elDica.textContent = dica;
      clearTimeout(tAguardando);
      if (estado === 'aguardando') tAguardando = setTimeout(t.desistiu, esperaMs);
    };
    t.atual = () => (el ? el.dataset.estado : '');
    t.desistiu = () => {  // nao aconteceu nada: volta ao normal, com um tremor
      if (!el || !t.visivel || el.dataset.estado !== 'aguardando') return;
      t.estado('normal');
      el.classList.remove('falhou'); void el.offsetWidth; el.classList.add('falhou');
    };
    t.esperarDesistir = (ms) => { clearTimeout(tAguardando); tAguardando = setTimeout(t.desistiu, ms); };
    t.mostrar = () => {
      if (!el) return;
      clearTimeout(tSumir);
      t.okPendente = false;
      if (!t.visivel || el.dataset.estado === 'ok') t.estado('normal');
      t.visivel = true;
      el.classList.add('ativa');
    };
    t.esconder = () => {
      if (!el) return;
      clearTimeout(tSumir); clearTimeout(tAguardando);
      t.okPendente = false; t.visivel = false;
      el.classList.remove('ativa');
    };
    t.concluir = () => {
      if (!el) return;
      t.estado('ok');
      if (navigator.vibrate) { try { navigator.vibrate([20, 50, 40]); } catch (e) {} }
      clearTimeout(tSumir);
      tSumir = setTimeout(() => { el.classList.remove('ativa'); t.visivel = false; }, 1300);
    };
    // condicao terminou: mostra o check (ou guarda para quando o painel voltar a frente)
    t.terminou = () => {
      if (!t.visivel || t.atual() === 'ok' || t.okPendente) return;
      if (document.visibilityState === 'visible') t.concluir();
      else t.okPendente = true;
    };
    return t;
  }

  const telaVideo = criarTelaAnel('tela-video', {
    normal: ['Vídeo desligado', 'toque para acender o monitor'],
    aguardando: ['Acendendo…', 'o monitor volta em instantes'],
    ok: ['Vídeo ligado', 'monitor aceso'],
  }, 8000);

  function abrirAppDigital() {
    vibrarCurto(25);
    location.href = INTENT_DIGITAL;
    // Se o adb estiver no ar, o PC traz o Fully de volta depois do desbloqueio (server/actions.py)
    fetch(comToken('/action/voltar_painel'), { method: 'POST' }).catch(() => {});
  }

  function acenderVideo() {
    vibrarCurto(25);
    telaVideo.estado('aguardando');
    fetch(comToken('/action/acender_video'), { method: 'POST' })
      .then((r) => { if (!r.ok) telaVideo.desistiu(); })
      .catch(() => telaVideo.desistiu());
  }
  const botaoVideo = document.getElementById('botao-video');
  if (botaoVideo) botaoVideo.addEventListener('click', acenderVideo);

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible') return;
    if (telaVideo.okPendente) { telaVideo.okPendente = false; telaVideo.concluir(); }
    // voltou do app de digital: se o PC seguir bloqueado em 6 s, a digital nao foi (cancelou)
    if (boot && boot.fase === 'digital') {
      clearTimeout(temporizadorDigital);
      temporizadorDigital = setTimeout(digitalDesistiu, 6000);
    }
  });

  // PC bloqueado: o portao fecha em "Desbloquear". O app de digital so abre no toque do botao.
  // Desbloqueado com o video apagado: botao de acender o monitor.
  let fechandoBoot = false;
  function atualizarBloqueio(bloqueio) {
    if (pcSaindoDesde || !portaoConectado) return; // PC suspendendo/desligando: vale a tela do aviso
    if (!bloqueio || bloqueio.bloqueado === undefined) {
      // sem o coletor de bloqueio, nao da para esperar o desbloqueio: abre direto
      if (!estadoConhecido) { estadoConhecido = true; if (boot && portaoConectado) concluirBoot(); desenharPortao(); }
      return;
    }
    estadoConhecido = true;
    if (bloqueio.bloqueado) {
      if (telaVideo.visivel) telaVideo.esconder();
      if (!pcBloqueado) { pcBloqueado = true; acordarRepouso(); }
      // acordou pelo ON (digital ja pedida): a barra segue em 60%; sem toque, mostra o "Desbloquear"
      if (boot && boot.fase !== 'digital') {
        if (boot.porToque) faseBoot('bloqueio');
        else boot = null;
      }
    } else {
      pcBloqueado = false;
      if (bloqueio.video === 'desligado') telaVideo.mostrar();
      else telaVideo.terminou();
      // desbloqueou: a barra corre ate 100% e a porta abre no painel
      if (boot && boot.fase !== 'pronto' && !fechandoBoot) {
        fechandoBoot = true;
        clearTimeout(temporizadorDigital);
        faseBoot('entrando');
        setTimeout(() => { fechandoBoot = false; if (boot) concluirBoot(); }, 1200);
      }
    }
    desenharPortao();
  }

  // Interface mudou no PC: recarrega a pagina (o Fully so recarrega sozinho quando da erro)
  let versaoWeb = null;
  function conferirVersaoWeb(v) {
    if (!v) return;
    if (versaoWeb === null) { versaoWeb = v; return; }
    if (v !== versaoWeb) location.reload();
  }

  function atualizarPainel(dados) {
    if (!dados) return;
    conferirVersaoWeb(dados.versao_web);
    // cada aviso vale uma vez: depois de acordar, um aviso velho ainda no ar nao fecha o portao de novo
    if (!dados.energia) avisoEnergia(null);
    else if (dados.energia_seq !== ultimoSeqEnergia) { ultimoSeqEnergia = dados.energia_seq; avisoEnergia(dados.energia); }
    atualizarBloqueio(dados.bloqueio);

    // Estado do microfone
    if (dados.mic_mudo !== undefined) {
      micMudo = Boolean(dados.mic_mudo);
      sincronizarBotoesMic();
    }

    // Bloco Claude Usage & Claude (Tela 1 - Quadrante 1)
    const blocoCldUsage = extrairBloco(dados, 'claude_usage');
    const blocoClaude = extrairBloco(dados, 'claude');
    const erroClaude = blocoClaude.erro || blocoCldUsage.erro;
    const msgErroClaude = [blocoClaude.msgErro, blocoCldUsage.msgErro].filter(Boolean).join(' | ');
    atualizarIndicadorErro('erro-claude', erroClaude, msgErroClaude);

    const cldUsage = blocoCldUsage.val;
    const listaLimitesCld = (cldUsage && Array.isArray(cldUsage.limites)) ? cldUsage.limites : [];
    const containerLimitesCld = document.getElementById('claude-limites-lista');
    if (containerLimitesCld) {
      if (listaLimitesCld.length === 0) {
        containerLimitesCld.innerHTML = '<div class="linha-dado rotulo-secundario">Sem limites registrados</div>';
      } else {
        containerLimitesCld.innerHTML = '';
        listaLimitesCld.forEach(lim => {
          const nome = lim.nome || 'Limite';
          const usadoPct = lim.usado_pct !== undefined && lim.usado_pct !== null ? Number(lim.usado_pct) : 0;
          let corBarra = 'barra-verde';
          if (usadoPct >= 90) {
            corBarra = 'barra-alerta';
          } else if (usadoPct >= 70) {
            corBarra = 'barra-ambar';
          }
          const strReset = formatarTempoRestanteReset(lim.reset);
          const txtDireita = strReset
            ? `${Math.round(usadoPct)}% usado · reseta em ${strReset}`
            : `${Math.round(usadoPct)}% usado`;

          const divItem = document.createElement('div');
          divItem.className = 'item-limite-claude';
          divItem.innerHTML = `
            <div class="barra-rotulo-linha">
              <span>${nome}</span>
              <span>${txtDireita}</span>
            </div>
            <div class="trilho-barra">
              <div class="preenchimento-barra ${corBarra}" style="width: ${Math.max(0, Math.min(100, usadoPct))}%;"></div>
            </div>
          `;
          containerLimitesCld.appendChild(divItem);
        });
      }
    }

    const cld = blocoClaude.val || {};
    const cldHoje = cld.hoje || {};
    const cldMes = cld.mes || {};
    const cldSessao = cld.sessao || {};

    const elCldCompacto = document.getElementById('claude-hoje-compacto');
    if (elCldCompacto) {
      const inTok = formatarCurto(cldHoje.input);
      const outTok = formatarCurto(cldHoje.output);
      const crTok = formatarCurto(cldHoje.cache_read);
      const cwTok = formatarCurto(cldHoje.cache_write);
      const cHoje = formatarUsd(cldHoje.custo_equiv_usd);
      const cMes = formatarUsd(cldMes.custo_equiv_usd);
      elCldCompacto.innerHTML = `Hoje: In ${inTok} · Out ${outTok} · CR ${crTok} · CW ${cwTok}<br>≈ $ API hoje <span class="texto-verde">${cHoje}</span> · mês <span class="texto-verde">${cMes}</span>`;
    }

    const sessaoTokens = (cldSessao.input || 0) + (cldSessao.output || 0) + (cldSessao.cache_read || 0) + (cldSessao.cache_write || 0);
    const elCldSessao = document.getElementById('claude-sessao');
    if (elCldSessao) {
      elCldSessao.textContent = `Sessão: ${formatarCurto(sessaoTokens)} tok · ≈ ${formatarUsd(cldSessao.custo_equiv_usd)}`;
    }

    // Bloco OmniRoute (Tela 1 - Quadrante 2)
    const blocoOmni = extrairBloco(dados, 'omniroute');
    atualizarIndicadorErro('erro-omniroute', blocoOmni.erro, blocoOmni.msgErro);
    const omni = blocoOmni.val || {};

    const quadOmni = document.getElementById('quad-omniroute');
    if (quadOmni) {
      quadOmni.classList.toggle('servico-offline', !omni.online);
    }

    atualizarServico('omniroute', omni.online);

    const ultimaOmni = omni.ultima || {};
    const elOmniUltima = document.getElementById('omniroute-ultima');
    if (elOmniUltima) {
      const prov = ultimaOmni.provedor || '—';
      const mod = ultimaOmni.modelo || '—';
      const combo = ultimaOmni.combo ? ` · ${ultimaOmni.combo}` : '';
      elOmniUltima.textContent = `${prov} · ${mod}${combo}`;
    }

    const omniHoje = omni.hoje || {};
    const elOmniReqs = document.getElementById('omniroute-reqs');
    if (elOmniReqs) {
      elOmniReqs.textContent = `Requisições: ${omniHoje.requisicoes !== undefined ? Number(omniHoje.requisicoes).toLocaleString('pt-BR') : '—'}`;
    }
    const elOmniAcerto = document.getElementById('omniroute-acerto');
    if (elOmniAcerto) {
      elOmniAcerto.textContent = `Taxa de Acerto: ${omniHoje.taxa_acerto != null ? Number(omniHoje.taxa_acerto).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + '%' : '—'}`;
    }
    const elOmniLat = document.getElementById('omniroute-latencia');
    if (elOmniLat) {
      elOmniLat.textContent = `Latência Média: ${formatarMs(omniHoje.latencia_media_ms)}`;
    }

    // Bloco Ollama (Tela 1 - Quadrante 3)
    const blocoOllama = extrairBloco(dados, 'ollama');
    atualizarIndicadorErro('erro-ollama', blocoOllama.erro, blocoOllama.msgErro);
    const oll = blocoOllama.val || {};

    const quadOll = document.getElementById('quad-ollama');
    if (quadOll) {
      quadOll.classList.toggle('servico-offline', !oll.online);
    }

    atualizarServico('ollama', oll.online);

    const elOllamaVel = document.getElementById('ollama-velocidade');
    if (elOllamaVel) {
      const tokS = oll.tokens_s !== undefined && oll.tokens_s !== null ? Number(oll.tokens_s).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : '—';
      const modNome = oll.tokens_s_modelo ? ` (${oll.tokens_s_modelo})` : '';
      elOllamaVel.textContent = `${tokS} tok/s${modNome}`;
    }

    const listaModelosOll = Array.isArray(oll.modelos) ? oll.modelos : [];
    const containerModelos = document.getElementById('ollama-modelos-lista');
    if (containerModelos) {
      if (listaModelosOll.length === 0) {
        containerModelos.innerHTML = '<div class="linha-dado rotulo-secundario">Nenhum modelo carregado</div>';
      } else {
        containerModelos.innerHTML = '';
        listaModelosOll.forEach(m => {
          const nomeM = m.nome || 'desconhecido';
          const vramM = m.vram_gb !== undefined && m.vram_gb !== null ? Number(m.vram_gb).toFixed(1) + ' GB' : '— GB';
          const expM = formatarSegundosParaMmSs(m.expira_em_s);
          const divItem = document.createElement('div');
          divItem.className = 'linha-dado';
          divItem.textContent = `${nomeM} · ${vramM} · ${expM}`;
          containerModelos.appendChild(divItem);
        });
      }
    }

    // Bloco AGY & Financeiro (Tela 1 - Quadrante 4)
    const blocoAgy = extrairBloco(dados, 'agy');
    atualizarIndicadorErro('erro-agy', blocoAgy.erro, blocoAgy.msgErro);
    const agy = blocoAgy.val || {};
    const listaLimites = Array.isArray(agy.limites) ? agy.limites : [];
    const containerLimites = document.getElementById('agy-limites-lista');
    if (containerLimites) {
      if (listaLimites.length === 0) {
        containerLimites.innerHTML = '<div class="linha-dado rotulo-secundario">Sem limites registrados</div>';
      } else {
        containerLimites.innerHTML = '';
        listaLimites.forEach(lim => {
          const grupo = lim.grupo || '';
          const limNome = lim.limite || '';
          let sufixo = '';
          if (/five hour|5h/i.test(limNome)) {
            sufixo = ' 5h';
          } else if (/week|semana/i.test(limNome)) {
            sufixo = ' semana';
          }
          const rotuloFinal = `${grupo}${sufixo}`.trim() || 'Limite';
          const pctRest = lim.restante_pct !== undefined && lim.restante_pct !== null ? Number(lim.restante_pct) : 0;

          let classeCor = 'barra-verde';
          if (pctRest < 10) {
            classeCor = 'barra-alerta';
          } else if (pctRest < 30) {
            classeCor = 'barra-ambar';
          }

          const itemDiv = document.createElement('div');
          itemDiv.className = 'item-limite-agy';
          itemDiv.innerHTML = `
            <div class="barra-rotulo-linha">
              <span>${rotuloFinal}</span>
              <span>${Math.round(pctRest)}%</span>
            </div>
            <div class="trilho-barra">
              <div class="preenchimento-barra ${classeCor}" style="width: ${Math.max(0, Math.min(100, pctRest))}%;"></div>
            </div>
          `;
          containerLimites.appendChild(itemDiv);
        });
      }
    }

    const maestroHoje = agy.maestro_hoje || {};
    const elMaestro = document.getElementById('agy-maestro');
    if (elMaestro) {
      const ch = maestroHoje.chamadas !== undefined ? Number(maestroHoje.chamadas).toLocaleString('pt-BR') : '—';
      const tokTot = (maestroHoje.tokens_in || 0) + (maestroHoje.tokens_out || 0);
      elMaestro.textContent = `Maestro hoje: ${ch} ch · ${formatarCurto(tokTot)} tok`;
    }

    // Bloco Financeiro
    const blocoFin = extrairBloco(dados, 'financeiro');
    const fin = blocoFin.val || {};
    const hojeUsd = fin.hoje_usd !== undefined ? fin.hoje_usd : null;
    const mesUsd = fin.mes_usd !== undefined ? fin.mes_usd : null;
    const hojeBrl = fin.hoje_brl !== undefined ? fin.hoje_brl : null;
    const mesBrl = fin.mes_brl !== undefined ? fin.mes_brl : null;
    const taxaCmb = fin.usd_brl !== undefined ? fin.usd_brl : null;

    const elTopFin = document.getElementById('topo-financeiro');
    if (elTopFin) {
      elTopFin.textContent = `${formatarUsd(hojeUsd)}`;
    }

    const elFinHoje = document.getElementById('fin-gasto-hoje');
    if (elFinHoje) {
      elFinHoje.textContent = `Hoje ${formatarUsd(hojeUsd)}`;
    }

    const elFinMes = document.getElementById('fin-gasto-mes');
    if (elFinMes) {
      elFinMes.textContent = `Mês ${formatarUsd(mesUsd)} (${formatarBrl(mesBrl)})`;
    }

    const elFinCot = document.getElementById('fin-cotacao');
    if (elFinCot) {
      elFinCot.textContent = `USD/BRL ${taxaCmb !== null ? 'R$ ' + Number(taxaCmb).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}`;
    }

    // Atualizacao da Tela PC (Tela 2)
    atualizarTelaPC(dados);

    // Historico OmniRoute (Tela 6)
    const historicoOmni = Array.isArray(omni.historico) ? omni.historico.slice(0, 10) : [];
    const tbodyHist = document.getElementById('corpo-tabela-historico');
    if (tbodyHist) {
      if (historicoOmni.length === 0) {
        tbodyHist.innerHTML = '<tr><td colspan="5" class="linha-sem-dados">Nenhum registro</td></tr>';
      } else {
        tbodyHist.innerHTML = '';
        historicoOmni.forEach(item => {
          const tr = document.createElement('tr');
          const horaFmt = formatarIsoParaHhMm(item.hora);
          const provFmt = item.provedor || '—';
          const modFmt = item.modelo || '—';
          const tokFmt = formatarCurto(item.tokens);
          const custoFmt = item.custo_usd !== undefined && item.custo_usd !== null ? '$' + Number(item.custo_usd).toFixed(4) : '$0.00';
          tr.innerHTML = `
            <td>${horaFmt}</td>
            <td>${provFmt}</td>
            <td>${modFmt}</td>
            <td>${tokFmt}</td>
            <td>${custoFmt}</td>
          `;
          tbodyHist.appendChild(tr);
        });
      }
    }

    // Bloco Celular (Tela 6)
    const blocoCel = extrairBloco(dados, 'celular');
    atualizarIndicadorErro('erro-celular', blocoCel.erro, blocoCel.msgErro);
    const cel = blocoCel.val || {};

    const elS10Bat = document.getElementById('s10-bateria');
    if (elS10Bat) {
      if (cel.nivel !== null && cel.nivel !== undefined) {
        const niv = Number(cel.nivel);
        elS10Bat.textContent = `${niv}%`;
        if (niv > 85 || niv < 20) {
          elS10Bat.className = 'celular-valor valor-ambar';
        } else {
          elS10Bat.className = 'celular-valor valor-verde';
        }
      } else {
        elS10Bat.textContent = '—%';
        elS10Bat.className = 'celular-valor';
      }
    }

    const elS10Temp = document.getElementById('s10-temp');
    if (elS10Temp) {
      elS10Temp.textContent = cel.temp_c !== null && cel.temp_c !== undefined ? `${Number(cel.temp_c).toFixed(1)}°C` : '—°C';
    }

    const elS10Carga = document.getElementById('s10-carregando');
    if (elS10Carga) {
      if (cel.carregando !== null && cel.carregando !== undefined) {
        elS10Carga.textContent = cel.carregando ? 'Sim' : 'Não';
      } else {
        elS10Carga.textContent = '—';
      }
    }

    // Bloco Mídia (Tela Mídia)
    atualizarMidia(dados.midia);
  }

  // Relogio local no topo
  function atualizarRelogioLocal() {
    const agora = new Date();
    const elRelogio = document.getElementById('hora-local');
    if (elRelogio) {
      elRelogio.textContent = agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    }
  }
  setInterval(atualizarRelogioLocal, 1000);
  atualizarRelogioLocal();

  // Bateria do navegador para o servidor
  let gerenciadorBateria = null;
  let socketAtivo = null;

  async function inicializarApiBateria() {
    if ('getBattery' in navigator) {
      try {
        gerenciadorBateria = await navigator.getBattery();
        const emitirBateria = () => enviarTelemetriaBateria();
        gerenciadorBateria.addEventListener('levelchange', emitirBateria);
        gerenciadorBateria.addEventListener('chargingchange', emitirBateria);
      } catch (e) {}
    }
  }

  function enviarTelemetriaBateria() {
    if (!gerenciadorBateria || !socketAtivo || socketAtivo.readyState !== WebSocket.OPEN) return;
    try {
      socketAtivo.send(JSON.stringify({
        tipo: 'bateria',
        nivel: Math.round(gerenciadorBateria.level * 100),
        carregando: Boolean(gerenciadorBateria.charging)
      }));
    } catch (e) {}
  }

  // Wake Lock de Tela
  let travaDeTela = null;
  async function requisitarWakeLock() {
    if ('wakeLock' in navigator) {
      try {
        travaDeTela = await navigator.wakeLock.request('screen');
      } catch (e) {}
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      requisitarWakeLock();
    }
  });

  // Pixel shift anti burn-in a cada 5 min
  function aplicarPixelShift() {
    const deslocamentos = [-2, -1, 0, 1, 2];
    const dx = deslocamentos[Math.floor(Math.random() * deslocamentos.length)];
    const dy = deslocamentos[Math.floor(Math.random() * deslocamentos.length)];
    document.body.style.transform = `translate(${dx}px, ${dy}px)`;
  }
  setInterval(aplicarPixelShift, 5 * 60 * 1000);

  // Tela de Energia (botao circular gigante de liga/desliga com opcoes verticais)
  function inicializarTelaEnergia() {
    const telaEl = document.getElementById('tela-energia');
    const btn = document.getElementById('energia-botao');
    const nomeEl = document.getElementById('energia-nome');
    const descEl = document.getElementById('energia-desc');
    const pontosEl = document.querySelectorAll('.energia-ponto');
    if (!telaEl || !btn || !nomeEl || !descEl) return;

    const opcoes = [
      {
        id: 'energia_suspender',
        nome: 'Suspender',
        descricao: 'toque para suspender · arraste ↕ para mais',
        cor: 'var(--verde)',
        requerConfirmacao: false
      },
      {
        id: 'energia_desligar',
        nome: 'Desligar',
        descricao: 'desliga de verdade',
        cor: 'var(--vermelho)',
        requerConfirmacao: true
      },
      {
        id: 'energia_reiniciar',
        nome: 'Reiniciar',
        descricao: 'reinicia o Windows',
        cor: 'var(--ambar)',
        requerConfirmacao: true
      },
      {
        id: 'energia_bloquear',
        nome: 'Bloquear',
        descricao: 'tela de bloqueio',
        cor: 'var(--verde)',
        requerConfirmacao: false
      }
    ];

    let indiceAtual = 0;
    let timerArmado = null;
    let armado = false;

    function desarmar() {
      if (timerArmado) {
        clearTimeout(timerArmado);
        timerArmado = null;
      }
      armado = false;
      btn.classList.remove('armado');
      const op = opcoes[indiceAtual];
      if (descEl) descEl.textContent = op.descricao;
    }

    function mudarOpcao(novoIndice) {
      desarmar();
      indiceAtual = novoIndice;
      const op = opcoes[indiceAtual];

      telaEl.dataset.opcao = op.id;
      telaEl.style.setProperty('--cor-opcao', op.cor);
      nomeEl.textContent = op.nome;
      descEl.textContent = op.descricao;

      pontosEl.forEach((ponto, i) => {
        ponto.classList.toggle('ativo', i === indiceAtual);
      });
    }

    function tratarToque() {
      const op = opcoes[indiceAtual];
      if (op.requerConfirmacao) {
        if (!armado) {
          armado = true;
          btn.classList.add('armado');
          descEl.textContent = 'toque de novo para confirmar';
          vibrarCurto(25);
          timerArmado = setTimeout(() => {
            desarmar();
          }, 4000);
          return;
        }
      }
      desarmar();
      // o servidor tambem avisa sozinho; este aviso local garante a tela certa se o dele nao sair
      const aviso = { energia_suspender: 'suspendendo', energia_desligar: 'desligando',
        energia_reiniciar: 'reiniciando' }[op.id];
      executarAcao(op.id, btn).then((ok) => { if (ok && aviso) avisoEnergia(aviso); });
    }

    // Gestos verticais no botao circular (sem atrapalhar o swipe horizontal)
    let y0 = null;
    let x0 = 0;
    let ultimoDy = 0;
    let arrastou = false;

    btn.addEventListener('pointerdown', (e) => {
      if (e.button !== undefined && e.button !== 0) return;
      y0 = e.clientY;
      x0 = e.clientX;
      ultimoDy = 0;
      arrastou = false;
    });

    btn.addEventListener('pointermove', (e) => {
      if (y0 === null) return;
      const dy = e.clientY - y0;
      const dx = e.clientX - x0;
      ultimoDy = dy;
      if (!arrastou && Math.abs(dy) > 10 && Math.abs(dy) > Math.abs(dx)) {
        arrastou = true;
        try { btn.setPointerCapture(e.pointerId); } catch (err) {}
      }
    });

    function concluir(dy) {
      const tinhaArrastado = arrastou;
      y0 = null;
      if (!tinhaArrastado) return;
      if (dy < -30) {
        // Arrastou para cima: proxima opcao
        mudarOpcao((indiceAtual + 1) % opcoes.length);
        vibrarCurto(15);
      } else if (dy > 30) {
        // Arrastou para baixo: opcao anterior
        mudarOpcao((indiceAtual - 1 + opcoes.length) % opcoes.length);
        vibrarCurto(15);
      }
    }

    btn.addEventListener('pointerup', (e) => {
      if (y0 === null) return;
      try { btn.releasePointerCapture(e.pointerId); } catch (err) {}
      concluir(e.clientY - y0);
    });

    btn.addEventListener('pointercancel', (e) => {
      try { btn.releasePointerCapture(e.pointerId); } catch (err) {}
      if (y0 !== null && arrastou) {
        concluir(ultimoDy);
      } else {
        y0 = null;
        arrastou = false;
      }
    });

    btn.addEventListener('click', () => {
      if (arrastou) {
        arrastou = false;
        return;
      }
      tratarToque();
    });

    // Estado inicial: suspender
    mudarOpcao(0);
  }

  // ===== Tela de Mídia =====
  let sessaoMidiaAtivaId = null;
  let sessaoMidiaEscolhidaUsuario = null;
  let dadosMidiaUltimo = null;
  let estaTocandoMidia = false;
  let duracaoMidiaAtualS = 0;
  let basePosicaoMidiaS = 0;
  let baseMomentoMidiaMs = 0;
  let arrastandoProgressoMidia = false;
  let arrastandoVolumeMidia = false;
  let ultimaUrlCapaMidia = null;
  let timerProgressoMidia = null;
  let timerThrottleVolumeMidia = null;
  let valorPendenteVolumeMidia = null;
  let ultimoEnvioVolumeMidia = 0;
  let velocidadeMidiaAtual = 1;
  // Depois de um toque, o PC leva ~1 s para refletir o novo estado: segura o que o toque mostrou.
  let segurarPlayAteMs = 0;
  let segurarVelocidadeAteMs = 0;

  function vibrarEToqueAtivo(el) {
    vibrarCurto(25);
    if (el) {
      el.classList.add('toque-ativo');
      setTimeout(() => el.classList.remove('toque-ativo'), 250);
    }
  }

  async function enviarComandoMidia(cmd, valor, sessaoId) {
    const id = sessaoId !== undefined ? sessaoId : sessaoMidiaAtivaId;
    const corpo = { id: id || null };
    if (valor !== undefined) {
      corpo.valor = valor;
    }
    try {
      const resp = await fetch(comToken(`/midia/${cmd}`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(corpo)
      });
      const dados = await resp.json();
      if (!dados.ok) {
        exibirToast(dados.msg || 'Erro no comando de mídia', false);
      }
      return dados;
    } catch (err) {
      exibirToast('Falha na comunicação com o servidor', false);
      return { ok: false, msg: 'Falha na comunicação' };
    }
  }

  function enviarVolumeThrottled(valor) {
    valorPendenteVolumeMidia = valor;
    const agora = Date.now();
    const tempoRestante = 150 - (agora - ultimoEnvioVolumeMidia);
    if (tempoRestante <= 0) {
      ultimoEnvioVolumeMidia = agora;
      enviarComandoMidia('volume', valor);
      valorPendenteVolumeMidia = null;
    } else if (!timerThrottleVolumeMidia) {
      timerThrottleVolumeMidia = setTimeout(() => {
        timerThrottleVolumeMidia = null;
        ultimoEnvioVolumeMidia = Date.now();
        if (valorPendenteVolumeMidia !== null) {
          enviarComandoMidia('volume', valorPendenteVolumeMidia);
          valorPendenteVolumeMidia = null;
        }
      }, tempoRestante);
    }
  }

  function cancelarThrottleVolume() {
    if (timerThrottleVolumeMidia) {
      clearTimeout(timerThrottleVolumeMidia);
      timerThrottleVolumeMidia = null;
    }
    valorPendenteVolumeMidia = null;
  }

  function formatarTempoSegundos(segundos) {
    if (!segundos || isNaN(segundos) || segundos < 0) return '0:00';
    const total = Math.floor(segundos);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    if (h > 0) {
      return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  function atualizarEstiloSliderVolume(val) {
    const slider = document.getElementById('midia-volume-slider');
    if (slider) {
      const v = Math.max(0, Math.min(100, Number(val) || 0));
      slider.style.background = `linear-gradient(to right, var(--verde) ${v}%, rgba(255, 255, 255, 0.12) ${v}%)`;
    }
  }

  // <svg> não tem a propriedade .hidden (só elementos HTML): é preciso mexer no atributo.
  function alternarIcone(el, esconder) {
    if (el) el.toggleAttribute('hidden', Boolean(esconder));
  }

  function definirIconePlayPauseMidia(tocando) {
    alternarIcone(document.querySelector('.midia-ic-play'), tocando);
    alternarIcone(document.querySelector('.midia-ic-pause'), !tocando);
    const btn = document.getElementById('midia-btn-play');
    if (btn) {
      btn.title = tocando ? 'Pausar' : 'Tocar';
      btn.setAttribute('aria-label', tocando ? 'Pausar' : 'Tocar');
    }
  }

  function formatarVelocidade(v) {
    return `${String(Number(v)).replace('.', ',')}x`;
  }

  function definirVelocidadeMidia(v) {
    velocidadeMidiaAtual = Number(v) || 1;
    const btn = document.getElementById('midia-btn-vel');
    if (btn) btn.textContent = formatarVelocidade(velocidadeMidiaAtual);
    document.querySelectorAll('#midia-vel-menu button').forEach(b => {
      const ativo = Math.abs(Number(b.dataset.vel) - velocidadeMidiaAtual) < 0.01;
      b.classList.toggle('ativo', ativo);
      b.setAttribute('aria-checked', ativo ? 'true' : 'false');
    });
  }

  function abrirMenuVelocidade(abrir) {
    const menu = document.getElementById('midia-vel-menu');
    const btn = document.getElementById('midia-btn-vel');
    if (!menu || !btn) return;
    menu.toggleAttribute('hidden', !abrir);
    btn.setAttribute('aria-expanded', abrir ? 'true' : 'false');
  }

  function iniciarLoopProgressoMidia() {
    if (!timerProgressoMidia) {
      timerProgressoMidia = setInterval(avancarProgressoMidiaLocal, 250);
    }
  }

  function pararLoopProgressoMidia() {
    if (timerProgressoMidia) {
      clearInterval(timerProgressoMidia);
      timerProgressoMidia = null;
    }
  }

  function renderizarProgressoMidia(pos, duracao) {
    const elAtual = document.getElementById('midia-tempo-atual');
    const elTotal = document.getElementById('midia-tempo-total');
    const elPreench = document.getElementById('midia-progresso-preench');
    if (elAtual) elAtual.textContent = formatarTempoSegundos(pos);
    if (elTotal) elTotal.textContent = formatarTempoSegundos(duracao);
    if (elPreench) {
      const pct = duracao > 0 ? Math.min(100, Math.max(0, (pos / duracao) * 100)) : 0;
      elPreench.style.width = pct + '%';
    }
  }

  function avancarProgressoMidiaLocal() {
    if (!estaTocandoMidia || arrastandoProgressoMidia || duracaoMidiaAtualS <= 0) return;
    const decorridoS = (performance.now() - baseMomentoMidiaMs) / 1000;
    const pos = Math.min(duracaoMidiaAtualS, Math.max(0, basePosicaoMidiaS + decorridoS));
    renderizarProgressoMidia(pos, duracaoMidiaAtualS);
  }

  function atualizarCapaMidia(capaUrl) {
    const img = document.getElementById('midia-capa-img');
    const placeholder = document.getElementById('midia-capa-placeholder');
    if (!img || !placeholder) return;
    if (!capaUrl) {
      ultimaUrlCapaMidia = null;
      img.hidden = true;
      img.removeAttribute('src');
      placeholder.hidden = false;
      return;
    }
    const urlFinal = comToken(capaUrl);
    if (ultimaUrlCapaMidia !== urlFinal) {
      ultimaUrlCapaMidia = urlFinal;
      img.onload = () => {
        img.hidden = false;
        placeholder.hidden = true;
      };
      img.onerror = () => {
        img.hidden = true;
        placeholder.hidden = false;
      };
      img.src = urlFinal;
    } else if (img.complete && img.naturalWidth > 0) {
      img.hidden = false;
      placeholder.hidden = true;
    }
  }

  function atualizarMidia(midia) {
    const elErro = document.getElementById('midia-erro');
    const elVazio = document.getElementById('midia-vazio');
    const elDetalhe = document.getElementById('midia-detalhe');
    const elChips = document.getElementById('midia-chips');
    const btnMudo = document.getElementById('midia-btn-mudo');
    const icSom = document.querySelector('.midia-ic-som');
    const icMudo = document.querySelector('.midia-ic-mudo');
    const sliderVol = document.getElementById('midia-volume-slider');
    const txtVol = document.getElementById('midia-volume-valor');

    dadosMidiaUltimo = midia || null;

    // Erro do backend
    if (elErro) {
      if (midia && midia.erro) {
        elErro.textContent = midia.erro;
        elErro.hidden = false;
      } else {
        elErro.textContent = '';
        elErro.hidden = true;
      }
    }

    // Volume e mudo (permanecem visíveis mesmo sem sessões)
    if (midia && midia.volume !== undefined && !arrastandoVolumeMidia) {
      const volNum = Math.max(0, Math.min(100, Number(midia.volume) || 0));
      if (sliderVol) sliderVol.value = volNum;
      if (txtVol) txtVol.textContent = `${volNum}%`;
      atualizarEstiloSliderVolume(volNum);
    }
    if (midia && midia.mudo !== undefined) {
      const mudo = Boolean(midia.mudo);
      if (btnMudo) {
        btnMudo.classList.toggle('mudo', mudo);
        btnMudo.title = mudo ? 'Desativar mudo' : 'Mudo';
      }
      alternarIcone(icSom, mudo);
      alternarIcone(icMudo, !mudo);
    }

    const sessoes = (midia && Array.isArray(midia.sessoes)) ? midia.sessoes : [];

    // Sem sessões ativas
    if (sessoes.length === 0) {
      sessaoMidiaAtivaId = null;
      sessaoMidiaEscolhidaUsuario = null;
      estaTocandoMidia = false;
      pararLoopProgressoMidia();
      atualizarCapaMidia(null);
      if (elVazio) elVazio.hidden = false;
      if (elDetalhe) elDetalhe.hidden = true;
      if (elChips) { elChips.hidden = true; elChips.innerHTML = ''; }
      return;
    }

    // Seleção de sessão: manter a do usuário se ainda existir; senão voltar para atual (ou a primeira)
    if (sessaoMidiaEscolhidaUsuario && sessoes.some(s => s.id === sessaoMidiaEscolhidaUsuario)) {
      sessaoMidiaAtivaId = sessaoMidiaEscolhidaUsuario;
    } else {
      sessaoMidiaEscolhidaUsuario = null;
      const existeAtual = midia.atual && sessoes.some(s => s.id === midia.atual);
      sessaoMidiaAtivaId = existeAtual ? midia.atual : sessoes[0].id;
    }

    const sessao = sessoes.find(s => s.id === sessaoMidiaAtivaId) || sessoes[0];
    sessaoMidiaAtivaId = sessao.id;

    if (elVazio) elVazio.hidden = true;
    if (elDetalhe) elDetalhe.hidden = false;

    // Chips de sessões se houver mais de 1
    if (elChips) {
      if (sessoes.length > 1) {
        elChips.hidden = false;
        elChips.innerHTML = '';
        sessoes.forEach(s => {
          const chip = document.createElement('button');
          chip.type = 'button';
          chip.className = 'midia-chip' + (s.id === sessaoMidiaAtivaId ? ' ativo' : '');
          chip.dataset.id = s.id;
          const estaTocando = Boolean(s.tocando && s.status === 'tocando');
          const iconeMini = estaTocando
            ? '<svg viewBox="0 0 24 24" class="midia-chip-ic"><polygon points="6 4 19 12 6 20 6 4" fill="currentColor"/></svg>'
            : '<svg viewBox="0 0 24 24" class="midia-chip-ic"><rect x="6" y="4" width="4" height="16" fill="currentColor"/><rect x="14" y="4" width="4" height="16" fill="currentColor"/></svg>';
          chip.innerHTML = `${iconeMini}<span>${escaparHtml(s.app || s.id)}</span>`;
          chip.addEventListener('click', () => {
            vibrarEToqueAtivo(chip);
            sessaoMidiaEscolhidaUsuario = s.id;
            sessaoMidiaAtivaId = s.id;
            atualizarMidia(dadosMidiaUltimo);
          });
          elChips.appendChild(chip);
        });
      } else {
        elChips.hidden = true;
        elChips.innerHTML = '';
      }
    }

    // Informações da sessão
    const elApp = document.getElementById('midia-app');
    const elTitulo = document.getElementById('midia-titulo');
    const elArtista = document.getElementById('midia-artista');
    if (elApp) elApp.textContent = (sessao.app || sessao.id || 'MÍDIA').toUpperCase();
    if (elTitulo) elTitulo.textContent = sessao.titulo || 'Sem título';
    if (elArtista) elArtista.textContent = sessao.artista || sessao.album || '';

    // Capa
    atualizarCapaMidia(sessao.capa);

    // Estado de reprodução
    if (Date.now() >= segurarPlayAteMs) {
      estaTocandoMidia = Boolean(sessao.tocando && sessao.status === 'tocando');
    }
    definirIconePlayPauseMidia(estaTocandoMidia);

    // Velocidade
    const btnVel = document.getElementById('midia-btn-vel');
    const podeVel = Boolean(sessao.pode_velocidade);
    if (btnVel) btnVel.toggleAttribute('hidden', !podeVel);
    if (!podeVel) abrirMenuVelocidade(false);
    if (Date.now() >= segurarVelocidadeAteMs) {
      definirVelocidadeMidia(sessao.velocidade || 1);
    }

    // Progresso e seek
    duracaoMidiaAtualS = Number(sessao.duracao_s) || 0;
    basePosicaoMidiaS = Number(sessao.posicao_s) || 0;
    baseMomentoMidiaMs = performance.now();

    const elBlocoProgresso = document.getElementById('midia-progresso');
    const elBarraProgresso = document.getElementById('midia-barra-progresso');
    if (elBlocoProgresso) {
      if (duracaoMidiaAtualS <= 0) {
        elBlocoProgresso.hidden = true;
      } else {
        elBlocoProgresso.hidden = false;
        if (elBarraProgresso) {
          const podeSeek = Boolean(sessao.pode_seek);
          elBarraProgresso.classList.toggle('desativada', !podeSeek);
        }
        if (!arrastandoProgressoMidia) {
          renderizarProgressoMidia(basePosicaoMidiaS, duracaoMidiaAtualS);
        }
      }
    }

    if (estaTocandoMidia && duracaoMidiaAtualS > 0) {
      iniciarLoopProgressoMidia();
    } else {
      pararLoopProgressoMidia();
    }

    // Botões de pular: número pular_s
    const pularS = Number(midia.pular_s) || 10;
    const elRotuloVoltar = document.getElementById('midia-voltar-rotulo');
    const elRotuloAvancar = document.getElementById('midia-avancar-rotulo');
    const btnVoltar = document.getElementById('midia-btn-voltar');
    const btnAvancar = document.getElementById('midia-btn-avancar');
    if (elRotuloVoltar) elRotuloVoltar.textContent = pularS;
    if (elRotuloAvancar) elRotuloAvancar.textContent = pularS;
    if (btnVoltar) btnVoltar.title = `Voltar ${pularS}s`;
    if (btnAvancar) btnAvancar.title = `Avançar ${pularS}s`;
  }

  function inicializarTelaMidia() {
    const btnAnterior = document.getElementById('midia-btn-anterior');
    const btnVoltar = document.getElementById('midia-btn-voltar');
    const btnPlay = document.getElementById('midia-btn-play');
    const btnAvancar = document.getElementById('midia-btn-avancar');
    const btnProxima = document.getElementById('midia-btn-proxima');
    const btnMudo = document.getElementById('midia-btn-mudo');
    const barraProgresso = document.getElementById('midia-barra-progresso');
    const sliderVolume = document.getElementById('midia-volume-slider');
    const caixaSliderVolume = document.querySelector('.midia-volume-slider-caixa');

    if (btnAnterior) {
      btnAnterior.addEventListener('click', () => {
        vibrarEToqueAtivo(btnAnterior);
        enviarComandoMidia('anterior');
      });
    }

    if (btnVoltar) {
      btnVoltar.addEventListener('click', () => {
        vibrarEToqueAtivo(btnVoltar);
        enviarComandoMidia('voltar');
      });
    }

    if (btnPlay) {
      btnPlay.addEventListener('click', async () => {
        vibrarEToqueAtivo(btnPlay);
        estaTocandoMidia = !estaTocandoMidia;
        segurarPlayAteMs = Date.now() + 2000;
        definirIconePlayPauseMidia(estaTocandoMidia);
        if (estaTocandoMidia) {
          baseMomentoMidiaMs = performance.now();
          iniciarLoopProgressoMidia();
        } else {
          pararLoopProgressoMidia();
        }
        const resp = await enviarComandoMidia('alternar');
        if (!resp.ok) segurarPlayAteMs = 0;
      });
    }

    // Toque na miniatura: traz a janela que está tocando (Chrome, VLC, Media Player...) para a frente no PC
    const capaMoldura = document.getElementById('midia-capa-moldura');
    if (capaMoldura) {
      const focar = () => {
        vibrarEToqueAtivo(capaMoldura);
        enviarComandoMidia('focar').then(r => { if (r.ok) exibirToast(r.msg, true); });
      };
      capaMoldura.addEventListener('click', focar);
      capaMoldura.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); focar(); }
      });
    }

    // Velocidade: botão "1x" no rodapé abre a lista de valores
    const btnVel = document.getElementById('midia-btn-vel');
    const menuVel = document.getElementById('midia-vel-menu');
    if (btnVel && menuVel) {
      btnVel.addEventListener('click', (e) => {
        e.stopPropagation();
        vibrarEToqueAtivo(btnVel);
        abrirMenuVelocidade(menuVel.hasAttribute('hidden'));
      });
      menuVel.querySelectorAll('button').forEach(b => {
        b.addEventListener('click', async (e) => {
          e.stopPropagation();
          vibrarEToqueAtivo(b);
          const anterior = velocidadeMidiaAtual;
          const v = Number(b.dataset.vel);
          abrirMenuVelocidade(false);
          definirVelocidadeMidia(v);
          segurarVelocidadeAteMs = Date.now() + 4000;
          const resp = await enviarComandoMidia('velocidade', v);
          if (!resp.ok) {
            segurarVelocidadeAteMs = 0;
            definirVelocidadeMidia(anterior);
          }
        });
      });
      document.addEventListener('click', (e) => {
        if (!menuVel.hasAttribute('hidden') && !menuVel.contains(e.target) && e.target !== btnVel) {
          abrirMenuVelocidade(false);
        }
      });
    }

    if (btnAvancar) {
      btnAvancar.addEventListener('click', () => {
        vibrarEToqueAtivo(btnAvancar);
        enviarComandoMidia('avancar');
      });
    }

    if (btnProxima) {
      btnProxima.addEventListener('click', () => {
        vibrarEToqueAtivo(btnProxima);
        enviarComandoMidia('proxima');
      });
    }

    if (btnMudo) {
      btnMudo.addEventListener('click', () => {
        vibrarEToqueAtivo(btnMudo);
        enviarComandoMidia('mudo');
      });
    }

    // Gestos da Barra de Progresso (Seek)
    if (barraProgresso) {
      const trilho = barraProgresso.querySelector('.midia-progresso-trilho') || barraProgresso;

      const obterPct = (e) => {
        const rect = trilho.getBoundingClientRect();
        if (rect.width <= 0) return 0;
        return Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      };

      barraProgresso.addEventListener('pointerdown', (e) => {
        if (barraProgresso.classList.contains('desativada')) return;
        if (duracaoMidiaAtualS <= 0) return;
        e.stopPropagation();
        try { barraProgresso.setPointerCapture(e.pointerId); } catch (err) {}
        arrastandoProgressoMidia = true;
        const pct = obterPct(e);
        const pos = pct * duracaoMidiaAtualS;
        renderizarProgressoMidia(pos, duracaoMidiaAtualS);
      });

      barraProgresso.addEventListener('pointermove', (e) => {
        if (!arrastandoProgressoMidia) return;
        e.stopPropagation();
        const pct = obterPct(e);
        const pos = pct * duracaoMidiaAtualS;
        renderizarProgressoMidia(pos, duracaoMidiaAtualS);
      });

      const finalizarSeek = (e) => {
        if (!arrastandoProgressoMidia) return;
        e.stopPropagation();
        try { barraProgresso.releasePointerCapture(e.pointerId); } catch (err) {}
        arrastandoProgressoMidia = false;
        const pct = obterPct(e);
        const pos = Math.round(pct * duracaoMidiaAtualS * 10) / 10;
        basePosicaoMidiaS = pos;
        baseMomentoMidiaMs = performance.now();
        renderizarProgressoMidia(pos, duracaoMidiaAtualS);
        enviarComandoMidia('posicao', pos);
      };

      barraProgresso.addEventListener('pointerup', finalizarSeek);
      barraProgresso.addEventListener('pointercancel', (e) => {
        if (arrastandoProgressoMidia) {
          try { barraProgresso.releasePointerCapture(e.pointerId); } catch (err) {}
          arrastandoProgressoMidia = false;
          renderizarProgressoMidia(basePosicaoMidiaS, duracaoMidiaAtualS);
        }
      });

      barraProgresso.addEventListener('touchstart', (e) => e.stopPropagation(), { passive: true });
      barraProgresso.addEventListener('touchmove', (e) => { e.stopPropagation(); e.preventDefault(); }, { passive: false });
      barraProgresso.addEventListener('touchend', (e) => e.stopPropagation(), { passive: true });
    }

    // Gestos e Controles de Volume
    if (sliderVolume) {
      const txtVol = document.getElementById('midia-volume-valor');

      const iniciarArrastoVolume = (e) => {
        e.stopPropagation();
        arrastandoVolumeMidia = true;
      };

      const tratarInputVolume = (e) => {
        e.stopPropagation();
        arrastandoVolumeMidia = true;
        const val = Number(sliderVolume.value);
        if (txtVol) txtVol.textContent = `${val}%`;
        atualizarEstiloSliderVolume(val);
        enviarVolumeThrottled(val);
      };

      const finalizarArrastoVolume = (e) => {
        e.stopPropagation();
        if (arrastandoVolumeMidia) {
          arrastandoVolumeMidia = false;
          cancelarThrottleVolume();
          const val = Number(sliderVolume.value);
          enviarComandoMidia('volume', val);
        }
      };

      sliderVolume.addEventListener('pointerdown', iniciarArrastoVolume);
      sliderVolume.addEventListener('input', tratarInputVolume);
      sliderVolume.addEventListener('change', finalizarArrastoVolume);
      sliderVolume.addEventListener('pointerup', finalizarArrastoVolume);
      sliderVolume.addEventListener('pointercancel', (e) => {
        arrastandoVolumeMidia = false;
        cancelarThrottleVolume();
      });

      sliderVolume.addEventListener('touchstart', (e) => e.stopPropagation(), { passive: true });
      sliderVolume.addEventListener('touchmove', (e) => { e.stopPropagation(); }, { passive: true });
      sliderVolume.addEventListener('touchend', (e) => e.stopPropagation(), { passive: true });

      if (caixaSliderVolume) {
        caixaSliderVolume.addEventListener('touchstart', (e) => e.stopPropagation(), { passive: true });
        caixaSliderVolume.addEventListener('touchmove', (e) => { e.stopPropagation(); }, { passive: true });
      }
    }
  }

  // Navegacao e Indicador de Paginas
  function inicializarIndicadorPaginas() {
    const container = document.getElementById('container-horizontal');
    const pontos = document.querySelectorAll('.ponto-pag');
    if (!container || !pontos.length) return;
    const telas = container.querySelectorAll('.tela');

    container.addEventListener('scroll', () => {
      const largura = container.clientWidth || window.innerWidth;
      const indice = Math.round(container.scrollLeft / largura);
      pontos.forEach((p, i) => {
        if (i === indice) {
          p.classList.add('ativo');
        } else {
          p.classList.remove('ativo');
        }
      });
    }, { passive: true });

    pontos.forEach((p, i) => {
      p.addEventListener('click', () => {
        if (telas[i]) {
          telas[i].scrollIntoView({ behavior: 'smooth', inline: 'start' });
        }
      });
    });
  }

  // Conexao WebSocket com reconexao automatica (1s, 2s, 4s... ate 10s)
  let tentativaConexaoWs = 0;
  function conectarWebSocket() {
    const protocolo = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = comToken(`${protocolo}//${window.location.host}/ws`);

    try {
      socketAtivo = new WebSocket(wsUrl);
    } catch (err) {
      agendarReconexaoWs();
      return;
    }
    // Sem resposta em 4 s (PC desligado: o pacote some sem erro), desiste e tenta de novo
    const tentativa = socketAtivo;
    setTimeout(() => {
      if (tentativa.readyState === WebSocket.CONNECTING) { try { tentativa.close(); } catch (e) {} }
    }, 4000);

    socketAtivo.onopen = () => {
      ultimoPacoteWs = Date.now();
      tentativaConexaoWs = 0;
      atualizarStatusWs(true);
      portaoConexao(true);
      enviarTelemetriaBateria();
      if (!acoesCarregadas) {
        carregarAcoes();
      }
    };

    socketAtivo.onmessage = (evento) => {
      ultimoPacoteWs = Date.now();
      try {
        const pacote = JSON.parse(evento.data);
        if (pacote && pacote.tipo === 'estado' && pacote.dados) {
          atualizarPainel(pacote.dados);
        }
      } catch (err) {
        console.error('Falha ao decodificar pacote WS:', err);
      }
    };

    socketAtivo.onclose = () => {
      atualizarStatusWs(false);
      portaoConexao(false);
      agendarReconexaoWs();
    };

    socketAtivo.onerror = () => {
      try { socketAtivo.close(); } catch (e) {}
    };
  }

  // Conexao meio aberta: o WebView segue achando que esta conectado, mas nao chega nada (o servidor manda 1 pacote/s).
  // 6 s sem pacote = queda: descarta o socket e procura o PC de novo.
  let ultimoPacoteWs = Date.now();
  setInterval(() => {
    const s = socketAtivo;
    if (!s || s.readyState !== WebSocket.OPEN || Date.now() - ultimoPacoteWs < 6000) return;
    s.onclose = null; s.onmessage = null; s.onerror = null;
    try { s.close(); } catch (e) {}
    socketAtivo = null;
    atualizarStatusWs(false);
    portaoConexao(false);
    tentativaConexaoWs = 0;
    agendarReconexaoWs();
  }, 2000);

  // O celular fica procurando o PC: tenta em 1 s, 2 s e depois a cada 3 s, para sempre.
  let temporizadorReconexao = null;
  function agendarReconexaoWs() {
    const delay = Math.min(3000, 1000 * Math.pow(2, tentativaConexaoWs));
    tentativaConexaoWs++;
    clearTimeout(temporizadorReconexao);
    temporizadorReconexao = setTimeout(conectarWebSocket, delay);
  }

  function reconectarAgora() {
    clearTimeout(temporizadorReconexao);
    if (socketAtivo && socketAtivo.readyState <= WebSocket.OPEN) return; // ja conectando ou conectado
    tentativaConexaoWs = 0;
    conectarWebSocket();
  }

  // ===== Portao: abre quando o PC esta conectado E o painel esta ligado (botao ON/OFF) =====
  let portaoConectado = false;
  let portaoLigado = true;
  try { portaoLigado = localStorage.getItem('painel_ligado') !== '0'; } catch (e) {}
  let temporizadorQueda = null;
  let temporizadorFalha = null;
  let temporizadorDigital = null;
  let pcBloqueado = false;      // Windows na tela de bloqueio (pelo painel ou pelo vigia)
  let estadoConhecido = false;  // so abre a porta depois do 1o pacote dizer se o PC esta bloqueado

  // Sem o PC, o portao mostra como ele saiu (suspenso, desligado) e espera o toque no ON.
  const TEXTOS_PC_FORA = {
    suspenso: ['PC suspenso', 'toque para acordar · a digital acorda e desbloqueia'],
    desligado: ['PC desligado', 'toque para ligar · a digital liga e desbloqueia'],
    fora: ['PC desligado ou dormindo', 'toque no botão para ligar o PC'],
  };
  let pcFora = 'fora';
  try { const s = localStorage.getItem('pc_fora'); if (TEXTOS_PC_FORA[s]) pcFora = s; } catch (e) {}
  function marcarPcFora(estado) {
    pcFora = TEXTOS_PC_FORA[estado] ? estado : 'fora';
    try { localStorage.setItem('pc_fora', pcFora); } catch (e) {}
  }

  // Aviso do PC antes de sumir (server/collectors/bloqueio.py): fecha o portao na hora com a tela certa
  let pcSaindoDesde = 0;
  let ultimoSeqEnergia = null;
  let esperarVigiaCair = false; // durante o desligamento o vigia ainda responde: so vale depois de cair
  function avisoEnergia(evento) {
    if (!evento) {
      // o PC desistiu (suspensao/desligamento cancelado) e segue mandando dados: reabre
      if (pcSaindoDesde && Date.now() - pcSaindoDesde > 15000 && socketAtivo &&
          socketAtivo.readyState === WebSocket.OPEN) {
        pcSaindoDesde = 0;
        portaoConexao(true);
      }
      return;
    }
    if (pcSaindoDesde) return;
    pcSaindoDesde = Date.now();
    esperarVigiaCair = true;
    marcarPcFora(evento === 'suspendendo' ? 'suspenso' : 'desligado');
    clearTimeout(temporizadorQueda);
    clearTimeout(temporizadorDigital);
    portaoConectado = false;
    pcBloqueado = false;
    estadoConhecido = false;
    boot = null;
    if (evento === 'reiniciando') faseBoot('reiniciando');
    acordarRepouso();
    desenharPortao();
  }

  // ===== Barra de inicializacao: 0% (tocou no ON / PC reiniciando) ate 100% (painel conectado) =====
  // As fases vem do vigia (server/vigia.py, porta 8081), que roda desde o boot, antes do logon.
  // Dentro de cada fase a barra anda sozinha em direcao ao teto, sem nunca voltar.
  const FASES_BOOT = {
    acordando:   { de: 0,  ate: 25, tau: 20, txt: ['Ligando o PC…', 'encoste o dedo no leitor: é a digital que liga o PC'] },
    reiniciando: { de: 0,  ate: 30, tau: 20, txt: ['Reiniciando…', 'o Windows está fechando'] },
    windows:     { de: 35, ate: 55, tau: 15, txt: ['Iniciando o Windows…', 'carregando o sistema'] },
    bloqueio:    { de: 60, ate: 64, tau: 30, txt: ['Windows pronto', 'toque no botão para desbloquear com a digital'] },
    digital:     { de: 60, ate: 68, tau: 20, txt: ['Encoste o dedo', 'no leitor do celular · o painel volta sozinho'] },
    entrando:    { de: 70, ate: 96, tau: 10, txt: ['Entrando no Windows…', 'abrindo o painel'] },
    pronto:      { de: 100, ate: 100, tau: 1, txt: ['Windows ligado', 'abrindo o painel'] },
  };
  // porToque: a barra comecou por um toque no botao (a digital ja foi pedida). Sem toque, quando o
  // Windows chega na tela de bloqueio a barra some e o portao mostra o "Desbloquear".
  let boot = null; // { fase, desde, pct, porToque }
  function faseBoot(fase, porToque) {
    if (!FASES_BOOT[fase]) return;
    if (!boot) { boot = { fase: null, desde: 0, pct: 0, porToque: false }; acordarRepouso(); }
    if (porToque) boot.porToque = true;
    if (boot.fase === fase) return;
    boot.fase = fase;
    boot.desde = Date.now();
    boot.pct = Math.max(boot.pct, FASES_BOOT[fase].de);
    desenharPortao();
  }
  setInterval(() => {
    if (!boot) return;
    const f = FASES_BOOT[boot.fase];
    const t = (Date.now() - boot.desde) / 1000;
    boot.pct = Math.max(boot.pct, f.de + (f.ate - f.de) * (1 - Math.exp(-t / f.tau)));
    desenharPortao();
  }, 250);
  function concluirBoot() {
    faseBoot('pronto');
    setTimeout(() => { if (boot && boot.fase === 'pronto') { boot = null; desenharPortao(); } }, 900);
  }

  // Sem painel conectado, pergunta ao vigia a cada 2 s em que ponto o Windows esta
  let vigiaOcupado = false;
  async function consultarVigia() {
    if (portaoConectado || vigiaOcupado) return;
    vigiaOcupado = true;
    const ctrl = new AbortController();
    const limite = setTimeout(() => ctrl.abort(), 1800);
    try {
      const r = await fetch(`${location.protocol}//${location.hostname}:8081/`, { signal: ctrl.signal, cache: 'no-store' });
      const s = await r.json();
      if (!portaoConectado && !esperarVigiaCair && s && s.ok) {
        pcBloqueado = s.fase === 'bloqueio';
        if (s.fase === 'bloqueio') {
          // tela de bloqueio do Windows: segue a barra so se ja houve toque; senao, "Desbloquear"
          if (boot && boot.porToque) { if (boot.fase !== 'digital') faseBoot('bloqueio'); }
          else if (boot) { boot = null; acordarRepouso(); }
          desenharPortao();
        } else {
          faseBoot(s.fase === 'pronto' ? 'entrando' : s.fase);
        }
        if (s.fase === 'pronto' || s.fase === 'entrando') reconectarAgora();
      }
    } catch (e) {
      esperarVigiaCair = false; // PC sumiu de vez: a proxima resposta do vigia ja e o PC voltando
      if (pcBloqueado && !portaoConectado) { pcBloqueado = false; desenharPortao(); }
    } finally {
      clearTimeout(limite);
      vigiaOcupado = false;
    }
  }
  setInterval(consultarVigia, 2000);

  // OLED: sem toque por 2 min, o portao esmaece (volta no primeiro toque ou quando o PC liga)
  let temporizadorRepouso = null;
  function acordarRepouso() {
    const el = document.getElementById('portao');
    if (el) el.classList.remove('repouso');
    clearTimeout(temporizadorRepouso);
    temporizadorRepouso = setTimeout(() => {
      if (el && !boot) el.classList.add('repouso');
    }, 120000);
  }

  function desenharPortao() {
    const el = document.getElementById('portao');
    if (!el) return;
    const status = document.getElementById('portao-status');
    const dica = document.getElementById('portao-dica');
    const rotulo = document.getElementById('power-rotulo');
    const iniciando = boot !== null; // com a barra na tela, o portao so abre quando ela chega a 100%
    // PC bloqueado (ou Windows esperando a digital no boot): o botao vira "Desbloquear"
    const bloqueado = (pcBloqueado && !iniciando) || (iniciando && boot.fase === 'bloqueio');
    const aberto = portaoConectado && estadoConhecido && portaoLigado && !iniciando && !pcBloqueado;
    const falhou = el.classList.contains('falhou');
    el.classList.toggle('aberto', aberto);
    el.classList.toggle('fechado', !aberto);
    el.classList.toggle('bloqueado', bloqueado);
    el.classList.toggle('pronto', (portaoConectado && !portaoLigado && !iniciando && !pcBloqueado) || bloqueado);
    el.classList.toggle('procurando', !portaoConectado && !falhou && !iniciando && !pcBloqueado);
    el.classList.toggle('iniciando', iniciando);
    el.classList.toggle('ligando', iniciando && !falhou && boot.fase !== 'bloqueio' && boot.fase !== 'pronto');
    if (rotulo) {
      rotulo.textContent = bloqueado ? 'DESBLOQUEAR' : iniciando ? '···' : portaoConectado ? 'ON' : 'LIGAR';
      rotulo.classList.toggle('longo', bloqueado);
    }
    const botao = document.getElementById('botao-power');
    if (botao) botao.setAttribute('aria-label', bloqueado ? 'Desbloquear o PC com a digital' : 'Ligar o PC');
    const barra = document.getElementById('boot-barra');
    const pct = document.getElementById('boot-pct');
    if (iniciando && barra) barra.style.width = boot.pct.toFixed(1) + '%';
    if (iniciando && pct) pct.textContent = Math.floor(boot.pct) + '%';
    if (aberto || !status || !dica || falhou) return;
    let txt;
    if (iniciando) txt = FASES_BOOT[boot.fase].txt;
    else if (pcBloqueado) txt = ['PC bloqueado', 'toque no botão para desbloquear com a digital'];
    else if (portaoConectado && !estadoConhecido) txt = ['PC conectado', 'conferindo o PC…'];
    else if (portaoConectado) txt = ['PC conectado', 'toque no botão para abrir o painel'];
    else txt = TEXTOS_PC_FORA[pcFora];
    const travado = iniciando && boot.fase === 'entrando' && Date.now() - boot.desde > 60000;
    status.textContent = txt[0];
    dica.textContent = travado ? 'o painel não abriu no PC · rode servidor\\abrir.bat' : txt[1];
  }

  function portaoConexao(conectado) {
    clearTimeout(temporizadorQueda);
    if (conectado) {
      clearTimeout(temporizadorFalha);
      const el = document.getElementById('portao');
      if (el) el.classList.remove('falhou');
      portaoConectado = true;
      pcSaindoDesde = 0;
      esperarVigiaCair = false;
      estadoConhecido = false; // o 1o pacote (atualizarBloqueio) decide: abre, ou fica no "Desbloquear"
      desenharPortao();
    } else if (portaoConectado) {
      // so fecha se a queda durar mais de 4 s (um soluco do Wi-Fi nao fecha a porta)
      temporizadorQueda = setTimeout(() => {
        portaoConectado = false;
        estadoConhecido = false;
        pcBloqueado = false;
        marcarPcFora('fora'); // sumiu sem avisar
        acordarRepouso();
        desenharPortao();
      }, 4000);
    }
  }

  function alternarPainel(ligar) {
    portaoLigado = ligar;
    try { localStorage.setItem('painel_ligado', ligar ? '1' : '0'); } catch (e) {}
    if (navigator.vibrate) { try { navigator.vibrate(ligar ? [30, 40, 60] : 40); } catch (e) {} }
    desenharPortao();
  }

  function mostrarFalhaPortao(titulo, dicaTxt) {
    const el = document.getElementById('portao');
    if (!el) return;
    el.classList.remove('procurando', 'ligando', 'iniciando', 'falhou');
    void el.offsetWidth;
    el.classList.add('falhou');
    const status = document.getElementById('portao-status');
    const dica = document.getElementById('portao-dica');
    if (status) status.textContent = titulo;
    if (dica) dica.textContent = dicaTxt;
    setTimeout(() => { el.classList.remove('falhou'); desenharPortao(); }, 3500);
  }

  function desbloquearComDigital() {
    abrirAppDigital();
    faseBoot('digital', true);
    clearTimeout(temporizadorDigital);
    temporizadorDigital = setTimeout(digitalDesistiu, 60000); // o leitor ficou aberto sem dedo
  }

  // Voltou do app e o PC segue bloqueado: a barra some e o "Desbloquear" volta, com um tremor
  function digitalDesistiu() {
    if (!boot || boot.fase !== 'digital') return;
    if (!pcBloqueado && portaoConectado) return; // desbloqueou: atualizarBloqueio ja cuida
    boot = null;
    mostrarFalhaPortao('Não desbloqueou', 'toque no botão para tentar de novo');
  }

  function inicializarPortao() {
    const botao = document.getElementById('botao-power');
    if (botao) {
      botao.addEventListener('click', () => {
        alternarPainel(true);
        // PC na tela de bloqueio: o toque abre o leitor; ao voltar, a barra corre ate o painel abrir
        if (pcBloqueado || (boot && (boot.fase === 'bloqueio' || boot.fase === 'digital'))) {
          desbloquearComDigital();
          return;
        }
        if (portaoConectado) return;
        // PC dormindo ou desligado: o app de digital manda o Wake-on-LAN e depois pede a digital.
        abrirAppDigital();
        reconectarAgora();
        if (boot) { boot.porToque = true; return; }
        faseBoot('acordando', true);
        const el = document.getElementById('portao');
        clearTimeout(temporizadorFalha);
        temporizadorFalha = setTimeout(() => {
          if (portaoConectado || !el || !boot || boot.fase !== 'acordando') return;
          boot = null;
          mostrarFalhaPortao('O PC não respondeu', 'confira se o PC está ligado e no mesmo Wi-Fi · sigo tentando');
        }, 90000); // acordar da suspensao leva uns segundos; ligar do zero, ate ~1 min
      });
    }
    const portaoEl = document.getElementById('portao');
    if (portaoEl) portaoEl.addEventListener('pointerdown', acordarRepouso);
    const desligar = document.getElementById('botao-desligar');
    if (desligar) desligar.addEventListener('click', () => alternarPainel(false));
    // Voltou do bloqueio ou do segundo plano: procura o PC na hora
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') reconectarAgora();
    });
    window.addEventListener('online', reconectarAgora);
    desenharPortao();
    acordarRepouso();
    consultarVigia();
  }

  function atualizarStatusWs(conectado) {
    const ponto = document.getElementById('ponto-ws');
    if (!ponto) return;
    if (conectado) {
      ponto.className = 'ponto-ws conectado';
      ponto.title = 'WebSocket conectado';
    } else {
      ponto.className = 'ponto-ws desconectado';
      ponto.title = 'WebSocket desconectado';
    }
  }

  // Inicializacao Geral
  window.addEventListener('DOMContentLoaded', () => {
    inicializarIndicadorPaginas();
    inicializarTelaEnergia();
    inicializarTelaMidia();
    inicializarResizeSparklines();
    inicializarApiBateria();
    requisitarWakeLock();
    inicializarPortao();
    carregarAcoes();
    conectarWebSocket();
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    }
  });
})();

// Tela cheia no primeiro toque (esconde barras do Chrome quando nao instalado como PWA)
// No toque, o Chrome so concede "ativacao de usuario" no fim do toque (pointerup), nao no pointerdown.
document.addEventListener('pointerup', () => {
  if (!document.fullscreenElement && document.documentElement.requestFullscreen) {
    document.documentElement.requestFullscreen({ navigationUI: 'hide' }).catch(() => {});
  }
});