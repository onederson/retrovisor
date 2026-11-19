"""Liga (ou desliga) os avisos do Claude Code para o Vendel, no ~/.claude/settings.json.

Uso:  python scripts/instalar_vendel.py            -> instala (pode rodar de novo, nao duplica)
      python scripts/instalar_vendel.py --remover  -> tira so os hooks do Vendel

Os outros hooks que ja existem (rtk, maestro...) ficam como estao. Antes de gravar, guarda uma copia
em settings.json.antes-do-vendel.
"""
import json
import shutil
import sys
from pathlib import Path

EVENTOS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Notification", "Stop", "SessionEnd"]
COM_MATCHER = {"PreToolUse", "PostToolUse"}
MARCA = "mini_hook.py"


def comando() -> str:
    script = (Path(__file__).resolve().parent / "mini_hook.py").as_posix()
    python = Path(sys.executable).as_posix()
    return f'"{python}" -I "{script}"'


def sem_vendel(grupos: list) -> list:
    saida = []
    for g in grupos:
        hooks = [h for h in g.get("hooks", []) if MARCA not in h.get("command", "")]
        if hooks:
            saida.append({**g, "hooks": hooks})
    return saida


def main() -> int:
    remover = "--remover" in sys.argv
    arq = Path.home() / ".claude" / "settings.json"
    cfg = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    hooks = cfg.setdefault("hooks", {})
    for ev in EVENTOS:
        grupos = sem_vendel(hooks.get(ev, []))
        if not remover:
            novo = {"hooks": [{"type": "command", "command": comando(), "timeout": 5}]}
            if ev in COM_MATCHER:
                novo = {"matcher": "*", **novo}
            grupos.append(novo)
        if grupos:
            hooks[ev] = grupos
        else:
            hooks.pop(ev, None)
    if arq.exists():
        shutil.copy2(arq, arq.with_name("settings.json.antes-do-vendel"))
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Vendel desligado do Claude Code." if remover else
          "Vendel ligado ao Claude Code. Janelas novas do Claude ja aparecem no celular.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
