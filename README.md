# Retrovisor

**Um celular antigo vira o painel de instrumentos do seu PC.**

O Retrovisor transforma um Android parado na gaveta (aqui, um Galaxy S10+) numa tela fixa ao lado do monitor. Ela mostra o estado do PC em tempo real e funciona como um "stream deck" de toque. Basta olhar de relance, como num retrovisor, para saber quanto a GPU está esquentando, quanto você já gastou de IA hoje e o que está tocando, sem sair da janela em que está trabalhando.

Tudo roda no seu PC (Windows). O celular só abre uma página web, sem app nativo e sem root.

---

## Para que serve

- **Monitorar o PC:** CPU por núcleo, GPU (uso, temperatura, potência, clocks, VRAM), RAM, disco, rede e os processos que mais pesam.
- **Acompanhar o uso e o custo de IA:** tokens e custo do Claude Code, limites de uso do Claude e do agy, modelos carregados no Ollama, chamadas que passam pelo OmniRoute, gasto do dia e do mês em dólar e em real (com cotação automática).
- **Controlar o PC pelo toque:** mídia, volume, microfone, monitores, abrir ou trazer apps para a frente, carregar e descarregar modelos do Ollama, suspender, desligar, reiniciar e bloquear.
- **Dar outra vida a um celular velho:** ele fica na tomada 24/7, com a carga travada em 85% para poupar a bateria.

---

## Como funciona

```
┌──────────────── PC (Windows) ────────────────┐            ┌──── Celular ────┐
│                                               │            │                 │
│  coletores ──► hub ──► servidor FastAPI :8080 │ ◄── Wi-Fi ─┤  Chrome / Fully │
│  (hardware,     (junta     │  WebSocket /ws   │   ou adb   │  Kiosk abrindo  │
│   IA, mídia…)   o estado)  │  (estado a cada 1 s)          │  a página web   │
│                            │  POST /action/…  │ ──────────►│  (PWA)          │
│                    ações no Windows ◄─────────┤  toques    │                 │
│                                               │            │                 │
│  vigia :8081 (avisa o celular enquanto o PC   │            │                 │
│               ainda está ligando/bloqueado)   │            │                 │
└───────────────────────────────────────────────┘            └─────────────────┘
```

1. **Coletores** (`server/collectors/`): cada um lê uma fonte de dados no seu intervalo próprio. Exemplos: `psutil`/NVML para hardware, a API do Ollama, o banco do OmniRoute, os logs do Claude Code e a cotação do dólar. O formato que cada um devolve está em [`docs/CONTRATO.md`](docs/CONTRATO.md).
2. **Hub** (`server/hub.py`): roda os coletores em threads e guarda o último valor bom de cada um. Se um coletor falha, o painel mostra o erro sem perder o resto.
3. **Servidor** (`server/main.py`, FastAPI + uvicorn): entrega a página e, pelo WebSocket `/ws`, manda o estado completo a cada 1 segundo.
4. **Interface** (`web/`): página única feita para tela OLED (fundo preto, sem branco e com leve deslocamento de pixels a cada 5 min contra marcas na tela). Funciona como PWA.
5. **Ações** (`server/actions.py`): cada botão chama `POST /action/<id>`, que executa no Windows. Por exemplo, enviar a tecla de mídia, trocar o monitor, abrir um app ou suspender o PC.
6. **Vigia** (`server/vigia.py`): processo separado que sobe junto com o Windows, antes do login, e responde na porta 8081. Enquanto o painel ainda não está no ar, o celular mostra um "portão" fechado com um botão ON e reconecta sozinho quando o PC volta.

### Segurança

- Acessos vindos do próprio PC (`localhost`, que inclui o celular pelo `adb reverse`) não precisam de token.
- Qualquer outro acesso, como o celular pelo Wi-Fi, precisa do `token` definido em `config.toml`. Ele vai uma vez na URL (`?t=<token>`) e fica gravado num cookie.
- Libere a porta só na **rede privada** (o `autostart.ps1` já cria a regra assim). Não exponha o painel na internet: ele consegue desligar o seu PC.

---

## As telas

