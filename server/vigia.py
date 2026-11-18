"""Vigia para abrir o app de digital no celular quando o PC bloqueia / liga / acorda.

Executavel via: python -m server.vigia
"""
import json
import logging
from logging.handlers import RotatingFileHandler
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import threading
import time
from typing import Any, Dict, List, Optional

import psutil

from . import config, celular_adb


class EstadoVigia:
    def __init__(self) -> None:
        self.ultima_volta: Optional[float] = None
        self.bloqueado_anterior: Optional[bool] = None
        self.gatilho_ts: Optional[float] = None
        self.digital_ok: bool = False
        self.tentativa_digital_ts: Optional[float] = None
        self.aguardando_desbloqueio: bool = False


def _get(estado: Any, attr: str, default: Any = None) -> Any:
    if isinstance(estado, dict):
        return estado.get(attr, default)
    return getattr(estado, attr, default)


def _set(estado: Any, attr: str, val: Any) -> None:
    if isinstance(estado, dict):
        estado[attr] = val
    else:
        setattr(estado, attr, val)


def passo(estado: Any, agora: float, bloqueado: bool) -> List[str]:
    """Processa um ciclo do vigia e devolve as acoes a executar ('digital' ou 'fully').

    Gatilhos:
      (i) primeira volta depois de iniciar (boot);
      (ii) salto de relogio > 10 s (PC acordou da suspensao);
      (iii) transicao desbloqueado -> bloqueado (Win+L, painel, inatividade).
    Excecao: se o PC ja estava bloqueado e continua bloqueado sem salto, nada de novo.
    """
    acoes: List[str] = []
    logger = logging.getLogger("server.vigia")

    ultima_volta = _get(estado, "ultima_volta", None)
    bloqueado_anterior = _get(estado, "bloqueado_anterior", None)
    gatilho_ts = _get(estado, "gatilho_ts", None)
    digital_ok = _get(estado, "digital_ok", False)
    tentativa_digital_ts = _get(estado, "tentativa_digital_ts", None)
    aguardando_desbloqueio = _get(estado, "aguardando_desbloqueio", False)

    is_boot = (ultima_volta is None)
    is_salto = (ultima_volta is not None and (agora - ultima_volta) > 10.0)
    is_transicao_bloqueio = (bloqueado_anterior is False and bloqueado is True)

    novo_gatilho = False
    if is_boot:
        if bloqueado:
            novo_gatilho = True
    elif is_salto:
        if bloqueado:
            novo_gatilho = True
    elif is_transicao_bloqueio:
        novo_gatilho = True

    if novo_gatilho:
        logger.info(
            "Gatilho detectado (boot=%s, salto=%s, transicao=%s)",
            is_boot,
            is_salto,
            is_transicao_bloqueio,
        )
        gatilho_ts = agora
        digital_ok = False
        tentativa_digital_ts = None
        aguardando_desbloqueio = True
        _set(estado, "gatilho_ts", gatilho_ts)
        _set(estado, "digital_ok", digital_ok)
        _set(estado, "tentativa_digital_ts", tentativa_digital_ts)
        _set(estado, "aguardando_desbloqueio", aguardando_desbloqueio)

    if not bloqueado:
        # Se depois de um gatilho o PC estava bloqueado e passa a desbloqueado,
        # pede "fully" uma vez ate 10 min apos o gatilho e volta ao repouso.
        if aguardando_desbloqueio:
            if gatilho_ts is not None and (agora - gatilho_ts) <= 600.0:
                acoes.append("fully")
            _set(estado, "aguardando_desbloqueio", False)
            _set(estado, "gatilho_ts", None)
            _set(estado, "digital_ok", False)
            _set(estado, "tentativa_digital_ts", None)
    else:
        # Bloqueado: se mais de 10 min se passaram desde o gatilho, expira aguardando_desbloqueio
        if gatilho_ts is not None and (agora - gatilho_ts) > 600.0:
            _set(estado, "aguardando_desbloqueio", False)
            _set(estado, "gatilho_ts", None)
            gatilho_ts = None

        # Modo "abrindo digital" por ate 90 s a partir do gatilho
        if gatilho_ts is not None and (agora - gatilho_ts) <= 90.0:
            current_digital_ok = _get(estado, "digital_ok", False)
            if not current_digital_ok:
                current_tentativa = _get(estado, "tentativa_digital_ts", None)
                if current_tentativa is None or (agora - current_tentativa) >= 5.0 - 1e-9:
                    acoes.append("digital")
                    _set(estado, "tentativa_digital_ts", agora)

    _set(estado, "ultima_volta", agora)
    _set(estado, "bloqueado_anterior", bloqueado)
    return acoes


