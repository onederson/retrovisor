> **Documento histórico:** é o planejamento inicial. O painel atual tem 7 telas; veja o [README](README.md).

# Planejamento do Projeto: S10+ AI & PC Telemetry + Stream Deck (OLED-Safe)

## 1. Visão Geral e Objetivo
Transformar um **Samsung Galaxy S10+ (SM-G975F)** com falha de tensão/PWM no display em uma central de comando de mesa dedicada e conectada ao PC. 

O dispositivo funcionará em modo Kiosk exibindo uma aplicação unificada dividida em **painéis navegáveis por gesto lateral (Swipe)**, combinando:
1. **Monitoramento em tempo real de LLMs e Custos** (Claude, AGY, OmniRoute e Ollama Local).
2. **Telemetria de Hardware do PC** (CPU, GPU, VRAM, RAM e Rede).
3. **Stream Deck / Macro Pad Interativo** (atalhos de desenvolvimento, controle de mídia/OBS e gerenciamento rápido de modelos locais).

---

## 2. Regras de Engenharia para o Display (Contorno do Defeito Físico)
Como o painel Dynamic AMOLED do S10+ apresenta listras entre $10\%$ e $99\%$ de brilho e falha durante picos de corrente em fundos brancos, a interface seguirá restrições visuais estritas:

* **Fundo 100% Preto Puro (`#000000`):** Desliga fisicamente os pixels de fundo no painel AMOLED, mantendo o consumo elétrico próximo de zero na maior parte da tela.
* **Proibição de Branco Puro (`#FFFFFF`):** Nenhum texto, ícone ou borda usará branco puro para evitar o acionamento simultâneo máximo dos subpixels R, G e B.
* **Paleta de Baixa Corrente (Low-Current Dark UI):**
  * Texto primário: Cinza suave (`#9E9E9E`) ou Verde Matriz suave (`#00C853` com opacidade reduzida).
  * Destaques / Gráficos: Ciano escuro (`#00838F`), Âmbar (`#FF8F00`) e Roxo suave (`#7E57C2`).
  * Alertas de orçamento/temperatura: Vermelho escuro (`#C62828`) sem piscar a tela inteira.
* **Trava de Brilho Físico:** Brilho do Android fixado abaixo de $10\%$ (ou em $100\%$ combinado com máscara de software via *OLED Saver* caso necessário), sem brilho automático.
* **Prevenção de Burn-in:** Deslocamento sutil de $1\text{ px}$ a $2\text{ px}$ (*pixel shifting*) nos containers estáticos a cada $5\text{ minutos}$.

---

## 3. Preparação do Hardware e Sistema no S10+
Como o aparelho já possui o *e-fuse* do Knox alterado (`0x1`), o uso de **Root** é recomendado para garantir operação segura $24/7$ na tomada ou base sem fio Qi:

1. **Controle de Bateria (Obrigatório):**
   * Módulo **ACC (Advanced Charging Controller)** via Magisk configurado para interromper a carga em $65\%$ e retomar apenas em $55\%$ (`acc 65 55`), evitando estufamento da bateria.
2. **Comunicação com o PC (Latência Zero):**
   * **Opção A (Cabo USB-C):** Usando `adb reverse tcp:8080 tcp:8080` para trafegar toda a telemetria e comandos via USB sem depender do Wi-Fi.
   * **Opção B (Base Sem Fio Qi):** Conexão via Wi-Fi local (`5 GHz`) apontando para o IP estático do PC na porta `8080`.
3. **Execução da Interface (Modo Kiosk):**
   * **Fully Kiosk Browser** ou **PWA em Tela Cheia** (sem barra de status e sem barra de navegação do Android), com tela configurada para manter-se acesa enquanto o PC estiver ligado.

---

## 4. Arquitetura da Solução (Por que um Web App Local Unificado?)
Em vez de usar aplicativos separados (como *Pitikapp* para hardware e *Touch Portal* para botões), que exigem trocar de app e não possuem integração nativa com APIs de LLMs ou roteadores como o OmniRoute, a arquitetura será baseada em um **Servidor Local em Python (FastAPI + WebSockets)** rodando no PC e um **Frontend HTML5/CSS/JS** aberto no S10+.

