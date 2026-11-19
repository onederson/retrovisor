import pytest

from server import gestos, sentidos


def _quadro_faixa(cx_norm: float | None, largura_faixa: int = 8, fundo: int = 30, cor: int = 220) -> bytes:
    """Gera quadro 64x36 cinza com uma faixa vertical simulando a mao em cx_norm (0..1)."""
    w, h = gestos.LARGURA, gestos.ALTURA
    buf = bytearray([fundo] * (w * h))
    if cx_norm is not None:
        cx = int(round(cx_norm * (w - 1)))
        x0 = max(0, cx - largura_faixa // 2)
        x1 = min(w, x0 + largura_faixa)
        for y in range(4, h - 4):
            base = y * w
            for x in range(x0, x1):
                buf[base + x] = cor
    return bytes(buf)


def test_swipe_esquerda():
    det = gestos.DetectorGestos()
    det.processar(_quadro_faixa(None), agora=0.0)
    resultados = []
    posicoes = [0.85, 0.72, 0.58, 0.42, 0.28, 0.14]
    for i, pos in enumerate(posicoes, start=1):
        r = det.processar(_quadro_faixa(pos), agora=i * (1 / 15))
        if r:
            resultados.append(r)
    assert resultados == ["esquerda"]


def test_swipe_direita():
    det = gestos.DetectorGestos()
    det.processar(_quadro_faixa(None), agora=0.0)
    resultados = []
    posicoes = [0.15, 0.28, 0.42, 0.58, 0.72, 0.86]
    for i, pos in enumerate(posicoes, start=1):
        r = det.processar(_quadro_faixa(pos), agora=i * (1 / 15))
        if r:
            resultados.append(r)
    assert resultados == ["direita"]


def test_inverter_direcao():
    det = gestos.DetectorGestos(inverter=True)
    det.processar(_quadro_faixa(None), agora=0.0)
    resultados = []
    for i, pos in enumerate([0.85, 0.70, 0.55, 0.40, 0.22], start=1):
        r = det.processar(_quadro_faixa(pos), agora=i * 0.07)
        if r:
            resultados.append(r)
    assert resultados == ["direita"]


def test_cooldown_ignora_retorno_e_libera_depois():
    det = gestos.DetectorGestos(cooldown_s=0.8)
    det.processar(_quadro_faixa(None), agora=0.0)

    # Primeiro aceno: direita -> esquerda
    disparou = None
    t = 0.0
    for pos in [0.85, 0.70, 0.52, 0.35, 0.18]:
        t += 0.07
        r = det.processar(_quadro_faixa(pos), agora=t)
        if r:
            disparou = r
            break
    assert disparou == "esquerda"

    # Retorno imediato da mao dentro do cooldown nao deve disparar
    retorno = []
    for pos in [0.20, 0.40, 0.60, 0.82]:
        t += 0.07
        r = det.processar(_quadro_faixa(pos), agora=t)
        if r:
            retorno.append(r)
    assert retorno == []

    # Depois do cooldown, novo aceno deve disparar normalmente
    t += 1.0
    det.processar(_quadro_faixa(None), agora=t)
    depois = []
    for pos in [0.15, 0.32, 0.50, 0.68, 0.85]:
        t += 0.07
        r = det.processar(_quadro_faixa(pos), agora=t)
        if r:
            depois.append(r)
    assert depois == ["direita"]


def test_imagem_parada_e_ruido_pequeno_nao_disparam():
    det = gestos.DetectorGestos()
    base = bytearray(_quadro_faixa(None))
    det.processar(bytes(base), agora=0.0)
    for i in range(1, 10):
        q = bytearray(base)
        # Altera apenas 3 pixels espalhados (abaixo de min_pixels)
        q[10 * gestos.LARGURA + (i * 4) % gestos.LARGURA] = 250
        assert det.processar(bytes(q), agora=i * 0.07) is None


def test_flash_global_nao_dispara():
    det = gestos.DetectorGestos()
    escuro = bytes([20] * gestos.TAM_QUADRO)
    claro = bytes([230] * gestos.TAM_QUADRO)
    det.processar(escuro, agora=0.0)
    for i in range(1, 6):
        q = claro if i % 2 else escuro
        assert det.processar(q, agora=i * 0.07) is None


def test_oscilacao_sem_consistencia_nao_dispara():
    det = gestos.DetectorGestos()
    det.processar(_quadro_faixa(None), agora=0.0)
    # Vai e volta rapidamente sem direcao consistente
    posicoes = [0.20, 0.55, 0.25, 0.60, 0.30, 0.55]
    for i, pos in enumerate(posicoes, start=1):
        assert det.processar(_quadro_faixa(pos), agora=i * 0.06) is None


def test_cego_bloqueia_inicio():
    ctrl = gestos.ControladorGestos()
    antigo = sentidos.PRIVACIDADE["cego"]
    try:
        sentidos.PRIVACIDADE["cego"] = True
        resp = ctrl.iniciar({})
        assert resp["ok"] is False
        assert "cego" in resp["erro"]
        assert ctrl.ativo is False
    finally:
        sentidos.PRIVACIDADE["cego"] = antigo


def test_versao_scrcpy():
    assert gestos._versao_scrcpy(r"C:\apps\scrcpy-win64-v5.0.1\scrcpy.exe") == "5.0.1"
    assert gestos._versao_scrcpy(r"C:\apps\scrcpy\scrcpy.exe") == "5.0.1"
