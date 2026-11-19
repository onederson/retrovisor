import json
import pytest

from server import humor, main
from server.mini import Mini


class RelogioFalso:
    def __init__(self, t0=1763560000.0):
        self.t = float(t0)

    def __call__(self):
        return self.t

    def avancar(self, segundos):
        self.t += segundos
        return self.t


def test_nivel():
    assert humor.nivel(0) == 1
    assert humor.nivel(1) == 1
    assert humor.nivel(4) == 1
    assert humor.nivel(5) == 2
    assert humor.nivel(19) == 2
    assert humor.nivel(20) == 3
    assert humor.nivel(44) == 3
    assert humor.nivel(45) == 4
    assert humor.nivel(-5) == 1


def test_extras():
    # Nenhum atingido
    res = humor.calcular(12, 0, 0, 0, 0, None, None)
    assert res["extras"] == []

    res = humor.calcular(12, 0, 0, 0, 0, 79.9, 79.9)
    assert res["extras"] == []

    # Cansado
    res = humor.calcular(12, 0, 0, 0, 0, 80.0, 50.0)
    assert res["extras"] == ["cansado"]

    # Calor
    res = humor.calcular(12, 0, 0, 0, 0, 50.0, 80.0)
    assert res["extras"] == ["calor"]

    # Ambos
    res = humor.calcular(12, 0, 0, 0, 0, 85.0, 85.0)
    assert res["extras"] == ["cansado", "calor"]


def test_energia_faixas_de_hora():
    # 9h às 17h59 -> 1.0 (cansado -> 0.8)
    for h in [9, 12, 17]:
        assert humor.calcular(h, 0, 0, 0, 0, None, None)["energia"] == 1.0
        assert humor.calcular(h, 0, 0, 0, 0, 80, None)["energia"] == 0.8

    # 18h às 22h59 -> 0.6 (cansado -> 0.4)
    for h in [18, 20, 22]:
        assert humor.calcular(h, 0, 0, 0, 0, None, None)["energia"] == 0.6
        assert humor.calcular(h, 0, 0, 0, 0, 80, None)["energia"] == 0.4

    # 23h às 5h59 -> 0.25 (cansado -> 0.05)
    for h in [23, 0, 3, 5]:
        assert humor.calcular(h, 0, 0, 0, 0, None, None)["energia"] == 0.25
        assert humor.calcular(h, 0, 0, 0, 0, 80, None)["energia"] == 0.05

    # 6h às 8h59 -> 0.5 (cansado -> 0.3)
    for h in [6, 7, 8]:
        assert humor.calcular(h, 0, 0, 0, 0, None, None)["energia"] == 0.5
        assert humor.calcular(h, 0, 0, 0, 0, 80, None)["energia"] == 0.3


def test_alegria_com_e_sem_queda():
    # Sem queda (> 240 em ambos)
    # 0 tarefas, 0 carinhos -> 0.4
    assert humor.calcular(12, 0, 0, 0, 0, None, None)["alegria"] == 0.4
    # 2 tarefas (+0.1), 1 carinho (+0.1) -> 0.6
    assert humor.calcular(12, 0, 0, 2, 1, None, None)["alegria"] == 0.6
    # Limite superior 1.0
    assert humor.calcular(12, 0, 0, 10, 5, None, None)["alegria"] == 1.0

    # Limites estritos: 240 exato não aplica queda
    assert humor.calcular(12, 240, 240, 0, 0, None, None)["alegria"] == 0.4
    assert humor.calcular(12, 241, 240, 0, 0, None, None)["alegria"] == 0.4
    assert humor.calcular(12, 240, 241, 0, 0, None, None)["alegria"] == 0.4

    # Com queda: ambos > 240 -> -0.3
    assert humor.calcular(12, 241, 241, 0, 0, None, None)["alegria"] == 0.1
    # Com valor alto: 1.0 - 0.3 -> 0.7
    assert humor.calcular(12, 300, 300, 10, 5, None, None)["alegria"] == 0.7


def test_estado_regras_precedencia():
    # 1. Madrugada (hora >= 23 ou < 6) -> sonolento
    res = humor.calcular(23, 10, 10, 20, 10, None, None)
    assert res["estado"] == "sonolento"
    assert res["motivo"] == "é madrugada, tô com sono"

    res = humor.calcular(4, 300, 300, 0, 0, None, None)
    assert res["estado"] == "sonolento"

    # 2. Carente (min_sem_toque > 240 e min_sem_claude > 240)
    res = humor.calcular(12, 241, 241, 20, 10, None, None)
    assert res["estado"] == "carente"
    assert res["motivo"] == "faz tempo que você não aparece"

    # 3. Concluídas hoje >= 10 -> animado
    res = humor.calcular(12, 50, 50, 10, 2, None, None)
    assert res["estado"] == "animado"
    assert res["motivo"] == "dia produtivo: 10 tarefas"

    res = humor.calcular(12, 50, 50, 15, 2, None, None)
    assert res["estado"] == "animado"
    assert res["motivo"] == "dia produtivo: 15 tarefas"

    # 4. Carinhos hoje >= 5 -> animado
    res = humor.calcular(12, 50, 50, 5, 5, None, None)
    assert res["estado"] == "animado"
    assert res["motivo"] == "ganhei muito carinho hoje"

    # 5. Min sem claude < 30 -> curioso
    res = humor.calcular(12, 50, 29.9, 0, 0, None, None)
    assert res["estado"] == "curioso"
    assert res["motivo"] == "tem coisa acontecendo"

    # 6. Senão -> tranquilo
    res = humor.calcular(12, 50, 30.0, 0, 0, None, None)
    assert res["estado"] == "tranquilo"
    assert res["motivo"] == "tudo calmo"


