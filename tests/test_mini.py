import hashlib
import http.server
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import main
from server.mini import Mini


class RelogioFalso:
    def __init__(self, t0=1763560000.0):
        self.t = float(t0)

    def __call__(self):
        return self.t

    def avancar(self, segundos):
        self.t += segundos
        return self.t


def test_mapeamento_evento_ferramenta(tmp_path):
    tabela = [
        ("SessionStart", None, "ocioso"),
        ("UserPromptSubmit", None, "pensando"),
        ("PreToolUse", "Edit", "digitando"),
        ("PreToolUse", "Write", "digitando"),
        ("PreToolUse", "MultiEdit", "digitando"),
        ("PreToolUse", "NotebookEdit", "digitando"),
        ("PreToolUse", "Read", "lendo"),
        ("PreToolUse", "Grep", "lendo"),
        ("PreToolUse", "Glob", "lendo"),
        ("PreToolUse", "LS", "lendo"),
        ("PreToolUse", "WebFetch", "lendo"),
        ("PreToolUse", "WebSearch", "lendo"),
        ("PreToolUse", "Bash", "executando"),
        ("PreToolUse", "PowerShell", "executando"),
        ("PreToolUse", "Agent", "delegando"),
        ("PreToolUse", "Task", "delegando"),
        ("PreToolUse", "mcp__sqlite", "trabalhando"),
        ("PreToolUse", "outra_coisa", "trabalhando"),
        ("PreToolUse", None, "trabalhando"),
        ("PostToolUse", None, "pensando"),
        ("Notification", None, "precisa"),
        ("Stop", None, "concluido"),
    ]
    relogio = RelogioFalso()
    mini = Mini(tmp_path / "mini.json", relogio=relogio)
    for i, (evt, ferr, estado_esperado) in enumerate(tabela):
        sid = f"s_{i}"
        ok = mini.evento({"sessao": sid, "evento": evt, "ferramenta": ferr, "projeto": "proj"})
        assert ok is True
        snap = mini.snapshot()
        sessao_snap = next(s for s in snap["sessoes"] if s["id"] == hashlib.sha1(sid.encode()).hexdigest()[:6])
        assert sessao_snap["estado"] == estado_esperado


def test_validacao(tmp_path):
    relogio = RelogioFalso()
    mini = Mini(tmp_path / "mini.json", relogio=relogio)

    casos_invalidos = [
        "nao dict",
        123,
        None,
        {},
        {"evento": "SessionStart"},  # sem sessao
        {"sessao": "s/1", "evento": "SessionStart"},  # barra
        {"sessao": "a" * 101, "evento": "SessionStart"},  # 101 chars
        {"sessao": "s1", "evento": "Desconhecido"},  # evento desconhecido
    ]

    for dados in casos_invalidos:
        assert mini.evento(dados) is False
        assert mini.seq == 0


def test_desde_nao_muda_se_estado_repete(tmp_path):
    relogio = RelogioFalso(1763560000.0)
    mini = Mini(tmp_path / "mini.json", relogio=relogio)

    mini.evento({"sessao": "s1", "evento": "SessionStart"})
    desde_inicial = mini.snapshot()["sessoes"][0]["desde"]

    relogio.avancar(100)
    mini.evento({"sessao": "s1", "evento": "SessionStart"})
    snap = mini.snapshot()
    assert snap["sessoes"][0]["desde"] == desde_inicial

    relogio.avancar(50)
    mini.evento({"sessao": "s1", "evento": "UserPromptSubmit"})
    snap2 = mini.snapshot()
    assert snap2["sessoes"][0]["desde"] != desde_inicial


def test_stop_e_session_end(tmp_path):
    relogio = RelogioFalso(1763560000.0)
    mini = Mini(tmp_path / "mini.json", relogio=relogio)

    mini.evento({"sessao": "s1", "evento": "UserPromptSubmit"})
    mini.evento({"sessao": "s1", "evento": "Stop"})
    assert mini.snapshot()["hoje"]["concluidas"] == 1

    # Dois Stop seguidos contam 1
    mini.evento({"sessao": "s1", "evento": "Stop"})
    assert mini.snapshot()["hoje"]["concluidas"] == 1

    # Stop vindo de estado nao-ativo nao conta
    mini.evento({"sessao": "s2", "evento": "SessionStart"})
    mini.evento({"sessao": "s2", "evento": "Stop"})
    assert mini.snapshot()["hoje"]["concluidas"] == 1

    # SessionEnd remove
    mini.evento({"sessao": "s1", "evento": "SessionEnd"})
    snap = mini.snapshot()
    id_s1 = hashlib.sha1(b"s1").hexdigest()[:6]
    assert not any(s["id"] == id_s1 for s in snap["sessoes"])