def configurar_logging() -> logging.Logger:
    log_dir = config.RAIZ / "cache"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "vigia.log"

    logger = logging.getLogger("server.vigia")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=200_000,
            backupCount=2,
            encoding="utf-8",
        )
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


PORTA_STATUS = 8081


def servidor_no_ar(porta: int = 8080) -> bool:
    """O painel (uvicorn) ja aceita conexao?"""
    try:
        with socket.create_connection(("127.0.0.1", porta), timeout=0.3):
            return True
    except OSError:
        return False


def status_boot(bloqueado: Optional[bool], servidor: bool, uptime_s: float) -> Dict[str, Any]:
    """O que o celular le em http://<pc>:8081/ enquanto o painel ainda nao subiu.
    fase: "windows" (iniciando), "bloqueio" (tela de bloqueio), "entrando" (logado, painel subindo), "pronto"."""
    if servidor:
        fase = "pronto"
    elif bloqueado is None:
        fase = "windows"
    elif bloqueado:
        fase = "bloqueio"
    else:
        fase = "entrando"
    return {"ok": True, "fase": fase, "bloqueado": bloqueado, "servidor": servidor, "uptime": int(uptime_s)}


class _StatusHandler(BaseHTTPRequestHandler):
    """So leitura, sem acao nenhuma: o celular acompanha o PC ligando (barra de carregamento)."""

    def do_GET(self) -> None:  # noqa: N802
        # le na hora: o laco do vigia pode estar parado num adb lento
        corpo = json.dumps(status_boot(celular_adb.pc_bloqueado(), servidor_no_ar(),
                                       time.time() - psutil.boot_time())).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")  # a pagina vem da porta 8080
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *args: Any) -> None:
        pass


def iniciar_status(logger: logging.Logger) -> None:
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", PORTA_STATUS), _StatusHandler)
    except OSError as e:
        logger.warning("Status na porta %s nao abriu: %s", PORTA_STATUS, e)
        return
    threading.Thread(target=srv.serve_forever, name="status-boot", daemon=True).start()
    logger.info("Status do boot na porta %s.", PORTA_STATUS)


# Bloqueio, boot ou volta da suspensao NAO abrem o app de digital sozinhos: o painel fica no portao
# ("Ligar"/"Desbloquear") ate o toque no botao. O "fully" (trazer o painel de volta depois do
# desbloqueio) continua valendo.
ABRIR_DIGITAL_SOZINHO = False


def main() -> None:
    logger = configurar_logging()
    logger.info("Vigia iniciado.")
    iniciar_status(logger)
    cfg = config.carregar()
    estado = EstadoVigia()

    while True:
        try:
            agora = time.time()
            bloqueado = celular_adb.pc_bloqueado()
            acoes = passo(estado, agora, bloqueado)

            for acao in acoes:
                if acao == "digital" and not ABRIR_DIGITAL_SOZINHO:
                    # o app de digital so abre pelo botao do portao no painel (web/app.js)
                    estado.digital_ok = True
                elif acao == "digital":
                    logger.info("Executando acao 'digital': acordando celular e abrindo app de digital...")
                    celular_adb.acordar_celular(cfg)
                    ok = celular_adb.abrir_no_celular(cfg, celular_adb.PACOTE_DIGITAL)
                    if ok:
                        estado.digital_ok = True
                        logger.info("App de digital aberto com sucesso.")
                    else:
                        logger.warning("Falha ao abrir app de digital.")
                elif acao == "fully":
                    logger.info("Executando acao 'fully': esperando 1s e abrindo Fully Kiosk...")
                    time.sleep(1)
                    ok = celular_adb.abrir_no_celular(cfg, celular_adb.PACOTE_FULLY)
                    if ok:
                        logger.info("Fully Kiosk aberto com sucesso.")
                    else:
                        logger.warning("Falha ao abrir Fully Kiosk.")
        except Exception as e:
            logger.exception("Erro no ciclo do vigia: %s", e)

        time.sleep(1)


if __name__ == "__main__":
    main()