Navegue deslizando para os lados. Os pontos no topo mostram em que tela você está. A barra superior fica sempre visível, com hora, gasto do dia, CPU, GPU, status da conexão e o botão ⏻, que fecha o painel.

| # | Tela | O que tem |
|---|------|-----------|
| 1 | **IA** | Quatro quadrantes. **Claude:** limites de uso, tokens de hoje (entrada, saída, cache), custo equivalente de API e sessão. **OmniRoute:** liga/desliga, requisições, taxa de acerto, latência. **Ollama:** liga/desliga, tokens/s, modelos na VRAM. **agy e financeiro:** limites do agy, uso do maestro e gasto real em USD e BRL, hoje e no mês. |
| 2 | **PC** | GPU e CPU detalhadas, com gráficos (uso, temperatura, potência, clocks, ventoinha, encoder/decoder, uma barra por thread), top 5 processos, RAM, VRAM, swap, disco, rede e tempo ligado. |
| 3 | **Windows** | Teclado 4×3: só uma tela (arraste para escolher o monitor), duplicar, estender, área de trabalho, play/pause, próxima, volume ±, mudo, microfone, captura de tela, gerenciador de tarefas. |
| 4 | **Mídia** | O que está tocando em qualquer app do Windows: capa, título, artista, barra de progresso, voltar e avançar X s, faixa anterior e próxima, play/pause, volume, mudo e velocidade (0,25× a 2×, quando o app aceita). |
| 5 | **Apps** | Teclado 4×3 que abre o app ou, se ele já estiver aberto, traz a janela para a frente: Discord, Rocket League, Arquivos, os apps de `[apps]` no `config.toml` e uma tecla "Escolher app" com busca no Menu Iniciar. |
| 6 | **Modelos e celular** | Carregar ou liberar modelos do Ollama, zerar a sessão, liberar portas de desenvolvimento, apagar a tela; últimas 10 chamadas do OmniRoute; bateria e temperatura do próprio celular. |
| 7 | **Energia** | Um botão grande: arraste ↕ para escolher entre suspender, desligar, reiniciar e bloquear, e toque para executar. Desligar e reiniciar pedem um segundo toque para confirmar. |
| 8 | **Vendel** | O bichinho assistente. Cada janela do Claude Code vira um Vendel que mostra o que ela faz: pensando, escrevendo (vira teclado), lendo (olho de lupa), rodando comando (engrenagem), precisa de você (acena, o celular vibra e aparece um aviso em qualquer tela) e terminou (comemora). Sem toque por 2 min, o painel vem sozinho para cá. Toque nele para fazer carinho; segure para o resumo do dia. Tem humor (animado, curioso, com sono, carente), conversa por voz (microfone), olha fotos (câmera), faz perguntas para melhorar a memória e tem botões de **mudo**, **cego** e **forma** do Megabrain (base → suprema). O cérebro é o projeto `Vendel` (memória no Obsidian), que o painel sobe sozinho. Ligar uma vez: `python scripts/instalar_vendel.py` (desfazer: `--remover`). Detalhes em `docs/MINI.md` e `CELULAR.md`. |

---

## Requisitos

