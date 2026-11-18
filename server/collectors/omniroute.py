import sqlite3
from datetime import datetime, timezone
import httpx
from ..config import caminho


def collect(cfg: dict, ctx: dict) -> dict:
    db_path = caminho(cfg, "omniroute_db")

    now_local = datetime.now().astimezone()
    hoje_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    mes_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    hoje_utc_str = hoje_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    mes_utc_str = mes_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=2)
    try:
        cur = conn.cursor()

        # Ultima chamada real
        cur.execute(
            "SELECT timestamp, status, model, provider, combo_name FROM call_logs "
            "WHERE model != 'connection-test' ORDER BY timestamp DESC LIMIT 1"
        )
        row = cur.fetchone()
        ultima = None
        ultima_dt_utc = None
        if row:
            ts_raw, status, model, provider, combo_name = row
            dt_utc = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            ultima_dt_utc = dt_utc
            hora_local = dt_utc.astimezone().isoformat(timespec="seconds")
            ultima = {
                "hora": hora_local,
                "modelo": model,
                "provedor": provider,
                "combo": combo_name if combo_name else None,
                "status": int(status) if status is not None else None,
            }

        # Metricas hoje em call_logs
        cur.execute(
            "SELECT status, duration, tokens_in, tokens_out FROM call_logs "
            "WHERE model != 'connection-test' AND timestamp >= ?",
            (hoje_utc_str,),
        )
        rows = cur.fetchall()
        requisicoes = len(rows)
        erros = sum(1 for r in rows if r[0] is None or int(r[0]) >= 400)
        taxa_acerto = round((requisicoes - erros) / requisicoes * 100, 1) if requisicoes > 0 else None
        valid_durations = [r[1] for r in rows if r[1] is not None]
        latencia_media_ms = (
            int(round(sum(valid_durations) / len(valid_durations)))
            if valid_durations
            else None
        )
        tokens_in = sum(r[2] for r in rows if r[2] is not None)
        tokens_out = sum(r[3] for r in rows if r[3] is not None)
        hoje = {
            "requisicoes": requisicoes,
            "erros": erros,
            "taxa_acerto": taxa_acerto,
            "latencia_media_ms": latencia_media_ms,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }

        # Custos em usage_history
        cur.execute(
            "SELECT SUM(COALESCE(provider_cost_usd, 0.0)) FROM usage_history WHERE timestamp >= ?",
            (hoje_utc_str,),
        )
        custo_hoje_usd = float(cur.fetchone()[0] or 0.0)

        cur.execute(
            "SELECT SUM(COALESCE(provider_cost_usd, 0.0)) FROM usage_history WHERE timestamp >= ?",
            (mes_utc_str,),
        )
        custo_mes_usd = float(cur.fetchone()[0] or 0.0)

        # Historico recente (10 linhas)
        cur.execute(
            "SELECT timestamp, provider, model, tokens_input, tokens_output, provider_cost_usd, success "
            "FROM usage_history ORDER BY timestamp DESC LIMIT 10"
        )
        historico_rows = cur.fetchall()
        historico = []
        for r in historico_rows:
            ts_raw, provider, model, tok_in, tok_out, cost, success = r
            dt_utc = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            hora_local = dt_utc.astimezone().isoformat(timespec="seconds")
            tokens = int((tok_in or 0) + (tok_out or 0))
            custo_usd = float(cost) if cost is not None else 0.0
            status = 200 if success == 1 else 500
            historico.append(
                {
                    "hora": hora_local,
                    "provedor": provider,
                    "modelo": model,
                    "tokens": tokens,
                    "custo_usd": custo_usd,
                    "status": status,
                }
            )
    finally:
        conn.close()

    online = False
    url = cfg.get("omniroute", {}).get("url")
    if url:
        try:
            resp = httpx.get(url, timeout=1.5)
            online = True
        except Exception:
            pass

    if not online and ultima_dt_utc is not None:
        now_utc = datetime.now(timezone.utc)
        diff = (now_utc - ultima_dt_utc).total_seconds()
        if 0 <= diff < 600:
            online = True

    return {
        "online": online,
        "ultima": ultima,
        "hoje": hoje,
        "custo_hoje_usd": round(custo_hoje_usd, 4),
        "custo_mes_usd": round(custo_mes_usd, 4),
        "historico": historico,
    }