def test_trabalhando_s_e_por_projeto(tmp_path):
    relogio = RelogioFalso(1763560000.0)
    mini = Mini(tmp_path / "mini.json", relogio=relogio)

    mini.evento({"sessao": "s1", "evento": "UserPromptSubmit", "projeto": "p1"})
    relogio.avancar(50)
    mini.evento({"sessao": "s1", "evento": "PreToolUse", "ferramenta": "Bash", "projeto": "p1"})
    assert mini.snapshot()["hoje"]["trabalhando_s"] == 50
    assert mini.snapshot()["hoje"]["por_projeto"]["p1"] == 50

    # Teto de 300 s
    relogio.avancar(400)
    mini.evento({"sessao": "s1", "evento": "PostToolUse", "projeto": "p1"})
    assert mini.snapshot()["hoje"]["trabalhando_s"] == 350
    assert mini.snapshot()["hoje"]["por_projeto"]["p1"] == 350

    # Outro projeto
    mini.evento({"sessao": "s2", "evento": "UserPromptSubmit", "projeto": "p2"})
    relogio.avancar(20)
    mini.evento({"sessao": "s2", "evento": "Stop", "projeto": "p2"})
    snap = mini.snapshot()
    assert snap["hoje"]["trabalhando_s"] == 370
    assert snap["hoje"]["por_projeto"]["p1"] == 350
    assert snap["hoje"]["por_projeto"]["p2"] == 20


def test_limpeza(tmp_path):
    relogio = RelogioFalso(1763560000.0)
    mini = Mini(tmp_path / "mini.json", relogio=relogio)

    # ativo + 11 min -> ocioso
    mini.evento({"sessao": "s1", "evento": "UserPromptSubmit"})
    relogio.avancar(11 * 60)
    snap = mini.snapshot()
    assert snap["sessoes"][0]["estado"] == "ocioso"

    # 31 min -> removida
    relogio.avancar(20 * 60)  # total 31 min desde o ultimo evento
    snap = mini.snapshot()
    assert len(snap["sessoes"]) == 0

    # concluido + 11 s -> ocioso
    mini.evento({"sessao": "s2", "evento": "Stop"})
    assert mini.snapshot()["sessoes"][0]["estado"] == "concluido"
    relogio.avancar(11)
    snap2 = mini.snapshot()
    assert snap2["sessoes"][0]["estado"] == "ocioso"


def test_virada_do_dia_e_persistencia(tmp_path):
    relogio = RelogioFalso(1763560000.0)
    arq = tmp_path / "mini.json"
    m1 = Mini(arq, relogio=relogio)

    m1.evento({"sessao": "s1", "evento": "UserPromptSubmit", "projeto": "projA"})
    relogio.avancar(30)
    m1.evento({"sessao": "s1", "evento": "Stop", "projeto": "projA"})

    snap = m1.snapshot()
    assert snap["hoje"]["concluidas"] == 1
    assert snap["hoje"]["trabalhando_s"] == 30
    assert snap["hoje"]["por_projeto"]["projA"] == 30

    # Novo Mini recarrega
    m2 = Mini(arq, relogio=relogio)
    snap2 = m2.snapshot()
    assert snap2["hoje"]["concluidas"] == 1
    assert snap2["hoje"]["trabalhando_s"] == 30
    assert snap2["hoje"]["por_projeto"]["projA"] == 30

    # Virada do dia zera
    relogio.avancar(86400)
    snap_virou = m1.snapshot()
    assert snap_virou["hoje"]["concluidas"] == 0
    assert snap_virou["hoje"]["trabalhando_s"] == 0
    assert snap_virou["hoje"]["por_projeto"] == {}

    # Arquivo corrompido nao quebra
    arq_ruim = tmp_path / "ruim.json"
    arq_ruim.write_text("nao e json valido {{{", encoding="utf-8")
    m3 = Mini(arq_ruim, relogio=relogio)
    snap3 = m3.snapshot()
    assert snap3["hoje"]["concluidas"] == 0


def test_limite_20_sessoes(tmp_path):
    relogio = RelogioFalso(1763560000.0)
    mini = Mini(tmp_path / "mini.json", relogio=relogio)

    for i in range(25):
        relogio.avancar(1)
        mini.evento({"sessao": f"s_{i:02d}", "evento": "SessionStart"})

    snap = mini.snapshot()
    assert len(snap["sessoes"]) == 20
    ids_atuais = {s["id"] for s in snap["sessoes"]}
    for i in range(5):
        id_i = hashlib.sha1(f"s_{i:02d}".encode()).hexdigest()[:6]
        assert id_i not in ids_atuais
    for i in range(5, 25):
        id_i = hashlib.sha1(f"s_{i:02d}".encode()).hexdigest()[:6]
        assert id_i in ids_atuais


def test_id_tem_6_caracteres_e_nao_e_session_id(tmp_path):
    relogio = RelogioFalso(1763560000.0)
    mini = Mini(tmp_path / "mini.json", relogio=relogio)
    sid = "sessao-longa-identificador-123"
    mini.evento({"sessao": sid, "evento": "SessionStart"})
    snap = mini.snapshot()
    item = snap["sessoes"][0]
    assert item["id"] != sid
    assert len(item["id"]) == 6
    assert item["id"] == hashlib.sha1(sid.encode("utf-8")).hexdigest()[:6]


