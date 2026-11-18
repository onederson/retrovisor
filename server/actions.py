import ctypes
import os
import re
import subprocess
import threading
import time
from ctypes import POINTER, cast
from pathlib import Path
from typing import Callable

import comtypes
from comtypes import CLSCTX_ALL
import httpx
import psutil
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

from . import janelas, telas
from .config import RAIZ, caminho
from .celular_adb import PACOTE_DIGITAL, PACOTE_FULLY, pc_bloqueado as _pc_bloqueado, abrir_no_celular as _abrir_no_celular

KEYEVENTF_KEYUP = 2


def _teclas(*vks: int) -> None:
    user32 = getattr(getattr(ctypes, "windll", None), "user32", None)
    if user32:
        for vk in vks:
            user32.keybd_event(vk, 0, 0, 0)
        for vk in reversed(vks):
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def _acao_ollama_ejetar(cfg: dict, hub) -> dict:
    url = cfg.get("ollama", {}).get("url", "http://localhost:11434").rstrip("/")
    resp = httpx.get(f"{url}/api/ps", timeout=10)
    resp.raise_for_status()
    dados = resp.json()
    modelos = dados.get("models", [])
    for item in modelos:
        nome = item if isinstance(item, str) else (item.get("name") or item.get("model"))
        if nome:
            r_post = httpx.post(
                f"{url}/api/generate",
                json={"model": nome, "keep_alive": 0},
                timeout=10,
            )
            r_post.raise_for_status()
    return {"ok": True, "msg": f"{len(modelos)} modelo(s) descarregado(s)"}


_DESANEXADO = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
_PROGRAMAS = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"


def _exe(cfg: dict, servico: str, padrao: Path) -> Path:
    escolhido = cfg.get(servico, {}).get("app")
    exe = Path(escolhido).expanduser() if escolhido else padrao
    if not exe.exists():
        raise RuntimeError(f"{exe.name} nao encontrado")
    return exe


