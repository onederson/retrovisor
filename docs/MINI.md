# Mini — o assistente que mora no S10+

Status (2026-11-19): **fase 1 feita**. `server/mini.py`, `scripts/mini_hook.py`,
`scripts/instalar_vendel.py`, `web/vendel.js` (tela 8), testes em `tests/test_mini.py`.
Fases 2 e 3 e o cérebro ainda são plano.

Diferenças em relação ao plano abaixo, decididas na implementação:
- `Notification` de ociosidade ("Claude is waiting for your input", `notification_type = idle_prompt`)
  é ignorada no hook: só pedido de permissão vira `precisa`. Senão o Vendel acenaria depois de toda tarefa.
- Sessões rodando em worktree do maestro (`/.maestro/wt/`) aparecem como ajudante "maestro".
- Extras: o Vendel se monta pixel a pixel quando uma janela abre e se desfaz quando fecha; toque = carinho
  (coração); relógio fraco no canto e resumo do dia ("hoje: 7 tarefas · 1h30 de Claude"); a cena inteira
  anda 1–2 px por minuto para não marcar o OLED.

## Ideia em uma frase

O Pestinha (projeto `Assistente`) vira o **cérebro** (memória no vault + conversa) e o Mini, um
bichinho de pixel no S10+, vira o **corpo e o rosto**: mostra o que cada janela do Claude está
fazendo, aparece sozinho quando o painel fica parado e, na fase 3, conversa por voz.

## Por que mudar o plano do Assistente

| Hoje no Pestinha | Problema | Na proposta |
|---|---|---|
| REPL de texto no terminal | Ninguém lembra de abrir; não tem presença | Mora no S10+, sempre à vista |
| Cérebro sem LLM (regex + templates) | Soa robótico rápido | Ollama local (grátis) responde; regex só para comandos `/` |
| Só reage quando você digita | Não percebe nada | Recebe eventos do Claude, do PC e do relógio e avisa sozinho |
| Memória no vault, grafo, humor | **Isso é bom** | Fica igual, vira biblioteca usada pelo servidor |

Observação: a pasta `Assistente` não é um repositório git. Antes da fase 3, fazer `git init` lá.

---

## Fase 1 — Mini + estados do Claude

### 1.1 De onde vêm os estados: hooks do Claude Code

Script novo `scripts/mini_hook.py` (só biblioteca padrão), registrado em `~/.claude/settings.json`
ao lado dos hooks que já existem (rtk, maestro). Ele:

1. Lê o JSON do hook pela entrada padrão (`session_id`, `hook_event_name`, `cwd`, `tool_name`).
2. Faz `POST http://127.0.0.1:8080/mini/evento` com `{sessao, evento, projeto, ferramenta, quando}`,
   timeout de 0,3 s.
3. **Sempre** sai com código 0 e sem imprimir nada: com o servidor fora, o Claude não pode travar
   nem receber texto estranho no contexto. Não manda conteúdo de prompt, só o nome do evento e da ferramenta.

`projeto` = nome da pasta do `cwd` (ex.: `s10+`). Nada de caminho completo na tela.

Eventos registrados e o que viram:

| Hook | Estado do Mini |
|---|---|
| `SessionStart` | aparece um Mini novo (acenando, depois `ocioso`) |
| `UserPromptSubmit` | `pensando` (balão "…") |
| `PreToolUse` Edit / Write / NotebookEdit | `digitando` |
| `PreToolUse` Read / Grep / Glob / WebFetch / WebSearch | `lendo` (lupa) |
| `PreToolUse` Bash / PowerShell | `executando` (chave inglesa) |
| `PreToolUse` Agent | `delegando` (um mini-ajudante pequeno aparece ao lado) |
| `PreToolUse` outras | `trabalhando` (genérico) |
| `Notification` | `precisa_voce` (acena + celular vibra uma vez) |
| `Stop` | `concluido` (comemora por 8 s, depois `ocioso`) |
| `SessionEnd` | o Mini daquela janela se despede e some |