def test_rota_mini_evento(monkeypatch):
    client = TestClient(main.app)

    # host nao local -> 403
    resp_403 = client.post("/mini/evento", json={"sessao": "s1", "evento": "SessionStart"})
    assert resp_403.status_code == 403

    # com _local liberado
    monkeypatch.setattr(main, "_local", lambda h: True)

    # corpo valido -> 200 e {"ok": true}
    resp_200 = client.post("/mini/evento", json={"sessao": "s1", "evento": "SessionStart"})
    assert resp_200.status_code == 200
    assert resp_200.json() == {"ok": True}

    # evento invalido -> 400
    resp_400 = client.post("/mini/evento", json={"sessao": "s1", "evento": "Invalido"})
    assert resp_400.status_code == 400

    # corpo de 5000 bytes -> 413
    resp_413 = client.post(
        "/mini/evento",
        content=b"x" * 5000,
        headers={"Content-Type": "application/json"},
    )
    assert resp_413.status_code == 413


def test_hook_mini(monkeypatch):
    corpos = []

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            tam = int(self.headers.get("Content-Length", 0))
            corpos.append(self.rfile.read(tam))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    porta = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        entrada = json.dumps({
            "session_id": "minha-sessao",
            "hook_event_name": "PreToolUse",
            "cwd": "C:/x/s10+",
            "tool_name": "Edit",
        }).encode("utf-8")

        # (a) confere os 5 campos, projeto == "s10+" para cwd = "C:/x/s10+"
        env = {**os.environ, "MINI_PORTA": str(porta), "MINI": "sessao"}
        r = subprocess.run(
            [sys.executable, "-I", "scripts/mini_hook.py"],
            input=entrada,
            capture_output=True,
            env=env,
            timeout=5,
        )
        assert r.returncode == 0
        assert len(corpos) == 1
        d = json.loads(corpos[0])
        assert d["sessao"] == "minha-sessao"
        assert d["evento"] == "PreToolUse"
        assert d["projeto"] == "s10+"
        assert d["ferramenta"] == "Edit"
        assert d["tipo"] == "sessao"

        # (b) MINI=0 -> servidor nao recebe nada
        corpos.clear()
        env_zero = {**os.environ, "MINI_PORTA": str(porta), "MINI": "0"}
        r_zero = subprocess.run(
            [sys.executable, "-I", "scripts/mini_hook.py"],
            input=entrada,
            capture_output=True,
            env=env_zero,
            timeout=5,
        )
        assert r_zero.returncode == 0
        assert len(corpos) == 0

        def rodar(d):
            corpos.clear()
            subprocess.run([sys.executable, "-I", "scripts/mini_hook.py"], input=json.dumps(d).encode(),
                           capture_output=True, env={**os.environ, "MINI_PORTA": str(porta), "MINI": "sessao"},
                           timeout=5)
            return [json.loads(c) for c in corpos]

        # (e) Notification de "esperando voce digitar" nao vira "precisa"; a de permissao vira
        base = {"session_id": "s1", "hook_event_name": "Notification", "cwd": "C:/x/s10+"}
        assert rodar({**base, "message": "Claude is waiting for your input"}) == []
        assert rodar({**base, "notification_type": "idle_prompt", "message": "x"}) == []
        assert len(rodar({**base, "message": "Claude needs your permission to use Bash"})) == 1

        # (f) tarefa do maestro (worktree) aparece como ajudante "maestro"
        enviado = rodar({"session_id": "s2", "hook_event_name": "Stop",
                         "cwd": "C:\\Users\\V\\.maestro\\wt\\20261119-0001"})
        assert enviado[0]["tipo"] == "ajudante" and enviado[0]["projeto"] == "maestro"
    finally:
        srv.shutdown()

    # (c) porta sem ninguem ouvindo -> codigo 0, stdout e stderr vazios, em menos de 2 s
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta_livre = s.getsockname()[1]
    s.close()

    t_inicio = time.time()
    env_fechado = {**os.environ, "MINI_PORTA": str(porta_livre)}
    env_fechado.pop("MINI", None)
    r_fechado = subprocess.run(
        [sys.executable, "-I", "scripts/mini_hook.py"],
        input=entrada,
        capture_output=True,
        env=env_fechado,
        timeout=5,
    )
    duracao = time.time() - t_inicio
    assert r_fechado.returncode == 0
    assert r_fechado.stdout == b""
    assert r_fechado.stderr == b""
    assert duracao < 2.0

    # (d) entrada que nao e JSON -> codigo 0, saida vazia
    r_invalido = subprocess.run(
        [sys.executable, "-I", "scripts/mini_hook.py"],
        input=b"isto nao e json valido",
        capture_output=True,
        timeout=5,
    )
    assert r_invalido.returncode == 0
    assert r_invalido.stdout == b""
    assert r_invalido.stderr == b""