**No PC**
- Windows 10/11 (o projeto usa APIs do Windows: controles de mídia, áudio, monitores e energia).
- Python **3.11+**.
- Opcionais (sem eles, só a parte correspondente fica indisponível):
  - GPU NVIDIA, para os dados de GPU;
  - [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) (`adb`), para bateria do celular, conexão por cabo e acordar a tela;
  - [Ollama](https://ollama.com), OmniRoute, Claude Code e agy, para os quadrantes de IA.

**No celular**
- Qualquer Android com Chrome. Recomendado: [Fully Kiosk Browser](https://www.fully-kiosk.com) para tela cheia de verdade.
- Sem root.

---

## Instalação

```powershell
git clone https://github.com/onederson/retrovisor.git
cd retrovisor

# 1. Crie a sua configuração a partir do exemplo e troque o token
copy config.example.toml config.toml
notepad config.toml        # mude [servidor] token para um valor só seu

# 2. Suba o servidor (cria o .venv e instala as dependências na primeira vez)
powershell -ExecutionPolicy Bypass -File scripts\start.ps1
```

Teste no próprio PC: abra `http://localhost:8080`.

### Conectar o celular

Escolha uma das opções:

- **Pelo Wi-Fi (recomendado):** no celular, abra `http://<ip-do-pc>:8080/?t=<seu-token>`. Depois disso, basta `http://<ip-do-pc>:8080`.
  Para o Chrome tratar o endereço como "seguro" (tela cheia, manter a tela acesa, service worker), ative em `chrome://flags` a opção *Insecure origins treated as secure* com esse endereço.
- **Pelo cabo / adb:** com a depuração USB ligada, o `start.ps1` faz `adb reverse tcp:8080 tcp:8080`, e o celular abre `http://localhost:8080`.

Depois, no Chrome, use **Adicionar à tela inicial**, ou aponte o Fully Kiosk para a mesma URL.

O passo a passo completo de preparação do celular (trava de bateria em 85%, tela sempre ligada, rotação, adb por Wi-Fi) está em [`CELULAR.md`](CELULAR.md).

### Iniciar com o Windows

Em um PowerShell **como administrador**:

```powershell
scripts\autostart.ps1      # servidor do painel no logon + porta 8080 liberada na rede privada
scripts\vigia.ps1          # vigia na inicialização + porta 8081 (portão no celular)
```

Para desfazer, rode o mesmo script com `-Remover`.

Atalhos do dia a dia, na pasta `servidor/`: `abrir.bat`, `fechar.bat` e `reiniciar.bat` (o servidor roda escondido, sem janela).

---

## Configuração

Tudo fica em `config.toml`, que não vai para o git porque guarda o seu token. O modelo comentado é o [`config.example.toml`](config.example.toml).

| Seção | Para que serve |
|-------|----------------|
| `[servidor]` | host, porta e o **token** de acesso pelo Wi-Fi |
| `[intervalos]` | de quantos em quantos segundos cada coletor roda |
| `[caminhos]` | onde ficam os logs do Claude, o banco do OmniRoute, o `adb` etc. |
| `[ollama]` | URL da API e os modelos dos botões "Carregar" |
| `[omniroute]` | URL da API |
| `[acoes]` | terminal, repositório dos botões de git e portas que "Liberar portas" encerra |
| `[celular]` | endereço do celular no adb (`ip:5555`) |
| `[midia]` | apps que a tela de mídia ignora e quantos segundos pulam os botões ⏪ ⏩ |
| `[apps]` | até 8 apps da tela Apps: nome no Menu Iniciar e processo da janela |

Os preços por modelo, usados para calcular o custo dos tokens, ficam em [`pricing.toml`](pricing.toml).

---

## Estrutura

```
server/
  main.py          servidor FastAPI: página, WebSocket /ws, /action, /midia, autenticação
  hub.py           roda os coletores e monta o estado
  actions.py       tudo o que os botões fazem no Windows
  janelas.py       trazer janelas para a frente, atalhos do Menu Iniciar
  telas.py         ligar, desligar e duplicar monitores
  vigia.py         processo do "portão" (porta 8081)
  celular_adb.py   comandos no celular via adb
  collectors/      um arquivo por fonte de dados (hardware, ollama, omniroute,
                   claude, claude_usage, agy, fx, celular, bloqueio, midia)
web/               a interface (HTML, CSS, JS, service worker, ícones)
scripts/           instalação, inicialização automática e utilitários
servidor/          abrir, fechar e reiniciar com dois cliques
tests/             testes (pytest)
docs/CONTRATO.md   formato dos dados de cada coletor
CELULAR.md         como preparar o celular
```

---

## Desenvolvimento

```powershell
.venv\Scripts\python -m pytest            # roda os testes
$env:PAINEL_SO_VALIDAR = "1"              # modo ensaio: ações perigosas (desligar, bloquear,
                                          # trocar monitor) só validam, sem executar
python scripts\checar_oled.py             # confere se a interface não tem cores claras
```

**Para criar um coletor novo:** crie `server/collectors/<nome>.py` com `collect(cfg, ctx) -> dict`, registre-o em `server/hub.py` e adicione o intervalo em `[intervalos]`. As regras estão em [`docs/CONTRATO.md`](docs/CONTRATO.md).