**Sessões fantasmas:** o próprio Retrovisor roda `claude -p "/usage"` (coletor `claude_usage`), e
o Pestinha/maestro também chamam a CLI. Isso dispararia hooks e criaria Minis falsos. Regra: quem
chama o `claude` por programa define a variável `MINI=0` no ambiente; o hook herda o ambiente e,
vendo `MINI=0`, sai sem enviar nada. O maestro pode usar `MINI=ajudante` para aparecer como
mini-ajudante em vez de sessão inteira.

### 1.2 Servidor

Módulo novo `server/mini.py` (não é coletor, recebe eventos):

- Rota `POST /mini/evento`: **só aceita pedido da própria máquina** (`_local`), valida campos e
  tamanho, ignora evento desconhecido.
- Estado em memória por sessão: `{projeto, estado, ferramenta, desde, ultimo_evento}`.
- Limpeza: sessão sem evento há 30 min some; estado ativo (`pensando`, `digitando`…) sem evento há
  10 min vira `ocioso` (cobre Claude fechado à força, sem `SessionEnd`).
- Contadores do dia em `cache/mini.json`: tarefas concluídas, tempo trabalhando por projeto.
- O snapshot do WebSocket ganha a chave `mini`:
  ```json
  {"sessoes": [{"id": "ab12", "projeto": "s10+", "estado": "digitando",
                "ferramenta": "Edit", "desde": "2026-11-19T14:02:10-03:00"}],
   "hoje": {"concluidas": 7, "trabalhando_s": 5400},
   "seq": 42}
  ```
  `id` = 4 primeiros caracteres do session_id (só para diferenciar, nunca o id inteiro).
- Reação imediata: igual ao aviso de energia, o laço do `/ws` interrompe a espera de 1 s quando o
  `seq` do Mini muda. A animação começa em menos de 100 ms após o hook.

### 1.3 Tela própria (8ª tela)

`<section class="tela" id="tela-mini">`, a última do swipe.

- Fundo preto puro. Um Mini por sessão ativa, até 4 (o resto vira "+2"). Sem sessões: um Mini só,
  sozinho, à toa.
- Embaixo de cada Mini: nome do projeto e o estado com tempo ("digitando · 40 s"), em cinza escuro.
- Desenho em `<canvas>` com sprites de pixel art definidos no próprio `app.js` (matrizes 16×16,
  ampliadas sem suavizar). Nada de imagem externa. Personagem **original**, na paleta laranja do
  Claude, não é cópia do mascote oficial.
- Animação a ~8 quadros/s; para de desenhar quando a tela não está visível (economia).
- Tocar num Mini: ele reage (pula, coração). Na fase 2, o toque longo abre o resumo da sessão.

### 1.4 Ir para o Mini sozinho

- Reaproveita o temporizador de repouso que já existe (`acordarRepouso`, 2 min sem toque).
- Com o PC conectado e o portão aberto: em vez de só esmaecer, rola até `tela-mini`.
- Com o PC desligado/bloqueado: continua como hoje (portão), o Mini não tem o que mostrar.
- Não pula se houver sobreposição aberta (tela de vídeo, modal, edição de tecla).
- Chegando no Mini, fica lá; o toque não volta para a tela anterior (você navega como quiser).
- `precisa_voce` em qualquer tela: vibra uma vez e mostra uma faixa pequena no topo
  "s10+ precisa de você"; tocar na faixa leva ao Mini.

### 1.5 OLED

- Fundo `#000`, nada claro parado. Cada Mini anda devagar pela sua área; os rótulos mudam de posição
  alguns pixels a cada minuto.
- 10 min sem nenhum evento nem toque: `dormindo` (Mini encolhido, "zzz" fraco, brilho baixo).
- 23h–6h: tudo com brilho reduzido.

### 1.6 Testes da fase 1

- `tests/test_mini.py`: mapeamento hook→estado, limpeza por tempo, rejeição de pedido não local,
  campos inválidos, `MINI=0` no hook, hook com servidor fora (sai 0 em < 0,5 s, sem saída).
- No aparelho: abrir 2 janelas do Claude, conferir 2 Minis, pedir uma permissão e ver a vibração.

---

## Fase 2 — Vida de tamagotchi

Sem mecânica de punição (o Mini nunca "morre" nem cobra comida). O humor vem de coisas reais e usa
os estados que o Pestinha já tem: **animado, curioso, tranquilo, sonolento, carente**.

