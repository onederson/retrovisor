"""Midia tocando no PC (tela Midia do painel), pelos controles de midia do Windows (GSMTC).

Cada app que toca algo (Chrome, Spotify, VLC...) vira uma sessao com titulo, artista, posicao,
miniatura e comandos. Apps em [midia].ignorar (padrao: Brave) ficam de fora.

A WinRT e assincrona: um loop asyncio proprio roda numa thread fixa e guarda o gerenciador de
sessoes; o coletor (1 s) e os comandos vindos do celular so mandam corrotinas para ele.
A miniatura nao vai no WebSocket: fica em cache e sai por /midia/capa (a URL muda com a faixa).
"""
import asyncio
import ctypes
import hashlib
import threading
import time
from datetime import datetime, timezone
from urllib.parse import quote

from .. import janelas

_STATUS = {0: "fechado", 1: "abrindo", 2: "abrindo", 3: "parado", 4: "tocando", 5: "pausado"}
_TICKS_S = 10_000_000  # a WinRT conta tempo em unidades de 100 ns

VELOCIDADES = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
_NAVEGADORES = ("chrome", "msedge", "edge", "opera", "vivaldi", "firefox", "brave")

_loop: asyncio.AbstractEventLoop | None = None
_trava = threading.Lock()
_gerente = None
_capas: dict[str, tuple[str, bytes, str]] = {}  # id -> (versao, bytes, content-type)
_vel: dict[str, float] = {}  # velocidade pedida pelo painel, para apps que nao informam a sua


def _modo_velocidade(aumid: str, nativo: bool) -> str | None:
    """Como mudar a velocidade: 'nativo' (o app aceita pelo Windows), 'navegador' (atalho < > do
    YouTube), 'vlc' (atalhos = [ ]) ou None (o app nao deixa)."""
    if nativo:
        return "nativo"
    nome = _nome_app(aumid).lower()
    if any(n in nome for n in _NAVEGADORES):
        return "navegador"
    if "vlc" in nome:
        return "vlc"
    return None


def _teclas_velocidade(modo: str, v: float) -> str:
    """Sequencia de teclas que leva a velocidade a v a partir de qualquer valor (sem depender do atual)."""
    if modo == "navegador":  # YouTube: < e > andam 0,25x, de 0,25x a 2x; 7x '<' sempre chega no 0,25x
        return "<" * 7 + ">" * round((v - 0.25) / 0.25)
    if modo == "vlc":  # VLC: '=' volta ao 1x; '[' e ']' andam 0,1x
        return "=" + ("]" if v > 1 else "[") * int(abs(v - 1) / 0.1 + 0.01)
    return ""


def _no_loop(coro, limite: float = 5.0):
    """Roda a corrotina no loop da WinRT (criado na primeira chamada) e espera o resultado."""
    global _loop
    with _trava:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            threading.Thread(target=_loop.run_forever, name="midia-winrt", daemon=True).start()
    return asyncio.run_coroutine_threadsafe(coro, _loop).result(limite)


async def _mgr():
    global _gerente
    if _gerente is None:
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as M
        _gerente = await M.request_async()
    return _gerente


def _ignorar(cfg: dict) -> list[str]:
    return [s.lower() for s in cfg.get("midia", {}).get("ignorar", ["brave"])]


def _ignorado(aumid: str, ignorar: list[str]) -> bool:
    a = (aumid or "").lower()
    return any(i in a for i in ignorar)


def _nome_app(aumid: str) -> str:
    """'Spotify.exe' -> 'Spotify'; 'SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify' -> 'Spotify'."""
    nome = (aumid or "?").split("!")[-1]
    nome = nome.rsplit("\\", 1)[-1]
    if nome.lower().endswith(".exe"):
        nome = nome[:-4]
    return nome or "?"


def _posicao(tl, tocando: bool) -> float:
    pos = tl.position.total_seconds()
    if tocando:  # a posicao do Windows e de quando o app avisou; anda o relogio ate agora
        try:
            pos += max(0.0, (datetime.now(timezone.utc) - tl.last_updated_time).total_seconds())
        except Exception:
            pass
    fim = tl.end_time.total_seconds()
    return round(min(pos, fim) if fim > 0 else pos, 1)


async def _ler_capa(ref) -> tuple[bytes, str] | None:
    from winrt.windows.storage.streams import DataReader
    stream = await ref.open_read_async()
    tam = int(stream.size)
    if not tam or tam > 5_000_000:
        return None
    leitor = DataReader(stream.get_input_stream_at(0))
    await leitor.load_async(tam)
    buf = bytearray(tam)
    leitor.read_bytes(buf)
    return bytes(buf), (stream.content_type or "image/png")


def _id_unico(aumid: str, vistos: dict) -> str:
    vistos[aumid] = vistos.get(aumid, 0) + 1
    return aumid if vistos[aumid] == 1 else f"{aumid}#{vistos[aumid]}"


