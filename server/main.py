import asyncio
from datetime import datetime
import hmac
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import cerebro, config, gestos, humor, sentidos
from .collectors import bloqueio, midia
from .hub import Hub
from .mini import Mini

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
try:  # sobe junto com o Windows: o painel passa na frente dos outros programas da inicializacao
    import psutil
    psutil.Process().nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
except Exception:
    pass
CFG = config.carregar()
HUB = Hub(CFG)
MINI = Mini(config.caminho(CFG, "cache") / "mini.json")
WEB = config.RAIZ / "web"

try:
    from . import actions
except Exception as e:  # o painel funciona sem as acoes
    logging.getLogger("main").warning("acoes indisponiveis: %s", e)
    actions = None


@asynccontextmanager
async def ciclo(app: FastAPI):
    HUB.iniciar()
    asyncio.get_running_loop().run_in_executor(None, cerebro.garantir_servico, CFG)  # cerebro do Vendel
    yield
    gestos.GESTOS.parar()
    await HUB.parar()


app = FastAPI(lifespan=ciclo)


@app.middleware("http")
async def sem_cache(request: Request, call_next):
    """O Chrome do celular guardava CSS/JS antigos com HTML novo: o painel sempre revalida."""
    resp = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


def _local(host: str | None) -> bool:
    return host in ("127.0.0.1", "::1", "localhost")


def autorizado(host: str | None, token: str | None) -> bool:
    """Localhost (PC ou celular via adb reverse) passa; Wi-Fi exige o token do config."""
    if _local(host):
        return True
    esperado = CFG["servidor"].get("token", "")
    return bool(token) and hmac.compare_digest(token, esperado)


@app.get("/health")
def health():
    return {"ok": True}


def _token(req) -> str | None:
    """Token da URL (?t=) ou do cookie gravado na primeira visita (PWA abre "/" sem ?t=)."""
    return req.query_params.get("t") or req.cookies.get("painel_t")


@app.get("/")
def index(request: Request):
    if not autorizado(request.client.host if request.client else None, _token(request)):
        raise HTTPException(403, "token invalido")
    resp = FileResponse(WEB / "index.html")
    if request.query_params.get("t"):
        resp.set_cookie("painel_t", request.query_params["t"], max_age=10 * 365 * 86400,
                        httponly=True, samesite="lax")  # lax: o Chrome envia ao abrir por intent/restaurar aba
    return resp


