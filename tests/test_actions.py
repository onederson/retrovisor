import os
import subprocess
from pathlib import Path

import httpx
import psutil
import pytest
from pycaw.pycaw import AudioUtilities

from server import actions


def test_listar_acoes(monkeypatch):
    monkeypatch.setattr(actions.telas, "listar", lambda: [
        {"indice": 0, "nome": "Beyond TV", "ativo": True},
        {"indice": 1, "nome": "LG ULTRAGEAR", "ativo": False},
    ])
    cfg = {
        "ollama": {
            "url": "http://localhost:11434",
            "modelos": {
                "Qwen": "qwen3.6:35b-a3b-coding",
                "Gemma": "gemma4:12b-it-qat",
                "GPT-OSS": "gpt-oss:20b",
            },
        },
        "acoes": {},
        "caminhos": {"adb": "C:/platform-tools/adb.exe", "cache": "cache_inexistente_teste"},
    }
    lista = actions.listar(cfg)

    for item in lista:
        assert {"id", "rotulo", "descricao", "tela", "ativo"} <= set(item.keys())
        assert item["descricao"]

    tela2 = [item for item in lista if item["tela"] == 2]
    assert [item["id"] for item in tela2] == [
        "tela_so", "tela_duplicar", "tela_estender", "area_trabalho",
        "media_play", "media_proxima", "vol_down", "vol_up",
        "som_mudo", "mic_mute", "print", "gerenciador",
    ]
    tela4 = [item for item in lista if item["tela"] == 4]
    assert [item["id"] for item in tela4] == [
        "discord", "rocket_league", "explorador", "app_brave",
        "app_steam", "app_epicgames", "app_vscode", "app_obs",
        "app_telegram", "app_obsidian", "app_vlc", "app_livre",
    ]
    so = next(it for it in tela2 if it["id"] == "tela_so")
    assert so["opcoes"] == [
        {"id": "tela_so_0", "rotulo": "Só tela 1", "descricao": "Beyond TV"},
        {"id": "tela_so_1", "rotulo": "Só tela 2", "descricao": "LG ULTRAGEAR · desligada"},
    ]
    livre = next(it for it in tela4 if it["id"] == "app_livre")
    assert livre["escolhivel"] is True and livre["rotulo"] == "Escolher app"
    assert not any(item["id"] in ("omniroute_perfil", "abrir_ia", "git_status") for item in lista)

    tela3 = [item for item in lista if item["tela"] == 3]
    ids_tela3 = [item["id"] for item in tela3]
    for esperado in ("ollama_load_qwen", "ollama_load_gemma", "ollama_load_gptoss",
                     "ollama_ejetar", "tela_apagar"):
        assert esperado in ids_tela3

    item_qwen = next(it for it in tela3 if it["id"] == "ollama_load_qwen")
    assert item_qwen["rotulo"] == "Carregar Qwen"


def test_so_tela_por_indice(monkeypatch):
    chamadas = []
    monkeypatch.setattr(actions.telas, "so_tela", lambda i, **kw: chamadas.append(i) or {"ok": True, "msg": "x"})
    assert actions.executar("tela_so_2", {}, hub=None) == {"ok": True, "msg": "x"}
    assert chamadas == [2]
    assert actions.executar("tela_so", {}, hub=None)["ok"] is False  # a tecla em si nao executa nada
    assert actions.executar("tela_so_999", {}, hub=None)["ok"] is False


