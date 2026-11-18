"""Monitores do Windows via QueryDisplayConfig/SetDisplayConfig (user32), sem programas de terceiros.

- listar(): monitores conectados, em ordem ESTAVEL (placa + id da saida), ligados ou nao.
- so_tela(indice): deixa so aquele monitor ligado (vira o principal). Se ele estiver desligado,
  primeiro estende para todos (topologia "Estender" salva no Windows) e depois isola.
"""
import ctypes
import time
from ctypes import wintypes

QDC_ALL_PATHS = 0x1
QDC_ONLY_ACTIVE_PATHS = 0x2
SDC_TOPOLOGY_EXTEND = 0x4
SDC_USE_SUPPLIED_DISPLAY_CONFIG = 0x20
SDC_VALIDATE = 0x40
SDC_APPLY = 0x80
SDC_SAVE_TO_DATABASE = 0x200
SDC_ALLOW_CHANGES = 0x400
MODO_ORIGEM = 1
MODO_DESTINO = 2
NOME_DESTINO = 2  # DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class Origem(ctypes.Structure):
    _fields_ = [("adapterId", LUID), ("id", ctypes.c_uint32),
                ("modeInfoIdx", ctypes.c_uint32), ("statusFlags", ctypes.c_uint32)]


class Racional(ctypes.Structure):
    _fields_ = [("Numerator", ctypes.c_uint32), ("Denominator", ctypes.c_uint32)]


class Destino(ctypes.Structure):
    _fields_ = [("adapterId", LUID), ("id", ctypes.c_uint32), ("modeInfoIdx", ctypes.c_uint32),
                ("outputTechnology", ctypes.c_uint32), ("rotation", ctypes.c_uint32),
                ("scaling", ctypes.c_uint32), ("refreshRate", Racional),
                ("scanLineOrdering", ctypes.c_uint32), ("targetAvailable", wintypes.BOOL),
                ("statusFlags", ctypes.c_uint32)]


class Caminho(ctypes.Structure):
    _fields_ = [("sourceInfo", Origem), ("targetInfo", Destino), ("flags", ctypes.c_uint32)]


class ModoOrigem(ctypes.Structure):
    _fields_ = [("width", ctypes.c_uint32), ("height", ctypes.c_uint32),
                ("pixelFormat", ctypes.c_uint32), ("position", wintypes.POINTL)]


class _UniaoModo(ctypes.Union):
    _fields_ = [("sourceMode", ModoOrigem), ("_bruto", ctypes.c_byte * 48)]


class Modo(ctypes.Structure):
    _fields_ = [("infoType", ctypes.c_uint32), ("id", ctypes.c_uint32),
                ("adapterId", LUID), ("u", _UniaoModo)]


class NomeDestino(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("size", ctypes.c_uint32), ("adapterId", LUID),
                ("id", ctypes.c_uint32), ("flags", ctypes.c_uint32),
                ("outputTechnology", ctypes.c_uint32), ("edidManufactureId", ctypes.c_uint16),
                ("edidProductCodeId", ctypes.c_uint16), ("connectorInstance", ctypes.c_uint32),
                ("monitorFriendlyDeviceName", ctypes.c_wchar * 64),
                ("monitorDevicePath", ctypes.c_wchar * 128)]


def _u32():
    return ctypes.WinDLL("user32")


def _consultar(flags: int):
    u = _u32()
    n_cam, n_modo = ctypes.c_uint32(), ctypes.c_uint32()
    err = u.GetDisplayConfigBufferSizes(flags, ctypes.byref(n_cam), ctypes.byref(n_modo))
    if err:
        raise OSError(f"GetDisplayConfigBufferSizes: {err}")
    cams = (Caminho * n_cam.value)()
    modos = (Modo * n_modo.value)()
    err = u.QueryDisplayConfig(flags, ctypes.byref(n_cam), cams, ctypes.byref(n_modo), modos, None)
    if err:
        raise OSError(f"QueryDisplayConfig: {err}")
    return list(cams[: n_cam.value]), list(modos[: n_modo.value])


