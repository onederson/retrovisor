"""Ponte entre o celular e o cerebro do Vendel (projeto Vendel, servico em http://127.0.0.1:8090).

- Sobe o servico do cerebro sozinho (sem janela) se ele estiver fora e o caminho estiver no config:
    [vendel]
    cerebro = "C:/Users/Vendel/Desktop/Projetos/Vendel"
    python = "C:/Users/Vendel/AppData/Local/Programs/Python/Python311/pythonw.exe"
- Rotas para o celular (mesma autorizacao do resto do painel):
    POST /vendel/falar {texto, modo}   GET /vendel/pergunta   POST /vendel/responder {id, texto}
    GET /vendel/estado
"""
import logging
import os
import subprocess
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

log = logging.getLogger("cerebro")
URL = "http://127.0.0.1:8090"


def no_ar() -> bool:
    try:
        return httpx.get(URL + "/saude", timeout=1.5).status_code == 200
    except Exception:
        return False


def garantir_servico(cfg: dict) -> None:
    v = cfg.get("vendel") or {}
    pasta = Path(str(v.get("cerebro") or ""))
    if not v.get("cerebro") or not (pasta / "vendel" / "servico.py").exists() or no_ar():
        return
    python = str(v.get("python") or "pythonw")
    flags = 0x00000008 | 0x08000000 | 0x00000200  # DETACHED_PROCESS | CREATE_NO_WINDOW | NEW_PROCESS_GROUP
    try:
        subprocess.Popen([python, "-m", "vendel.servico"], cwd=pasta, creationflags=flags,
                         env={**os.environ, "MINI": "0"}, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        log.info("cerebro do Vendel iniciado")
    except Exception as e:
        log.warning("cerebro do Vendel nao subiu: %s", e)


def rotas(autorizado, token, cfg: dict | None = None) -> APIRouter:
    from . import sentidos
    r = APIRouter()
    cfg = cfg or {}

    def checar(req: Request) -> None:
        if not autorizado(req.client.host if req.client else None, token(req)):
            raise HTTPException(403, "token invalido")

    async def repassar(metodo: str, rota: str, corpo: dict | None = None, timeout: float = 10):
        try:
            async with httpx.AsyncClient(timeout=timeout) as c:
                resp = await c.request(metodo, URL + rota, json=corpo)
            return resp.json()
        except Exception:
            raise HTTPException(503, "cerebro do Vendel fora do ar")

    @r.post("/vendel/falar")
    async def falar(req: Request):
        checar(req)
        dados = await req.json()
        texto = str(dados.get("texto") or "")[:2000]
        modo = str(dados.get("modo") or "local")
        if modo not in ("local", "local2", "claude", "agy"):
            modo = "local"
        # "abre o Discord", "pausa a música": o painel faz na hora (so programas do Menu Iniciar)
        import asyncio
        from . import comandos
        from .collectors import midia
        pedido = comandos.interpretar(texto)
        if pedido and pedido["tipo"] == "abrir":
            res = await asyncio.to_thread(comandos.abrir, pedido["alvo"])
            if res.get("resposta"):
                return {"resposta": res["resposta"], "modo": "comando"}
        elif pedido and pedido["tipo"] == "midia":
            res = await asyncio.to_thread(midia.comando, cfg, pedido["cmd"], None, None)
            return {"resposta": pedido["resposta"] if res.get("ok") else "Não tem nada tocando agora.", "modo": "comando"}
        return await repassar("POST", "/falar", {"texto": texto, "modo": modo}, timeout=240)

    @r.post("/vendel/ouvir")
    async def ouvir(req: Request):
        """WAV gravado no celular -> texto (o gemma4 do PC transcreve)."""
        checar(req)
        corpo = await req.body()
        if len(corpo) > 4 * 1024 * 1024:
            raise HTTPException(413, "audio grande demais")
        try:
            async with httpx.AsyncClient(timeout=120) as c:
                resp = await c.post(URL + "/ouvir", content=corpo, headers={"Content-Type": "audio/wav"})
            return resp.json()
        except Exception:
            raise HTTPException(503, "cerebro do Vendel fora do ar")

    @r.get("/vendel/voz")
    async def voz(req: Request, texto: str = ""):
        """Texto -> fala (WAV) com a voz do Windows."""
        checar(req)
        try:
            async with httpx.AsyncClient(timeout=60) as c:
                resp = await c.get(URL + "/voz", params={"texto": texto[:1500]})
        except Exception:
            raise HTTPException(503, "cerebro do Vendel fora do ar")
        if resp.status_code != 200:
            raise HTTPException(resp.status_code, "sem voz")
        return Response(resp.content, media_type="audio/wav", headers={"Cache-Control": "private, max-age=3600"})

    @r.post("/vendel/ver")
    async def ver(req: Request):
        """Foto tirada agora no celular (base64) + pergunta -> resposta. A foto nao e guardada."""
        checar(req)
        dados = await req.json()
        img = str(dados.get("imagem") or "")
        if len(img) > 4_500_000:
            raise HTTPException(413, "foto grande demais")
        return await repassar("POST", "/ver", {"imagem": img, "pergunta": str(dados.get("pergunta") or "")[:500]},
                              timeout=180)

    @r.get("/vendel/pergunta")
    async def pergunta(req: Request):
        checar(req)
        return await repassar("GET", "/pergunta")

    @r.post("/vendel/responder")
    async def responder(req: Request):
        checar(req)
        dados = await req.json()
        return await repassar("POST", "/responder", {"id": str(dados.get("id") or "")[:20],
                                                      "texto": str(dados.get("texto") or "")[:2000]})

    # Ouvido pelo microfone do celular (o PC liga pelo scrcpy; ver server/sentidos.py)
    @r.post("/vendel/escutar/iniciar")
    def escutar_iniciar(req: Request):
        checar(req)
        return sentidos.OUVIDO.iniciar(cfg, URL)

    @r.get("/vendel/escutar/estado")
    def escutar_estado(req: Request):
        checar(req)
        return sentidos.OUVIDO.info()

    @r.post("/vendel/escutar/parar")
    def escutar_parar(req: Request):
        checar(req)
        sentidos.OUVIDO.parar()
        return {"ok": True}

    @r.post("/vendel/olhar")
    async def olhar(req: Request):
        """Tira uma foto agora com a camera da frente do celular e pergunta ao cerebro. A foto nao e guardada."""
        checar(req)
        import asyncio
        import base64
        dados = await req.json()
        try:
            jpg = await asyncio.to_thread(sentidos.foto, cfg)
        except PermissionError:
            raise HTTPException(403, "cego ligado")
        except Exception as e:
            raise HTTPException(503, str(e)[:100])
        pergunta = str(dados.get("pergunta") or "")[:500] or "O que você está vendo?"
        return await repassar("POST", "/ver", {"imagem": base64.b64encode(jpg).decode(), "pergunta": pergunta},
                              timeout=180)

    @r.get("/vendel/estado")
    async def estado(req: Request):
        checar(req)
        return await repassar("GET", "/estado")

    return r
