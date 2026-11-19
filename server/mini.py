import hashlib
import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path

from . import humor

DIGITANDO = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
LENDO = {"Read", "Grep", "Glob", "LS", "WebFetch", "WebSearch"}
EXECUTANDO = {"Bash", "PowerShell"}
DELEGANDO = {"Agent", "Task"}
ATIVOS = {"pensando", "digitando", "lendo", "executando", "delegando", "trabalhando"}
EVENTOS_VALIDOS = {
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Notification",
    "Stop",
    "SessionEnd",
}
_RE_SESSAO = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


class Mini:
    def __init__(self, arquivo: Path, relogio=time.time):
        self.arquivo = Path(arquivo)
        self.relogio = relogio
        self._lock = threading.Lock()
        self.seq = 0
        self.sessoes: dict[str, dict] = {}
        agora = float(self.relogio())
        data_hoje = self._data_local(agora)
        self.hoje = {
            "data": data_hoje,
            "concluidas": 0,
            "trabalhando_s": 0,
            "por_projeto": {},
        }
        self.total_concluidas = 0
        self.carinhos_hoje = 0
        self.ultimo_toque = agora
        self.ultimo_evento = agora
        self._ultimo_gravou_toque = 0.0
        self._carregar_hoje()

    def _data_local(self, ts: float | None = None) -> str:
        if ts is None:
            ts = float(self.relogio())
        return datetime.fromtimestamp(ts).astimezone().strftime("%Y-%m-%d")

    def _carregar_hoje(self):
        try:
            if self.arquivo.exists():
                conteudo = json.loads(self.arquivo.read_text(encoding="utf-8"))
                if isinstance(conteudo, dict):
                    if conteudo.get("data") == self.hoje["data"]:
                        self.hoje["concluidas"] = int(conteudo.get("concluidas", 0))
                        self.hoje["trabalhando_s"] = int(conteudo.get("trabalhando_s", 0))
                        por_proj = conteudo.get("por_projeto", {})
                        if isinstance(por_proj, dict):
                            self.hoje["por_projeto"] = {str(k): int(v) for k, v in por_proj.items()}
                        self.carinhos_hoje = int(conteudo.get("carinhos_hoje", 0))
                    if "total_concluidas" in conteudo:
                        self.total_concluidas = int(conteudo["total_concluidas"])
                    if "ultimo_toque" in conteudo:
                        self.ultimo_toque = float(conteudo["ultimo_toque"])
        except Exception:
            agora = float(self.relogio())
            self.hoje = {
                "data": self._data_local(agora),
                "concluidas": 0,
                "trabalhando_s": 0,
                "por_projeto": {},
            }
            self.total_concluidas = 0
            self.carinhos_hoje = 0
            self.ultimo_toque = agora

    def _gravar_hoje(self):
        try:
            self.arquivo.parent.mkdir(parents=True, exist_ok=True)
            dados = {
                **self.hoje,
                "total_concluidas": self.total_concluidas,
                "carinhos_hoje": self.carinhos_hoje,
                "ultimo_toque": self.ultimo_toque,
            }
            self.arquivo.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _virar_dia_se_necessario(self, agora: float):
        data_atual = self._data_local(agora)
        if data_atual != self.hoje["data"]:
            self.hoje = {
                "data": data_atual,
                "concluidas": 0,
                "trabalhando_s": 0,
                "por_projeto": {},
            }
            self.carinhos_hoje = 0
            self._gravar_hoje()

    def evento(self, dados: dict) -> bool:
        if not isinstance(dados, dict):
            return False

        sessao = dados.get("sessao")
        if not isinstance(sessao, str) or not _RE_SESSAO.match(sessao):
            return False

        evt = dados.get("evento")
        if evt not in EVENTOS_VALIDOS:
            return False

        with self._lock:
            agora = float(self.relogio())
            self.ultimo_evento = agora
            self._virar_dia_se_necessario(agora)

            s_existente = self.sessoes.get(sessao)
            estado_anterior_ativo = bool(s_existente and s_existente["estado"] in ATIVOS)
            mudou_contadores = False

            if estado_anterior_ativo:
                delta = int(min(agora - s_existente["ultimo"], 300))
                if delta > 0:
                    self.hoje["trabalhando_s"] += delta
                    proj_anterior = s_existente["projeto"]
                    self.hoje["por_projeto"][proj_anterior] = (
                        self.hoje["por_projeto"].get(proj_anterior, 0) + delta
                    )
                    mudou_contadores = True

            if evt == "Stop" and estado_anterior_ativo:
                self.hoje["concluidas"] += 1
                self.total_concluidas += 1
                mudou_contadores = True

            if mudou_contadores:
                self._gravar_hoje()

            if evt == "SessionEnd":
                if sessao in self.sessoes:
                    del self.sessoes[sessao]
                self.seq += 1
                return True

            if "projeto" in dados and dados["projeto"] is not None:
                proj = str(dados["projeto"]).strip()[:40]
                if not proj:
                    proj = "?"
            else:
                proj = s_existente["projeto"] if s_existente else "?"

            tipo = dados.get("tipo")
            if tipo != "ajudante":
                tipo = "sessao"

            ferr = None
            if evt == "SessionStart":
                novo_estado = "ocioso"
            elif evt == "UserPromptSubmit":
                novo_estado = "pensando"
            elif evt == "PreToolUse":
                f_raw = dados.get("ferramenta")
                ferr = str(f_raw)[:60] if f_raw is not None else None
                if ferr in DIGITANDO:
                    novo_estado = "digitando"
                elif ferr in LENDO:
                    novo_estado = "lendo"
                elif ferr in EXECUTANDO:
                    novo_estado = "executando"
                elif ferr in DELEGANDO:
                    novo_estado = "delegando"
                else:
                    novo_estado = "trabalhando"
            elif evt == "PostToolUse":
                novo_estado = "pensando"
            elif evt == "Notification":
                novo_estado = "precisa"
            elif evt == "Stop":
                novo_estado = "concluido"
            else:
                return False

            if s_existente:
                if novo_estado != s_existente["estado"]:
                    s_existente["estado"] = novo_estado
                    s_existente["desde"] = agora
                s_existente["ultimo"] = agora
                s_existente["projeto"] = proj
                s_existente["ferramenta"] = ferr
                s_existente["tipo"] = tipo
            else:
                self.sessoes[sessao] = {
                    "sessao": sessao,
                    "projeto": proj,
                    "estado": novo_estado,
                    "ferramenta": ferr,
                    "tipo": tipo,
                    "desde": agora,
                    "ultimo": agora,
                    "criada": agora,
                }

            if len(self.sessoes) > 20:
                mais_antiga = min(
                    self.sessoes.keys(),
                    key=lambda k: (self.sessoes[k]["ultimo"], self.sessoes[k]["criada"]),
                )
                del self.sessoes[mais_antiga]

            self.seq += 1
            return True

    def carinho(self):
        with self._lock:
            agora = float(self.relogio())
            self._virar_dia_se_necessario(agora)
            self.carinhos_hoje += 1
            self.ultimo_toque = agora
            self._gravar_hoje()
            self._ultimo_gravou_toque = agora
            self.seq += 1

    def toque(self):
        with self._lock:
            agora = float(self.relogio())
            self._virar_dia_se_necessario(agora)
            self.ultimo_toque = agora
            if agora - self._ultimo_gravou_toque >= 60.0:
                self._gravar_hoje()
                self._ultimo_gravou_toque = agora

    def snapshot(self) -> dict:
        with self._lock:
            agora = float(self.relogio())
            self._virar_dia_se_necessario(agora)

            mudou = False
            for sid in list(self.sessoes):
                s = self.sessoes[sid]
                tempo_sem_evento = agora - s["ultimo"]
                if tempo_sem_evento > 1800:
                    del self.sessoes[sid]
                    mudou = True
                elif (s["estado"] in ATIVOS or s["estado"] == "precisa") and tempo_sem_evento > 600:
                    s["estado"] = "ocioso"
                    s["desde"] = agora
                    s["ferramenta"] = None
                    mudou = True
                elif s["estado"] == "concluido" and tempo_sem_evento > 10:
                    s["estado"] = "ocioso"
                    s["desde"] = agora
                    s["ferramenta"] = None
                    mudou = True

            if mudou:
                self.seq += 1

            sessoes_ordenadas = sorted(
                self.sessoes.values(),
                key=lambda s: (s["criada"], s["sessao"]),
            )
            lista_sessoes = [
                {
                    "id": hashlib.sha1(s["sessao"].encode("utf-8")).hexdigest()[:6],
                    "projeto": s["projeto"],
                    "estado": s["estado"],
                    "ferramenta": s["ferramenta"],
                    "tipo": s["tipo"],
                    "desde": datetime.fromtimestamp(s["desde"])
                    .astimezone()
                    .isoformat(timespec="seconds"),
                }
                for s in sessoes_ordenadas
            ]

            return {
                "sessoes": lista_sessoes,
                "hoje": {
                    "concluidas": int(self.hoje["concluidas"]),
                    "trabalhando_s": int(self.hoje["trabalhando_s"]),
                    "por_projeto": {str(k): int(v) for k, v in self.hoje["por_projeto"].items()},
                },
                "vida": {
                    "nivel": humor.nivel(self.total_concluidas),
                    "total_concluidas": int(self.total_concluidas),
                    "carinhos_hoje": int(self.carinhos_hoje),
                    "min_sem_toque": round(max(0.0, agora - self.ultimo_toque) / 60.0, 1),
                    "min_sem_claude": round(max(0.0, agora - self.ultimo_evento) / 60.0, 1),
                },
                "seq": self.seq,
            }
