"""Hook do Claude Code -> Vendel. Avisa o painel (server/mini.py) do que cada janela esta fazendo.

Nunca manda prompt, conteudo de ferramenta nem caminho completo: so sessao, evento, nome da pasta e
nome da ferramenta. Nunca imprime nada e sempre sai com 0 (o Claude nao pode travar por causa disto).
Instalar: python scripts/instalar_vendel.py
"""
import json
import os
import sys
import urllib.request
from pathlib import Path


def _so_esperando(d: dict) -> bool:
    """Notification de ociosidade (Claude parado esperando o prompt), nao de permissao."""
    if d.get("notification_type") == "idle_prompt":
        return True
    return "waiting for your input" in str(d.get("message", "")).lower()


def main():
    if os.environ.get("MINI") == "0":
        return
    bruto = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    d = json.loads(bruto)
    if d.get("hook_event_name") == "Notification" and _so_esperando(d):
        return  # "esperando voce digitar" depois de terminar nao e pedido de permissao
    cwd = d.get("cwd", "")
    nome_proj = Path(cwd).name if cwd else "?"
    if not nome_proj:
        nome_proj = "?"
    tipo = "ajudante" if os.environ.get("MINI") == "ajudante" else "sessao"
    if "/.maestro/wt/" in cwd.replace("\\", "/"):  # tarefa delegada pelo maestro
        tipo, nome_proj = "ajudante", "maestro"
    payload = {
        "sessao": d["session_id"],
        "evento": d["hook_event_name"],
        "projeto": nome_proj,
        "ferramenta": d.get("tool_name"),
        "tipo": tipo,
    }
    porta = os.environ.get("MINI_PORTA") or 8080
    url = f"http://127.0.0.1:{porta}/mini/evento"
    corpo = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=corpo,
        headers={"Content-Type": "application/json"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=0.3) as resp:
        resp.read()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        pass
    sys.exit(0)
