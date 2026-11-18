"""Trazer um programa para a frente (abrindo se preciso) e catalogo de apps do Menu Iniciar.

O celular nunca manda caminho nem comando: so escolhe um NOME da lista do Menu Iniciar,
que o servidor resolve de novo na hora de abrir.
"""
import ctypes
import json
import os
import time
from ctypes import wintypes
from pathlib import Path

SW_RESTORE = 9
SW_SHOW = 5
WM_SYSCOMMAND = 0x0112
SC_CLOSE = 0xF060
VK_MENU = 0x12
KEYEVENTF_KEYUP = 2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


_USER32 = None


def _u32():
    global _USER32
    if _USER32 is None:
        u = ctypes.WinDLL("user32", use_last_error=True)
        u.GetForegroundWindow.restype = wintypes.HWND
        u.GetWindow.restype = wintypes.HWND
        u.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
        _USER32 = u
    return _USER32


def _exe_do_processo(pid: int) -> str:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = wintypes.DWORD(len(buf))
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        k32.CloseHandle(h)


def janelas_do_programa(exes: set[str]) -> list[int]:
    """Janelas visiveis, com titulo e sem dono (as "principais") dos executaveis pedidos."""
    u = _u32()
    achadas: list[int] = []
    PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cada(hwnd, _):
        if not u.IsWindowVisible(hwnd) or u.GetWindow(hwnd, 4):  # 4 = GW_OWNER
            return True
        if u.GetWindowTextLengthW(hwnd) == 0:
            return True
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if _exe_do_processo(pid.value) in exes:
            achadas.append(hwnd)
        return True

    u.EnumWindows(PROC(cada), 0)
    return achadas


def _programa_na_frente(exes: set[str]) -> bool:
    u = _u32()
    fg = u.GetForegroundWindow()
    if not fg or u.IsIconic(fg):
        return False
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(fg, ctypes.byref(pid))
    return _exe_do_processo(pid.value) in exes


def trazer_para_frente(hwnd: int) -> bool:
    u = _u32()
    if u.GetForegroundWindow() == hwnd and not u.IsIconic(hwnd):
        return True
    u.ShowWindow(hwnd, SW_RESTORE if u.IsIconic(hwnd) else SW_SHOW)
    # O Windows so deixa trocar a janela da frente se o processo acabou de receber entrada:
    # um ALT sintetico libera (truque classico, nao digita nada).
    u.keybd_event(VK_MENU, 0, 0, 0)
    u.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    u.BringWindowToTop(hwnd)
    ok = bool(u.SetForegroundWindow(hwnd))
    return ok and u.GetForegroundWindow() == hwnd


