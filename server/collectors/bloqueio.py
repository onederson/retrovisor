"""PC bloqueado? Video apagado?

- bloqueado: enquanto a tela de bloqueio do Windows esta aberta, o LogonUI.exe roda.
- video: "ligado", "desligado" ou "esmaecido". Vem do aviso do Windows GUID_CONSOLE_DISPLAY_STATE
  (o mesmo que apaga o monitor por inatividade), recebido numa janela invisivel em uma thread propria.
  Fora do Windows, ou se o aviso nao chegar, fica None (o painel ignora).
- energia: a mesma janela recebe "vai suspender" (PBT_APMSUSPEND) e "vai desligar/reiniciar"
  (WM_QUERYENDSESSION); o celular mostra a tela certa antes de o PC sumir.
"""
import ctypes
import logging
import re
import subprocess
import sys
import threading
import time

import psutil

log = logging.getLogger("bloqueio")

_ESTADOS = {0: "desligado", 1: "ligado", 2: "esmaecido"}
_video: dict = {"estado": None}
_vigia_iniciado = False
# PC indo embora: "suspendendo", "desligando" ou "reiniciando". O seq muda a cada aviso e o
# WebSocket (server/main.py) manda na hora, sem esperar o ciclo de 1 s.
_energia: dict = {"evento": None, "seq": 0, "ts": 0.0}


def energia(agora: float | None = None) -> dict:
    """Aviso velho (o PC desistiu de suspender/desligar e seguiu ligado) vale como nenhum."""
    agora = time.time() if agora is None else agora
    evento = _energia["evento"] if agora - _energia["ts"] <= 20 else None
    return {"evento": evento, "seq": _energia["seq"]}


def avisar_energia(evento, esperar: bool = True) -> None:
    _energia["evento"] = evento
    _energia["seq"] += 1
    _energia["ts"] = time.time()
    log.info("energia: %s", evento)
    if esperar:
        # O Windows espera esta resposta: 1,2 s bastam para o aviso sair pelo WebSocket
        time.sleep(1.2)


def _eh_reinicio() -> bool:
    """Quem pede desligar/reiniciar grava o evento 1074 no log System antes de avisar os apps.
    O 5o campo diz o tipo ("restart", "reiniciar", "power off", "Desligar o sistema"...)."""
    try:
        r = subprocess.run(
            ["wevtutil", "qe", "System", "/q:*[System[(EventID=1074)]]", "/c:1", "/rd:true", "/f:xml"],
            capture_output=True, text=True, timeout=1.5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return _tipo_reinicio(r.stdout)
    except Exception:
        return False


def _tipo_reinicio(xml: str, agora: float | None = None) -> bool:
    """So vale um evento dos ultimos 2 min (um reinicio antigo nao conta)."""
    from datetime import datetime
    dados = re.findall(r"<Data[^>]*>([^<]*)</Data>", xml or "")
    m = re.search(r"SystemTime=['\"]([0-9T:\-]+)", xml or "")
    if len(dados) < 5 or not m:
        return False
    try:
        quando = datetime.fromisoformat(m.group(1) + "+00:00").timestamp()
    except ValueError:
        return False
    if abs((time.time() if agora is None else agora) - quando) > 120:
        return False
    return bool(re.search(r"rein|restart", dados[4], re.I))


def _vigiar_video() -> None:
    from ctypes import wintypes as w

    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
    user32.DefWindowProcW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.CreateWindowExW.restype = w.HWND
    user32.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]
    user32.RegisterPowerSettingNotification.restype = w.HANDLE
    user32.RegisterPowerSettingNotification.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD]
    user32.GetMessageW.argtypes = [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT]

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", w.DWORD), ("Data2", w.WORD), ("Data3", w.WORD), ("Data4", ctypes.c_ubyte * 8)]

    class POWERBROADCAST_SETTING(ctypes.Structure):
        _fields_ = [("PowerSetting", GUID), ("DataLength", w.DWORD), ("Data", w.DWORD)]

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [("style", w.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int), ("hInstance", w.HINSTANCE), ("hIcon", w.HICON),
                    ("hCursor", w.HANDLE), ("hbrBackground", w.HBRUSH), ("lpszMenuName", w.LPCWSTR),
                    ("lpszClassName", w.LPCWSTR)]

    # GUID_CONSOLE_DISPLAY_STATE {6FE69556-704A-47A0-8F24-C28D936FDA47}
    guid = GUID(0x6FE69556, 0x704A, 0x47A0, (ctypes.c_ubyte * 8)(0x8F, 0x24, 0xC2, 0x8D, 0x93, 0x6F, 0xDA, 0x47))
    WM_POWERBROADCAST, PBT_POWERSETTINGCHANGE = 0x0218, 0x8013

    WM_QUERYENDSESSION, ENDSESSION_LOGOFF = 0x0011, 0x80000000
    PBT_APMSUSPEND, PBT_APMRESUMESUSPEND, PBT_APMRESUMEAUTOMATIC = 0x4, 0x7, 0x12

    def wndproc(hwnd, msg, wparam, lparam):
        if msg == WM_POWERBROADCAST and wparam == PBT_POWERSETTINGCHANGE and lparam:
            s = ctypes.cast(lparam, ctypes.POINTER(POWERBROADCAST_SETTING)).contents
            _video["estado"] = _ESTADOS.get(s.Data, "ligado")
            return 1
        if msg == WM_POWERBROADCAST and wparam == PBT_APMSUSPEND:
            avisar_energia("suspendendo")
            return 1
        if msg == WM_POWERBROADCAST and wparam in (PBT_APMRESUMESUSPEND, PBT_APMRESUMEAUTOMATIC):
            avisar_energia(None, esperar=False)
            return 1
        if msg == WM_QUERYENDSESSION and not (lparam & ENDSESSION_LOGOFF):
            avisar_energia("reiniciando" if _eh_reinicio() else "desligando")
            return 1  # nunca segura o desligamento
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    proc = WNDPROC(wndproc)  # referencia viva enquanto a thread roda
    hinst = kernel32.GetModuleHandleW(None)
    wc = WNDCLASSW(lpfnWndProc=proc, hInstance=hinst, lpszClassName="PainelS10VigiaVideo")
    user32.RegisterClassW(ctypes.byref(wc))
    # janela comum e invisivel (sem WS_VISIBLE): recebe os avisos de energia
    hwnd = user32.CreateWindowExW(0, wc.lpszClassName, "vigia-video", 0, 0, 0, 0, 0, None, None, hinst, None)
    if not hwnd or not user32.RegisterPowerSettingNotification(hwnd, ctypes.byref(guid), 0):
        log.warning("vigia de video nao iniciou")
        return
    msg = w.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def _iniciar_vigia() -> None:
    global _vigia_iniciado
    if _vigia_iniciado or sys.platform != "win32":
        return
    _vigia_iniciado = True
    threading.Thread(target=_vigiar_video, name="vigia-video", daemon=True).start()


def collect(cfg: dict, ctx: dict) -> dict:
    _iniciar_vigia()
    bloqueado = any((p.info.get("name") or "").lower() == "logonui.exe"
                    for p in psutil.process_iter(["name"]))
    return {"bloqueado": bloqueado, "video": _video["estado"]}
