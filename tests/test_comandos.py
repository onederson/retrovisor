"""Comandos de voz do Vendel (abrir programa, musica). So nomes do Menu Iniciar; o resto vira conversa."""
from server import comandos

CATALOGO = {"Discord": 1, "Google Chrome": 2, "Visual Studio Code": 3, "Obsidian": 4, "Calculadora": 5}


def test_abrir_programas_falados():
    casos = {"Abre o Discord": "Discord", "Vendel, abre o Chrome pra mim": "Google Chrome",
             "abre o vs code": "Visual Studio Code", "abrir o obsidian por favor": "Obsidian",
             "abre a calculadora": "Calculadora"}
    for frase, esperado in casos.items():
        p = comandos.interpretar(frase)
        assert p and p["tipo"] == "abrir", frase
        assert comandos.achar_programa(p["alvo"], CATALOGO) == esperado, frase


def test_conversa_nao_vira_comando():
    for frase in ["O que você pode fazer?", "abre o coração pra mim e me conta como foi seu dia", "toca em mim"]:
        p = comandos.interpretar(frase)
        assert p is None or comandos.achar_programa(p.get("alvo", ""), CATALOGO) is None, frase


def test_musica():
    assert comandos.interpretar("pausa a música")["cmd"] == "alternar"
    assert comandos.interpretar("próxima música")["cmd"] == "proxima"
    assert comandos.interpretar("volta a música")["cmd"] == "anterior"
