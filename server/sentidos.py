"""Ouvido e olho do Vendel pelo celular, sem app pago.

O Fully gratis nao deixa a pagina usar microfone nem camera (e recurso PLUS). Entao o PC liga o
microfone ou a camera do S10+ pelo scrcpy (via adb) so quando o dono aperta o botao, e desliga logo depois.
- Ouvido: grava ate 1,4 s de silencio depois da fala (maximo 15 s), converte para WAV 16 kHz mono e manda
  para o cerebro transcrever. O audio nunca vai para o disco do vault; o arquivo temporario e apagado.
- Olho: grava 1,5 s da camera da frente e tira o ultimo quadro (JPEG). Apagado logo depois.
- Privacidade: com "mudo"/"cego" ligados no celular, o servidor se recusa a abrir microfone/camera.
- Presenca: tempo desde o ultimo teclado/mouse do PC (nao usa camera).
"""
import array
import ctypes
import glob
import logging
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import httpx

log = logging.getLogger("sentidos")
PRIVACIDADE = {"mudo": False, "cego": False}
CABECALHO_SCRCPY = 112          # scrcpy grava WAV PCM 16 bits, 2 canais, 48 kHz; o audio comeca no byte 112
BLOCO = 48000 * 2 * 2 // 10     # 100 ms de audio
FALA_RMS = 450
SILENCIO_FIM_S = 1.4
MAX_FALA_S = 15
SEM_FALA_DESISTE_S = 8
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def pc_parado_s() -> float:
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    try:
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return round((ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000.0, 1)
    except Exception:
        pass
    return 0.0


def _scrcpy(cfg: dict) -> str | None:
    v = (cfg.get("vendel") or {}).get("scrcpy")
    if v and Path(v).exists():
        return v
    achados = glob.glob(os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Genymobile.scrcpy*\scrcpy-win64-*\scrcpy.exe"))
    return sorted(achados)[-1] if achados else None


def _env(cfg: dict) -> dict:
    adb = (cfg.get("caminhos") or {}).get("adb") or "adb"
    return {**os.environ, "ADB": str(adb)}


def _serial(cfg: dict) -> str:
    return (cfg.get("celular") or {}).get("adb_serial") or ""


def _wav16k_mono(pcm: bytes) -> bytes:
    """PCM 48 kHz estereo 16 bits -> 16 kHz mono (media dos canais e de 3 amostras: filtro simples)."""
    amostras = array.array("h")
    amostras.frombytes(pcm[: len(pcm) - len(pcm) % 12])
    saida = array.array("h")
    for i in range(0, len(amostras), 6):  # 3 quadros estereo -> 1 amostra mono
        s = (amostras[i] + amostras[i + 1] + amostras[i + 2] + amostras[i + 3] + amostras[i + 4] + amostras[i + 5]) // 6
        saida.append(s)
    dados = saida.tobytes()
    cab = b"RIFF" + struct.pack("<I", 36 + len(dados)) + b"WAVEfmt " + struct.pack(
        "<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16) + b"data" + struct.pack("<I", len(dados))
    return cab + dados


def _rms(bloco: bytes) -> float:
    a = array.array("h")
    a.frombytes(bloco[: len(bloco) - len(bloco) % 2])
    if not a:
        return 0.0
    return (sum(x * x for x in a[::8]) / max(1, len(a[::8]))) ** 0.5


class Ouvido:
    """Uma escuta por vez. Estados: parado, preparando, ouvindo, transcrevendo, pronto, nada, erro."""

    def __init__(self):
        self.trava = threading.Lock()
        self.estado = "parado"
        self.texto = ""
        self.erro = ""
        self._parar = threading.Event()
        self.desde = 0.0

    def info(self) -> dict:
        return {"estado": self.estado, "texto": self.texto, "erro": self.erro}

    def parar(self) -> None:
        self._parar.set()

    def iniciar(self, cfg: dict, url_cerebro: str) -> dict:
        if PRIVACIDADE["mudo"]:
            return {"ok": False, "erro": "mudo ligado"}
        with self.trava:
            if self.estado in ("preparando", "ouvindo", "transcrevendo"):
                return {"ok": True, **self.info()}
            self.estado, self.texto, self.erro, self.desde = "preparando", "", "", time.time()
            self._parar.clear()
        limpar_sobras()
        threading.Thread(target=self._rodar_protegido, args=(cfg, url_cerebro), daemon=True).start()
        return {"ok": True, **self.info()}

    def _rodar_protegido(self, cfg: dict, url_cerebro: str) -> None:
        try:
            self._rodar(cfg, url_cerebro)
        except Exception as e:
            log.warning("escuta falhou: %s", e)
            self.estado, self.erro = "erro", str(e)[:120]

    def _rodar(self, cfg: dict, url_cerebro: str) -> None:
        exe, serial = _scrcpy(cfg), _serial(cfg)
        if not exe or not serial:
            self.estado, self.erro = "erro", "scrcpy ou celular nao configurado"
            return
        pasta = Path(tempfile.mkdtemp(prefix="vendel_ouvido_"))
        arq = pasta / "mic.wav"
        proc = None
        try:
            proc = subprocess.Popen([exe, "-s", serial, "--no-video", "--no-playback", "--audio-source=mic",
                                     "--audio-codec=raw", f"--record={arq.name}"], cwd=pasta, env=_env(cfg),
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=SEM_JANELA)
            lido, falou, quieto_desde, inicio_ouvir = CABECALHO_SCRCPY, False, None, None
            fundo: list[float] = []  # barulho do ambiente nos primeiros 500 ms
            while True:
                if self._parar.is_set() or PRIVACIDADE["mudo"]:
                    break
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
                tam = arq.stat().st_size if arq.exists() else 0
                if tam < CABECALHO_SCRCPY + BLOCO:
                    if time.time() - self.desde > 15:
                        self.erro = "o microfone do celular nao abriu"
                        break
                    continue
                if inicio_ouvir is None:
                    inicio_ouvir, self.estado = time.time(), "ouvindo"
                with open(arq, "rb") as f:
                    f.seek(lido)
                    novo = f.read(tam - lido)
                lido += len(novo) - len(novo) % 4
                for i in range(0, len(novo) - BLOCO + 1, BLOCO):
                    nivel = _rms(novo[i:i + BLOCO])
                    if len(fundo) < 5:
                        fundo.append(nivel)
                        continue
                    limite = max(FALA_RMS, 3 * sorted(fundo)[len(fundo) // 2])
                    if nivel > limite:
                        falou, quieto_desde = True, None
                    elif falou and quieto_desde is None:
                        quieto_desde = time.time()
                agora = time.time()
                if falou and quieto_desde and agora - quieto_desde > SILENCIO_FIM_S:
                    break
                if agora - inicio_ouvir > MAX_FALA_S or (not falou and agora - inicio_ouvir > SEM_FALA_DESISTE_S):
                    break
        except Exception as e:
            self.erro = str(e)[:120]
        finally:
            if proc and proc.poll() is None:
                proc.kill()  # o microfone do celular fecha aqui
                try:
                    proc.wait(3)
                except Exception:
                    pass
        try:
            pcm = arq.read_bytes()[CABECALHO_SCRCPY:] if arq.exists() else b""
        finally:
            _apagar(pasta)
        if PRIVACIDADE["mudo"]:
            self.estado = "nada"
            return
        if self.erro and len(pcm) < BLOCO:
            self.estado = "erro"
            return
        if len(pcm) < BLOCO * 5:
            self.estado = "nada"
            return
        self.estado = "transcrevendo"
        try:
            r = httpx.post(url_cerebro + "/ouvir", content=_wav16k_mono(pcm),
                           headers={"Content-Type": "audio/wav"}, timeout=120)
            resp = r.json() or {}
            if resp.get("erro"):
                self.estado, self.erro = "erro", "o cerebro nao conseguiu ouvir (Ollama fora?)"
                return
            self.texto = resp.get("texto", "")
            self.estado = "pronto" if self.texto else "nada"
        except Exception as e:
            self.estado, self.erro = "erro", f"cerebro fora do ar: {str(e)[:80]}"


def _apagar(pasta: Path) -> None:
    """Apaga a pasta temporaria. O Windows as vezes segura o arquivo um instante depois do scrcpy fechar:
    tenta de novo e, se ainda falhar, a limpeza de sobras pega na proxima vez."""
    for _ in range(10):
        shutil.rmtree(pasta, ignore_errors=True)
        if not pasta.exists():
            return
        time.sleep(0.3)


def limpar_sobras() -> None:
    for p in Path(tempfile.gettempdir()).glob("vendel_o*_*"):
        if p.is_dir() and time.time() - p.stat().st_mtime > 120:
            shutil.rmtree(p, ignore_errors=True)


OUVIDO = Ouvido()


def foto(cfg: dict) -> bytes:
    """Um quadro da camera da frente (JPEG). Levanta PermissionError se 'cego' estiver ligado."""
    if PRIVACIDADE["cego"]:
        raise PermissionError("cego ligado")
    exe, serial = _scrcpy(cfg), _serial(cfg)
    if not exe or not serial:
        raise RuntimeError("scrcpy ou celular nao configurado")
    pasta = Path(tempfile.mkdtemp(prefix="vendel_olho_"))
    try:
        subprocess.run([exe, "-s", serial, "--video-source=camera", "--camera-facing=front",
                        "--camera-size=1280x720", "--no-audio", "--no-playback", "--record=cam.mkv",
                        "--time-limit=2"], cwd=pasta, env=_env(cfg), timeout=40, creationflags=SEM_JANELA,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-sseof", "-0.3", "-i", "cam.mkv", "-frames:v", "1",
                        "-q:v", "4", "cam.jpg"], cwd=pasta, timeout=30, creationflags=SEM_JANELA,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        jpg = pasta / "cam.jpg"
        if not jpg.exists():
            raise RuntimeError("a camera do celular nao abriu")
        return jpg.read_bytes()
    finally:
        _apagar(pasta)
