import subprocess
from unittest.mock import MagicMock
import pytest

from server import celular_adb
from server.vigia import EstadoVigia, passo


def test_boot_bloqueado_e_sucesso_nao_repete():
    """Boot com PC bloqueado -> 'digital'; depois de sucesso, nao repete."""
    estado = EstadoVigia()
    # Primeira volta (boot) com PC bloqueado
    acoes = passo(estado, agora=100.0, bloqueado=True)
    assert acoes == ["digital"]

    # Simula sucesso do executor
    estado.digital_ok = True

    # Voltas seguintes enquanto continua bloqueado nao pedem nada de novo
    assert passo(estado, agora=101.0, bloqueado=True) == []
    assert passo(estado, agora=105.0, bloqueado=True) == []
    assert passo(estado, agora=110.0, bloqueado=True) == []


def test_falha_abertura_repete_a_cada_5s_e_para_apos_90s():
    """Falha de abertura repete no maximo a cada 5 s e para apos 90 s."""
    estado = EstadoVigia()
    # Gatilho inicial
    assert passo(estado, agora=0.0, bloqueado=True) == ["digital"]
    # Sem sucesso (digital_ok permanece False)

    # Menos de 5 s nao repete
    assert passo(estado, agora=1.0, bloqueado=True) == []
    assert passo(estado, agora=2.0, bloqueado=True) == []
    assert passo(estado, agora=4.9, bloqueado=True) == []

    # Repete a cada 5 s ate 90 s, sem salto > 10 s
    for t in range(5, 95, 5):
        if t <= 90:
            assert passo(estado, agora=float(t), bloqueado=True) == ["digital"]
        else:
            # Apos 90 s para de tentar
            assert passo(estado, agora=float(t), bloqueado=True) == []

    assert passo(estado, agora=96.0, bloqueado=True) == []
    assert passo(estado, agora=100.0, bloqueado=True) == []


def test_salto_relogio_com_bloqueado():
    """Salto de relogio de 3600 s com bloqueado -> 'digital'."""
    estado = EstadoVigia()
    # Estado inicial: rodando desbloqueado
    assert passo(estado, agora=100.0, bloqueado=False) == []
    assert passo(estado, agora=101.0, bloqueado=False) == []

    # Salto de relogio (suspensao S3): PC acorda bloqueado
    acoes = passo(estado, agora=3701.0, bloqueado=True)
    assert acoes == ["digital"]


def test_bloqueio_sem_salto_transicao_pede_digital():
    """Bloqueio sem salto (voltas de 1 s, bloqueado passa de False a True) -> 'digital'.
    Excecao: se o PC ja estava bloqueado e continua bloqueado sem salto de relogio, nada de novo.
    """
    estado = EstadoVigia()
    # PC desbloqueado
    assert passo(estado, agora=10.0, bloqueado=False) == []
    assert passo(estado, agora=11.0, bloqueado=False) == []

    # Transicao: bloqueado passa de False a True (ex: Win+L)
    acoes = passo(estado, agora=12.0, bloqueado=True)
    assert acoes == ["digital"]

    # Simula sucesso na abertura
    estado.digital_ok = True

    # PC ja estava bloqueado e continua bloqueado sem salto: nada de novo
    assert passo(estado, agora=13.0, bloqueado=True) == []
    assert passo(estado, agora=14.0, bloqueado=True) == []
    assert passo(estado, agora=18.0, bloqueado=True) == []


def test_depois_do_gatilho_desbloqueio_pede_fully_uma_unica_vez():
    """Depois do gatilho, bloqueado True -> False -> 'fully' uma unica vez."""
    estado = EstadoVigia()
    # Gatilho de boot bloqueado
    assert passo(estado, agora=0.0, bloqueado=True) == ["digital"]
    estado.digital_ok = True

    assert passo(estado, agora=1.0, bloqueado=True) == []
    assert passo(estado, agora=5.0, bloqueado=True) == []

    # Usuario desbloqueia o PC (LogonUI some)
    assert passo(estado, agora=10.0, bloqueado=False) == ["fully"]

    # Voltas seguintes nao pedem mais 'fully' (uma unica vez e volta ao repouso)
    assert passo(estado, agora=11.0, bloqueado=False) == []
    assert passo(estado, agora=12.0, bloqueado=False) == []
    assert passo(estado, agora=20.0, bloqueado=False) == []


def test_desbloqueio_apos_10_min_esquece_fully():
    """Se o desbloqueio ocorrer apos 10 min do gatilho, nao pede 'fully'."""
    estado = EstadoVigia()
    assert passo(estado, agora=0.0, bloqueado=True) == ["digital"]
    estado.digital_ok = True

    # Desbloqueio apos 601 segundos (> 10 minutos)
    assert passo(estado, agora=601.0, bloqueado=False) == []


def test_boot_desbloqueado_nao_faz_nada():
    """Boot com PC desbloqueado -> nada."""
    estado = EstadoVigia()
    assert passo(estado, agora=100.0, bloqueado=False) == []
    assert passo(estado, agora=101.0, bloqueado=False) == []
    assert passo(estado, agora=102.0, bloqueado=False) == []


def test_salto_relogio_desbloqueado_nao_faz_nada():
    """Gatilho com PC desbloqueado nao faz nada."""
    estado = EstadoVigia()
    assert passo(estado, agora=100.0, bloqueado=False) == []
    assert passo(estado, agora=3700.0, bloqueado=False) == []


def test_celular_adb_abrir_no_celular(monkeypatch):
    """Teste de celular_adb.abrir_no_celular com subprocess.run em monkeypatch."""
    cfg = {"caminhos": {"adb": "adb"}, "celular": {"adb_serial": "192.168.3.6:5555"}}

    # Caso 1: Sucesso ("Events injected: 1" e returncode == 0)
    mock_sucesso = MagicMock()
    mock_sucesso.returncode = 0
    mock_sucesso.stdout = "Events injected: 1\n"
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_sucesso)

    assert celular_adb.abrir_no_celular(cfg, celular_adb.PACOTE_DIGITAL) is True

    # Caso 2: Falha (Events injected: 0)
    mock_falha = MagicMock()
    mock_falha.returncode = 0
    mock_falha.stdout = "Events injected: 0\n"
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_falha)

    assert celular_adb.abrir_no_celular(cfg, celular_adb.PACOTE_DIGITAL) is False

    # Caso 3: returncode != 0
    mock_erro = MagicMock()
    mock_erro.returncode = 1
    mock_erro.stdout = "Events injected: 1\n"
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_erro)

    assert celular_adb.abrir_no_celular(cfg, celular_adb.PACOTE_DIGITAL) is False

    # Caso 4: Excecao
    def _erro(*args, **kwargs):
        raise RuntimeError("ADB disconnected")

    monkeypatch.setattr(subprocess, "run", _erro)
    assert celular_adb.abrir_no_celular(cfg, celular_adb.PACOTE_DIGITAL) is False


def test_celular_adb_acordar_celular(monkeypatch):
    """Teste de celular_adb.acordar_celular com subprocess.run em monkeypatch."""
    cfg = {"caminhos": {"adb": "adb"}, "celular": {"adb_serial": "192.168.3.6:5555"}}

    mock_ok = MagicMock()
    mock_ok.returncode = 0
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_ok)
    assert celular_adb.acordar_celular(cfg) is True

    mock_fail = MagicMock()
    mock_fail.returncode = 1
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_fail)
    assert celular_adb.acordar_celular(cfg) is False
