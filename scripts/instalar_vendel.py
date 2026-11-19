"""Liga (ou desliga) os avisos dos CLIs de IA para o Vendel (Claude, agy, Gemini, OpenCode).

Uso:  python scripts/instalar_vendel.py            -> instala nos CLIs detectados
      python scripts/instalar_vendel.py --remover  -> tira os hooks do Vendel
      python scripts/instalar_vendel.py --home <dir> [--remover] -> usa pasta home customizada

Antes de gravar, guarda uma copia em *.antes-do-vendel.
"""
import json
import shutil
import sys
from pathlib import Path

MARCA = "mini_hook.py"

CLAUDE_EVENTOS = [
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Notification",
    "Stop",
    "SessionEnd",
]
CLAUDE_COM_MATCHER = {"PreToolUse", "PostToolUse"}

GEMINI_EVENTOS = [
    "SessionStart",
    "BeforeAgent",
    "BeforeTool",
    "AfterTool",
    "Notification",
    "AfterAgent",
    "SessionEnd",
]
GEMINI_COM_MATCHER = {"BeforeTool", "AfterTool"}

OPENCODE_PLUGIN_JS = """export const VendelPlugin = async ({ directory }) => {
  const enviar = async (sessao, evento, ferramenta, dir) => {
    if (process.env.MINI === "0") return;
    const caminho = (dir || directory || (typeof process !== "undefined" && process.cwd ? process.cwd() : "")) || "";
    const normalizado = caminho.replace(/\\\\/g, "/");
    let projeto = "?";
    if (caminho) {
      const partes = normalizado.split("/").filter(Boolean);
      if (partes.length > 0) {
        projeto = partes[partes.length - 1];
      }
    }
    let tipo = process.env.MINI === "ajudante" ? "ajudante" : "sessao";
    if (normalizado.includes("/.maestro/wt/")) {
      tipo = "ajudante";
      projeto = "maestro";
    }
    const sessaoSanitizada = String(sessao || "").replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 100) || "opencode";
    const porta = process.env.MINI_PORTA || 8080;
    const body = JSON.stringify({
      sessao: sessaoSanitizada,
      evento,
      projeto,
      ferramenta: ferramenta || null,
      tipo,
      cli: "opencode"
    });
    try {
      await fetch(`http://127.0.0.1:${porta}/mini/evento`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
        signal: AbortSignal.timeout(300)
      }).catch(() => {});
    } catch (_) {}
  };

  return {
    "tool.execute.before": async (input) => {
      await enviar(input?.sessionID || "opencode", "PreToolUse", input?.tool || null);
    },
    "tool.execute.after": async (input) => {
      await enviar(input?.sessionID || "opencode", "PostToolUse", input?.tool || null);
    },
    event: async ({ event }) => {
      const tipoEvt = event?.type;
      let mapeado = null;
      if (tipoEvt === "session.created") {
        mapeado = "SessionStart";
      } else if (tipoEvt === "session.status") {
        if (event?.properties?.status?.type === "busy") {
          mapeado = "UserPromptSubmit";
        }
      } else if (tipoEvt === "session.idle") {
        mapeado = "Stop";
      } else if (tipoEvt === "session.deleted") {
        mapeado = "SessionEnd";
      } else if (tipoEvt === "permission.asked" || tipoEvt === "permission.updated") {
        mapeado = "Notification";
      }
      if (mapeado) {
        await enviar(event?.sessionID || event?.properties?.sessionID || "opencode", mapeado, null);
      }
    }
  };
};
"""


def comando(cli: str) -> str:
    script = (Path(__file__).resolve().parent / "mini_hook.py").as_posix()
    python = Path(sys.executable).as_posix()
    return f'"{python}" -I "{script}" --cli {cli}'


def sem_vendel(grupos: list) -> list:
    saida = []
    for g in grupos:
        hooks = [h for h in g.get("hooks", []) if MARCA not in h.get("command", "")]
        if hooks:
            saida.append({**g, "hooks": hooks})
    return saida