def test_multi_cli_ferramentas_e_cli_snapshot(tmp_path):
    relogio = RelogioFalso()
    mini = Mini(tmp_path / "mini.json", relogio=relogio)

    ferramentas_esperadas = [
        ("edit_file", "digitando"),
        ("write_file", "digitando"),
        ("read_file", "lendo"),
        ("grep_search", "lendo"),
        ("run_command", "executando"),
        ("run_shell_command", "executando"),
        ("invoke_subagent", "delegando"),
        ("swarm", "delegando"),
        ("ask_question", "precisa"),
        ("bash", "executando"),
        ("patch", "digitando"),
    ]

    for ferr, estado_esperado in ferramentas_esperadas:
        sid = f"sess_{ferr}"
        ok = mini.evento({
            "sessao": sid,
            "evento": "PreToolUse",
            "ferramenta": ferr,
            "projeto": "proj",
        })
        assert ok is True
        snap = mini.snapshot()
        sid_hash = hashlib.sha1(sid.encode()).hexdigest()[:6]
        sessao_snap = next(s for s in snap["sessoes"] if s["id"] == sid_hash)
        assert sessao_snap["estado"] == estado_esperado

    # Case-insensitive
    mini.evento({"sessao": "s_case", "evento": "PreToolUse", "ferramenta": "EDIT_FILE"})
    s_case = next(s for s in mini.snapshot()["sessoes"] if s["id"] == hashlib.sha1(b"s_case").hexdigest()[:6])
    assert s_case["estado"] == "digitando"

    # Preservacao do campo cli
    mini.evento({"sessao": "s_cli", "evento": "UserPromptSubmit", "cli": "  AGY  "})
    snap_cli = mini.snapshot()
    s_cli = next(s for s in snap_cli["sessoes"] if s["id"] == hashlib.sha1(b"s_cli").hexdigest()[:6])
    assert s_cli["cli"] == "agy"

    # Evento subsequente sem cli preserva o cli anterior
    mini.evento({"sessao": "s_cli", "evento": "PreToolUse", "ferramenta": "edit_file"})
    snap_cli2 = mini.snapshot()
    s_cli2 = next(s for s in snap_cli2["sessoes"] if s["id"] == hashlib.sha1(b"s_cli").hexdigest()[:6])
    assert s_cli2["cli"] == "agy"
    assert s_cli2["estado"] == "digitando"


def test_hook_mini_agy():
    corpos = []

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            tam = int(self.headers.get("Content-Length", 0))
            corpos.append(self.rfile.read(tam))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    porta = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        # PreToolUse com camelCase
        entrada_pre = json.dumps({
            "conversationId": "conv-agy-1",
            "hookEventName": "PreToolUse",
            "workspacePaths": ["C:/workspace/proj1"],
            "toolCall": {"name": "read_file"},
        }).encode("utf-8")

        env = {**os.environ, "MINI_PORTA": str(porta), "MINI": "sessao"}
        r_pre = subprocess.run(
            [sys.executable, "-I", "scripts/mini_hook.py", "--cli", "agy"],
            input=entrada_pre,
            capture_output=True,
            env=env,
            timeout=5,
        )
        assert r_pre.returncode == 0
        assert json.loads(r_pre.stdout.decode()) == {"decision": "allow"}
        assert len(corpos) == 1
        d_pre = json.loads(corpos[0])
        assert d_pre["sessao"] == "conv-agy-1"
        assert d_pre["evento"] == "PreToolUse"
        assert d_pre["projeto"] == "proj1"
        assert d_pre["ferramenta"] == "read_file"
        assert d_pre["cli"] == "agy"

        # Outros eventos: Stop, PreInvocation, SessionStart, PostToolUse -> stdout {}
        for ev in ["Stop", "PreInvocation", "SessionStart", "PostToolUse"]:
            corpos.clear()
            entrada_ev = json.dumps({
                "conversationId": "conv-agy-1",
                "hookEventName": ev,
                "workspacePaths": ["C:/workspace/proj1"],
            }).encode("utf-8")
            r_ev = subprocess.run(
                [sys.executable, "-I", "scripts/mini_hook.py", "--cli", "agy"],
                input=entrada_ev,
                capture_output=True,
                env=env,
                timeout=5,
            )
            assert r_ev.returncode == 0
            assert json.loads(r_ev.stdout.decode()) == {}

        # MINI=0 -> servidor nao recebe, mas stdout ainda e emitido
        corpos.clear()
        env_zero = {**os.environ, "MINI_PORTA": str(porta), "MINI": "0"}
        r_zero = subprocess.run(
            [sys.executable, "-I", "scripts/mini_hook.py", "--cli", "agy"],
            input=entrada_pre,
            capture_output=True,
            env=env_zero,
            timeout=5,
        )
        assert r_zero.returncode == 0
        assert len(corpos) == 0
        assert json.loads(r_zero.stdout.decode()) == {"decision": "allow"}

    finally:
        srv.shutdown()

    # Servidor fechado -> ainda imprime JSON valido e sai 0
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta_livre = s.getsockname()[1]
    s.close()

    env_fechado = {**os.environ, "MINI_PORTA": str(porta_livre)}
    env_fechado.pop("MINI", None)
    r_fechado = subprocess.run(
        [sys.executable, "-I", "scripts/mini_hook.py", "--cli", "agy"],
        input=entrada_pre,
        capture_output=True,
        env=env_fechado,
        timeout=5,
    )
    assert r_fechado.returncode == 0
    assert json.loads(r_fechado.stdout.decode()) == {"decision": "allow"}
    assert r_fechado.stderr == b""


