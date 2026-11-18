# Contrato de dados

Cada coletor fica em `server/collectors/<nome>.py` e expõe:

```python
def collect(cfg: dict, ctx: dict) -> dict
```

- `cfg`: `config.toml` já carregado, com `cfg["_raiz"]` (pasta do projeto) e `cfg["_pricing"]` (`pricing.toml`).
- `ctx`: dicionário persistente **só daquele coletor**, entre chamadas. Serve para offsets de arquivo, caches etc.
- A função é **síncrona**. O hub a chama via `asyncio.to_thread`, no intervalo de `cfg["intervalos"][<nome>]`.
- Pode lançar exceção. O hub grava `{"erro": "<msg>"}` e mantém o último valor bom em `ultimo_ok`.
- Nunca imprimir, logar ou devolver segredos (chaves de API, tokens, conteúdo de `server.env`).
- Horários devolvidos em ISO 8601 local (`datetime.now().astimezone().isoformat(timespec="seconds")`). "Hoje" e "mês" seguem o fuso local.

O WebSocket `/ws` envia a cada 1 s: `{"tipo": "estado", "dados": {<nome>: <saida>, ..., "financeiro": {...}, "sessao_inicio": iso, "agora": iso}}`.

## hardware
```json
{"cpu_pct": 12.5, "cpu_temp": null, "ram_pct": 41.2, "ram_usado_gb": 13.1, "ram_total_gb": 31.9,
 "gpu_nome": "NVIDIA GeForce RTX 5060 Ti", "gpu_pct": 7, "gpu_temp": 41,
 "vram_usado_gb": 2.3, "vram_total_gb": 15.9, "rede_down_kbps": 120.4, "rede_up_kbps": 15.2,

 "cpu_nome": "AMD Ryzen 5 5600X 6-Core Processor", "cpu_nucleos_fisicos": 6,
 "cpu_nucleos": [12.0, 3.1, 0.0, 45.2, 8.8, 1.0, 0.0, 2.2, 5.5, 0.0, 1.1, 9.9],
 "cpu_clock_mhz": 4450, "cpu_base_mhz": 3701,
 "ram_disponivel_gb": 18.8, "swap_pct": 5.7,
 "gpu_clock_mhz": 2602, "gpu_clock_max_mhz": 3090, "gpu_mem_clock_mhz": 14001,
 "gpu_power_w": 27.1, "gpu_power_limite_w": 180.0, "gpu_fan_pct": 0, "gpu_pstate": 0,
 "gpu_mem_ctrl_pct": 1, "gpu_enc_pct": 0, "gpu_dec_pct": 0,
 "gpu_pcie_rx_mbps": 5.3, "gpu_pcie_tx_mbps": 5.3, "gpu_temp_limite": 89,
 "gpu_throttle": ["power"], "gpu_driver": "616.56",
 "disco_leitura_mbps": 1.2, "disco_escrita_mbps": 0.4,
 "processos_top": [{"nome": "ollama.exe", "cpu_pct": 35.2, "ram_mb": 812}],
 "uptime_s": 86400}
```
- `cpu_temp` é `null` quando o Windows não fornece o dado (sem apps de terceiros). A rede, o disco e o PCIe são taxas desde a chamada anterior, guardadas em `ctx`.
- Qualquer campo não suportado vale `null`. Cada leitura NVML tem o seu próprio try, e uma falha não zera as outras.
- `gpu_fan_pct` 0 é normal: o modo semi-passivo mantém a ventoinha parada com a GPU fria.
- `gpu_throttle` é uma lista de motivos ativos, entre "power", "termico", "hw_slowdown", "sync_boost", "app_clock", "display" e "potencia_hw". Uma GPU ociosa dá lista vazia.
- `processos_top`: os 5 processos com mais CPU, atualizados a cada 3 s e guardados em `ctx` entre as chamadas. O `cpu_pct` é a % de uma CPU dividida pelo número de núcleos lógicos (escala de 0 a 100 da máquina toda).

## claude_usage
Lido de `claude -p "/usage"` (assinatura).
```json
{"limites": [{"nome": "Sessão 5h", "usado_pct": 22, "reset": "2026-11-17T05:39:00-03:00"},
             {"nome": "Semana", "usado_pct": 20, "reset": "2026-11-21T03:59:00-03:00"}],
 "atualizado": "2026-11-17T05:10:00-03:00"}
```
`reset` pode ser `null`. Podem vir mais linhas (por exemplo, "Semana Opus").

## ollama
```json
{"online": true, "modelos": [{"nome": "qwen3-coder:30b", "vram_gb": 18.2, "expira_em_s": 240}],
 "tokens_s": 54.3, "tokens_s_modelo": "qwen3-coder:30b", "tokens_s_quando": "2026-11-17T10:00:00-03:00"}
```

## omniroute
```json
{"online": true,
 "ultima": {"hora": "...", "modelo": "...", "provedor": "...", "combo": "...|null", "status": 200},
 "hoje": {"requisicoes": 120, "erros": 7, "taxa_acerto": 94.2, "latencia_media_ms": 1830, "tokens_in": 0, "tokens_out": 0},
 "custo_hoje_usd": 0.0, "custo_mes_usd": 0.005,
 "historico": [{"hora": "...", "provedor": "...", "modelo": "...", "tokens": 1234, "custo_usd": 0.0, "status": 200}]}
```

## claude
```json
{"hoje": {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "custo_equiv_usd": 0.0, "mensagens": 0},
 "mes": {"...": "mesmo formato"}, "sessao": {"...": "mesmo formato, desde sessao_inicio"},
 "janela5h": {"inicio": "...|null", "fim": "...|null", "restante_s": 0, "tokens": 0, "custo_equiv_usd": 0.0},
 "ultimo_modelo": "claude-opus-5-5"}
```
Como é assinatura, o custo é **equivalente em API** (estimativa) e não entra no gasto real.

## agy
```json
{"limites": [{"grupo": "Gemini Models", "limite": "Five Hour Limit Remaining", "restante_pct": 98, "reset": "2026-11-17T08:43:21Z"}],
 "atualizado": "...", "fonte": "usage|maestro",
 "maestro_hoje": {"chamadas": 12, "tokens_in": 200000, "tokens_out": 9000}, "esgotados": ["omni-free-code"]}
```

## fx
```json
{"usd_brl": 5.43, "atualizado": "..."}
```

## celular
```json
{"nivel": 91, "temp_c": 32.0, "carregando": false, "fonte": "adb|browser|nenhuma"}
```

## financeiro (o hub calcula)
```json
{"hoje_usd": 0.0, "mes_usd": 0.0, "hoje_brl": 0.0, "mes_brl": 0.0,
 "claude_equiv_hoje_usd": 0.0, "claude_equiv_mes_usd": 0.0}
```
O gasto real (`hoje_usd`/`mes_usd`) é o custo pago do OmniRoute. Claude e agy são assinatura.

## Ações
`POST /action/{id}` devolve `{"ok": bool, "msg": str, "estado": {...opcional}}`. `GET /actions` lista `[{"id", "rotulo", "tela", "ativo"}]`.
