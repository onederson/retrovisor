"""Hook dos CLIs (Claude, agy, Gemini, Codex) -> Vendel. Avisa o painel (server/mini.py) do que cada janela esta fazendo.

Nunca manda prompt, conteudo de ferramenta nem caminho completo: so sessao, evento, nome da pasta e
nome da ferramenta. Respeita o contrato de stdout de cada CLI e sempre sai com 0.
Instalar: python scripts/instalar_vendel.py
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path


MAPEAMENTO_EVENTOS = {
    "SessionStart": "SessionStart",
    "UserPromptSubmit": "UserPromptSubmit",
    "PreInvocation": "UserPromptSubmit",
    "BeforeAgent": "UserPromptSubmit",
    "PreToolUse": "PreToolUse",
    "BeforeTool": "PreToolUse",
    "PostToolUse": "PostToolUse",
    "AfterTool": "PostToolUse",
    "Notification": "Notification",
    "Stop": "Stop",
    "AfterAgent": "Stop",
    "agent-turn-complete": "Stop",
    "SessionEnd": "SessionEnd",
}

_RE_TESTANDO = re.compile(
    r"\b(pytest|jest|vitest|cargo\s+test|npm\s+test|pnpm\s+test|yarn\s+test|go\s+test|unittest|mocha|rspec|phpunit|dotnet\s+test)\b",
    re.IGNORECASE,
)
_RE_ENVIANDO = re.compile(
    r"\b(git\s+(commit|push)|gh\s+pr\s+create)\b",
    re.IGNORECASE,
)
_RE_ARQUITETO_CMD = re.compile(
    r"\b(mkdir|npm\s+init|create-next-app|cargo\s+new|django-admin)\b",
    re.IGNORECASE,
)


def _detectar_atividade(evento_canonico: str, ferramenta: str | None, d: dict) -> str | None:
    if not isinstance(d, dict):
        return None

    if evento_canonico == "PreToolUse":
        f = (ferramenta or "").lower()
        if f in {"webfetch", "websearch", "search_web", "google_web_search", "read_url_content"}:
            return "pescando"
        if f in {"read_many_files", "glob", "find_by_name", "list_dir", "list_directory"}:
            return "bibliotecario"
        if f in {"enterplanmode", "plan", "create_plan", "write_plan"}:
            return "arquiteto"
        if f in {"bash", "powershell", "run_command", "run_shell_command", "shell", "execute"}:
            cmd_raw = d.get("tool_input")
            if cmd_raw is None and isinstance(d.get("toolCall"), dict):
                cmd_raw = d["toolCall"].get("input")
            if cmd_raw is None:
                cmd_raw = d.get("arguments")

            texto_comando = ""
            if isinstance(cmd_raw, dict):
                for k in ("command", "CommandLine", "cmd", "script"):
                    v = cmd_raw.get(k)
                    if isinstance(v, str):
                        texto_comando = v
                        break
                    elif isinstance(v, list):
                        texto_comando = " ".join(str(item) for item in v)
                        break
            elif isinstance(cmd_raw, str):
                texto_comando = cmd_raw

            if _RE_TESTANDO.search(texto_comando):
                return "testando"
            if _RE_ENVIANDO.search(texto_comando):
                return "enviando"
            if _RE_ARQUITETO_CMD.search(texto_comando):
                return "arquiteto"
            return "academia"
        return None

    if evento_canonico == "PostToolUse":
        tr = d.get("tool_response")
        res = d.get("result")
        err = d.get("error")
        is_err = d.get("is_error")
        ec = d.get("exit_code")
        rc = d.get("returncode")

        partes_texto = []
        for val in (err, tr, res):
            if val is not None:
                if isinstance(val, (str, dict, list)):
                    partes_texto.append(str(val))
        texto_curto = (" ".join(partes_texto))[:500].lower()

        for token in ("429", "rate limit", "too many requests", "retry-after", "quota exceeded"):
            if token in texto_curto:
                return "cooldown"

        def _int_nonzero(v):
            return isinstance(v, int) and not isinstance(v, bool) and v != 0

        if is_err is True or _int_nonzero(ec) or _int_nonzero(rc):
            return "erro"

        if isinstance(tr, dict):
            if tr.get("is_error") is True or _int_nonzero(tr.get("exit_code")) or _int_nonzero(tr.get("returncode")):
                return "erro"
            if tr.get("error") is not None and tr.get("error") is not False and tr.get("error") != "":
                return "erro"

        if err is not None and err is not False and err != "":
            return "erro"

        return None

    return None


def _so_esperando(d: dict) -> bool:
    """Notification de ociosidade (parado esperando o prompt), nao de permissao."""
    if d.get("notification_type") == "idle_prompt":
        return True
    return "waiting for your input" in str(d.get("message", "")).lower()


def _resposta_stdout(cli: str | None, evento_bruto: str | None):
    try:
        if cli == "agy":
            if evento_bruto == "PreToolUse":
                sys.stdout.write('{"decision": "allow"}\n')
            else:
                sys.stdout.write("{}\n")
            sys.stdout.flush()
        elif cli == "gemini":
            sys.stdout.write("{}\n")
            sys.stdout.flush()
    except Exception:
        pass


def main():
    cli = None
    evento_bruto = None
    try:
        args = sys.argv[1:]
        cli_arg = None
        posicional_json = None
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--cli" and i + 1 < len(args):
                cli_arg = args[i + 1].strip().lower()
                i += 2
            elif arg.startswith("--cli="):
                cli_arg = arg.split("=", 1)[1].strip().lower()
                i += 1
            else:
                if arg.strip().startswith("{") and posicional_json is None:
                    posicional_json = arg
                i += 1

        cli = cli_arg

        bruto = ""
        try:
            if not sys.stdin.isatty():
                bruto = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        except Exception:
            bruto = ""

        if not bruto.strip() and posicional_json:
            bruto = posicional_json

        d = {}
        if bruto.strip():
            try:
                parsed = json.loads(bruto)
                if isinstance(parsed, dict):
                    d = parsed
            except Exception:
                d = {}

        evento_bruto = (
            d.get("hook_event_name")
            or d.get("hookEventName")
            or d.get("event")
            or d.get("type")
        )

        if not cli:
            if "conversationId" in d or "hookEventName" in d:
                cli = "agy"
            elif evento_bruto in {"BeforeAgent", "AfterAgent", "BeforeTool", "AfterTool"}:
                cli = "gemini"
            elif evento_bruto == "agent-turn-complete":
                cli = "codex"
            else:
                cli = None

        evento_canonico = MAPEAMENTO_EVENTOS.get(evento_bruto)
        if not evento_canonico:
            return

        sessao_bruta = (
            d.get("session_id")
            or d.get("conversationId")
            or d.get("thread-id")
            or d.get("thread_id")
            or d.get("conversation_id")
        )
        if not sessao_bruta:
            return
        sessao = re.sub(r"[^A-Za-z0-9_-]", "_", str(sessao_bruta))[:100]
        if not sessao:
            return

        if evento_canonico == "Notification" and _so_esperando(d):
            return

        cwd = d.get("cwd") or ""
        if not cwd and isinstance(d.get("workspacePaths"), list) and d["workspacePaths"]:
            cwd = str(d["workspacePaths"][0]) or ""

        nome_proj = Path(cwd).name if cwd else "?"
        if not nome_proj:
            nome_proj = "?"
        tipo = "ajudante" if os.environ.get("MINI") == "ajudante" else "sessao"
        if "/.maestro/wt/" in cwd.replace("\\", "/"):
            tipo, nome_proj = "ajudante", "maestro"

        ferramenta = (
            d.get("tool_name")
            or (d.get("toolCall", {}).get("name") if isinstance(d.get("toolCall"), dict) else None)
            or d.get("toolName")
        )

        if os.environ.get("MINI") == "0":
            return

        payload = {
            "sessao": sessao,
            "evento": evento_canonico,
            "projeto": nome_proj,
            "ferramenta": ferramenta,
            "tipo": tipo,
        }
        if cli is not None:
            payload["cli"] = cli

        atividade = _detectar_atividade(evento_canonico, ferramenta, d)
        if atividade:
            payload["atividade"] = atividade

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
    except Exception:
        pass
    finally:
        _resposta_stdout(cli, evento_bruto)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        pass
    sys.exit(0)