def instalar_claude(home: Path, remover: bool = False) -> bool:
    claude_dir = home / ".claude"
    arq = claude_dir / "settings.json"
    if remover and not arq.exists():
        return False
    if not (claude_dir.exists() or home == Path.home()):
        return False

    cfg = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    hooks = cfg.setdefault("hooks", {})
    cmd = comando("claude")
    for ev in CLAUDE_EVENTOS:
        grupos = sem_vendel(hooks.get(ev, []))
        if not remover:
            novo = {"hooks": [{"type": "command", "command": cmd, "timeout": 5}]}
            if ev in CLAUDE_COM_MATCHER:
                novo = {"matcher": "*", **novo}
            grupos.append(novo)
        if grupos:
            hooks[ev] = grupos
        else:
            hooks.pop(ev, None)

    if not hooks:
        cfg.pop("hooks", None)

    if arq.exists():
        shutil.copy2(arq, arq.with_name("settings.json.antes-do-vendel"))
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def instalar_agy(home: Path, remover: bool = False) -> bool:
    config_dir = home / ".gemini" / "config"
    antigravity_dir = home / ".gemini" / "antigravity-cli"
    if not (config_dir.exists() or antigravity_dir.exists()):
        return False

    arq = config_dir / "hooks.json"
    cfg = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}

    if remover:
        if "vendel" not in cfg and not arq.exists():
            return False
        if arq.exists():
            shutil.copy2(arq, arq.with_name("hooks.json.antes-do-vendel"))
        cfg.pop("vendel", None)
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True

    cmd_agy = comando("agy")
    vendel_cfg = {
        "SessionStart": [{"type": "command", "command": cmd_agy, "timeout": 5}],
        "PreInvocation": [{"type": "command", "command": cmd_agy, "timeout": 5}],
        "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": cmd_agy, "timeout": 5}]}],
        "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": cmd_agy, "timeout": 5}]}],
        "Stop": [{"type": "command", "command": cmd_agy, "timeout": 5}],
    }
    if arq.exists():
        shutil.copy2(arq, arq.with_name("hooks.json.antes-do-vendel"))
    cfg["vendel"] = vendel_cfg
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def instalar_gemini(home: Path, remover: bool = False) -> bool:
    gemini_dir = home / ".gemini"
    if not gemini_dir.exists():
        return False

    arq = gemini_dir / "settings.json"
    if remover and not arq.exists():
        return False

    cfg = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    hooks = cfg.setdefault("hooks", {})
    cmd_gemini = comando("gemini")

    for ev in GEMINI_EVENTOS:
        grupos = sem_vendel(hooks.get(ev, []))
        if not remover:
            novo = {"hooks": [{"type": "command", "command": cmd_gemini, "timeout": 5000}]}
            if ev in GEMINI_COM_MATCHER:
                novo = {"matcher": ".*", **novo}
            grupos.append(novo)
        if grupos:
            hooks[ev] = grupos
        else:
            hooks.pop(ev, None)

    if not hooks:
        cfg.pop("hooks", None)

    if arq.exists():
        shutil.copy2(arq, arq.with_name("settings.json.antes-do-vendel"))
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def instalar_opencode(home: Path, remover: bool = False) -> bool:
    opencode_dir = home / ".config" / "opencode"
    if not opencode_dir.exists():
        return False

    plugin_arq = opencode_dir / "plugins" / "vendel.js"
    if remover:
        if plugin_arq.exists():
            plugin_arq.unlink()
            return True
        return False

    plugin_arq.parent.mkdir(parents=True, exist_ok=True)
    plugin_arq.write_text(OPENCODE_PLUGIN_JS, encoding="utf-8")
    return True


def instalar_todos(home: Path, remover: bool = False) -> list[str]:
    afetados = []
    if instalar_claude(home, remover=remover):
        afetados.append("Claude Code")
    if instalar_agy(home, remover=remover):
        afetados.append("Antigravity (agy)")
    if instalar_gemini(home, remover=remover):
        afetados.append("Gemini CLI")
    if instalar_opencode(home, remover=remover):
        afetados.append("OpenCode")
    return afetados


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    remover = "--remover" in argv
    home = Path.home()
    if "--home" in argv:
        idx = argv.index("--home")
        if idx + 1 < len(argv):
            home = Path(argv[idx + 1]).resolve()

    afetados = instalar_todos(home, remover=remover)
    if afetados:
        acao = "desligado de" if remover else "ligado a"
        print(f"Vendel {acao}: {', '.join(afetados)}.")
    else:
        print("Nenhum CLI configurado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