def test_hook_mini_gemini():
    corpos = []

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            tam = int(self.headers.get("Content-Length", 0))
            corpos.append(self.rfile.read(tam))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    porta = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        env = {**os.environ, "MINI_PORTA": str(porta), "MINI": "sessao"}
        casos = [
            ("BeforeAgent", "UserPromptSubmit", None),
            ("BeforeTool", "PreToolUse", "run_shell_command"),
            ("AfterTool", "PostToolUse", None),
            ("AfterAgent", "Stop", None),
        ]
        for evt_bruto, evt_esperado, ferr in casos:
            corpos.clear()
            dados = {
                "session_id": "gem-sess",
                "hook_event_name": evt_bruto,
                "cwd": "C:/projetos/meu_gemini",
            }
            if ferr:
                dados["tool_name"] = ferr

            r = subprocess.run(
                [sys.executable, "-I", "scripts/mini_hook.py", "--cli", "gemini"],
                input=json.dumps(dados).encode("utf-8"),
                capture_output=True,
                env=env,
                timeout=5,
            )
            assert r.returncode == 0
            assert json.loads(r.stdout.decode()) == {}
            assert len(corpos) == 1
            recebido = json.loads(corpos[0])
            assert recebido["evento"] == evt_esperado
            assert recebido["cli"] == "gemini"
            assert recebido["projeto"] == "meu_gemini"
            if ferr:
                assert recebido["ferramenta"] == ferr
    finally:
        srv.shutdown()


def test_hook_mini_codex():
    corpos = []

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            tam = int(self.headers.get("Content-Length", 0))
            corpos.append(self.rfile.read(tam))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    porta = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        env = {**os.environ, "MINI_PORTA": str(porta), "MINI": "sessao"}
        json_arg = json.dumps({
            "type": "agent-turn-complete",
            "thread-id": "th-1",
            "cwd": "C:/x/s10+",
        })
        r = subprocess.run(
            [sys.executable, "-I", "scripts/mini_hook.py", json_arg],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env=env,
            timeout=5,
        )
        assert r.returncode == 0
        assert r.stdout == b""
        assert len(corpos) == 1
        d = json.loads(corpos[0])
        assert d["sessao"] == "th-1"
        assert d["evento"] == "Stop"
        assert d["projeto"] == "s10+"
        assert d["cli"] == "codex"
    finally:
        srv.shutdown()