@app.get("/sw.js")
def service_worker():
    """Na raiz para valer no site todo; nao tem dado nenhum, so guarda a casca do painel."""
    return FileResponse(WEB / "sw.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})


@app.get("/actions")
def listar_acoes(request: Request):
    if not autorizado(request.client.host if request.client else None, _token(request)):
        raise HTTPException(403, "token invalido")
    return actions.listar(CFG) if actions else []


@app.get("/apps")
async def apps_disponiveis(request: Request):
    """Nomes do Menu Iniciar para a tecla livre (o celular so escolhe nome, nunca caminho/comando)."""
    if not autorizado(request.client.host if request.client else None, _token(request)):
        raise HTTPException(403, "token invalido")
    return await asyncio.to_thread(actions.listar_apps) if actions else []


@app.post("/app_slot")
async def escolher_app(request: Request):
    if not autorizado(request.client.host if request.client else None, _token(request)):
        raise HTTPException(403, "token invalido")
    if actions is None:
        raise HTTPException(503, "acoes indisponiveis")
    corpo = await request.json()
    return await asyncio.to_thread(actions.escolher_app, CFG, str(corpo.get("nome", ""))[:200])


@app.post("/action/{acao_id}")
async def executar(acao_id: str, request: Request):
    if not autorizado(request.client.host if request.client else None, _token(request)):
        raise HTTPException(403, "token invalido")
    if actions is None:
        raise HTTPException(503, "acoes indisponiveis")
    return await asyncio.to_thread(actions.executar, acao_id, CFG, HUB)


@app.get("/midia/capa")
def midia_capa(request: Request, id: str = ""):
    """Miniatura do que esta tocando; a URL muda com a faixa (?v=), entao o celular pode guardar."""
    if not autorizado(request.client.host if request.client else None, _token(request)):
        raise HTTPException(403, "token invalido")
    c = midia.capa(id)
    if not c:
        raise HTTPException(404, "sem capa")
    return Response(c[0], media_type=c[1], headers={"Cache-Control": "private, max-age=86400"})


@app.post("/midia/{cmd}")
async def midia_comando(cmd: str, request: Request):
    if not autorizado(request.client.host if request.client else None, _token(request)):
        raise HTTPException(403, "token invalido")
    try:
        corpo = await request.json()
    except Exception:
        corpo = {}
    sid = corpo.get("id")
    return await asyncio.to_thread(midia.comando, CFG, cmd, str(sid)[:300] if sid else None, corpo.get("valor"))


@app.post("/mini/evento")
async def mini_evento(request: Request):
    host = request.client.host if request.client else None
    if not _local(host):
        raise HTTPException(403, "acesso nao local")
    corpo = await request.body()
    if len(corpo) > 4096:
        raise HTTPException(413, "corpo muito grande")
    try:
        dados = json.loads(corpo.decode("utf-8"))
    except Exception:
        raise HTTPException(400, "json invalido")
    if not isinstance(dados, dict) or not MINI.evento(dados):
        raise HTTPException(400, "evento invalido")
    return {"ok": True}


def calcular_humor(mini_snap: dict, hub_estado: dict, hora: int | None = None) -> dict | None:
    try:
        vida = mini_snap.get("vida") if isinstance(mini_snap, dict) else {}
        if not isinstance(vida, dict):
            vida = {}
        hoje = mini_snap.get("hoje") if isinstance(mini_snap, dict) else {}
        if not isinstance(hoje, dict):
            hoje = {}

        min_sem_toque = float(vida.get("min_sem_toque", 0.0))
        min_sem_claude = float(vida.get("min_sem_claude", 0.0))
        concluidas_hoje = int(hoje.get("concluidas", 0))
        carinhos_hoje = int(vida.get("carinhos_hoje", 0))

        uso_5h = None
        try:
            limites = (hub_estado.get("claude_usage") or {}).get("limites") or []
            if isinstance(limites, list):
                for item in limites:
                    if isinstance(item, dict) and str(item.get("nome", "")).startswith("Sessão"):
                        val = item.get("usado_pct")
                        uso_5h = float(val) if val is not None else None
                        break
        except Exception:
            uso_5h = None

        gpu = None
        try:
            hw = hub_estado.get("hardware") or {}
            if isinstance(hw, dict) and hw.get("gpu_temp") is not None:
                gpu = float(hw["gpu_temp"])
        except Exception:
            gpu = None

        if hora is None:
            hora = datetime.now().astimezone().hour

        return humor.calcular(
            hora=hora,
            min_sem_toque=min_sem_toque,
            min_sem_claude=min_sem_claude,
            concluidas_hoje=concluidas_hoje,
            carinhos_hoje=carinhos_hoje,
            uso_5h_pct=uso_5h,
            gpu_temp=gpu,
        )
    except Exception:
        return None


@app.get("/gestos/estado")
def gestos_estado(request: Request):
    if not autorizado(request.client.host if request.client else None, _token(request)):
        raise HTTPException(403, "token invalido")
    return gestos.GESTOS.info()


@app.post("/gestos/ligar")
async def gestos_ligar(request: Request):
    if not autorizado(request.client.host if request.client else None, _token(request)):
        raise HTTPException(403, "token invalido")
    return await asyncio.to_thread(gestos.GESTOS.iniciar, CFG)


@app.post("/gestos/desligar")
async def gestos_desligar(request: Request):
    if not autorizado(request.client.host if request.client else None, _token(request)):
        raise HTTPException(403, "token invalido")
    return await asyncio.to_thread(gestos.GESTOS.parar)


@app.websocket("/ws")
async def ws(sock: WebSocket):
    if not autorizado(sock.client.host if sock.client else None, _token(sock)):
        await sock.close(code=4403)
        return
    await sock.accept()

    async def receber():
        while True:
            msg = await sock.receive_json()
            if not isinstance(msg, dict):
                continue
            tipo = msg.get("tipo")
            if tipo == "bateria":
                HUB.bateria_browser = {k: msg.get(k) for k in ("nivel", "carregando")}
            elif tipo == "carinho":
                MINI.carinho()
            elif tipo == "toque":
                MINI.toque()
            elif tipo == "privacidade":  # botoes mudo/cego do Vendel: o servidor tambem se recusa
                sentidos.PRIVACIDADE["mudo"] = bool(msg.get("mudo"))
                sentidos.PRIVACIDADE["cego"] = bool(msg.get("cego"))
                if sentidos.PRIVACIDADE["mudo"]:
                    sentidos.OUVIDO.parar()
                if sentidos.PRIVACIDADE["cego"]:
                    gestos.GESTOS.parar()

    leitor = asyncio.create_task(receber())
    try:
        while not leitor.done():
            en = bloqueio.energia()
            dados = HUB.snapshot()
            dados["energia"] = en["evento"]
            dados["energia_seq"] = en["seq"]
            dados["mini"] = MINI.snapshot()
            dados["mini"]["pc_parado_s"] = sentidos.pc_parado_s()  # presenca: teclado/mouse do PC
            dados["gestos"] = gestos.GESTOS.info()
            try:
                dados["mini"]["humor"] = calcular_humor(dados["mini"], HUB.estado)
            except Exception:
                pass
            mini_seq = MINI.seq
            gestos_seq = gestos.GESTOS.seq
            gestos_estado_atual = dados["gestos"]["estado"]
            await sock.send_json({"tipo": "estado", "dados": dados})
            # 1 pacote/s; energia, mini ou gesto sai na hora (~50 ms)
            for _ in range(20):
                await asyncio.sleep(0.05)
                if (
                    bloqueio.energia()["seq"] != en["seq"]
                    or MINI.seq != mini_seq
                    or gestos.GESTOS.seq != gestos_seq
                    or gestos.GESTOS.estado != gestos_estado_atual
                ):
                    break
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        leitor.cancel()


app.include_router(cerebro.rotas(autorizado, _token, CFG))  # /vendel/*: conversa, voz, foto, perguntas
app.mount("/static", StaticFiles(directory=WEB, check_dir=False), name="static")