def test_modos_de_tela_e_discord(monkeypatch, tmp_path):
    popens = []
    monkeypatch.setattr(subprocess, "Popen", lambda args: popens.append(args))
    for acao, modo in (("tela_duplicar", "/clone"), ("tela_estender", "/extend")):
        assert actions.executar(acao, {}, hub=None)["ok"] is True
        assert popens[-1][0].endswith("DisplaySwitch.exe") and popens[-1][1] == modo

    focos = []

    def focar(exes, abrir, espera_s=12.0, **kw):
        focos.append(exes)
        abrir()
        return {"ok": True, "msg": "aberto"}

    monkeypatch.setattr(actions.janelas, "focar_ou_abrir", focar)
    upd = tmp_path / "Update.exe"
    upd.write_text("")
    assert actions.executar("discord", {"acoes": {"discord": str(upd)}}, hub=None)["ok"] is True
    assert focos[-1] == {"discord.exe"}
    assert popens[-1] == [str(upd), "--processStart", "Discord.exe"]
    res = actions.executar("discord", {"acoes": {"discord": str(tmp_path / "nada.exe")}}, hub=None)
    assert res["ok"] is False

    abertos = []
    monkeypatch.setattr(actions.os, "startfile", lambda alvo: abertos.append(alvo), raising=False)
    assert actions.executar("rocket_league", {}, hub=None)["ok"] is True
    assert focos[-1] == {"rocketleague.exe"} and abertos[-1] == "steam://rungameid/252950"


def test_app_livre(monkeypatch, tmp_path):
    atalho = tmp_path / "Spotify.lnk"
    atalho.write_text("")
    monkeypatch.setattr(actions.janelas, "catalogo", lambda: {"Spotify": atalho})
    monkeypatch.setattr(actions.janelas, "exe_do_atalho", lambda a: "spotify.exe")
    focos = []
    monkeypatch.setattr(actions.janelas, "focar_ou_abrir",
                        lambda exes, abrir, espera_s=12.0: focos.append(exes) or {"ok": True, "msg": "aberto"})
    cfg = {"caminhos": {"cache": str(tmp_path)}}

    assert actions.executar("app_livre", cfg, hub=None)["ok"] is False  # nada escolhido ainda
    assert actions.escolher_app(cfg, "C:/Windows/System32/cmd.exe")["ok"] is False  # so nomes do Menu Iniciar
    assert actions.escolher_app(cfg, "Spotify")["ok"] is True
    assert actions.executar("app_livre", cfg, hub=None) == {"ok": True, "msg": "Spotify aberto"}
    assert focos == [{"spotify.exe"}]
    livre = next(it for it in actions.listar(cfg) if it["id"] == "app_livre")
    assert livre["rotulo"] == "Spotify"


def test_id_desconhecido():
    cfg = {"ollama": {"modelos": {}}}
    res = actions.executar("desconhecido", cfg, hub=None)
    assert res == {"ok": False, "msg": "acao desconhecida"}


def test_ollama_ejetar(monkeypatch):
    cfg = {"ollama": {"url": "http://localhost:11434"}}

    class MockResp:
        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

        def raise_for_status(self):
            pass

    def mock_get(url, timeout):
        assert url == "http://localhost:11434/api/ps"
        assert timeout == 10
        return MockResp({"models": [{"name": "qwen"}, {"name": "gemma"}]})

    posts = []

    def mock_post(url, json, timeout):
        posts.append((url, json, timeout))
        return MockResp({})

    monkeypatch.setattr(httpx, "get", mock_get)
    monkeypatch.setattr(httpx, "post", mock_post)

    res = actions.executar("ollama_ejetar", cfg, hub=None)
    assert res["ok"] is True
    assert res["msg"] == "2 modelo(s) descarregado(s)"
    assert len(posts) == 2
    assert posts[0] == (
        "http://localhost:11434/api/generate",
        {"model": "qwen", "keep_alive": 0},
        10,
    )
    assert posts[1] == (
        "http://localhost:11434/api/generate",
        {"model": "gemma", "keep_alive": 0},
        10,
    )


def test_sessao_reset():
    cfg = {}

    class HubFalso:
        def reset_sessao(self):
            return "2026-11-17T01:30:00-03:00"

    hub = HubFalso()
    res = actions.executar("sessao_reset", cfg, hub)
    assert res["ok"] is True
    assert res["estado"]["sessao_inicio"] == "2026-11-17T01:30:00-03:00"


