"""Avisos de energia (suspender/desligar/reiniciar) e status do boot servido pelo vigia."""
import json
import urllib.request

from server import vigia
from server.collectors import bloqueio


def _evento_1074(quando: str, tipo: str) -> str:
    dados = ["C:\\WINDOWS\\system32\\winlogon.exe (PC)", "PC", "Outro", "0x500ff", tipo, "", "PC\\Eu"]
    corpo = "".join(f"<Data Name='param{i + 1}'>{d}</Data>" for i, d in enumerate(dados))
    return (f"<Event><System><EventID>1074</EventID><TimeCreated SystemTime='{quando}.1234567Z'/></System>"
            f"<EventData>{corpo}</EventData></Event>")


def test_reinicio_pelo_evento_1074():
    from datetime import datetime, timezone
    agora = datetime(2026, 11, 18, 17, 0, 30, tzinfo=timezone.utc).timestamp()
    for tipo in ("restart", "reiniciar", "Reiniciar o sistema"):
        assert bloqueio._tipo_reinicio(_evento_1074("2026-11-18T17:00:00", tipo), agora) is True
    for tipo in ("power off", "Desligar o sistema", "Desligado"):
        assert bloqueio._tipo_reinicio(_evento_1074("2026-11-18T17:00:00", tipo), agora) is False
    # reinicio de horas atras nao conta
    assert bloqueio._tipo_reinicio(_evento_1074("2026-11-18T14:00:00", "restart"), agora) is False
    assert bloqueio._tipo_reinicio("", agora) is False


def test_aviso_de_energia_muda_seq_e_expira(monkeypatch):
    monkeypatch.setattr(bloqueio, "_energia", {"evento": None, "seq": 0, "ts": 0.0})
    monkeypatch.setattr(bloqueio.time, "sleep", lambda s: None)
    bloqueio.avisar_energia("suspendendo")
    e = bloqueio.energia()
    assert e["evento"] == "suspendendo" and e["seq"] == 1
    # o PC desistiu e seguiu ligado: depois de 20 s o aviso some
    assert bloqueio.energia(agora=bloqueio._energia["ts"] + 25)["evento"] is None
    bloqueio.avisar_energia(None, esperar=False)
    assert bloqueio.energia() == {"evento": None, "seq": 2}


def test_status_boot_fases():
    assert vigia.status_boot(None, False, 10)["fase"] == "windows"
    assert vigia.status_boot(True, False, 30)["fase"] == "bloqueio"
    assert vigia.status_boot(False, False, 60)["fase"] == "entrando"
    s = vigia.status_boot(False, True, 90)
    assert s == {"ok": True, "fase": "pronto", "bloqueado": False, "servidor": True, "uptime": 90}


def test_status_boot_http_libera_cors(monkeypatch):
    from http.server import ThreadingHTTPServer
    import threading
    monkeypatch.setattr(vigia.celular_adb, "pc_bloqueado", lambda: True)
    monkeypatch.setattr(vigia, "servidor_no_ar", lambda porta=8080: False)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), vigia._StatusHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/", timeout=3) as r:
            assert r.headers["Access-Control-Allow-Origin"] == "*"
            corpo = json.loads(r.read())
        assert corpo["fase"] == "bloqueio" and corpo["bloqueado"] is True
    finally:
        srv.shutdown()
