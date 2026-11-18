import asyncio
import importlib
import json
import logging
from datetime import datetime
from pathlib import Path

from .config import caminho

log = logging.getLogger("hub")

COLETORES = ["hardware", "ollama", "omniroute", "claude", "claude_usage", "agy", "fx", "celular", "bloqueio", "midia"]


def agora_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Hub:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.estado: dict = {}
        self.ctx: dict = {nome: {} for nome in COLETORES}
        self.tarefas: list[asyncio.Task] = []
        self._arq_sessao = caminho(cfg, "cache") / "sessao.json"
        self.sessao_inicio = self._ler_sessao()
        self.bateria_browser: dict | None = None

    # ---- sessao (botao "Reset contador") ----
    def _ler_sessao(self) -> str:
        try:
            return json.loads(self._arq_sessao.read_text(encoding="utf-8"))["inicio"]
        except Exception:
            return self.reset_sessao()

    def reset_sessao(self) -> str:
        self.sessao_inicio = agora_iso()
        self._arq_sessao.parent.mkdir(parents=True, exist_ok=True)
        self._arq_sessao.write_text(json.dumps({"inicio": self.sessao_inicio}), encoding="utf-8")
        return self.sessao_inicio

    # ---- coletores ----
    async def _laco(self, nome: str, mod):
        intervalo = self.cfg["intervalos"].get(nome, 5)
        while True:
            ctx = self.ctx[nome]
            ctx["sessao_inicio"] = self.sessao_inicio
            ctx["bateria_browser"] = self.bateria_browser
            try:
                saida = await asyncio.to_thread(mod.collect, self.cfg, ctx)
                self.estado[nome] = saida
                self.estado.setdefault("_ok", {})[nome] = saida
            except Exception as e:  # coletor nunca derruba o servidor
                log.warning("coletor %s falhou: %s", nome, e)
                self.estado[nome] = {"erro": str(e)[:200], "ultimo_ok": self.estado.get("_ok", {}).get(nome)}
            await asyncio.sleep(intervalo)

    def iniciar(self):
        for nome in COLETORES:
            try:
                mod = importlib.import_module(f".collectors.{nome}", __package__)
            except Exception as e:
                log.warning("coletor %s indisponivel: %s", nome, e)
                self.estado[nome] = {"erro": f"indisponivel: {e}"[:200]}
                continue
            self.tarefas.append(asyncio.create_task(self._laco(nome, mod)))

    async def parar(self):
        for t in self.tarefas:
            t.cancel()

    # ---- snapshot enviado ao celular ----
    def _bom(self, nome: str) -> dict:
        d = self.estado.get(nome) or {}
        return (d.get("ultimo_ok") or {}) if "erro" in d else d

    def financeiro(self) -> dict:
        omni, claude, fx = self._bom("omniroute"), self._bom("claude"), self._bom("fx")
        taxa = fx.get("usd_brl") or 0
        hoje = omni.get("custo_hoje_usd") or 0
        mes = omni.get("custo_mes_usd") or 0
        return {
            "hoje_usd": round(hoje, 4), "mes_usd": round(mes, 4),
            "hoje_brl": round(hoje * taxa, 2) if taxa else None,
            "mes_brl": round(mes * taxa, 2) if taxa else None,
            "claude_equiv_hoje_usd": (claude.get("hoje") or {}).get("custo_equiv_usd"),
            "claude_equiv_mes_usd": (claude.get("mes") or {}).get("custo_equiv_usd"),
            "usd_brl": taxa or None,
        }

    def snapshot(self) -> dict:
        dados = {k: v for k, v in self.estado.items() if not k.startswith("_")}
        dados["financeiro"] = self.financeiro()
        dados["sessao_inicio"] = self.sessao_inicio
        dados["agora"] = agora_iso()
        dados["versao_web"] = versao_web()
        return dados


WEB = Path(__file__).resolve().parent.parent / "web"


def versao_web() -> str:
    """Muda quando qualquer arquivo da interface muda: o celular recarrega a pagina sozinho."""
    try:
        return str(max(int(p.stat().st_mtime) for p in WEB.iterdir() if p.is_file()))
    except Exception:
        return ""