def test_instalar_vendel(tmp_path):
    # Simula ~/.claude, ~/.gemini/config (com hooks.json contendo ai-memory),
    # ~/.gemini/settings.json e ~/.config/opencode
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)

    gemini_config_dir = tmp_path / ".gemini" / "config"
    gemini_config_dir.mkdir(parents=True)
    hooks_json = gemini_config_dir / "hooks.json"
    hooks_json.write_text(json.dumps({"ai-memory": {"regras": ["r1"]}}, indent=2) + "\n", encoding="utf-8")

    gemini_settings = tmp_path / ".gemini" / "settings.json"
    gemini_settings.write_text(json.dumps({"tema": "escuro"}, indent=2) + "\n", encoding="utf-8")

    opencode_dir = tmp_path / ".config" / "opencode"
    opencode_dir.mkdir(parents=True)

    # 1. Instalação
    r1 = subprocess.run(
        [sys.executable, "-I", "scripts/instalar_vendel.py", "--home", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert r1.returncode == 0
    assert "Claude Code" in r1.stdout
    assert "Antigravity (agy)" in r1.stdout
    assert "Gemini CLI" in r1.stdout
    assert "OpenCode" in r1.stdout

    # Verifica Claude
    claude_settings = claude_dir / "settings.json"
    assert claude_settings.exists()
    claude_cfg = json.loads(claude_settings.read_text(encoding="utf-8"))
    assert "SessionStart" in claude_cfg["hooks"]
    assert "mini_hook.py" in claude_cfg["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "--cli claude" in claude_cfg["hooks"]["SessionStart"][0]["hooks"][0]["command"]

    # Verifica Antigravity (agy)
    agy_cfg = json.loads(hooks_json.read_text(encoding="utf-8"))
    assert agy_cfg["ai-memory"] == {"regras": ["r1"]}
    assert "vendel" in agy_cfg
    assert "SessionStart" in agy_cfg["vendel"]
    assert "PreToolUse" in agy_cfg["vendel"]
    assert "--cli agy" in agy_cfg["vendel"]["SessionStart"][0]["command"]
    assert (gemini_config_dir / "hooks.json.antes-do-vendel").exists()

    # Verifica Gemini CLI
    gem_cfg = json.loads(gemini_settings.read_text(encoding="utf-8"))
    assert gem_cfg["tema"] == "escuro"
    assert "hooks" in gem_cfg
    assert "BeforeTool" in gem_cfg["hooks"]
    assert gem_cfg["hooks"]["BeforeTool"][0]["matcher"] == ".*"
    assert gem_cfg["hooks"]["BeforeTool"][0]["hooks"][0]["timeout"] == 5000
    assert "--cli gemini" in gem_cfg["hooks"]["BeforeTool"][0]["hooks"][0]["command"]
    assert (tmp_path / ".gemini" / "settings.json.antes-do-vendel").exists()

    # Verifica OpenCode
    plugin_js = opencode_dir / "plugins" / "vendel.js"
    assert plugin_js.exists()
    assert "export const VendelPlugin" in plugin_js.read_text(encoding="utf-8")

    # 2. Idempotência: rodar 2x
    r2 = subprocess.run(
        [sys.executable, "-I", "scripts/instalar_vendel.py", "--home", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert r2.returncode == 0
    claude_cfg2 = json.loads(claude_settings.read_text(encoding="utf-8"))
    assert len(claude_cfg2["hooks"]["SessionStart"]) == 1
    gem_cfg2 = json.loads(gemini_settings.read_text(encoding="utf-8"))
    assert len(gem_cfg2["hooks"]["SessionStart"]) == 1
    agy_cfg2 = json.loads(hooks_json.read_text(encoding="utf-8"))
    assert agy_cfg2["ai-memory"] == {"regras": ["r1"]}
    assert "vendel" in agy_cfg2

    # 3. Remoção limpa com --remover
    r3 = subprocess.run(
        [sys.executable, "-I", "scripts/instalar_vendel.py", "--home", str(tmp_path), "--remover"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert r3.returncode == 0
    assert "desligado de" in r3.stdout

    # Claude: sem hooks do vendel
    claude_cfg3 = json.loads(claude_settings.read_text(encoding="utf-8"))
    assert "hooks" not in claude_cfg3 or not claude_cfg3["hooks"]

    # Antigravity: "vendel" removido, "ai-memory" preservado
    agy_cfg3 = json.loads(hooks_json.read_text(encoding="utf-8"))
    assert "vendel" not in agy_cfg3
    assert agy_cfg3["ai-memory"] == {"regras": ["r1"]}

    # Gemini: hooks do vendel removidos, "tema" preservado
    gem_cfg3 = json.loads(gemini_settings.read_text(encoding="utf-8"))
    assert gem_cfg3.get("tema") == "escuro"
    assert "hooks" not in gem_cfg3 or not gem_cfg3["hooks"]

    # OpenCode: vendel.js removido
    assert not plugin_js.exists()


def test_mini_atividade_server(tmp_path):
    relogio = RelogioFalso()
    mini = Mini(tmp_path / "mini.json", relogio=relogio)

    # 1. Inferencia automatica no PreToolUse sem atividade
    # WebSearch -> estado="lendo", atividade="pescando"
    mini.evento({"sessao": "s_web", "evento": "PreToolUse", "ferramenta": "WebSearch"})
    snap = mini.snapshot()
    s = next(x for x in snap["sessoes"] if x["id"] == hashlib.sha1(b"s_web").hexdigest()[:6])
    assert s["estado"] == "lendo"
    assert s["atividade"] == "pescando"

    # Glob -> estado="lendo", atividade="bibliotecario"
    mini.evento({"sessao": "s_glob", "evento": "PreToolUse", "ferramenta": "Glob"})
    snap = mini.snapshot()
    s = next(x for x in snap["sessoes"] if x["id"] == hashlib.sha1(b"s_glob").hexdigest()[:6])
    assert s["estado"] == "lendo"
    assert s["atividade"] == "bibliotecario"

    # Bash -> estado="executando", atividade="academia"
    mini.evento({"sessao": "s_bash", "evento": "PreToolUse", "ferramenta": "Bash"})
    snap = mini.snapshot()
    s = next(x for x in snap["sessoes"] if x["id"] == hashlib.sha1(b"s_bash").hexdigest()[:6])
    assert s["estado"] == "executando"
    assert s["atividade"] == "academia"

    # 2. Passagem explicita de atividade="testando" seguida de PostToolUse sem erro -> atividade="teste_ok"
    mini.evento({"sessao": "s_test", "evento": "PreToolUse", "ferramenta": "Bash", "atividade": "testando"})
    snap = mini.snapshot()
    s = next(x for x in snap["sessoes"] if x["id"] == hashlib.sha1(b"s_test").hexdigest()[:6])
    assert s["estado"] == "executando"
    assert s["atividade"] == "testando"

    mini.evento({"sessao": "s_test", "evento": "PostToolUse"})
    snap = mini.snapshot()
    s = next(x for x in snap["sessoes"] if x["id"] == hashlib.sha1(b"s_test").hexdigest()[:6])
    assert s["estado"] == "pensando"
    assert s["atividade"] == "teste_ok"

    # 3. PostToolUse com atividade="erro" e atividade="cooldown"
    mini.evento({"sessao": "s_err", "evento": "PreToolUse", "ferramenta": "Bash", "atividade": "testando"})
    mini.evento({"sessao": "s_err", "evento": "PostToolUse", "atividade": "erro"})
    snap = mini.snapshot()
    s = next(x for x in snap["sessoes"] if x["id"] == hashlib.sha1(b"s_err").hexdigest()[:6])
    assert s["atividade"] == "erro"

    mini.evento({"sessao": "s_cd", "evento": "PreToolUse", "ferramenta": "Bash", "atividade": "pescando"})
    mini.evento({"sessao": "s_cd", "evento": "PostToolUse", "atividade": "cooldown"})
    snap = mini.snapshot()
    s = next(x for x in snap["sessoes"] if x["id"] == hashlib.sha1(b"s_cd").hexdigest()[:6])
    assert s["atividade"] == "cooldown"

    # 4. Rejeicao de atividade invalida (ignorada como None)
    # Com ferramenta sem fallback: Edit -> atividade fica None
    mini.evento({"sessao": "s_inv1", "evento": "PreToolUse", "ferramenta": "Edit", "atividade": "valor_invalido_xyz"})
    snap = mini.snapshot()
    s = next(x for x in snap["sessoes"] if x["id"] == hashlib.sha1(b"s_inv1").hexdigest()[:6])
    assert s["estado"] == "digitando"
    assert s["atividade"] is None

    # Com ferramenta com fallback: Bash -> atividade invalida ignorada, fallback aplica "academia"
    mini.evento({"sessao": "s_inv2", "evento": "PreToolUse", "ferramenta": "Bash", "atividade": "valor_invalido_xyz"})
    snap = mini.snapshot()
    s = next(x for x in snap["sessoes"] if x["id"] == hashlib.sha1(b"s_inv2").hexdigest()[:6])
    assert s["estado"] == "executando"
    assert s["atividade"] == "academia"

    # Em PostToolUse com atividade invalida (e sem sessao anterior de testando) -> None
    mini.evento({"sessao": "s_inv3", "evento": "PostToolUse", "atividade": "valor_invalido_xyz"})
    snap = mini.snapshot()
    s = next(x for x in snap["sessoes"] if x["id"] == hashlib.sha1(b"s_inv3").hexdigest()[:6])
    assert s["atividade"] is None

    # 5. Limpeza de atividade em Stop, SessionStart, UserPromptSubmit, Notification
    for evt in ["Stop", "UserPromptSubmit", "Notification", "SessionStart"]:
        mini.evento({"sessao": f"s_limpa_{evt}", "evento": "PreToolUse", "ferramenta": "Bash", "atividade": "testando"})
        mini.evento({"sessao": f"s_limpa_{evt}", "evento": evt})
        snap = mini.snapshot()
        s = next(x for x in snap["sessoes"] if x["id"] == hashlib.sha1(f"s_limpa_{evt}".encode()).hexdigest()[:6])
        assert s["atividade"] is None


def test_mini_hook_atividade_classificacao_e_privacidade(monkeypatch):
    from scripts.mini_hook import _detectar_atividade

    # 1. Classificacao unitaria em _detectar_atividade
    # pytest -> "testando"
    assert _detectar_atividade("PreToolUse", "bash", {"tool_input": {"command": "pytest -q"}}) == "testando"
    assert _detectar_atividade("PreToolUse", "powershell", {"tool_input": "npm test"}) == "testando"
    assert _detectar_atividade("PreToolUse", "run_command", {"arguments": {"CommandLine": "vitest run"}}) == "testando"

    # git push -> "enviando"
    assert _detectar_atividade("PreToolUse", "bash", {"tool_input": {"command": "git push origin main"}}) == "enviando"
    assert _detectar_atividade("PreToolUse", "bash", {"tool_input": {"command": "git commit -m 'feat'"}}) == "enviando"
    assert _detectar_atividade("PreToolUse", "bash", {"tool_input": {"command": "gh pr create --title foo"}}) == "enviando"

    # arquiteto
    assert _detectar_atividade("PreToolUse", "plan", {}) == "arquiteto"
    assert _detectar_atividade("PreToolUse", "bash", {"tool_input": {"command": "mkdir src"}}) == "arquiteto"

    # pescando e bibliotecario
    assert _detectar_atividade("PreToolUse", "websearch", {}) == "pescando"
    assert _detectar_atividade("PreToolUse", "glob", {}) == "bibliotecario"

    # PostToolUse com is_error: True -> "erro"
    assert _detectar_atividade("PostToolUse", None, {"is_error": True}) == "erro"
    assert _detectar_atividade("PostToolUse", None, {"exit_code": 1}) == "erro"
    assert _detectar_atividade("PostToolUse", None, {"tool_response": {"is_error": True}}) == "erro"

    # PostToolUse com "429 Too Many Requests" -> "cooldown"
    assert _detectar_atividade("PostToolUse", None, {"error": "Error: 429 Too Many Requests"}) == "cooldown"
    assert _detectar_atividade("PostToolUse", None, {"tool_response": "Rate limit reached. Quota exceeded."}) == "cooldown"
    assert _detectar_atividade("PostToolUse", None, {"result": "retry-after: 30"}) == "cooldown"

    # 2. Teste ponta a ponta com subprocess garantindo que comando bruto NUNCA vaza no payload
    corpos = []

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            tam = int(self.headers.get("Content-Length", 0))
            corpos.append(self.rfile.read(tam))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    porta = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        env = {**os.environ, "MINI_PORTA": str(porta), "MINI": "sessao"}

        # Caso A: pytest com comando potencialmente sensivel
        comando_sensivel = "pytest tests/test_segredo.py --token=SUPER_SECRET_TOKEN_XYZ_123"
        entrada_pytest = json.dumps({
            "session_id": "sess-priv-1",
            "hook_event_name": "PreToolUse",
            "cwd": "C:/projetos/meu_app",
            "tool_name": "Bash",
            "tool_input": {"command": comando_sensivel},
        }).encode("utf-8")

        r = subprocess.run(
            [sys.executable, "-I", "scripts/mini_hook.py"],
            input=entrada_pytest,
            capture_output=True,
            env=env,
            timeout=5,
        )
        assert r.returncode == 0
        assert len(corpos) == 1
        d = json.loads(corpos[0])
        assert d["sessao"] == "sess-priv-1"
        assert d["evento"] == "PreToolUse"
        assert d["ferramenta"] == "Bash"
        assert d["atividade"] == "testando"
        # Regra critica de privacidade: NUNCA enviar comando bruto nem partes sensiveis
        payload_str = corpos[0].decode("utf-8")
        assert "SUPER_SECRET_TOKEN_XYZ_123" not in payload_str
        assert "test_segredo.py" not in payload_str
        assert "command" not in d
        assert "tool_input" not in d

        # Caso B: git push
        corpos.clear()
        entrada_git = json.dumps({
            "session_id": "sess-priv-2",
            "hook_event_name": "PreToolUse",
            "cwd": "C:/projetos/meu_app",
            "tool_name": "bash",
            "tool_input": {"command": "git push origin main"},
        }).encode("utf-8")
        r_git = subprocess.run(
            [sys.executable, "-I", "scripts/mini_hook.py"],
            input=entrada_git,
            capture_output=True,
            env=env,
            timeout=5,
        )
        assert r_git.returncode == 0
        assert len(corpos) == 1
        d_git = json.loads(corpos[0])
        assert d_git["atividade"] == "enviando"
        assert "git push origin main" not in corpos[0].decode("utf-8")

        # Caso C: PostToolUse com is_error: True
        corpos.clear()
        entrada_erro = json.dumps({
            "session_id": "sess-priv-3",
            "hook_event_name": "PostToolUse",
            "cwd": "C:/projetos/meu_app",
            "is_error": True,
            "tool_response": "detalhes internos confidenciais",
        }).encode("utf-8")
        r_err = subprocess.run(
            [sys.executable, "-I", "scripts/mini_hook.py"],
            input=entrada_erro,
            capture_output=True,
            env=env,
            timeout=5,
        )
        assert r_err.returncode == 0
        assert len(corpos) == 1
        d_err = json.loads(corpos[0])
        assert d_err["atividade"] == "erro"
        assert "detalhes internos confidenciais" not in corpos[0].decode("utf-8")

        # Caso D: PostToolUse com "429 Too Many Requests"
        corpos.clear()
        entrada_cooldown = json.dumps({
            "session_id": "sess-priv-4",
            "hook_event_name": "PostToolUse",
            "cwd": "C:/projetos/meu_app",
            "error": "HTTP 429 Too Many Requests: quota exceeded",
        }).encode("utf-8")
        r_cd = subprocess.run(
            [sys.executable, "-I", "scripts/mini_hook.py"],
            input=entrada_cooldown,
            capture_output=True,
            env=env,
            timeout=5,
        )
        assert r_cd.returncode == 0
        assert len(corpos) == 1
        d_cd = json.loads(corpos[0])
        assert d_cd["atividade"] == "cooldown"
        assert "HTTP 429 Too Many Requests: quota exceeded" not in corpos[0].decode("utf-8")

    finally:
        srv.shutdown()
