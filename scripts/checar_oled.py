"""Falha se web/ usar branco ou cores muito claras (regra OLED) ou se app.js tiver erro de sintaxe."""
import re
import shutil
import subprocess
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
erros = []
for arq in [a for a in WEB.glob("*.*") if a.suffix in (".html", ".css", ".js", ".json")]:
    texto = arq.read_text(encoding="utf-8")
    if re.search(r"\bwhite\b", texto, re.I):
        erros.append(f"{arq.name}: usa 'white'")
    for m in re.finditer(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", texto):
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        if min(r, g, b) > 0xC0:
            erros.append(f"{arq.name}: cor clara #{m.group(1)}")
if not (WEB / "index.html").exists():
    erros.append("falta web/index.html")
node = shutil.which("node")
if node and (WEB / "app.js").exists():
    r = subprocess.run([node, "--check", str(WEB / "app.js")], capture_output=True, text=True)
    if r.returncode:
        erros.append("app.js: " + r.stderr.strip()[:500])
print("\n".join(erros) or "OK")
sys.exit(1 if erros else 0)