def _chave(t: Destino) -> tuple:
    return (t.adapterId.HighPart, t.adapterId.LowPart, t.id)


def _nome(t: Destino) -> str:
    info = NomeDestino()
    info.type, info.size = NOME_DESTINO, ctypes.sizeof(NomeDestino)
    info.adapterId, info.id = t.adapterId, t.id
    if _u32().DisplayConfigGetDeviceInfo(ctypes.byref(info)) == 0 and info.monitorFriendlyDeviceName:
        return info.monitorFriendlyDeviceName
    return f"Monitor {t.id}"


def listar() -> list[dict]:
    """[{indice, nome, ativo, largura, altura}] em ordem estavel (nao muda quando liga/desliga tela)."""
    todos, _ = _consultar(QDC_ALL_PATHS)
    ativos, modos = _consultar(QDC_ONLY_ACTIVE_PATHS)
    res_ativa = {}
    for c in ativos:
        i = c.sourceInfo.modeInfoIdx
        if i < len(modos) and modos[i].infoType == MODO_ORIGEM:
            res_ativa[_chave(c.targetInfo)] = (modos[i].u.sourceMode.width, modos[i].u.sourceMode.height)
    vistos = {}
    for c in todos:
        t = c.targetInfo
        if t.targetAvailable and _chave(t) not in vistos:
            vistos[_chave(t)] = t
    saida = []
    for n, chave in enumerate(sorted(vistos)):
        larg, alt = res_ativa.get(chave, (None, None))
        saida.append({"indice": n, "chave": chave, "nome": _nome(vistos[chave]),
                      "ativo": chave in res_ativa, "largura": larg, "altura": alt})
    return saida


def _config_so(chave: tuple):
    """Monta (caminhos, modos) com SO o monitor `chave`, na posicao 0,0 (vira o principal)."""
    ativos, modos = _consultar(QDC_ONLY_ACTIVE_PATHS)
    alvo = next((c for c in ativos if _chave(c.targetInfo) == chave), None)
    if alvo is None:
        return None
    novos_modos = []
    for campo in ("sourceInfo", "targetInfo"):
        info = getattr(alvo, campo)
        m = Modo.from_buffer_copy(modos[info.modeInfoIdx])
        if campo == "sourceInfo":
            m.u.sourceMode.position.x = 0
            m.u.sourceMode.position.y = 0
        info.modeInfoIdx = len(novos_modos)
        novos_modos.append(m)
    return (Caminho * 1)(alvo), (Modo * len(novos_modos))(*novos_modos)


def _aplicar(cams, modos, so_validar: bool = False) -> int:
    flags = SDC_USE_SUPPLIED_DISPLAY_CONFIG | SDC_ALLOW_CHANGES
    flags |= SDC_VALIDATE if so_validar else (SDC_APPLY | SDC_SAVE_TO_DATABASE)
    return _u32().SetDisplayConfig(len(cams), cams, len(modos), modos, flags)


def estender() -> int:
    return _u32().SetDisplayConfig(0, None, 0, None, SDC_APPLY | SDC_TOPOLOGY_EXTEND)


def so_tela(indice: int, so_validar: bool = False) -> dict:
    mons = listar()
    if not 0 <= indice < len(mons):
        return {"ok": False, "msg": f"tela {indice + 1} nao existe ({len(mons)} conectada(s))"}
    alvo = mons[indice]
    rotulo = f"tela {indice + 1} ({alvo['nome']})"
    if not alvo["ativo"]:
        if so_validar:
            return {"ok": True, "msg": f"{rotulo} desligada: estenderia antes de isolar"}
        estender()
        time.sleep(3)  # o Windows leva um instante para religar as saidas
    config = _config_so(alvo["chave"])
    if config is None:
        return {"ok": False, "msg": f"{rotulo} nao ligou (cabo/monitor desligado?)"}
    err = _aplicar(*config, so_validar=so_validar)
    if err:
        return {"ok": False, "msg": f"Windows recusou ({err}) ao isolar a {rotulo}"}
    return {"ok": True, "msg": ("valido: " if so_validar else "so a ") + rotulo}