def _aumid_do_processo(pid: int) -> str:
    """AppUserModelID de um app empacotado (Loja/UWP/WinUI); '' para programa comum."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        n = ctypes.c_uint32(512)
        buf = ctypes.create_unicode_buffer(512)
        return buf.value if k32.GetApplicationUserModelId(h, ctypes.byref(n), buf) == 0 else ""
    except Exception:
        return ""
    finally:
        k32.CloseHandle(h)


def _janelas_principais() -> list[tuple[int, str, str, str]]:
    """[(hwnd, exe, aumid, titulo)] das janelas visiveis com titulo, na ordem da frente para tras.

    Janela de app UWP e do ApplicationFrameHost: o processo de verdade esta na janela filha.
    """
    u = _u32()
    PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    saida = []

    def cada(hwnd, _):
        if not u.IsWindowVisible(hwnd) or u.GetWindow(hwnd, 4):  # 4 = GW_OWNER
            return True
        tam = u.GetWindowTextLengthW(hwnd)
        if tam == 0:
            return True
        buf = ctypes.create_unicode_buffer(tam + 1)
        u.GetWindowTextW(hwnd, buf, tam + 1)
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe = _exe_do_processo(pid.value)
        if exe == "applicationframehost.exe":
            filhos = []

            def filho(h, _):
                p = wintypes.DWORD()
                u.GetWindowThreadProcessId(h, ctypes.byref(p))
                if p.value != pid.value:
                    filhos.append(p.value)
                    return False
                return True

            u.EnumChildWindows(hwnd, PROC(filho), 0)
            if filhos:
                pid = wintypes.DWORD(filhos[0])
                exe = _exe_do_processo(pid.value)
        saida.append((hwnd, exe, _aumid_do_processo(pid.value), buf.value))
        return True

    u.EnumWindows(PROC(cada), 0)
    return saida


def escolher_janela_midia(janelas: list[tuple[int, str, str, str]], aumid: str, titulo: str) -> int | None:
    """Melhor janela para a sessao de midia: mesmo AUMID > mesmo executavel; titulo da faixa desempata.

    'Chrome' -> chrome.exe, 'MSEdge' -> msedge.exe, 'vlc.exe' -> vlc.exe,
    'Microsoft.ZuneMusic_...!Microsoft.ZuneMusic' -> processo empacotado com esse AUMID.
    Sem nada do app, uma janela com o titulo da faixa no nome (ex.: Firefox, que usa AUMID em hash).
    """
    a = (aumid or "").lower()
    base = a.split("!")[-1].rsplit("\\", 1)[-1]
    exes = {base, base + ".exe", base.split(".")[0] + ".exe"}
    t = (titulo or "").strip().lower()[:40]
    melhor, nota_melhor = None, 0
    for hwnd, exe, app_id, nome in janelas:
        nota = 0
        if a and app_id and app_id.lower() == a:
            nota = 4
        elif exe and exe.lower() in exes:
            nota = 2
        if t and t in nome.lower():
            nota += 1
        if nota > nota_melhor:
            melhor, nota_melhor = hwnd, nota
    return melhor


def focar_midia(aumid: str, titulo: str) -> int | None:
    """Traz para a frente a janela que esta tocando; devolve o hwnd (ou None se nao achou)."""
    hwnd = escolher_janela_midia(_janelas_principais(), aumid, titulo)
    if hwnd is None:
        return None
    trazer_para_frente(hwnd)
    return hwnd


def janela_da_frente() -> int:
    return _u32().GetForegroundWindow() or 0


def mandar_para_bandeja(exes: set[str]) -> None:
    """Fecha as janelas como o botao X: apps como o Discord vao para os icones ocultos."""
    u = _u32()
    for h in janelas_do_programa(exes):
        u.PostMessageW(h, WM_SYSCOMMAND, SC_CLOSE, 0)


def focar_ou_abrir(exes: set[str], abrir, espera_s: float = 12.0, alternar: bool = False) -> dict:
    """Traz a janela do programa para a frente; se nao houver janela, chama abrir() e espera ela aparecer.

    alternar=True: se o programa ja estiver na frente, manda ele para a bandeja (como o X).
    """
    exes = {e.lower() for e in exes}
    if _programa_na_frente(exes):
        if alternar:
            mandar_para_bandeja(exes)
            return {"ok": True, "msg": "escondido"}
        return {"ok": True, "msg": "ja esta na frente"}
    for h in janelas_do_programa(exes):
        if trazer_para_frente(h):
            return {"ok": True, "msg": "trazido para a frente"}
    abrir()
    fim = time.monotonic() + espera_s
    while time.monotonic() < fim:
        time.sleep(0.5)
        for h in janelas_do_programa(exes):
            trazer_para_frente(h)
            return {"ok": True, "msg": "aberto"}
    return {"ok": True, "msg": "abrindo…"}  # jogos demoram: segue abrindo sozinho


# ---------- Catalogo do Menu Iniciar ----------
_PASTAS_MENU = [
    Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / r"Microsoft\Windows\Start Menu\Programs",
    Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs",
]
_IGNORAR = ("uninstall", "desinstalar", "readme", "leia-me", "help", "ajuda", "website", "manual",
            "add a new", "application verifier", "administrative tools", "debuggable", "component services")


def catalogo() -> dict[str, Path]:
    """{nome: atalho} de todos os .lnk/.url do Menu Iniciar (jogos da Steam viram .url)."""
    itens: dict[str, Path] = {}
    for pasta in _PASTAS_MENU:
        if not pasta.exists():
            continue
        for arq in pasta.rglob("*"):
            if arq.suffix.lower() not in (".lnk", ".url"):
                continue
            nome = arq.stem
            if any(p in nome.lower() for p in _IGNORAR):
                continue
            itens.setdefault(nome, arq)
    return dict(sorted(itens.items(), key=lambda kv: kv[0].lower()))


def exe_do_atalho(atalho: Path) -> str:
    """Executavel por tras de um .lnk (para achar a janela depois). .url nao tem: devolve ''."""
    if atalho.suffix.lower() != ".lnk":
        return ""
    try:
        import comtypes.client
        comtypes.CoInitialize()
        try:
            alvo = comtypes.client.CreateObject("WScript.Shell").CreateShortcut(str(atalho)).TargetPath
        finally:
            comtypes.CoUninitialize()
        return os.path.basename(alvo).lower() if alvo else ""
    except Exception:
        return ""


def ler_slot(arquivo: Path) -> str | None:
    try:
        return json.loads(arquivo.read_text(encoding="utf-8")).get("nome")
    except Exception:
        return None


def gravar_slot(arquivo: Path, nome: str) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps({"nome": nome}, ensure_ascii=False), encoding="utf-8")