def test_media_play(monkeypatch):
    cfg = {}
    chamadas = []
    monkeypatch.setattr(actions, "_teclas", lambda *vks: chamadas.append(vks))

    res = actions.executar("media_play", cfg, hub=None)
    assert res["ok"] is True
    assert chamadas == [(0xB3,)]


def test_excecao_dentro_de_acao(monkeypatch):
    cfg = {}

    def falha(*args, **kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(actions, "_teclas", falha)
    res = actions.executar("vol_up", cfg, hub=None)
    assert res["ok"] is False
    assert "falha simulada" in res["msg"]


def test_omniroute_perfil():
    cfg = {}
    res = actions.executar("omniroute_perfil", cfg, hub=None)
    assert res == {"ok": False, "msg": "ainda nao configurado"}


def test_ollama_load(monkeypatch):
    cfg = {
        "ollama": {
            "url": "http://localhost:11434",
            "modelos": {"Qwen": "qwen3.6:35b-a3b-coding"},
        }
    }
    posts = []

    class MockResp:
        def raise_for_status(self):
            pass

    def mock_post(url, json, timeout):
        posts.append((url, json, timeout))
        return MockResp()

    monkeypatch.setattr(httpx, "post", mock_post)
    res = actions.executar("ollama_load_qwen", cfg, hub=None)
    assert res["ok"] is True
    assert res["msg"] == "qwen3.6:35b-a3b-coding carregado"
    assert posts == [
        (
            "http://localhost:11434/api/generate",
            {"model": "qwen3.6:35b-a3b-coding", "keep_alive": "30m"},
            120,
        )
    ]


def test_teclas_outras(monkeypatch):
    cfg = {}
    chamadas = []
    monkeypatch.setattr(actions, "_teclas", lambda *vks: chamadas.append(vks))

    res_print = actions.executar("print", cfg, hub=None)
    assert res_print["ok"] is True
    assert chamadas[-1] == (0x5B, 0x10, 0x53)

    res_down = actions.executar("vol_down", cfg, hub=None)
    assert res_down["ok"] is True
    assert chamadas[-1] == (0xAE,)

    res_up = actions.executar("vol_up", cfg, hub=None)
    assert res_up["ok"] is True
    assert chamadas[-1] == (0xAF,)


def test_teclas_pressionar_e_soltar(monkeypatch):
    eventos = []

    class MockUser32:
        def keybd_event(self, vk, scan, flags, extra):
            eventos.append((vk, flags))

    class MockWindll:
        user32 = MockUser32()

    monkeypatch.setattr("ctypes.windll", MockWindll(), raising=False)

    actions._teclas(0x5B, 0x10, 0x53)
    assert eventos == [
        (0x5B, 0),
        (0x10, 0),
        (0x53, 0),
        (0x53, 2),
        (0x10, 2),
        (0x5B, 2),
    ]


def test_abrir_ia_e_terminal_wsl(monkeypatch):
    cfg = {
        "acoes": {
            "terminal": "wt.exe",
            "git_repo": "C:/Projetos",
        }
    }
    popens = []
    monkeypatch.setattr(subprocess, "Popen", lambda args: popens.append(args))

    res_ia = actions.executar("abrir_ia", cfg, hub=None)
    assert res_ia["ok"] is True
    assert popens[0] == ["wt.exe", "-d", str(Path("C:/Projetos").expanduser())]

    res_wsl = actions.executar("terminal_wsl", cfg, hub=None)
    assert res_wsl["ok"] is True
    assert popens[1] == ["wt.exe", "wsl.exe"]


def test_git_status(monkeypatch):
    cfg = {"acoes": {"git_repo": "~/Projetos"}}

    class MockRun:
        def __init__(self, code, stdout, stderr):
            self.returncode = code
            self.stdout = stdout
            self.stderr = stderr

    # Sucesso: trunca para 6 linhas
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: MockRun(0, "l1\nl2\nl3\nl4\nl5\nl6\nl7\nl8\n", ""),
    )
    res = actions.executar("git_status", cfg, hub=None)
    assert res["ok"] is True
    assert res["msg"] == "l1\nl2\nl3\nl4\nl5\nl6"

    # Erro: usa stderr
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: MockRun(1, "", "erro1\nerro2\nerro3\n"),
    )
    res_err = actions.executar("git_status", cfg, hub=None)
    assert res_err["ok"] is False
    assert res_err["msg"] == "erro1\nerro2\nerro3"


