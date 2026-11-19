"""Comandos de voz do Vendel que mexem no PC: "abre o Discord", "abre o Chrome", "pausa a música".

Seguranca (mesma regra da tela 5): so abre o que existe no Menu Iniciar do Windows, procurado pelo nome;
nunca roda caminho nem comando vindo da fala. Se o nome nao bater com nenhum programa, a frase segue para
o cerebro como conversa normal.
"""
import difflib
import os
import re
import unicodedata

from . import janelas

_VERBOS_ABRIR = r"(?:abr[aei]r?|abre|inici[ae]r?|liga[r]?|execut[ae]r?|rod[ae]r?|bota[r]?|coloca[r]?)"
_ABRIR = re.compile(rf"^(?:(?:vendel|ei|oi|por favor)[, ]+)*(?:me\s+)?{_VERBOS_ABRIR}\s+(?:o|a|os|as|um|uma)?\s*(.+)$")
_RABO = re.compile(r"\s*(?:pra mim|para mim|por favor|ai|aí|agora|rapidinho|ja|já)\s*$")
APELIDOS = {
    "chrome": "google chrome", "navegador": "google chrome", "zap": "whatsapp", "whats": "whatsapp",
    "explorador": "explorador de arquivos", "arquivos": "explorador de arquivos", "pastas": "explorador de arquivos",
    "vscode": "visual studio code", "vs code": "visual studio code", "code": "visual studio code",
    "obsidian": "obsidian", "steam": "steam", "rocket league": "rocket league",
}
_MIDIA = [  # comandos de server/collectors/midia.py
    (re.compile(r"\b(pausa|pause|para|parar)\b.*\b(musica|video|som)\b"), "alternar", "Pausei."),
    (re.compile(r"\b(toca|tocar|continua|despausa|solta)\b.*\b(musica|video|som)\b"), "alternar", "Pronto."),
    (re.compile(r"\b(proxima|pula|passa)\b.*\b(musica|faixa)\b"), "proxima", "Próxima."),
    (re.compile(r"\b(anterior|volta)\b.*\b(musica|faixa)\b"), "anterior", "Voltei uma."),
]


def _norm(texto: str) -> str:
    sem = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    sem = re.sub(r"[^\w\s+]", " ", sem.lower())
    return re.sub(r"\s+", " ", sem).strip()


def interpretar(texto: str) -> dict | None:
    """{'tipo': 'abrir', 'alvo': 'discord'} | {'tipo': 'midia', 'cmd': ..., 'resposta': ...} | None."""
    t = _norm(texto)
    if not t or len(t) > 80:
        return None
    m = _ABRIR.match(t)
    if m:
        alvo = _RABO.sub("", m.group(1)).strip()
        alvo = re.sub(r"^(programa|app|aplicativo|o|a)\s+", "", alvo).strip()
        if alvo and len(alvo.split()) <= 4:
            return {"tipo": "abrir", "alvo": alvo}
    for padrao, cmd, resposta in _MIDIA:
        if padrao.search(t) and len(t.split()) <= 6:
            return {"tipo": "midia", "cmd": cmd, "resposta": resposta}
    return None


def achar_programa(alvo: str, catalogo: dict) -> str | None:
    """Nome do Menu Iniciar que melhor bate com o que foi falado (ou None)."""
    alvo = APELIDOS.get(alvo, alvo)
    nomes = {_norm(n): n for n in catalogo}
    if alvo in nomes:
        return nomes[alvo]
    contem = sorted((n for n in nomes if alvo in n.split() or n.startswith(alvo)), key=len)
    if contem:
        return nomes[contem[0]]
    perto = difflib.get_close_matches(alvo, list(nomes), n=1, cutoff=0.72)
    return nomes[perto[0]] if perto else None


_cache_loja: dict = {"quando": 0.0, "apps": {}}


def apps_do_windows() -> dict:
    """{nome: AppID} de tudo que o Windows lista em Iniciar (inclui apps da Store, ex.: Calculadora, Xbox).
    Cache de 10 min. O AppID vem do proprio Windows, nunca da fala."""
    import json
    import subprocess
    import time
    if time.time() - _cache_loja["quando"] < 600:
        return _cache_loja["apps"]
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        dados = json.loads(r.stdout or "[]")
        apps = {d["Name"]: d["AppID"] for d in (dados if isinstance(dados, list) else [dados]) if d.get("Name")}
    except Exception:
        apps = {}
    _cache_loja.update(quando=time.time(), apps=apps)
    return apps


def abrir(alvo: str) -> dict:
    if APELIDOS.get(alvo, alvo) == "explorador de arquivos":
        os.startfile("explorer")
        return {"ok": True, "resposta": "Abri o Explorador de Arquivos."}
    catalogo = janelas.catalogo()
    nome = achar_programa(alvo, catalogo)
    if not nome:
        loja = apps_do_windows()
        nome_loja = achar_programa(alvo, loja)
        if nome_loja:
            os.startfile("shell:AppsFolder\\" + loja[nome_loja])
            return {"ok": True, "resposta": f"Abrindo {nome_loja}."}
        return {"ok": False, "resposta": None}  # nao e programa: vira conversa normal
    atalho = catalogo[nome]
    exe = janelas.exe_do_atalho(atalho)
    if not exe:
        os.startfile(str(atalho))
        return {"ok": True, "resposta": f"Abrindo {nome}."}
    res = janelas.focar_ou_abrir({exe}, lambda: os.startfile(str(atalho)), espera_s=8)
    if res.get("ok"):
        return {"ok": True, "resposta": f"Pronto, {nome} na tela."}
    return {"ok": True, "resposta": f"Mandei abrir {nome}, mas ainda não apareceu na tela."}