def test_mini_snapshot_tem_vida(tmp_path):
    relogio = RelogioFalso(1763560000.0)
    mini = Mini(tmp_path / "mini.json", relogio=relogio)
    snap = mini.snapshot()
    assert "vida" in snap
    vida = snap["vida"]
    assert vida["nivel"] == 1
    assert vida["total_concluidas"] == 0
    assert vida["carinhos_hoje"] == 0
    assert vida["min_sem_toque"] == 0.0
    assert vida["min_sem_claude"] == 0.0


def test_mini_total_concluidas_e_virada_do_dia(tmp_path):
    relogio = RelogioFalso(1763560000.0)
    arq = tmp_path / "mini.json"
    m = Mini(arq, relogio=relogio)

    m.evento({"sessao": "s1", "evento": "UserPromptSubmit", "projeto": "p1"})
    m.evento({"sessao": "s1", "evento": "Stop", "projeto": "p1"})
    m.carinho()

    snap = m.snapshot()
    assert snap["hoje"]["concluidas"] == 1
    assert snap["vida"]["total_concluidas"] == 1
    assert snap["vida"]["carinhos_hoje"] == 1

    # Virada do dia
    relogio.avancar(86400)
    snap_virou = m.snapshot()
    # concluidas e carinhos zeram
    assert snap_virou["hoje"]["concluidas"] == 0
    assert snap_virou["vida"]["carinhos_hoje"] == 0
    # total_concluidas NAO zera
    assert snap_virou["vida"]["total_concluidas"] == 1

    # Novo Mini recarrega total_concluidas persistido
    m2 = Mini(arq, relogio=relogio)
    snap2 = m2.snapshot()
    assert snap2["vida"]["total_concluidas"] == 1
    assert snap2["vida"]["carinhos_hoje"] == 0


def test_mini_carinho_e_toque_seq(tmp_path):
    relogio = RelogioFalso(1763560000.0)
    mini = Mini(tmp_path / "mini.json", relogio=relogio)

    seq_inicial = mini.seq
    # Toque não muda seq
    mini.toque()
    assert mini.seq == seq_inicial

    # Carinho muda seq
    mini.carinho()
    assert mini.seq == seq_inicial + 1


def test_mini_toque_grava_no_maximo_1x_por_minuto(tmp_path):
    relogio = RelogioFalso(1763560000.0)
    arq = tmp_path / "mini.json"
    mini = Mini(arq, relogio=relogio)

    gravacoes = 0
    orig_gravar = mini._gravar_hoje

    def spy_gravar():
        nonlocal gravacoes
        gravacoes += 1
        orig_gravar()

    mini._gravar_hoje = spy_gravar

    # Primeiro toque grava
    mini.toque()
    assert gravacoes == 1

    # Toques subsequentes em menos de 60s não gravam
    relogio.avancar(10)
    mini.toque()
    assert gravacoes == 1

    relogio.avancar(49)  # 59s desde a primeira gravação
    mini.toque()
    assert gravacoes == 1

    # Ao atingir 60s, grava novamente
    relogio.avancar(1)  # 60s exatos
    mini.toque()
    assert gravacoes == 2

    # Menos de 60s não grava
    relogio.avancar(30)
    mini.toque()
    assert gravacoes == 2

    # Mais de 60s grava
    relogio.avancar(31)  # 61s desde a gravação anterior
    mini.toque()
    assert gravacoes == 3


def test_mini_arquivo_antigo_sem_chaves_novas_carrega(tmp_path):
    relogio = RelogioFalso(1763560000.0)
    data_str = RelogioFalso().t
    data_hoje = Mini(tmp_path / "dummy.json", relogio=relogio)._data_local()
    arq = tmp_path / "mini.json"
    # Formato antigo sem total_concluidas, carinhos_hoje, ultimo_toque
    conteudo_antigo = {
        "data": data_hoje,
        "concluidas": 3,
        "trabalhando_s": 150,
        "por_projeto": {"p": 150},
    }
    arq.write_text(json.dumps(conteudo_antigo), encoding="utf-8")

    m = Mini(arq, relogio=relogio)
    snap = m.snapshot()

    assert snap["hoje"]["concluidas"] == 3
    assert "vida" in snap
    assert snap["vida"]["total_concluidas"] == 0
    assert snap["vida"]["carinhos_hoje"] == 0
    assert snap["vida"]["min_sem_toque"] == 0.0


def test_main_calcular_humor():
    mini_snap = {
        "vida": {
            "min_sem_toque": 10.0,
            "min_sem_claude": 5.0,
            "carinhos_hoje": 2,
        },
        "hoje": {"concluidas": 3},
    }
    hub_estado = {
        "claude_usage": {
            "limites": [
                {"nome": "Sessão 5h", "usado_pct": 85},
                {"nome": "Semana", "usado_pct": 20},
            ]
        },
        "hardware": {"gpu_temp": 82},
    }

    h = main.calcular_humor(mini_snap, hub_estado, hora=14)
    assert h is not None
    assert "cansado" in h["extras"]
    assert "calor" in h["extras"]
    assert h["estado"] == "curioso"  # min_sem_claude=5 < 30
    assert h["energia"] == 0.8  # 1.0 - 0.2 cansado

    # Sem limites nem hardware não quebra
    h2 = main.calcular_humor({}, {}, hora=14)
    assert h2 is not None
    assert h2["extras"] == []
    assert h2["estado"] == "curioso"  # min_sem_claude=0 < 30
