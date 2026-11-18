from datetime import datetime
import json
import httpx
from server.config import caminho

URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL"


def agora_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def collect(cfg: dict, ctx: dict) -> dict:
    arq_cache = caminho(cfg, "cache") / "fx.json"
    try:
        resp = httpx.get(URL, timeout=10.0)
        resp.raise_for_status()
        dados = resp.json()
        bid = float(dados["USDBRL"]["bid"])
        resultado = {"usd_brl": bid, "atualizado": agora_iso()}
        arq_cache.parent.mkdir(parents=True, exist_ok=True)
        arq_cache.write_text(json.dumps(resultado, ensure_ascii=False), encoding="utf-8")
        return resultado
    except Exception as e:
        if arq_cache.exists():
            try:
                cached = json.loads(arq_cache.read_text(encoding="utf-8"))
                return {
                    "usd_brl": float(cached["usd_brl"]),
                    "atualizado": cached["atualizado"],
                }
            except Exception:
                pass
        raise e
