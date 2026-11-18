from datetime import datetime, timedelta
import json
from pathlib import Path
import pytest
from server import config
from server.collectors import agy, celular, fx, hardware


def test_parse_usage():
    fixture_path = Path(__file__).parent / "fixtures" / "agy_usage.txt"
    texto = fixture_path.read_text(encoding="utf-8")
    itens = agy.parse_usage(texto)
    assert len(itens) == 5
    assert itens[0]["grupo"] == "Gemini Models"
    assert itens[0]["limite"] == "Weekly Limit Remaining"
    assert itens[0]["restante_pct"] == 30
    assert itens[0]["reset"] == "2026-11-21T13:17:46Z"


def test_parse_dumpsys():
    texto = """Current Battery Service state:
  AC powered: false
  USB powered: false
  Wireless powered: false
  Max charging current: 500000
  level: 91
  scale: 100
  voltage: 4123
  temperature: 320
  technology: Li-ion"""
    res = celular.parse_dumpsys(texto)
    assert res["nivel"] == 91
    assert res["temp_c"] == 32.0
    assert res["carregando"] is False
    assert res["fonte"] == "adb"


def test_agy_collect(tmp_path, monkeypatch):
    def mock_run(*args, **kwargs):
        raise FileNotFoundError("agy not found")

    monkeypatch.setattr(agy.subprocess, "run", mock_run)

    cfg = config.carregar()
    hist_file = tmp_path / "historico.jsonl"
    estado_file = tmp_path / "estado.json"
    cfg["caminhos"]["maestro_historico"] = str(hist_file)
    cfg["caminhos"]["maestro_estado"] = str(estado_file)

    hoje = datetime.now().astimezone().strftime("%Y-%m-%d")
    ontem = (datetime.now().astimezone() - timedelta(days=1)).strftime("%Y-%m-%d")

    linhas = [
        json.dumps({"exec": "agy-flash", "data": f"{hoje}T10:00:00", "tokens_in": 100, "tokens_out": 10}),
        json.dumps({"exec": "agy-pro", "data": f"{hoje}T11:00:00", "tokens_in": 200, "tokens_out": 20}),
        json.dumps({"exec": "agy-flash", "data": f"{ontem}T10:00:00", "tokens_in": 500, "tokens_out": 50}),
        json.dumps({"exec": "ollama-x", "data": f"{hoje}T12:00:00", "tokens_in": 1000, "tokens_out": 100}),
    ]
    hist_file.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    estado_file.write_text(json.dumps({"esgotado": {"omni-free-code": True}}), encoding="utf-8")

    ctx = {}
    resultado = agy.collect(cfg, ctx)
    assert resultado["maestro_hoje"] == {"chamadas": 2, "tokens_in": 300, "tokens_out": 30}
    assert resultado["fonte"] == "maestro"
    assert resultado["limites"] == []
    assert resultado["atualizado"] is None
    assert resultado["esgotados"] == ["omni-free-code"]


def test_fx_collect(tmp_path, monkeypatch):
    cfg = config.carregar()
    cfg["caminhos"]["cache"] = str(tmp_path / "cache")

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"USDBRL": {"bid": "5.40"}}

    chamada = 0

    def mock_get(url, **kwargs):
        nonlocal chamada
        chamada += 1
        if chamada == 1:
            return MockResponse()
        raise Exception("Rede indisponivel")

    monkeypatch.setattr(fx.httpx, "get", mock_get)

    ctx = {}
    # 1a chamada: sucesso, grava cache
    res1 = fx.collect(cfg, ctx)
    assert res1["usd_brl"] == 5.40
    assert (tmp_path / "cache" / "fx.json").exists()

    # 2a chamada: falha de rede, recupera do cache
    res2 = fx.collect(cfg, ctx)
    assert res2["usd_brl"] == 5.40
    assert res2["atualizado"] == res1["atualizado"]


def test_hardware_collect():
    cfg = config.carregar()
    ctx = {}
    chaves_esperadas = {
        "cpu_pct",
        "cpu_temp",
        "ram_pct",
        "ram_usado_gb",
        "ram_total_gb",
        "gpu_nome",
        "gpu_pct",
        "gpu_temp",
        "vram_usado_gb",
        "vram_total_gb",
        "rede_down_kbps",
        "rede_up_kbps",
    }

    res1 = hardware.collect(cfg, ctx)
    assert chaves_esperadas <= set(res1.keys())
    assert res1["rede_down_kbps"] == 0.0
    assert res1["rede_up_kbps"] == 0.0
    assert isinstance(res1["cpu_pct"], (int, float))
    assert isinstance(res1["ram_pct"], (int, float))
    assert isinstance(res1["ram_usado_gb"], (int, float))
    assert isinstance(res1["ram_total_gb"], (int, float))

    res2 = hardware.collect(cfg, ctx)
    assert chaves_esperadas <= set(res2.keys())
    assert isinstance(res2["rede_down_kbps"], (int, float))
    assert isinstance(res2["rede_up_kbps"], (int, float))


def test_celular_collect(monkeypatch):
    cfg = config.carregar()

    class MockProcessOk:
        returncode = 0
        stdout = "  level: 91\n  temperature: 320\n  AC powered: true\n"

    monkeypatch.setattr(celular.subprocess, "run", lambda *args, **kwargs: MockProcessOk())
    ctx = {}
    res = celular.collect(cfg, ctx)
    assert res["nivel"] == 91
    assert res["temp_c"] == 32.0
    assert res["carregando"] is True
    assert res["fonte"] == "adb"

    def mock_falha(*args, **kwargs):
        raise FileNotFoundError("adb")

    monkeypatch.setattr(celular.subprocess, "run", mock_falha)
    ctx = {"bateria_browser": {"nivel": 80, "carregando": False}}
    res = celular.collect(cfg, ctx)
    assert res["nivel"] == 80
    assert res["temp_c"] is None
    assert res["carregando"] is False
    assert res["fonte"] == "browser"

    ctx = {}
    res = celular.collect(cfg, ctx)
    assert res["nivel"] is None
    assert res["temp_c"] is None
    assert res["carregando"] is None
    assert res["fonte"] == "nenhuma"
