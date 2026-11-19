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
