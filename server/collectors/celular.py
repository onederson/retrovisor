import subprocess


def parse_dumpsys(texto: str) -> dict:
    nivel = None
    temp_c = None
    ac = False
    usb = False
    wireless = False

    for linha in texto.splitlines():
        linha = linha.strip()
        if ":" not in linha:
            continue
        chave, _, valor = linha.partition(":")
        chave = chave.strip()
        valor = valor.strip()
        if chave == "level":
            try:
                nivel = int(valor)
            except ValueError:
                pass
        elif chave == "temperature":
            try:
                temp_c = round(float(valor) / 10.0, 1)
            except ValueError:
                pass
        elif chave == "AC powered":
            ac = valor.lower() == "true"
        elif chave == "USB powered":
            usb = valor.lower() == "true"
        elif chave == "Wireless powered":
            wireless = valor.lower() == "true"

    carregando = ac or usb or wireless
    return {
        "nivel": nivel,
        "temp_c": temp_c,
        "carregando": carregando,
        "fonte": "adb",
    }


def _reconectar(adb_bin: str, cfg: dict) -> None:
    serial = cfg.get("celular", {}).get("adb_serial") or ""
    if ":" in serial:  # adb por Wi-Fi caiu: tenta religar
        try:
            subprocess.run([adb_bin, "connect", serial], capture_output=True, timeout=8)
        except Exception:
            pass


def _reverse(adb_bin: str, cfg: dict) -> None:
    """Mantem o celular abrindo http://localhost:8080 pelo adb (cabo ou Wi-Fi): contexto seguro no Chrome."""
    porta = str(cfg.get("servidor", {}).get("porta", 8080))
    try:
        subprocess.run([adb_bin, "reverse", f"tcp:{porta}", f"tcp:{porta}"], capture_output=True, timeout=8)
    except Exception:
        pass


def collect(cfg: dict, ctx: dict) -> dict:
    adb_bin = str(cfg.get("caminhos", {}).get("adb", "adb"))
    _reverse(adb_bin, cfg)
    for tentativa in range(2):
        try:
            proc = subprocess.run([adb_bin, "shell", "dumpsys", "battery"],
                                  capture_output=True, text=True, timeout=8)
            if proc.returncode == 0:
                dados = parse_dumpsys(proc.stdout)
                if dados.get("nivel") is not None:
                    return dados
        except Exception:
            pass
        if tentativa == 0:
            _reconectar(adb_bin, cfg)

    browser = ctx.get("bateria_browser")
    if isinstance(browser, dict) and browser.get("nivel") is not None:
        return {
            "nivel": browser["nivel"],
            "temp_c": None,
            "carregando": browser.get("carregando"),
            "fonte": "browser",
        }

    return {
        "nivel": None,
        "temp_c": None,
        "carregando": None,
        "fonte": "nenhuma",
    }