def test_liberar_portas(monkeypatch):
    cfg = {"acoes": {"portas_dev": [3000, 8000]}}

    class MockAddr:
        def __init__(self, port):
            self.port = port

    class MockConn:
        def __init__(self, port, pid, status="LISTEN"):
            self.laddr = MockAddr(port)
            self.pid = pid
            self.status = status

    conns = [
        MockConn(3000, 1001),
        MockConn(8000, 1002),
        MockConn(5000, 1003),
        MockConn(3000, os.getpid()),
    ]
    monkeypatch.setattr(psutil, "net_connections", lambda kind: conns)

    terminados = []

    class MockProc:
        def __init__(self, pid):
            self.pid = pid

        def name(self):
            if self.pid == 1001:
                return "node.exe"
            if self.pid == 1002:
                return "python.exe"
            return "other.exe"

        def terminate(self):
            terminados.append(self.pid)

    monkeypatch.setattr(psutil, "Process", MockProc)

    res = actions.executar("liberar_portas", cfg, hub=None)
    assert res["ok"] is True
    assert res["msg"] == "2 processo(s) encerrado(s): 3000:node.exe, 8000:python.exe"
    assert terminados == [1001, 1002]


def test_tela_apagar(monkeypatch):
    cfg = {"caminhos": {"adb": "C:/tools/adb.exe"}}

    class MockRun:
        def __init__(self, code):
            self.returncode = code

    # Sucesso
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockRun(0))
    res = actions.executar("tela_apagar", cfg, hub=None)
    assert res == {"ok": True, "msg": "tela apagada"}

    # Retorno diferente de 0
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockRun(1))
    res_falha = actions.executar("tela_apagar", cfg, hub=None)
    assert res_falha == {"ok": True, "msg": "apague pelo painel"}

    # Excecao
    def erro(*args, **kwargs):
        raise FileNotFoundError("adb ausente")

    monkeypatch.setattr(subprocess, "run", erro)
    res_exc = actions.executar("tela_apagar", cfg, hub=None)
    assert res_exc == {"ok": True, "msg": "apague pelo painel"}


def test_mic_mute(monkeypatch):
    cfg = {}

    class MockEndpoint:
        def __init__(self):
            self.mudo = 0

        def GetMute(self):
            return self.mudo

        def SetMute(self, val, ctx):
            self.mudo = 1 if val else 0

    endpoint = MockEndpoint()

    class MockMic:
        def Activate(self, iid, clsctx, extra):
            return None

    monkeypatch.setattr(AudioUtilities, "GetMicrophone", lambda: MockMic())
    monkeypatch.setattr("server.actions.cast", lambda iface, ptr: endpoint)
    monkeypatch.setattr("comtypes.CoInitialize", lambda: None)
    monkeypatch.setattr("comtypes.CoUninitialize", lambda: None)

    # 1. Primeira chamada: muta
    res1 = actions.executar("mic_mute", cfg, hub=None)
    assert res1["ok"] is True
    assert res1["estado"]["mic_mudo"] is True
    assert endpoint.mudo == 1

    # 2. Segunda chamada: desmuta
    res2 = actions.executar("mic_mute", cfg, hub=None)
    assert res2["ok"] is True
    assert res2["estado"]["mic_mudo"] is False
    assert endpoint.mudo == 0

    # 3. Sem microfone
    monkeypatch.setattr(AudioUtilities, "GetMicrophone", lambda: None)
    res3 = actions.executar("mic_mute", cfg, hub=None)
    assert res3 == {"ok": False, "msg": "sem microfone"}
