from datetime import datetime
import json
import os
import subprocess
from server.config import caminho


def parse_usage(texto: str) -> list[dict]:
    itens = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        partes = linha.split("\t")
        if len(partes) < 4:
            continue
        grupo = partes[0].strip()
        limite = partes[1].strip()
        pct_campo = partes[2].strip()
        reset = partes[3].strip()
        if not pct_campo.endswith("%"):
            continue
        try:
            restante_pct = int(pct_campo[:-1].strip())
        except ValueError:
            continue
        itens.append({
            "grupo": grupo,
            "limite": limite,
            "restante_pct": restante_pct,
            "reset": reset,
        })
    return itens


def calcular_maestro_hoje(cfg: dict) -> dict:
    zeros = {"chamadas": 0, "tokens_in": 0, "tokens_out": 0}
    try:
        arq = caminho(cfg, "maestro_historico")
    except Exception:
        return zeros
    if not arq.exists():
        return zeros

    hoje_str = datetime.now().astimezone().strftime("%Y-%m-%d")
    chamadas = 0
    tokens_in = 0
    tokens_out = 0

    try:
        with open(arq, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    obj = json.loads(linha)
                    if not isinstance(obj, dict):
                        continue
                    exec_val = obj.get("exec")
                    if not (isinstance(exec_val, str) and exec_val.startswith("agy")):
                        continue
                    data_val = str(obj.get("data", ""))
                    if not data_val.startswith(hoje_str):
                        continue
                    if "tokens_in" not in obj or obj["tokens_in"] is None:
                        continue
                    tin = int(obj["tokens_in"])
                    tout = int(obj.get("tokens_out") or 0)
                    chamadas += 1
                    tokens_in += tin
                    tokens_out += tout
                except Exception:
                    continue
    except Exception:
        return zeros

    return {
        "chamadas": chamadas,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }


def obter_esgotados(cfg: dict) -> list[str]:
    try:
        arq = caminho(cfg, "maestro_estado")
    except Exception:
        return []
    if not arq.exists():
        return []
    try:
        conteudo = json.loads(arq.read_text(encoding="utf-8"))
        if isinstance(conteudo, dict):
            esg = conteudo.get("esgotado")
            if isinstance(esg, dict):
                return list(esg.keys())
            elif isinstance(esg, list):
                return list(esg)
    except Exception:
        pass
    return []


def collect(cfg: dict, ctx: dict) -> dict:
    sucesso = False
    limites = None
    try:
        proc = subprocess.run(
            ["agy", "-p", "/usage", "--print-timeout", "60s"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
            env={**os.environ, "MINI": "0"},
        )
        if proc.returncode == 0:
            parsed = parse_usage(proc.stdout)
            if parsed:
                limites = parsed
                sucesso = True
    except Exception:
        pass

    if sucesso:
        fonte = "usage"
        atualizado = datetime.now().astimezone().isoformat(timespec="seconds")
        ctx["agy_limites"] = limites
        ctx["agy_atualizado"] = atualizado
    else:
        fonte = "maestro"
        limites = ctx.get("agy_limites", [])
        atualizado = ctx.get("agy_atualizado", None)

    return {
        "limites": limites,
        "atualizado": atualizado,
        "fonte": fonte,
        "maestro_hoje": calcular_maestro_hoje(cfg),
        "esgotados": obter_esgotados(cfg),
    }