| Fonte real | Efeito |
|---|---|
| Tarefas concluídas no dia | energia e alegria sobem; 10+ no dia → animado |
| Madrugada (23h–6h) | sonolento, boceja, dorme mais cedo |
| Muito tempo sem você tocar nem usar o Claude | carente (olha para a tela, acena de vez em quando) |
| Janela de 5h acima de 80% (`claude_usage`) | cansado, suando |
| GPU acima de 80 °C (`hardware`) | abanando, com calor |
| Toque / carinho | coração, humor sobe |

- Persistido em `cache/mini.json`.
- **Resumo do dia** (toque longo): tarefas concluídas, tempo de Claude trabalhando por projeto,
  tokens e custo equivalente (já existem no coletor `claude`).
- Opcional: nível pelo total de tarefas, que libera acessórios simples (chapéu, óculos).
- Tentar: toque longo numa sessão traz a janela do terminal para a frente (`server/janelas.py`).
  Depende de achar a janela certa pelo título; se não for confiável, fica de fora.

---

## Fase 3 — Jarvis (o Pestinha entra)

### 3.1 Pestinha como biblioteca

- `config.toml` do Retrovisor ganha `[mini] assistente = "C:/Users/Vendel/Desktop/Projetos/Assistente"`.
- O servidor importa o pacote `pestinha` (é só biblioteca padrão, não precisa instalar nada) e roda
  as chamadas numa thread. O REPL `python pestinha.py` continua funcionando igual.
- Mudança no Pestinha: conversa livre passa a usar o Ollama por padrão (backend `ollama` já existe
  no `config.toml` dele), com o cérebro de regex como plano B quando o Ollama estiver fora.
  Comandos `/lembrar`, `/sobre` etc. continuam sem LLM.
- O nome e a personalidade vêm de `Eu/Assistente.md` no vault: o Mini e o Pestinha são o mesmo ser.

### 3.2 Falar com ele

- Botão de microfone na tela do Mini. Reconhecimento de voz do Chrome (`SpeechRecognition`, pt-BR).
  Funciona porque o painel já é origem segura (localhost via `adb reverse` e a flag do Chrome).
- `POST /mini/falar {texto}` → Pestinha responde → texto no balão + voz (`speechSynthesis` pt-BR).
- Enquanto ele pensa, o Mini fica `pensando`, igual ao Claude.
- Tudo que você fala vai para o diário do vault (o Pestinha já faz isso).

### 3.3 Avisos por conta própria

Curtos, com voz opcional, e com **"não perturbe"** (botão) e silêncio automático 23h–7h:

- "Terminei no s10+" (Stop de uma sessão que trabalhou mais de 2 min).
- "O Claude precisa de você no s10+" (Notification).
- "Sua janela de 5h passou de 80%" / "reseta em 15 min".
- "A GPU está a 85 °C".
- O trabalho do dia vai para o diário do vault ("14:32 — tarefa concluída em [[s10+]]"), e o grafo
  do Pestinha aprende em que projetos você trabalha.

---

---

## O cérebro do Vendel (vale para a fase 3 em diante)

Pedido do onederson (2026-11-19): o Vendel é a consciência dele. **Tudo** que passa por qualquer IA
(Claude Code, Ollama, agy/Antigravity, OmniRoute, maestro, conversas com o próprio Vendel) alimenta a
memória. A memória é **local**, no Obsidian, e as ligações têm que ser **profundas**, não "as duas
notas falam de Python".

Princípio: **o vault é o cérebro; as IAs são só boca e raciocínio emprestados.** O modo Megabrain
pode usar Claude/agy para pensar melhor, mas o que entra e o que sai volta sempre para o vault.

### Etapa 1 — Captura (tudo cai numa caixa de entrada)

Cada fonte grava a conversa crua em `<vault>/.vendel/entrada/AAAA-MM-DD.jsonl` (pasta oculta, fora das notas):

| Fonte | Como pegar |
|---|---|
| Claude Code | já fica local em `~/.claude/projects/*.jsonl`; ler o que for novo (igual ao coletor `claude`) |
| Ollama | um "porteiro" local na porta 11434 que repassa ao Ollama real (movido para outra porta) e anota pergunta e resposta |
| OmniRoute | logs do próprio OmniRoute (verificar onde ficam) |
| agy / Antigravity | arquivos locais do agy (descobrir onde guarda as conversas) |
| maestro | logs de cada tarefa delegada |
| Vendel | tudo que você fala com ele |

