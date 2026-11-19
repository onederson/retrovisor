"""Deteccao leve de gestos horizontais pela camera frontal do S10+ via scrcpy-server + ffmpeg.

O Fully Kiosk gratis nao libera camera para a pagina web. Entao o servidor abre um stream H.264
direto do scrcpy-server (via adb forward, sem gravar em disco), decodifica em quadros cinza
64x36 a 15 fps no ffmpeg e detecta acenos horizontais (esquerda / direita) pelo deslocamento
do centroide de movimento.

Privacidade: respeita sentidos.PRIVACIDADE["cego"] e pausa automaticamente se o Vendel tirar foto.
"""
from __future__ import annotations

import contextlib
import logging
import re
import socket
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

from . import sentidos

log = logging.getLogger("gestos")

LARGURA = 64
ALTURA = 36
TAM_QUADRO = LARGURA * ALTURA

_FILTROS_GIRO = {
    90: "transpose=1",
    180: "transpose=1,transpose=1",
    270: "transpose=2",
}


class DetectorGestos:
    """Detecta acenos horizontais ('esquerda' / 'direita') em quadros cinza 64x36."""

    def __init__(
        self,
        largura: int = LARGURA,
        altura: int = ALTURA,
        pixel_limiar: int = 24,
        min_pixels: int = 18,
        max_pixels: int = 380,
        janela_s: float = 0.60,
        gap_reset_s: float = 0.25,
        min_quadros: int = 3,
        deslocamento_min: float = 0.26,
        consistencia_min: float = 0.65,
        cooldown_s: float = 0.85,
        inverter: bool = False,
    ) -> None:
        self.largura = largura
        self.altura = altura
        self.pixel_limiar = pixel_limiar
        self.min_pixels = min_pixels
        self.max_pixels = max_pixels
        self.janela_s = janela_s
        self.gap_reset_s = gap_reset_s
        self.min_quadros = min_quadros
        self.deslocamento_min = deslocamento_min
        self.consistencia_min = consistencia_min
        self.cooldown_s = cooldown_s
        self.inverter = inverter

        self._anterior: bytes | None = None
        self._traj: deque[tuple[float, float]] = deque()
        self._cooldown_ate: float = 0.0

    def reset(self) -> None:
        self._anterior = None
        self._traj.clear()
        self._cooldown_ate = 0.0

    def processar(self, quadro: bytes, agora: float | None = None) -> str | None:
        esperado = self.largura * self.altura
        if not quadro or len(quadro) != esperado:
            return None

        t = time.monotonic() if agora is None else float(agora)

        if self._anterior is None:
            self._anterior = quadro
            return None

        if t < self._cooldown_ate:
            self._anterior = quadro
            return None

        prev = self._anterior
        self._anterior = quadro

        larg = self.largura
        alt = self.altura
        limiar = self.pixel_limiar

        ativos = 0
        soma_x = 0.0
        soma_e = 0.0

        # Subamostragem 2x2 com margem de 2 px (~576 pixels/quadro -> < 0.3% CPU a 15 fps)
        for y in range(2, alt - 2, 2):
            base = y * larg
            for x in range(2, larg - 2, 2):
                idx = base + x
                d = quadro[idx] - prev[idx]
                if d < 0:
                    d = -d
                if d >= limiar:
                    ativos += 1
                    soma_e += d
                    soma_x += x * d

        if ativos < self.min_pixels or ativos > self.max_pixels or soma_e <= 0.0:
            if self._traj and (t - self._traj[-1][0]) > self.gap_reset_s:
                self._traj.clear()
            return None

        cx = (soma_x / soma_e) / max(1, larg - 1)

        if self._traj and (t - self._traj[-1][0]) > self.gap_reset_s:
            self._traj.clear()

        # Se o centroide saltou bruscamente para o lado oposto (ex.: mao sumiu de um lado e entrou do outro),
        # inicia uma trajetoria limpa a partir deste quadro.
        if self._traj and abs(cx - self._traj[-1][1]) > 0.45:
            self._traj.clear()

        self._traj.append((t, cx))
        corte = t - self.janela_s
        while self._traj and self._traj[0][0] < corte:
            self._traj.popleft()

        if len(self._traj) < self.min_quadros:
            return None

        dx = self._traj[-1][1] - self._traj[0][1]
        if abs(dx) < self.deslocamento_min:
            return None

        sinal = 1 if dx > 0 else -1
        passos_validos = 0
        passos_alinhados = 0
        pts = list(self._traj)
        for i in range(1, len(pts)):
            passo = pts[i][1] - pts[i - 1][1]
            if abs(passo) < 0.005:
                continue
            passos_validos += 1
            if (passo > 0 and sinal > 0) or (passo < 0 and sinal < 0):
                passos_alinhados += 1

        if passos_validos == 0 or (passos_alinhados / passos_validos) < self.consistencia_min:
            return None

        self._traj.clear()
        self._cooldown_ate = t + self.cooldown_s

        direcao = "esquerda" if dx < 0 else "direita"
        if self.inverter:
            direcao = "direita" if direcao == "esquerda" else "esquerda"
        return direcao