```
[ PC Principal (Host) ]
 ├── Coletor Hardware (psutil / NVML / LibreHardwareMonitor)
 ├── Coletor Ollama Local (API :11434/api/ps & métricas)
 ├── Coletor OmniRoute (API de status / logs de roteamento)
 ├── Coletor Claude & AGY (APIs de Usage / leitura de logs locais)
 ├── Executor de Comandos ( Teclas, Scripts, OBS, Controle de Áudio )
 └── Servidor FastAPI (WebSocket em tempo real :8080)
         │
         ▼  (Via USB ADB Reverse ou Wi-Fi Local)
[ Galaxy S10+ (Client Kiosk #000000) ]
 └── Interface Touch com Swipe Horizontal (CSS Scroll-Snap / Swiper)
      ├── [Tela 1] Painel de Telemetria IA + Custos + PC
      ├── [Tela 2] Stream Deck / Macro Pad (Grid de Botões)
      └── [Tela 3] Controle Rápido de Modelos (Ollama / OmniRoute)
```

---

## 5. Layout e Funcionalidades por Tela (Navegação por Swipe)

A navegação entre telas será feita **arrastando o dedo para os lados (Swipe Left/Right)** com transições suaves e sem flashes claros. Uma barra superior fixa e discreta permanece visível em todas as telas mostrando: **Hora**, **Gasto Total do Dia ($ / R$)** e **Temp. CPU/GPU**.

### Tela 1: Telemetria de IA, Tokens, Custos e Hardware (Tela Principal)
Dividida em 4 quadrantes com bordas finas (`#1F1F1F`) sobre fundo `#000000`:

1. **Quadrante Claude & AGY (Quotas e Tokens):**
   * **Claude:** Tokens consumidos no dia/sessão (*Input*, *Output*, *Cache Read/Write*), barra de progresso da janela de uso atual (ex: limite de 5h ou orçamento de API) e custo acumulado em dólares.
   * **AGY:** Consumo atual de tokens/créditos da conta, porcentagem restante da cota mensal/diária e status de disponibilidade dos agentes.
2. **Quadrante OmniRoute (Roteador de LLMs):**
   * Status do serviço (`ONLINE` / `OFFLINE`).
   * Modelo/Provedor ativo na última requisição e motivo do roteamento (ex: *Cost-Saving*, *Fallback*, *High-Reasoning*).
   * Contagem de requisições do dia, taxa de acerto/erro e latência média ($\text{ms}$).
3. **Quadrante Ollama Local (Inferência Local):**
   * Lista de modelos carregados na VRAM no momento (via `/api/ps`).
   * Consumo exato de VRAM pelo modelo (em $\text{GB}$) e tempo restante de *keep-alive*.
   * Velocidade da última geração em tempo real ($\text{tokens/s}$).
4. **Quadrante Consolidado Financeiro + Hardware PC:**
   * **Financeiro:** Total gasto **Hoje** e **Mês Atual** (somando Claude + AGY + rotas pagas do OmniRoute), exibido em $\text{USD}$ e convertido automaticamente para $\text{BRL}$.
   * **Hardware PC:** Barras compactas de CPU ($\%$ e $^\circ\text{C}$), GPU ($\%$ e $^\circ\text{C}$), VRAM Total usada e RAM do sistema.

---

### Tela 2: Stream Deck / Macro Pad (Ao arrastar para a esquerda)
Grade de botões táteis ($4 \times 3$ ou $5 \times 3$) com ícones monocromáticos/neon escuro e feedback tátil na tela (`navigator.vibrate(25)` ao tocar):

* **Linha 1 — Controle de IA e Ambiente Local:**
  * `[Ejetar VRAM Ollama]`: Envia comando para descarregar todos os modelos da GPU imediatamente (`keep_alive: 0`).
  * `[Trocar Perfil OmniRoute]`: Alterna entre modo *Econômico* (modelos leves/locais) e modo *Performance* (Claude/modelos topo de linha).
  * `[Abrir Claude / AGY]`: Foca ou abre o terminal/IDE de trabalho no PC.
  * `[Reset Contador Sessão]`: Zera o marcador temporário de tokens da tarefa atual para medir quanto uma *feature* específica custou.
