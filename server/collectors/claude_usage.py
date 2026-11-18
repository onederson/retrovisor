"""Limites da assinatura do Claude, lidos de `claude -p "/usage"` (comando local, sem chamada ao modelo)."""
import re
import shutil
import subprocess
from datetime import datetime

from ..config import caminho

_LINHA = re.compile(r"^Current (?P<nome>[^:]+):\s*(?P<pct>\d+(?:\.\d+)?)% used(?:\s*·\s*resets (?P<reset>.+?))?\s*$")
_RESET = re.compile(r"^(?P<mes>[A-Z][a-z]{2}) (?P<dia>\d{1,2}),? (?P<hora>\d{1,2})(?::(?P<min>\d{2}))?\s*(?P<ap>am|pm)")
_NOMES = {"session": "Sessão 5h", "week (all models)": "Semana"}
_MESES = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def _nome(bruto: str) -> str:
    b = bruto.strip()
    if b.lower() in _NOMES:
        return _NOMES[b.lower()]
    m = re.match(r"week \((.+)\)", b, re.I)
    return f"Semana {m.group(1)}" if m else b


def _reset_iso(txt: str | None, agora: datetime) -> str | None:
    if not txt:
        return None
    m = _RESET.match(txt.strip())
    if not m:
        return None
    h = int(m["hora"]) % 12 + (12 if m["ap"] == "pm" else 0)
    try:
        dt = agora.replace(month=_MESES[m["mes"]], day=int(m["dia"]), hour=h,
                           minute=int(m["min"] or 0), second=0, microsecond=0)
    except (KeyError, ValueError):
        return None
    if dt < agora and (agora - dt).days > 180:  # virada de ano
        dt = dt.replace(year=dt.year + 1)
    return dt.isoformat(timespec="seconds")


def parse_usage(texto: str, agora: datetime | None = None) -> list[dict]:
    agora = agora or datetime.now().astimezone()
    limites = []
    for linha in texto.splitlines():
        m = _LINHA.match(linha.strip())
        if m:
            limites.append({"nome": _nome(m["nome"]), "usado_pct": round(float(m["pct"])),
                            "reset": _reset_iso(m["reset"], agora)})
    return limites


def collect(cfg: dict, ctx: dict) -> dict:
    exe = ctx.get("exe") or shutil.which("claude")
    if not exe:
        raise RuntimeError("claude nao encontrado no PATH")
    ctx["exe"] = exe
    pasta = caminho(cfg, "cache")
    pasta.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([exe, "-p", "/usage"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=90, cwd=pasta,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    limites = parse_usage(r.stdout)
    if not limites:
        raise RuntimeError(f"/usage sem limites (exit {r.returncode}): {(r.stdout or r.stderr)[:120]}")
    return {"limites": limites, "atualizado": datetime.now().astimezone().isoformat(timespec="seconds")}