def _versao_scrcpy(exe: str) -> str:
    m = re.search(r"v(\d+\.\d+(?:\.\d+)?)", str(exe))
    return m.group(1) if m else "5.0.1"


def _porta_livre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _filtro_vf(giro: int, espelhar: bool) -> str:
    partes: list[str] = []
    if giro in _FILTROS_GIRO:
        partes.append(_FILTROS_GIRO[giro])
    if espelhar:
        partes.append("hflip")
    partes.append(f"scale={LARGURA}:{ALTURA}")
    return ",".join(partes)


class ControladorGestos:
    """Gerencia o stream da camera frontal do S10+ e publica gestos detectados."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.ativo: bool = False
        self.estado: str = "parado"
        self.erro: str = ""
        self.seq: int = 0
        self.ultimo_gesto: str = ""
        self.ultimo_ts: float = 0.0

        self._cfg: dict | None = None
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc_srv: subprocess.Popen | None = None
        self._proc_ff: subprocess.Popen | None = None
        self._porta_ativa: int | None = None
        self._adb_ativo: str = "adb"
        self._serial_ativo: str = ""

    def info(self) -> dict:
        with self._lock:
            return {
                "ativo": self.ativo,
                "estado": self.estado,
                "erro": self.erro,
                "seq": self.seq,
                "ultimo": {
                    "direcao": self.ultimo_gesto,
                    "ts": self.ultimo_ts,
                },
            }

    def iniciar(self, cfg: dict) -> dict:
        if sentidos.PRIVACIDADE.get("cego"):
            return {**self.info(), "ok": False, "erro": "cego ligado"}
        with self._lock:
            if self.ativo and self.estado in ("conectando", "ativo"):
                return {"ok": True, **self.info()}
            self._cfg = cfg
            self.ativo = True
            self.estado = "conectando"
            self.erro = ""
            self._parar.clear()
            t = threading.Thread(target=self._loop_protegido, args=(cfg,), daemon=True, name="gestos")
            self._thread = t
            t.start()
        return {"ok": True, **self.info()}

    def _matar_processos(self) -> None:
        for attr in ("_proc_ff", "_proc_srv"):
            p = getattr(self, attr, None)
            if p is not None:
                try:
                    if p.poll() is None:
                        p.kill()
                except Exception:
                    pass
                setattr(self, attr, None)
        porta = self._porta_ativa
        if porta is not None and self._serial_ativo:
            self._porta_ativa = None
            try:
                subprocess.run(
                    [self._adb_ativo, "-s", self._serial_ativo, "forward", "--remove", f"tcp:{porta}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    creationflags=sentidos.SEM_JANELA,
                )
            except Exception:
                pass

    def parar(self) -> dict:
        self._parar.set()
        with self._lock:
            self.ativo = False
            self.estado = "parado"
            self.erro = ""
        self._matar_processos()
        return {"ok": True, **self.info()}

    @contextlib.contextmanager
    def pausar_para_foto(self):
        with self._lock:
            estava_ativo = self.ativo
            cfg = self._cfg
            thread = self._thread
            if estava_ativo:
                self.estado = "pausado"
        if not estava_ativo:
            yield
            return
        self._parar.set()
        self._matar_processos()
        if thread and thread.is_alive():
            thread.join(timeout=3.0)
        try:
            yield
        finally:
            if cfg is not None and not sentidos.PRIVACIDADE.get("cego"):
                with self._lock:
                    if self.ativo:
                        self.estado = "conectando"
                        self._parar.clear()
                        t = threading.Thread(target=self._loop_protegido, args=(cfg,), daemon=True, name="gestos")
                        self._thread = t
                        t.start()

    def _loop_protegido(self, cfg: dict) -> None:
        try:
            self._loop(cfg)
        except Exception as e:
            log.warning("loop de gestos falhou: %s", e)
            with self._lock:
                if self.ativo:
                    self.estado = "erro"
                    self.erro = str(e)[:120]
                    self.ativo = False
        finally:
            self._matar_processos()

    def _dormir_interrompivel(self, seg: float) -> bool:
        fim = time.monotonic() + seg
        while time.monotonic() < fim:
            if self._parar.is_set() or sentidos.PRIVACIDADE.get("cego"):
                return False
            time.sleep(0.1)
        return not (self._parar.is_set() or sentidos.PRIVACIDADE.get("cego"))

    def _loop(self, cfg: dict) -> None:
        exe = sentidos._scrcpy(cfg)
        serial = sentidos._serial(cfg)
        if not exe or not serial:
            with self._lock:
                self.ativo = False
                self.estado = "erro"
                self.erro = "scrcpy ou celular nao configurado"
            return

        srv_jar = Path(exe).parent / "scrcpy-server"
        if not srv_jar.exists():
            with self._lock:
                self.ativo = False
                self.estado = "erro"
                self.erro = "scrcpy-server nao encontrado"
            return

        adb = (cfg.get("caminhos") or {}).get("adb") or "adb"
        versao = _versao_scrcpy(exe)
        gcfg = cfg.get("gestos") or {}
        espelhar = bool(gcfg.get("espelhar", True))
        inverter = bool(gcfg.get("inverter", False))
        giro = sentidos._giro_camera(cfg)
        vf = _filtro_vf(giro, espelhar)

        self._adb_ativo = str(adb)
        self._serial_ativo = serial

        push = subprocess.run(
            [str(adb), "-s", serial, "push", str(srv_jar), "/data/local/tmp/scrcpy-server.jar"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=15,
            creationflags=sentidos.SEM_JANELA,
        )
        if push.returncode != 0:
            with self._lock:
                self.ativo = False
                self.estado = "erro"
                self.erro = "falha ao enviar scrcpy-server para o celular"
            return

        detector = DetectorGestos(inverter=inverter)
        tentativa = 0

        while not self._parar.is_set() and not sentidos.PRIVACIDADE.get("cego"):
            tentativa += 1
            porta = _porta_livre()
            scid = f"{(int(time.time() * 1000) + tentativa) & 0x7FFFFFFF:08x}"
            detector.reset()

            with self._lock:
                if self.ativo:
                    self.estado = "conectando"

            try:
                subprocess.run(
                    [str(adb), "-s", serial, "forward", f"tcp:{porta}", f"localabstract:scrcpy_{scid}"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    creationflags=sentidos.SEM_JANELA,
                )
                self._porta_ativa = porta

                cmd_srv = [
                    str(adb), "-s", serial, "shell",
                    (
                        f"CLASSPATH=/data/local/tmp/scrcpy-server.jar app_process / "
                        f"com.genymobile.scrcpy.Server {versao} scid={scid} log_level=warn "
                        f"cleanup=false video_source=camera camera_facing=front "
                        f"camera_size=1280x720 camera_fps=15 video_bit_rate=1000000 "
                        f"audio=false control=false tunnel_forward=true raw_stream=true"
                    ),
                ]
                self._proc_srv = subprocess.Popen(
                    cmd_srv,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=sentidos.SEM_JANELA,
                )

                if not self._dormir_interrompivel(1.6):
                    break

                cmd_ff = [
                    "ffmpeg", "-loglevel", "error",
                    "-probesize", "32768", "-analyzeduration", "100000",
                    "-f", "h264", "-i", f"tcp://127.0.0.1:{porta}",
                    "-f", "rawvideo", "-pix_fmt", "gray",
                    "-vf", vf, "-",
                ]
                self._proc_ff = subprocess.Popen(
                    cmd_ff,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=0,
                    creationflags=sentidos.SEM_JANELA,
                )

                assert self._proc_ff.stdout is not None
                primeiro = True
                while not self._parar.is_set() and not sentidos.PRIVACIDADE.get("cego"):
                    buf = bytearray()
                    while len(buf) < TAM_QUADRO:
                        chunk = self._proc_ff.stdout.read(TAM_QUADRO - len(buf))
                        if not chunk:
                            break
                        buf.extend(chunk)
                    if len(buf) < TAM_QUADRO:
                        break
                    if primeiro:
                        primeiro = False
                        with self._lock:
                            if self.ativo:
                                self.estado = "ativo"
                                self.erro = ""
                    direcao = detector.processar(bytes(buf))
                    if direcao:
                        log.info("gesto detectado: %s", direcao)
                        with self._lock:
                            self.seq += 1
                            self.ultimo_gesto = direcao
                            self.ultimo_ts = time.time()
            except Exception as e:
                log.warning("stream de gestos interrompido: %s", e)
                with self._lock:
                    if self.ativo:
                        self.erro = str(e)[:120]
            finally:
                self._matar_processos()

            if self._parar.is_set() or sentidos.PRIVACIDADE.get("cego"):
                break
            if not self._dormir_interrompivel(2.0):
                break

        if sentidos.PRIVACIDADE.get("cego"):
            with self._lock:
                self.ativo = False
                self.estado = "parado"
                self.erro = ""


GESTOS = ControladorGestos()