async def _sessoes(ignorar: list[str]) -> list[tuple[str, object]]:
    """[(id, sessao)] dos apps nao ignorados, na ordem do Windows."""
    m = await _mgr()
    vistos: dict = {}
    saida = []
    for s in m.get_sessions():
        aumid = s.source_app_user_model_id
        sid = _id_unico(aumid, vistos)
        if not _ignorado(aumid, ignorar):
            saida.append((sid, s))
    return saida


async def _coletar(ignorar: list[str]) -> dict:
    m = await _mgr()
    lista = []
    vivos = set()
    for sid, s in await _sessoes(ignorar):
        try:
            props = await s.try_get_media_properties_async()
        except Exception:
            continue
        pb = s.get_playback_info()
        tl = s.get_timeline_properties()
        status = _STATUS.get(int(pb.playback_status), "parado")
        tocando = status == "tocando"
        titulo, artista, album = props.title or "", props.artist or "", props.album_title or ""
        versao = hashlib.sha1(f"{titulo}|{artista}|{album}".encode()).hexdigest()[:10]
        capa = None
        if props.thumbnail is not None:
            if _capas.get(sid, ("",))[0] != versao:
                try:
                    lida = await _ler_capa(props.thumbnail)
                    if lida:
                        _capas[sid] = (versao, *lida)
                except Exception:
                    pass  # tenta de novo no proximo ciclo
            if _capas.get(sid, ("",))[0] == versao:
                capa = f"/midia/capa?id={quote(sid, safe='')}&v={versao}"
        vivos.add(sid)
        ctrl = pb.controls
        nativo = bool(ctrl.is_playback_rate_enabled)
        try:
            taxa = float(pb.playback_rate or 0)
        except Exception:
            taxa = 0.0
        vel = taxa if nativo and taxa > 0 else _vel.get(sid, 1.0)
        lista.append({
            "id": sid, "app": _nome_app(s.source_app_user_model_id),
            "titulo": titulo, "artista": artista, "album": album,
            "tocando": tocando, "status": status,
            "posicao_s": _posicao(tl, tocando), "duracao_s": round(tl.end_time.total_seconds(), 1),
            "capa": capa, "pode_seek": bool(ctrl.is_playback_position_enabled),
            "velocidade": round(vel, 2),
            "pode_velocidade": _modo_velocidade(s.source_app_user_model_id, nativo) is not None,
        })
    for sid in list(_capas):
        if sid not in vivos:
            del _capas[sid]
    for sid in list(_vel):
        if sid not in vivos:
            del _vel[sid]
    atual = None
    cur = m.get_current_session()
    if cur is not None and not _ignorado(cur.source_app_user_model_id, ignorar):
        atual = next((x["id"] for x in lista if x["id"].split("#")[0] == cur.source_app_user_model_id), None)
    if atual is None and lista:  # Brave na frente ou nenhuma "atual": a primeira tocando, ou a primeira
        atual = next((x["id"] for x in lista if x["tocando"]), lista[0]["id"])
    return {"sessoes": lista, "atual": atual}


# ---- volume geral do PC (pycaw) ----
def _endpoint():
    import comtypes
    from pycaw.pycaw import AudioUtilities
    comtypes.CoInitialize()
    return AudioUtilities.GetSpeakers().EndpointVolume


def volume() -> dict:
    try:
        ep = _endpoint()
        return {"volume": round(ep.GetMasterVolumeLevelScalar() * 100), "mudo": bool(ep.GetMute())}
    except Exception:
        return {"volume": None, "mudo": None}


def collect(cfg: dict, ctx: dict) -> dict:
    dados = _no_loop(_coletar(_ignorar(cfg)))
    dados.update(volume())
    dados["pular_s"] = int(cfg.get("midia", {}).get("pular_s", 10))
    return dados


def capa(sid: str) -> tuple[bytes, str] | None:
    c = _capas.get(sid)
    return (c[1], c[2]) if c else None


# ---- comandos vindos do celular ----
async def _comando(sid: str | None, cmd: str, valor, ignorar: list[str], pular: int) -> dict:
    sessoes = dict(await _sessoes(ignorar))
    s = sessoes.get(sid) if sid else None
    if s is None:
        if not sessoes:
            return {"ok": False, "msg": "nada tocando"}
        s = next(iter(sessoes.values()))
    if cmd == "alternar":
        ok = await s.try_toggle_play_pause_async()
    elif cmd == "proxima":
        ok = await s.try_skip_next_async()
    elif cmd == "anterior":
        ok = await s.try_skip_previous_async()
    elif cmd in ("avancar", "voltar", "posicao"):
        tl = s.get_timeline_properties()
        tocando = int(s.get_playback_info().playback_status) == 4
        if cmd == "posicao":
            alvo = float(valor)
        else:
            alvo = _posicao(tl, tocando) + (pular if cmd == "avancar" else -pular)
        fim = tl.end_time.total_seconds()
        alvo = max(0.0, min(alvo, fim - 1) if fim > 1 else alvo)
        ok = await s.try_change_playback_position_async(int(alvo * _TICKS_S))
    else:
        return {"ok": False, "msg": "comando desconhecido"}
    return {"ok": bool(ok), "msg": cmd if ok else "o app recusou o comando"}


