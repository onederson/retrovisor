import os
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def carregar() -> dict:
    arq = RAIZ / "config.toml"
    if not arq.exists():  # clone novo: usa o exemplo ate o usuario criar o seu
        arq = RAIZ / "config.example.toml"
    cfg = tomllib.loads(arq.read_text(encoding="utf-8"))
    cfg["_pricing"] = tomllib.loads((RAIZ / "pricing.toml").read_text(encoding="utf-8"))
    cfg["_raiz"] = str(RAIZ)
    serial = cfg.get("celular", {}).get("adb_serial")
    if serial:  # o adb usa ANDROID_SERIAL quando ha mais de um aparelho (USB + Wi-Fi)
        os.environ["ANDROID_SERIAL"] = serial
    return cfg


def caminho(cfg: dict, chave: str) -> Path:
    """Caminho de [caminhos], expandindo ~ e resolvendo relativos a raiz do projeto."""
    p = Path(cfg["caminhos"][chave]).expanduser()
    return p if p.is_absolute() else RAIZ / p


def preco(cfg: dict, modelo: str) -> dict | None:
    """Precos por 1M tokens do prefixo mais longo que casa com o id do modelo."""
    tabela = cfg["_pricing"].get("modelos", {})
    melhor = max((k for k in tabela if modelo and modelo.startswith(k)), key=len, default=None)
    return tabela[melhor] if melhor else None
