import json
from datetime import datetime, timezone
import httpx
from ..config import caminho


def _calc_expira(exp: str | None) -> int | None:
    if not exp or not isinstance(exp, str):
        return None
    try:
        dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
        if dt.year < 2000:
            return None
        now = datetime.now(timezone.utc)
        diff = (dt - now).total_seconds()
        return max(0, int(diff))
    except Exception:
        return None


def collect(cfg: dict, ctx: dict) -> dict:
    url = cfg.get("ollama", {}).get("url", "http://localhost:11434")
    endpoint = f"{url.rstrip('/')}/api/ps"

    online = False
    modelos = []

    try:
        resp = httpx.get(endpoint, timeout=2.0)
        if resp.status_code == 200:
            online = True
            data = resp.json()
            for m in data.get("models", []):
                nome = m.get("name")
                size_vram = m.get("size_vram", 0) or 0
                vram_gb = round(size_vram / (1024**3), 1)
                expira_em_s = _calc_expira(m.get("expires_at"))
                modelos.append(
                    {
                        "nome": nome,
                        "vram_gb": vram_gb,
                        "expira_em_s": expira_em_s,
                    }
                )
    except Exception:
        online = False
        modelos = []

    tokens_s = None
    tokens_s_modelo = None
    tokens_s_quando = None

    try:
        p_hist = caminho(cfg, "maestro_historico")
        if p_hist.exists() and p_hist.is_file():
            with open(p_hist, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue
                    ex = entry.get("exec")
                    seg = entry.get("segundos")
                    tok = entry.get("tokens_out")
                    if isinstance(ex, str) and ex.startswith("ollama"):
                        if isinstance(seg, (int, float)) and seg > 0:
                            if isinstance(tok, (int, float)) and tok > 0:
                                tokens_s = round(tok / seg, 1)
                                tokens_s_modelo = ex
                                tokens_s_quando = entry.get("data")
    except Exception:
        pass

    return {
        "online": online,
        "modelos": modelos,
        "tokens_s": tokens_s,
        "tokens_s_modelo": tokens_s_modelo,
        "tokens_s_quando": tokens_s_quando,
    }