Antes de gravar: remover segredos (chaves, tokens, senhas, conteúdo de `.env`), com a mesma regra
de sempre. Conversas automáticas do próprio Vendel (`MINI=0`) não entram, para ele não ficar
digerindo a si mesmo.

### Etapa 2 — Digestão (Ollama local, quando o PC está parado ou de madrugada)

Para cada conversa nova, o modelo local extrai, sempre com a **fonte** (qual conversa, que dia):
- fatos sobre o onederson (gostos, rotina, pessoas, objetivos);
- o que ele **fez** e **decidiu**, e principalmente **por quê**;
- o que ele aprendeu, onde travou e o que funcionou;
- projetos, ferramentas e ideias.

Isso vira ou atualiza notas em `Pessoas/`, `Projetos/`, `Conceitos/`, `Decisoes/`, `Diario/`, sempre
acrescentando, nunca apagando o que você escreveu.

### Etapa 3 — Ligações profundas

Hoje o Pestinha liga duas notas porque apareceram juntas 3 vezes. Isso é a ligação "besta". A nova regra:

1. Buscar candidatas por **sentido**, não por palavra: embeddings locais no Ollama (ex.: `bge-m3`, bom em português).
2. O modelo local julga cada par e só cria a ligação se conseguir dizer **o tipo** e **o porquê**, com prova.
3. Tipos de ligação: `causou`, `por_causa_de`, `depende_de`, `parte_de`, `decidiu_por`, `trocou_por`,
   `contradiz`, `aprendeu_com`, `motivacao`, `repete_padrao`.
4. Gravada na nota como campo do Obsidian, que o grafo mostra e plugins como ExcaliBrain/Dataview leem:
   ```
   por_causa_de:: [[Maestro]]
   - O Retrovisor nasceu para ver o gasto de IA, porque o onederson divide o trabalho entre modelos baratos (conversa 2026-11-17).
   ```
5. Ligação sem porquê é descartada. Ligação com pouca certeza vira **pergunta** (etapa 5).

### Etapa 4 — Reflexão (uma vez por semana)

O Vendel relê a semana e escreve em `Eu/` notas de **padrões**, com links de prova:
- jeito de trabalhar ("começa pelo plano, gosta de ver funcionando na tela física");
- o que anima e o que trava;
- objetivos que aparecem várias vezes;
- contradições ("disse X em outubro, fez Y agora"), que viram pergunta.

### Etapa 5 — Perguntas para melhorar a memória

- Fila de perguntas em `<vault>/.vendel/perguntas.json`, geradas por: nota com pouca informação,
  ligação incerta, contradição, decisão sem porquê.
- Ele pergunta na hora certa: depois de uma tarefa concluída, nunca de madrugada, no máximo 3 por dia.
- A resposta entra na memória marcada como "o onederson disse", que vale mais que qualquer dedução.

### Megabrain

- Modo normal: Ollama local responde, com o contexto tirado do vault.
- Modo Megabrain: Claude ou agy respondem, para pensar mais fundo. **Atenção:** nesse modo, o pedaço
  de memória usado como contexto vai para a internet naquela resposta. A memória continua guardada
  só no PC. Notas marcadas `privado: true` nunca saem.
- Nos dois modos, a pergunta e a resposta voltam para a caixa de entrada e passam pela digestão.

---

## Fora do escopo (por enquanto)

- Ouvir o tempo todo ("Ei, Mini"): gasta bateria e exige detecção de palavra-chave.
- Mandar comandos para o Claude pelo celular (aprovar permissão etc.).
- Notificação fora do S10+ (no celular principal).

## Decisões (2026-11-19)

1. **Nome:** o bichinho se chama **Vendel**. Na fase 3, `Eu/Assistente.md` do vault passa a usar esse nome.
2. **Visual:** 3 opções desenhadas (A Bolinha, B Robozinho, C Bichinho de antenas). Falta escolher.
3. **Voz:** a voz pt-BR do próprio Android (`speechSynthesis`).