async def _info(sid: str | None, ignorar: list[str]) -> dict | None:
    """Dados da sessao para achar a janela e decidir como mudar a velocidade."""
    sessoes = await _sessoes(ignorar)
    if not sessoes:
        return None
    sid, s = next(((i, x) for i, x in sessoes if i == sid), sessoes[0])
    try:
        titulo = (await s.try_get_media_properties_async()).title or ""
    except Exception:
        titulo = ""
    return {"id": sid, "aumid": s.source_app_user_model_id or "", "titulo": titulo,
            "nativo": bool(s.get_playback_info().controls.is_playback_rate_enabled)}


async def _taxa_nativa(sid: str, v: float, ignorar: list[str]) -> bool:
    s = dict(await _sessoes(ignorar)).get(sid)
    return bool(s and await s.try_change_playback_rate_async(v))


def _digitar(texto: str, hwnd: int) -> None:
    """Digita caracteres na janela da frente pelo layout dela (no ABNT2 '[' e ']' ficam em outras teclas)."""
    u = ctypes.windll.user32
    u.VkKeyScanExW.restype = ctypes.c_short
    u.VkKeyScanExW.argtypes = [ctypes.c_wchar, ctypes.c_void_p]
    u.GetKeyboardLayout.restype = ctypes.c_void_p
    layout = u.GetKeyboardLayout(u.GetWindowThreadProcessId(hwnd, None))
    for ch in texto:
        r = u.VkKeyScanExW(ch, layout)
        if r == -1:
            continue
        vk, shift = r & 0xFF, bool(r & 0x100)
        if shift:
            u.keybd_event(0x10, 0, 0, 0)
        u.keybd_event(vk, 0, 0, 0)
        u.keybd_event(vk, 0, 2, 0)
        if shift:
            u.keybd_event(0x10, 0, 2, 0)
        time.sleep(0.04)


def _focar(info: dict) -> dict:
    if janelas.focar_midia(info["aumid"], info["titulo"]) is None:
        return {"ok": False, "msg": "não achei a janela do " + _nome_app(info["aumid"])}
    return {"ok": True, "msg": _nome_app(info["aumid"]) + " na frente"}


def _velocidade(info: dict, valor, ignorar: list[str]) -> dict:
    v = min(VELOCIDADES, key=lambda x: abs(x - float(valor)))
    modo = _modo_velocidade(info["aumid"], info["nativo"])
    if modo is None:
        return {"ok": False, "msg": f"o {_nome_app(info['aumid'])} não deixa mudar a velocidade"}
    if modo == "nativo":
        if not _no_loop(_taxa_nativa(info["id"], v, ignorar)):
            return {"ok": False, "msg": "o app recusou a velocidade"}
    else:
        # Sem controle pelo Windows: atalho de teclado na janela do app, e devolve o foco depois.
        antes = janelas.janela_da_frente()
        hwnd = janelas.focar_midia(info["aumid"], info["titulo"])
        if hwnd is None:
            return {"ok": False, "msg": "não achei a janela do " + _nome_app(info["aumid"])}
        time.sleep(0.3)
        _digitar(_teclas_velocidade(modo, v), hwnd)
        if antes and antes != hwnd:
            time.sleep(0.1)
            janelas.trazer_para_frente(antes)
    _vel[info["id"]] = v
    return {"ok": True, "msg": f"velocidade {v:g}x"}


def comando(cfg: dict, cmd: str, sid: str | None, valor=None) -> dict:
    try:
        if cmd in ("focar", "velocidade"):
            ignorar = _ignorar(cfg)
            info = _no_loop(_info(sid, ignorar))
            if info is None:
                return {"ok": False, "msg": "nada tocando"}
            return _focar(info) if cmd == "focar" else _velocidade(info, valor, ignorar)
        if cmd == "volume":
            v = max(0, min(100, int(float(valor))))
            ep = _endpoint()
            ep.SetMasterVolumeLevelScalar(v / 100, None)
            if v > 0 and ep.GetMute():
                ep.SetMute(0, None)
            return {"ok": True, "msg": f"volume {v}%"}
        if cmd == "mudo":
            ep = _endpoint()
            novo = not ep.GetMute()
            ep.SetMute(int(novo), None)
            return {"ok": True, "msg": "som mudo" if novo else "som ligado"}
        pular = int(cfg.get("midia", {}).get("pular_s", 10))
        return _no_loop(_comando(sid, cmd, valor, _ignorar(cfg), pular))
    except Exception as e:
        return {"ok": False, "msg": str(e)[:200]}
