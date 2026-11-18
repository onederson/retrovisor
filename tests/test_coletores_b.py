import json
import sqlite3
from datetime import datetime, timezone, timedelta
import httpx
import pytest

from server import config
from server.collectors import omniroute, claude, ollama


def test_omniroute(tmp_path, monkeypatch):
    cfg = config.carregar()
    db_file = tmp_path / "omniroute.sqlite"
    cfg["caminhos"]["omniroute_db"] = str(db_file)

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE call_logs (
            timestamp TEXT,
            status INTEGER,
            model TEXT,
            provider TEXT,
            duration INTEGER,
            tokens_in INTEGER,
            tokens_out INTEGER,
            combo_name TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE usage_history (
            timestamp TEXT,
            provider TEXT,
            model TEXT,
            tokens_input INTEGER,
            tokens_output INTEGER,
            provider_cost_usd REAL,
            success INTEGER
        )
        """
    )

    now_local = datetime.now().astimezone()
    now_utc = datetime.now(timezone.utc)

    # 1 connection-test hoje (ignorada)
    ts_conn = (now_utc - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    cur.execute(
        "INSERT INTO call_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ts_conn, 200, "connection-test", "prov", 100, 10, 10, None),
    )

    # 2 chamadas reais hoje (status 200 duration 1000; status 500 duration 3000)
    ts_call1 = (now_utc - timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    cur.execute(
        "INSERT INTO call_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ts_call1, 200, "gpt-4o", "openai", 1000, 100, 50, "default"),
    )
    ts_call2 = (now_utc - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    cur.execute(
        "INSERT INTO call_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ts_call2, 500, "claude-3-5", "anthropic", 3000, 200, 80, None),
    )

    # 1 de 40 dias atras
    ts_old = (now_utc - timedelta(days=40)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    cur.execute(
        "INSERT INTO call_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ts_old, 200, "gpt-4o", "openai", 500, 50, 50, None),
    )

    # usage_history com custo 0.01 hoje e 0.02 mais cedo no MESMO mes
    # (no dia 1 do mes use o proprio hoje, 1 minuto antes)
    ts_usage_today = (now_utc - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    cur.execute(
        "INSERT INTO usage_history VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts_usage_today, "openai", "gpt-4o", 100, 50, 0.01, 1),
    )

    if now_local.day == 1:
        ts_usage_earlier = (
            (now_local - timedelta(minutes=1))
            .astimezone(timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%S.000Z")
        )
        esperado_hoje = pytest.approx(0.03, abs=1e-4)
    else:
        earlier_month = now_local.replace(day=1, hour=12, minute=0, second=0, microsecond=0)
        ts_usage_earlier = earlier_month.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        esperado_hoje = pytest.approx(0.01, abs=1e-4)

    cur.execute(
        "INSERT INTO usage_history VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts_usage_earlier, "anthropic", "claude-3-5", 200, 80, 0.02, 1),
    )
    conn.commit()
    conn.close()

    class MockResp:
        status_code = 200

        def json(self):
            return {}

    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: MockResp())

    ctx = {}
    res = omniroute.collect(cfg, ctx)

    assert res["hoje"]["requisicoes"] == 2
    assert res["hoje"]["erros"] == 1
    assert res["hoje"]["taxa_acerto"] == 50.0
    assert res["hoje"]["latencia_media_ms"] == 2000
    assert res["custo_hoje_usd"] == esperado_hoje
    assert res["custo_mes_usd"] == pytest.approx(0.03, abs=1e-4)
    assert res["online"] is True
    assert res["ultima"] is not None
    assert res["ultima"]["modelo"] != "connection-test"
    assert res["ultima"]["modelo"] == "claude-3-5"


def test_claude(tmp_path):
    cfg = config.carregar()
    pasta_claude = tmp_path / "claude_projects"
    pasta_claude.mkdir()
    cfg["caminhos"]["claude_projects"] = str(pasta_claude)

    arquivo_jsonl = pasta_claude / "chat.jsonl"
    now_utc = datetime.now(timezone.utc)
    ts_now = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 3 linhas da MESMA resposta (mesmo message.id/requestId; modelo claude-opus-5-5;
    # usage input 10, output 100, cache_read 1000, cache_creation 2000 com
    # cache_creation.ephemeral_1h_input_tokens 2000; timestamp de agora)
    linha_opus = {
        "type": "assistant",
        "timestamp": ts_now,
        "requestId": "req_opus_1",
        "message": {
            "id": "msg_opus_1",
            "model": "claude-opus-5-5",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 100,
                "cache_read_input_tokens": 1000,
                "cache_creation_input_tokens": 2000,
                "cache_creation": {
                    "ephemeral_1h_input_tokens": 2000,
                },
            },
        },
    }

    # 1 resposta de claude-sonnet-5-5 (input 1, output 50)
    linha_sonnet = {
        "type": "assistant",
        "timestamp": ts_now,
        "requestId": "req_sonnet_1",
        "message": {
            "id": "msg_sonnet_1",
            "model": "claude-sonnet-5-5",
            "usage": {
                "input_tokens": 1,
                "output_tokens": 50,
            },
        },
    }

    with open(arquivo_jsonl, "w", encoding="utf-8") as f:
        f.write(json.dumps(linha_opus) + "\n")
        f.write(json.dumps(linha_opus) + "\n")
        f.write(json.dumps(linha_opus) + "\n")
        f.write(json.dumps(linha_sonnet) + "\n")

    ctx = {}
    res = claude.collect(cfg, ctx)

    # Checar o dedupe (hoje.output == 150, mensagens == 2)
    assert res["hoje"]["output"] == 150
    assert res["hoje"]["mensagens"] == 2

    # o custo da 1a resposta = (10*4 + 100*20 + 1000*0.20 + 2000*8)/1e6 somado ao da 2a (1*2 + 50*10)/1e6
    c1 = (10 * 4.0 + 100 * 20.0 + 1000 * 0.20 + 2000 * 8.0) / 1e6
    c2 = (1 * 2.0 + 50 * 10.0) / 1e6
    assert res["hoje"]["custo_equiv_usd"] == pytest.approx(round(c1 + c2, 4), abs=1e-4)

    # Checar janela5h com restante_s > 0
    assert res["janela5h"]["restante_s"] > 0
    assert res["janela5h"]["inicio"] is not None
    assert res["janela5h"]["fim"] is not None

    # Leitura incremental: acrescentar 1 linha nova e chamar collect com o MESMO ctx -> mensagens == 3
    linha_nova = {
        "type": "assistant",
        "timestamp": ts_now,
        "requestId": "req_opus_2",
        "message": {
            "id": "msg_opus_2",
            "model": "claude-opus-5-5",
            "usage": {
                "input_tokens": 5,
                "output_tokens": 20,
            },
        },
    }
    with open(arquivo_jsonl, "a", encoding="utf-8") as f:
        f.write(json.dumps(linha_nova) + "\n")

    res2 = claude.collect(cfg, ctx)
    assert res2["hoje"]["mensagens"] == 3


def test_ollama(tmp_path, monkeypatch):
    cfg = config.carregar()
    cfg["caminhos"]["maestro_historico"] = str(tmp_path / "historico.jsonl")

    # monkeypatch de httpx.get devolvendo um /api/ps de exemplo com 1 modelo (size_vram 2147483648 -> vram_gb 2.0)
    now_utc = datetime.now(timezone.utc)
    ts_expira = (now_utc + timedelta(seconds=240)).strftime("%Y-%m-%dT%H:%M:%SZ")

    class MockResp:
        status_code = 200

        def json(self):
            return {
                "models": [
                    {
                        "name": "qwen3-coder:30b",
                        "size_vram": 2147483648,
                        "expires_at": ts_expira,
                    }
                ]
            }

    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: MockResp())

    with open(cfg["caminhos"]["maestro_historico"], "w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "exec": "ollama/qwen3-coder:30b",
                    "data": "2026-11-17T10:00:00-03:00",
                    "segundos": 10.0,
                    "tokens_out": 543,
                }
            )
            + "\n"
        )

    ctx = {}
    res = ollama.collect(cfg, ctx)
    assert res["online"] is True
    assert len(res["modelos"]) == 1
    assert res["modelos"][0]["nome"] == "qwen3-coder:30b"
    assert res["modelos"][0]["vram_gb"] == 2.0
    assert res["modelos"][0]["expira_em_s"] > 0
    assert res["tokens_s"] == 54.3
    assert res["tokens_s_modelo"] == "ollama/qwen3-coder:30b"
    assert res["tokens_s_quando"] == "2026-11-17T10:00:00-03:00"

    # Caso de httpx.ConnectError -> online False
    def raise_connect_error(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx, "get", raise_connect_error)
    res_err = ollama.collect(cfg, ctx)
    assert res_err["online"] is False
    assert res_err["modelos"] == []


def test_omniroute_vazio(tmp_path, monkeypatch):
    cfg = config.carregar()
    db_file = tmp_path / "omniroute_vazio.sqlite"
    cfg["caminhos"]["omniroute_db"] = str(db_file)

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE call_logs (
            timestamp TEXT, status INTEGER, model TEXT, provider TEXT,
            duration INTEGER, tokens_in INTEGER, tokens_out INTEGER, combo_name TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE usage_history (
            timestamp TEXT, provider TEXT, model TEXT, tokens_input INTEGER,
            tokens_output INTEGER, provider_cost_usd REAL, success INTEGER
        )
        """
    )
    conn.commit()
    conn.close()

    def raise_error(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", raise_error)

    res = omniroute.collect(cfg, {})
    assert res["online"] is False
    assert res["ultima"] is None
    assert res["hoje"]["requisicoes"] == 0
    assert res["hoje"]["erros"] == 0
    assert res["hoje"]["taxa_acerto"] is None
    assert res["hoje"]["latencia_media_ms"] is None
    assert res["custo_hoje_usd"] == 0.0
    assert res["custo_mes_usd"] == 0.0
    assert res["historico"] == []


def test_claude_sem_arquivos(tmp_path):
    cfg = config.carregar()
    pasta = tmp_path / "claude_vazio"
    pasta.mkdir()
    cfg["caminhos"]["claude_projects"] = str(pasta)

    res = claude.collect(cfg, {})
    assert res["hoje"]["mensagens"] == 0
    assert res["janela5h"]["inicio"] is None
    assert res["janela5h"]["restante_s"] == 0
    assert res["ultimo_modelo"] is None


def test_claude_linha_sem_newline(tmp_path):
    cfg = config.carregar()
    pasta = tmp_path / "claude_nl"
    pasta.mkdir()
    cfg["caminhos"]["claude_projects"] = str(pasta)
    arquivo = pasta / "session.jsonl"

    linha = json.dumps({
        "type": "assistant",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "requestId": "req_1",
        "message": {
            "id": "msg_1",
            "model": "claude-haiku-5-5",
            "usage": {"input_tokens": 10, "output_tokens": 10},
        },
    })

    # Write without newline
    with open(arquivo, "wb") as f:
        f.write(linha.encode("utf-8"))

    ctx = {}
    res1 = claude.collect(cfg, ctx)
    assert res1["hoje"]["mensagens"] == 0

    # Add newline now
    with open(arquivo, "ab") as f:
        f.write(b"\n")

    res2 = claude.collect(cfg, ctx)
    assert res2["hoje"]["mensagens"] == 1


def test_ollama_sem_historico(tmp_path, monkeypatch):
    cfg = config.carregar()
    cfg["caminhos"]["maestro_historico"] = str(tmp_path / "inexistente.jsonl")

    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: None)

    res = ollama.collect(cfg, {})
    assert res["tokens_s"] is None
    assert res["tokens_s_modelo"] is None
    assert res["tokens_s_quando"] is None

