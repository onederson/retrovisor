import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from ..config import caminho, preco


def collect(cfg: dict, ctx: dict) -> dict:
    pasta = caminho(cfg, "claude_projects")

    offsets = ctx.setdefault("offsets", {})
    seen_messages = ctx.setdefault("seen_messages", set())
    events = ctx.setdefault("events", [])

    if pasta.exists() and pasta.is_dir():
        arquivos = sorted(pasta.rglob("*.jsonl"))
        for p in arquivos:
            file_key = str(p.resolve())
            try:
                size = p.stat().st_size
            except OSError:
                continue

            offset = offsets.get(file_key, 0)
            if size < offset:
                offset = 0

            try:
                with open(p, "rb") as f:
                    f.seek(offset)
                    chunk = f.read()
            except OSError:
                continue

            if not chunk:
                offsets[file_key] = offset
                continue

            last_nl = chunk.rfind(b"\n")
            if last_nl == -1:
                offsets[file_key] = offset
                continue

            valid_bytes = chunk[: last_nl + 1]
            offsets[file_key] = offset + last_nl + 1

            for raw_line in valid_bytes.splitlines():
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line.decode("utf-8", errors="replace"))
                except Exception:
                    continue

                if not isinstance(data, dict):
                    continue
                if data.get("type") != "assistant":
                    continue
                msg = data.get("message")
                if not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                if not isinstance(usage, dict):
                    continue

                msg_id = msg.get("id") or data.get("id")
                req_id = (
                    data.get("requestId")
                    or msg.get("requestId")
                    or data.get("request_id")
                    or msg.get("request_id")
                )
                dedupe_key = (str(msg_id), str(req_id)) if (msg_id or req_id) else None
                if dedupe_key:
                    if dedupe_key in seen_messages:
                        continue
                    seen_messages.add(dedupe_key)

                model = msg.get("model") or data.get("model")
                if not model or model == "<synthetic>":
                    continue

                p_info = preco(cfg, model)
                if not p_info:
                    continue

                inp = int(usage.get("input_tokens") or 0)
                out = int(usage.get("output_tokens") or 0)
                c_read = int(usage.get("cache_read_input_tokens") or 0)
                c_write = int(usage.get("cache_creation_input_tokens") or 0)

                w1h = 0
                w5m = 0
                cc = usage.get("cache_creation")
                if isinstance(cc, dict):
                    w1h = int(cc.get("ephemeral_1h_input_tokens") or 0)
                    w5m = int(cc.get("ephemeral_5m_input_tokens") or 0)
                else:
                    w1h = int(usage.get("cache_creation.ephemeral_1h_input_tokens") or 0)
                    w5m = int(usage.get("cache_creation.ephemeral_5m_input_tokens") or 0)

                if w1h == 0 and w5m == 0 and c_write > 0:
                    w5m = c_write

                p_in = float(p_info.get("input") or 0.0)
                p_out = float(p_info.get("output") or 0.0)
                p_read = float(p_info.get("cache_read") or 0.0)
                p_w5m = float(p_info.get("cache_write_5m") or 0.0)
                p_w1h = float(p_info.get("cache_write_1h") or 0.0)

                custo = (inp * p_in + out * p_out + c_read * p_read + w5m * p_w5m + w1h * p_w1h) / 1e6

                ts_str = data.get("timestamp") or msg.get("timestamp")
                if ts_str and isinstance(ts_str, str):
                    try:
                        dt_utc = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except Exception:
                        dt_utc = datetime.now(timezone.utc)
                else:
                    dt_utc = datetime.now(timezone.utc)

                dt_local = dt_utc.astimezone()

                events.append(
                    {
                        "dt": dt_local,
                        "modelo": model,
                        "input": inp,
                        "output": out,
                        "cache_read": c_read,
                        "cache_write": c_write,
                        "custo": custo,
                    }
                )

    now_local = datetime.now().astimezone()
    limite_35d = now_local - timedelta(days=35)
    events = [e for e in events if e["dt"] >= limite_35d]
    events.sort(key=lambda e: e["dt"])
    ctx["events"] = events

    ultimo_modelo = events[-1]["modelo"] if events else None

    hoje_inicio = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    mes_inicio = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    sessao_inicio_str = ctx.get("sessao_inicio")
    if sessao_inicio_str:
        try:
            sessao_dt = datetime.fromisoformat(sessao_inicio_str)
            if sessao_dt.tzinfo is None:
                sessao_dt = sessao_dt.replace(tzinfo=now_local.tzinfo)
        except Exception:
            sessao_dt = hoje_inicio
    else:
        sessao_dt = hoje_inicio

    def _calc_agregado(evs: list[dict]) -> dict:
        return {
            "input": sum(e["input"] for e in evs),
            "output": sum(e["output"] for e in evs),
            "cache_read": sum(e["cache_read"] for e in evs),
            "cache_write": sum(e["cache_write"] for e in evs),
            "custo_equiv_usd": round(sum(e["custo"] for e in evs), 4),
            "mensagens": len(evs),
        }

    hoje = _calc_agregado([e for e in events if e["dt"] >= hoje_inicio])
    mes = _calc_agregado([e for e in events if e["dt"] >= mes_inicio])
    sessao = _calc_agregado([e for e in events if e["dt"] >= sessao_dt])

    bloco_inicio = None
    bloco_fim = None
    bloco_eventos = []

    for ev in events:
        t = ev["dt"]
        if bloco_fim is None or t >= bloco_fim:
            bloco_inicio = t.replace(minute=0, second=0, microsecond=0)
            bloco_fim = bloco_inicio + timedelta(hours=5)
            bloco_eventos = [ev]
        else:
            bloco_eventos.append(ev)

    if bloco_fim is not None and now_local < bloco_fim:
        janela5h = {
            "inicio": bloco_inicio.isoformat(timespec="seconds"),
            "fim": bloco_fim.isoformat(timespec="seconds"),
            "restante_s": max(0, int((bloco_fim - now_local).total_seconds())),
            "tokens": sum(e["input"] + e["output"] + e["cache_write"] for e in bloco_eventos),
            "custo_equiv_usd": round(sum(e["custo"] for e in bloco_eventos), 4),
        }
    else:
        janela5h = {
            "inicio": None,
            "fim": None,
            "restante_s": 0,
            "tokens": 0,
            "custo_equiv_usd": 0.0,
        }

    return {
        "hoje": hoje,
        "mes": mes,
        "sessao": sessao,
        "janela5h": janela5h,
        "ultimo_modelo": ultimo_modelo,
    }