def _abrir_app(exe: Path, *args: str) -> None:
    # Abre como se fosse pelo menu Iniciar, sem cmd no meio.
    subprocess.Popen([str(exe), *args], cwd=str(exe.parent), creationflags=_DESANEXADO,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _fechar_janela_quando_abrir(nome_exe: str, limite_s: float = 30) -> None:
    """Espera a janela do app aparecer e manda WM_CLOSE (o X): o app segue rodando na bandeja."""
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _visiveis() -> list:
        pids = {p.pid for p in psutil.process_iter(["name"]) if (p.info.get("name") or "").lower() == nome_exe}
        achadas = []

        def _cb(h, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if pid.value in pids and user32.IsWindowVisible(h) and user32.GetWindowTextLengthW(h):
                achadas.append(h)
            return True
        user32.EnumWindows(WNDENUMPROC(_cb), 0)
        return achadas

    def _vigiar():
        fim = time.time() + limite_s
        while time.time() < fim:
            janelas = _visiveis()
            if janelas:
                time.sleep(0.5)  # deixa a janela terminar de montar antes de fechar
                for h in _visiveis():
                    user32.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE
                return
            time.sleep(0.3)
    threading.Thread(target=_vigiar, daemon=True).start()


def _matar_por_nome(prefixo: str) -> int:
    n = 0
    for p in psutil.process_iter(["name"]):
        nome = (p.info.get("name") or "").lower()
        if nome.startswith(prefixo):
            try:
                p.kill()
                n += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    return n


def _matar_por_porta(porta: int) -> int:
    pids = {c.pid for c in psutil.net_connections("tcp")
            if c.laddr and c.laddr.port == porta and c.status == psutil.CONN_LISTEN and c.pid}
    for pid in pids:
        try:
            for filho in psutil.Process(pid).children(recursive=True):
                filho.kill()
            psutil.Process(pid).kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return len(pids)


def _criar_acao_servico(servico: str, ligar: bool) -> Callable[[dict, object], dict]:
    def _acao(cfg: dict, hub) -> dict:
        if os.environ.get("PAINEL_SO_VALIDAR") == "1":
            return {"ok": True, "msg": f"(ensaio) {servico} {'ligar' if ligar else 'desligar'}"}
        if servico == "ollama":
            if ligar:
                # App da bandeja (o mesmo do autostart); ele sobe o "ollama serve" sozinho.
                _abrir_app(_exe(cfg, "ollama", _PROGRAMAS / "Ollama" / "ollama app.exe"))
                # O app novo abre uma janela e nao tem opcao de iniciar escondido: fecha no X, fica na bandeja.
                _fechar_janela_quando_abrir("ollama app.exe")
                return {"ok": True, "msg": "Ollama iniciando"}
            n = _matar_por_nome("ollama")  # ollama app.exe, ollama.exe e os runners
            return {"ok": True, "msg": f"Ollama desligado ({n} processo(s))" if n else "Ollama ja estava parado"}
        # OmniRoute: aplicativo do PC (Electron), que roda o proprio servidor na porta do config
        url = cfg.get("omniroute", {}).get("url", "http://127.0.0.1:20128")
        porta = int(url.rstrip("/").rsplit(":", 1)[-1])
        if ligar:
            # --hidden: o app sobe so com o icone na bandeja (mesmo modo do "iniciar com o Windows")
            _abrir_app(_exe(cfg, "omniroute", _PROGRAMAS / "OmniRoute" / "OmniRoute.exe"), "--hidden")
            return {"ok": True, "msg": "OmniRoute iniciando"}
        n = _matar_por_nome("omniroute")
        _matar_por_porta(porta)  # sobra de uma copia aberta pelo terminal (omniroute serve)
        return {"ok": True, "msg": "OmniRoute desligado" if n else "OmniRoute fechado"}
    return _acao


def _acao_omniroute_perfil(cfg: dict, hub) -> dict:
    return {"ok": False, "msg": "ainda nao configurado"}


def _acao_abrir_ia(cfg: dict, hub) -> dict:
    terminal = cfg.get("acoes", {}).get("terminal", "wt.exe")
    git_repo = Path(cfg.get("acoes", {}).get("git_repo", "~/Desktop/Projetos")).expanduser()
    subprocess.Popen([terminal, "-d", str(git_repo)])
    return {"ok": True, "msg": "terminal aberto"}


def _acao_sessao_reset(cfg: dict, hub) -> dict:
    iso = hub.reset_sessao()
    return {"ok": True, "msg": "sessao reiniciada", "estado": {"sessao_inicio": iso}}


def _acao_terminal_wsl(cfg: dict, hub) -> dict:
    terminal = cfg.get("acoes", {}).get("terminal", "wt.exe")
    subprocess.Popen([terminal, "wsl.exe"])
    return {"ok": True, "msg": "wsl aberto"}


def _acao_git_status(cfg: dict, hub) -> dict:
    git_repo = Path(cfg.get("acoes", {}).get("git_repo", "~/Desktop/Projetos")).expanduser()
    proc = subprocess.run(
        ["git", "-C", str(git_repo), "status", "-sb"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode == 0:
        linhas = proc.stdout.splitlines()[:6]
        return {"ok": True, "msg": "\n".join(linhas)}
    texto = proc.stderr if proc.stderr else proc.stdout
    linhas = texto.splitlines()[:6]
    return {"ok": False, "msg": "\n".join(linhas)}


def _acao_liberar_portas(cfg: dict, hub) -> dict:
    portas_dev = set(cfg.get("acoes", {}).get("portas_dev", []))
    meu_pid = os.getpid()
    encerrados = []
    pids_encerrados = set()
    for conn in psutil.net_connections(kind="inet"):
        status = getattr(conn, "status", "")
        if status == "LISTEN" or status == getattr(psutil, "CONN_LISTEN", "LISTEN"):
            if conn.laddr and conn.laddr.port in portas_dev:
                pid = conn.pid
                if pid and pid != meu_pid and pid not in pids_encerrados:
                    try:
                        p = psutil.Process(pid)
                        nome = p.name()
                        nome_lower = nome.lower()
                        if "node" in nome_lower or "python" in nome_lower:
                            p.terminate()
                            pids_encerrados.add(pid)
                            encerrados.append(f"{conn.laddr.port}:{nome}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
    if encerrados:
        msg = f"{len(encerrados)} processo(s) encerrado(s): {', '.join(encerrados)}"
    else:
        msg = "0 processo(s) encerrado(s)"
    return {"ok": True, "msg": msg}


def _acao_print(cfg: dict, hub) -> dict:
    _teclas(0x5B, 0x10, 0x53)
    return {"ok": True, "msg": "print acionado"}


def _acao_mic_mute(cfg: dict, hub) -> dict:
    comtypes.CoInitialize()
    try:
        mic = AudioUtilities.GetMicrophone()
        if not mic:
            return {"ok": False, "msg": "sem microfone"}
        interface = mic.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        endpoint = cast(interface, POINTER(IAudioEndpointVolume))
        mudo = bool(endpoint.GetMute())
        novo_mudo = not mudo
        endpoint.SetMute(novo_mudo, None)
        return {
            "ok": True,
            "msg": "microfone mutado" if novo_mudo else "microfone desmutado",
            "estado": {"mic_mudo": novo_mudo},
        }
    finally:
        comtypes.CoUninitialize()


def _acao_media_play(cfg: dict, hub) -> dict:
    _teclas(0xB3)
    return {"ok": True, "msg": "play/pause"}


def _acao_vol_down(cfg: dict, hub) -> dict:
    _teclas(0xAE)
    return {"ok": True, "msg": "volume diminuido"}


def _acao_vol_up(cfg: dict, hub) -> dict:
    _teclas(0xAF)
    return {"ok": True, "msg": "volume aumentado"}


def _criar_acao_ollama_load(nome_modelo: str) -> Callable[[dict, object], dict]:
    def _acao(cfg: dict, hub) -> dict:
        url = cfg.get("ollama", {}).get("url", "http://localhost:11434").rstrip("/")
        resp = httpx.post(
            f"{url}/api/generate",
            json={"model": nome_modelo, "keep_alive": "30m"},
            timeout=120,
        )
        resp.raise_for_status()
        return {"ok": True, "msg": f"{nome_modelo} carregado"}

    return _acao


def _bloquear_e_apagar_pc() -> None:
    """Como o botao de energia do Android: bloqueia o Windows e desliga os monitores (acendem com mouse/teclado)."""
    user32 = ctypes.windll.user32
    user32.LockWorkStation()
    time.sleep(1.5)  # a tela de bloqueio acende os monitores; apaga depois dela
    HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, DESLIGADO = 0xFFFF, 0x0112, 0xF170, 2
    user32.PostMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, DESLIGADO)


def _acao_acender_video(cfg: dict, hub) -> dict:
    """Video apagado por inatividade (PC desbloqueado): um mexer de mouse invisivel acende os monitores."""
    if os.environ.get("PAINEL_SO_VALIDAR") == "1":
        return {"ok": True, "msg": "(ensaio) acender vídeo"}
    user32 = ctypes.windll.user32
    MOUSEEVENTF_MOVE, ES_DISPLAY_REQUIRED = 0x0001, 0x00000002
    user32.mouse_event(MOUSEEVENTF_MOVE, 1, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_MOVE, -1, 0, 0, 0)  # volta o ponteiro para onde estava
    ctypes.windll.kernel32.SetThreadExecutionState(ES_DISPLAY_REQUIRED)
    return {"ok": True, "msg": "acendendo o vídeo"}


def _acao_tela_apagar(cfg: dict, hub) -> dict:
    if os.environ.get("PAINEL_SO_VALIDAR") != "1":  # testes: nao bloqueia o PC
        threading.Timer(1.0, _bloquear_e_apagar_pc).start()
    try:
        adb = str(caminho(cfg, "adb"))
        res = subprocess.run(
            [adb, "shell", "input", "keyevent", "223"],
            capture_output=True,
            timeout=8,
        )
        if res.returncode != 0:
            return {"ok": True, "msg": "apague pelo painel"}
        return {"ok": True, "msg": "tela apagada"}
    except Exception:
        return {"ok": True, "msg": "apague pelo painel"}


def _acao_discord(cfg: dict, hub) -> dict:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    update = Path(cfg.get("acoes", {}).get("discord", local / "Discord" / "Update.exe")).expanduser()
    if not update.exists():
        return {"ok": False, "msg": "Discord nao encontrado"}
    # Janela aberta: vem para a frente de tudo. Fechado ou so na bandeja: abre e depois traz para a frente.
    # Ja na frente: volta para os icones ocultos (alterna).
    res = janelas.focar_ou_abrir({"discord.exe"},
                                 lambda: subprocess.Popen([str(update), "--processStart", "Discord.exe"]),
                                 alternar=True)
    return {"ok": res["ok"], "msg": f"Discord {res['msg']}"}


def _acao_rocket_league(cfg: dict, hub) -> dict:
    uri = cfg.get("acoes", {}).get("rocket_league", "steam://rungameid/252950")
    res = janelas.focar_ou_abrir({"rocketleague.exe"}, lambda: os.startfile(uri), espera_s=4)
    return {"ok": res["ok"], "msg": f"Rocket League {res['msg']}"}


def _arquivo_slot(cfg: dict) -> Path:
    try:
        return caminho(cfg, "cache") / "app_slot.json"
    except KeyError:
        return RAIZ / "cache" / "app_slot.json"


def _acao_app_livre(cfg: dict, hub) -> dict:
    nome = janelas.ler_slot(_arquivo_slot(cfg))
    if not nome:
        return {"ok": False, "msg": "segure a tecla para escolher o app"}
    atalho = janelas.catalogo().get(nome)
    if atalho is None:
        return {"ok": False, "msg": f"{nome} sumiu do Menu Iniciar: segure para trocar"}
    exe = janelas.exe_do_atalho(atalho)
    if not exe:  # .url (ex.: jogo da Steam): so abre
        os.startfile(str(atalho))
        return {"ok": True, "msg": f"{nome} abrindo"}
    res = janelas.focar_ou_abrir({exe}, lambda: os.startfile(str(atalho)), espera_s=6)
    return {"ok": res["ok"], "msg": f"{nome} {res['msg']}"}


def escolher_app(cfg: dict, nome: str) -> dict:
    """Grava o app da tecla livre. So aceita um nome que exista no Menu Iniciar."""
    if nome not in janelas.catalogo():
        return {"ok": False, "msg": "app nao encontrado no Menu Iniciar"}
    janelas.gravar_slot(_arquivo_slot(cfg), nome)
    return {"ok": True, "msg": f"tecla agora abre {nome}"}


def listar_apps() -> list[str]:
    return list(janelas.catalogo().keys())


def _monitores() -> list[dict]:
    try:
        return telas.listar()
    except Exception:
        return []


def _acao_so_tela(indice: int) -> Callable[[dict, object], dict]:
    def _acao(cfg: dict, hub) -> dict:
        # PAINEL_SO_VALIDAR=1: ensaio (testes no aparelho), o Windows so valida e nao troca nada
        return telas.so_tela(indice, so_validar=os.environ.get("PAINEL_SO_VALIDAR") == "1")
    return _acao


def _criar_acao_tela(modo: str, msg: str) -> Callable[[dict, object], dict]:
    """DisplaySwitch.exe do Windows: /internal = so a tela principal, /clone = duplicar, /extend = estender."""
    def _acao(cfg: dict, hub) -> dict:
        subprocess.Popen([str(Path(os.environ.get("WINDIR", "C:/Windows")) / "System32" / "DisplaySwitch.exe"), f"/{modo}"])
        return {"ok": True, "msg": msg}

    return _acao




def _acao_desbloquear_pc(cfg: dict, hub) -> dict:
    """Reserva: abre o Remote Fingerprint Unlock pelo adb. O painel abre pelo link intent."""
    if not _abrir_no_celular(cfg, PACOTE_DIGITAL):
        return {"ok": False, "msg": "adb sem conexão: abra o app de digital na mão"}
    return _acao_voltar_painel(cfg, hub)


def _acao_voltar_painel(cfg: dict, hub) -> dict:
    """Quando o PC desbloquear, traz o Fully (painel) de volta para a frente. Depende do adb (melhor esforço)."""
    def voltar_ao_painel():
        for _ in range(120):  # ate 2 min esperando a digital
            time.sleep(1)
            if not _pc_bloqueado():
                time.sleep(1)
                _abrir_no_celular(cfg, PACOTE_FULLY)
                return

    threading.Thread(target=voltar_ao_painel, daemon=True).start()
    return {"ok": True, "msg": "encoste o dedo no leitor"}


# Tela de energia. Espera 2 s antes de agir: a resposta HTTP chega ao celular antes de o PC parar.
ENERGIA = {
    "suspender": (["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], "PC suspenso"),  # sem hibernacao = S3
    "desligar": (["shutdown.exe", "/s", "/t", "0"], "desligando o PC"),
    "reiniciar": (["shutdown.exe", "/r", "/t", "0"], "reiniciando o PC"),
}


def _criar_acao_energia(modo: str) -> Callable[[dict, object], dict]:
    def _acao(cfg: dict, hub) -> dict:
        if os.environ.get("PAINEL_SO_VALIDAR") == "1":  # testes: nao desliga nada
            return {"ok": True, "msg": f"(ensaio) {modo}"}
        if modo == "bloquear":
            threading.Timer(1.0, lambda: ctypes.windll.user32.LockWorkStation()).start()
            return {"ok": True, "msg": "PC bloqueado"}
        cmd, msg = ENERGIA[modo]
        threading.Timer(2.0, lambda: subprocess.Popen(cmd)).start()
        return {"ok": True, "msg": msg}
    return _acao


def _acao_gerenciador(cfg: dict, hub) -> dict:
    os.startfile("taskmgr.exe")
    return {"ok": True, "msg": "Gerenciador de Tarefas aberto"}


def _criar_acao_teclas(msg: str, *vks: int) -> Callable[[dict, object], dict]:
    def _acao(cfg: dict, hub) -> dict:
        _teclas(*vks)
        return {"ok": True, "msg": msg}
    return _acao


def _acao_explorador(cfg: dict, hub) -> dict:
    subprocess.Popen(["explorer.exe"])  # sempre uma janela nova, como Win+E
    return {"ok": True, "msg": "Explorador de Arquivos aberto"}


# Tela Apps: rotulo = (nome no Menu Iniciar, exe(s) da janela). O [apps] do config.toml substitui esta lista.
APPS_PADRAO: dict[str, dict] = {
    "Brave": {"menu": "Brave", "exe": "brave.exe"},
    "Steam": {"menu": "Steam", "exe": "steamwebhelper.exe"},
    "Epic Games": {"menu": "Epic Games Launcher", "exe": "EpicGamesLauncher.exe"},
    "VS Code": {"menu": "Visual Studio Code", "exe": "Code.exe"},
    "OBS": {"menu": "OBS Studio", "exe": "obs64.exe"},
    "Telegram": {"menu": "Telegram", "exe": "Telegram.exe"},
    "Obsidian": {"menu": "Obsidian", "exe": "Obsidian.exe"},
    "VLC": {"menu": "VLC media player", "exe": "vlc.exe"},
}


def _criar_acao_app(rotulo: str, menu: str, exes: set[str]) -> Callable[[dict, object], dict]:
    """Abre pelo atalho do Menu Iniciar; se ja estiver aberto, traz a janela para a frente."""
    def _acao(cfg: dict, hub) -> dict:
        atalho = janelas.catalogo().get(menu)
        if atalho is None:
            return {"ok": False, "msg": f"{rotulo} não está no Menu Iniciar"}
        if not exes:
            os.startfile(str(atalho))
            return {"ok": True, "msg": f"{rotulo} abrindo"}
        res = janelas.focar_ou_abrir(exes, lambda: os.startfile(str(atalho)), espera_s=8)
        return {"ok": res["ok"], "msg": f"{rotulo} {res['msg']}"}
    return _acao


def _apps(cfg: dict) -> dict[str, tuple[str, str, set[str]]]:
    """{id: (rotulo, menu, exes)} na ordem do config."""
    apps = {}
    for rotulo, dados in (cfg.get("apps") or APPS_PADRAO).items():
        slug = re.sub(r"[^a-z0-9]", "", rotulo.lower())
        exe = dados.get("exe", [])
        exes = {exe} if isinstance(exe, str) else set(exe)
        apps[f"app_{slug}"] = (rotulo, dados.get("menu", rotulo), {e.lower() for e in exes if e})
    return apps


# id: (rotulo, descricao, tela, funcao, ativo).
# Tela 2 = Windows (4x3), 4 = Apps (4x3), 3 = topo da tela Modelos, 0 = oculta.
def _registro(cfg: dict) -> dict[str, tuple[str, str, int, Callable, bool]]:
    reg: dict[str, tuple[str, str, int, Callable, bool]] = {
        # Tela Windows
        "tela_so": ("Só tela", "arraste ↕ p/ escolher", 2, None, True),
        "tela_duplicar": ("Duplicar", "espelha nas duas telas", 2, _criar_acao_tela("clone", "telas duplicadas"), True),
        "tela_estender": ("Estender", "área de trabalho nas duas", 2, _criar_acao_tela("extend", "telas estendidas"), True),
        "area_trabalho": ("Área de trabalho", "minimiza tudo (Win+D)", 2,
                          _criar_acao_teclas("área de trabalho", 0x5B, 0x44), True),
        "media_play": ("Play/Pause", "música ou vídeo", 2, _acao_media_play, True),
        "media_proxima": ("Próxima", "pula a faixa", 2, _criar_acao_teclas("próxima faixa", 0xB0), True),
        "vol_down": ("Volume −", "abaixa o som do PC", 2, _acao_vol_down, True),
        "vol_up": ("Volume +", "aumenta o som do PC", 2, _acao_vol_up, True),
        "som_mudo": ("Mudo", "liga / desliga o som", 2, _criar_acao_teclas("som alternado", 0xAD), True),
        "mic_mute": ("Microfone", "liga / desliga o mic", 2, _acao_mic_mute, True),
        "print": ("Print", "recortar a tela", 2, _acao_print, True),
        "gerenciador": ("Tarefas", "Gerenciador de Tarefas", 2, _acao_gerenciador, True),
        # Tela Apps
        "discord": ("Discord", "traz pra frente", 4, _acao_discord, True),
        "rocket_league": ("Rocket League", "abre ou traz pra frente", 4, _acao_rocket_league, True),
        "explorador": ("Arquivos", "Explorador de Arquivos", 4, _acao_explorador, True),
    }
    for acao_id, (rotulo, menu, exes) in _apps(cfg).items():
        reg.setdefault(acao_id, (rotulo, "abre ou traz pra frente", 4, _criar_acao_app(rotulo, menu, exes), True))
    reg["app_livre"] = (janelas.ler_slot(_arquivo_slot(cfg)) or "Escolher app", "segure p/ trocar", 4,
                        _acao_app_livre, True)
    modelos = cfg.get("ollama", {}).get("modelos", {})
    for rotulo, nome in modelos.items():
        slug = re.sub(r"[^a-z0-9]", "", rotulo.lower())
        reg[f"ollama_load_{slug}"] = (f"Carregar {rotulo}", "pré-carrega na GPU", 3,
                                      _criar_acao_ollama_load(nome), True)
    reg["ollama_ejetar"] = ("Liberar GPU", "esvazia a VRAM", 3, _acao_ollama_ejetar, True)
    reg["sessao_reset"] = ("Zerar sessão", "zera tokens/custo", 3, _acao_sessao_reset, True)
    reg["liberar_portas"] = ("Liberar portas", "fecha servidores dev", 3, _acao_liberar_portas, True)
    reg["tela_apagar"] = ("Apagar tela", "toque p/ acender", 3, _acao_tela_apagar, True)
    reg["omniroute_perfil"] = ("Perfil Omni", "", 0, _acao_omniroute_perfil, False)
    for servico in ("ollama", "omniroute"):
        reg[f"{servico}_ligar"] = ("Ligar", "", 0, _criar_acao_servico(servico, True), True)
        reg[f"{servico}_desligar"] = ("Desligar", "", 0, _criar_acao_servico(servico, False), True)
    reg["terminal_wsl"] = ("WSL", "terminal Linux", 0, _acao_terminal_wsl, True)
    reg["abrir_ia"] = ("Terminal", "abre na pasta do projeto", 0, _acao_abrir_ia, True)
    reg["git_status"] = ("Git", "o que mudou no projeto", 0, _acao_git_status, True)
    reg["desbloquear_pc"] = ("Desbloquear PC", "digital no celular", 0, _acao_desbloquear_pc, True)
    reg["voltar_painel"] = ("Voltar ao painel", "", 0, _acao_voltar_painel, True)
    reg["acender_video"] = ("Acender vídeo", "", 0, _acao_acender_video, True)
    for modo in ("suspender", "desligar", "reiniciar", "bloquear"):
        reg[f"energia_{modo}"] = (modo.capitalize(), "", 0, _criar_acao_energia(modo), True)
    return reg


def listar(cfg: dict) -> list[dict]:
    reg = _registro(cfg)
    lista = []
    for acao_id, (rotulo, desc, tela, _fn, ativo) in reg.items():
        if not tela:
            continue
        item = {"id": acao_id, "rotulo": rotulo, "descricao": desc, "tela": tela, "ativo": ativo}
        if acao_id == "tela_so":  # uma opcao por monitor; o celular troca arrastando a tecla
            item["opcoes"] = [
                {"id": f"tela_so_{m['indice']}", "rotulo": f"Só tela {m['indice'] + 1}",
                 "descricao": m["nome"] + ("" if m["ativo"] else " · desligada")}
                for m in _monitores()
            ]
        if acao_id == "app_livre":
            item["escolhivel"] = True
        lista.append(item)
    return lista


def executar(acao_id: str, cfg: dict, hub) -> dict:
    reg = _registro(cfg)
    m = re.fullmatch(r"tela_so_(\d{1,2})", acao_id)
    if m:
        reg[acao_id] = ("", "", 0, _acao_so_tela(int(m.group(1))), True)
    if acao_id not in reg or reg[acao_id][3] is None:
        return {"ok": False, "msg": "acao desconhecida"}
    _rotulo, _desc, _tela, fn, _ativo = reg[acao_id]
    try:
        return fn(cfg, hub)
    except Exception as e:
        return {"ok": False, "msg": str(e)[:200]}
