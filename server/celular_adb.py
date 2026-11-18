import subprocess
import psutil
from typing import Dict, Any

PACOTE_DIGITAL = "ro.andreimircius.remotefingerauth"
PACOTE_FULLY = "de.ozerov.fully"


def pc_bloqueado() -> bool:
    """Return True if LogonUI.exe is running (PC locked)."""
    return any((p.info.get("name") or "").lower() == "logonui.exe" for p in psutil.process_iter(["name"]))


def abrir_no_celular(cfg: Dict[str, Any], pacote: str) -> bool:
    """Open an app on the Android device via adb monkey command."""
    adb_bin = str(cfg.get("caminhos", {}).get("adb", "adb"))
    serial = cfg.get("celular", {}).get("adb_serial") or ""
    base = [adb_bin, "-s", serial] if serial else [adb_bin]
    try:
        if ":" in serial:
            subprocess.run([adb_bin, "connect", serial], capture_output=True, timeout=8)
        r = subprocess.run(
            [
                *base,
                "shell",
                "monkey",
                "-p",
                pacote,
                "-c",
                "android.intent.category.LAUNCHER",
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.returncode == 0 and "Events injected: 1" in r.stdout
    except Exception:
        return False


def acordar_celular(cfg: Dict[str, Any]) -> bool:
    """Send WAKEUP keyevent to wake the device. Does not toggle power state."""
    adb_bin = str(cfg.get("caminhos", {}).get("adb", "adb"))
    serial = cfg.get("celular", {}).get("adb_serial") or ""
    base = [adb_bin, "-s", serial] if serial else [adb_bin]
    try:
        # WAKEUP keycode 224
        r = subprocess.run(
            [
                *base,
                "shell",
                "input",
                "keyevent",
                "224",
            ],
            capture_output=True,
            timeout=8,
        )
        return r.returncode == 0
    except Exception:
        return False