* **Linha 2 — Produtividade e Dev:**
  * `[Terminal / WSL]`, `[Git Status / Push]`, `[Limpar Portas Node/Python]`, `[Print / OCR]`.
* **Linha 3 — Mídia, Áudio e Streaming (OBS):**
  * `[Mute Mic Global]` (muda de cor quando mutado), `[Play/Pause Mídia]`, `[Volume Down/Up]`, `[Trocar Cena OBS]`.

---

### Tela 3: Gerenciador Detalhado & Saúde do S10+ (Segundo Swipe)
* Botões diretos para pré-carregar modelos específicos no Ollama (ex: *Load Qwen*, *Load Llama*, *Load DeepSeek*) antes de começar a programar.
* Histórico das últimas 10 chamadas roteadas pelo **OmniRoute** (Horário | Provedor | Tokens | Custo estimado).
* Status interno do **Galaxy S10+**: Nível de bateria (confirmando a trava do ACC em $65\%$), temperatura da bateria do celular e botão para apagar/escurecer totalmente o painel à noite.

---

## 6. Como os Dados Serão Coletados no PC (Fontes de Dados)

| Módulo | Fonte de Dados / Integração no Backend Python | Frequência de Atualização |
| :--- | :--- | :--- |
| **Hardware PC** | Biblioteca `psutil` (CPU/RAM/Rede) + `pynvml` (GPU NVIDIA: VRAM, Temp, Load) ou API JSON do *LibreHardwareMonitor*. | A cada $1\text{ s}$ via WebSocket |
| **Ollama Local** | Requisição `GET http://localhost:11434/api/ps` para modelos na VRAM + interceptação/log de respostas para calcular $\text{tokens/s}$. | A cada $2\text{ s}$ |
| **OmniRoute** | Leitura da API/endpoint de métricas do OmniRoute (ou leitura do banco SQLite/JSON de logs do roteador local) extraindo tokens por rota e custo. | Tempo real / Evento |
| **Claude** | Leitura dos arquivos locais de telemetria/sessão (ex: logs JSONL do Claude Code em `~/.claude/projects/` ou endpoint de Usage da API Anthropic). | A cada $5\text{ s}$ ou por evento |
| **AGY** | Leitura do arquivo de estado/configuração local do cliente AGY, proxy de rede local ou endpoint de quota da conta. | A cada $10\text{ s}$ |
| **Câmbio USD/BRL** | Consulta na AwesomeAPI (`https://economia.awesomeapi.com.br/json/last/USD-BRL`) em cache para converter o gasto de tokens em Reais. | A cada $30\text{ min}$ |

---

## 7. Roteiro de Execução (Fases do Projeto)

### Fase 1: Preparação do S10+
- [ ] Garantir Root via Magisk e instalar o módulo **ACC** (`acc 65 55`).
- [ ] Ativar a Depuração USB nas Opções do Desenvolvedor.
- [ ] Instalar um navegador compatível com modo tela cheia (Chrome PWA ou Fully Kiosk) e travar o brilho no nível seguro ($<10\%$).

### Fase 2: Backend Base no PC (FastAPI)
- [ ] Criar servidor Python com FastAPI servindo a página HTML estática e um canal WebSocket (`/ws`).
- [ ] Implementar o coletor de Hardware (CPU, GPU, VRAM, RAM) e o coletor do **Ollama** (`/api/ps` + botão de *Unload VRAM*).

### Fase 3: Conectores de Tokens (Claude, AGY e OmniRoute)
- [ ] Mapear os diretórios de logs locais ou chaves de API de monitoramento do Claude, AGY e OmniRoute.
- [ ] Criar tabela de preços por $1\text{ milhão}$ de tokens (*Input*, *Output*, *Cache*) no backend para consolidar o gasto diário e mensal em $\text{USD}$ e $\text{BRL}$.

### Fase 4: Interface Touch OLED-Safe e Ações do Stream Deck
- [ ] Construir o frontend com CSS `#000000` estrito e *Scroll-Snap* horizontal para o gesto de arrastar entre Telemetria e Stream Deck.
- [ ] Mapear os endpoints de ação (`POST /action/{id}`) no Python para acionar atalhos de teclado, scripts e comandos de sistema no PC.