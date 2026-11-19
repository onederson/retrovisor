# Preparação do Galaxy S10+ (sem root)

Decisão: o aparelho fica **sem root** (bootloader travado). Desbloquear apagaria todos os dados.

## Bateria (uso 24/7 na tomada)
- Configurações > Assistência do aparelho e bateria > Bateria > Mais configurações > **Proteger bateria**: liga a trava de carga em **85%**.
- A tela 6 do painel (Modelos e Celular) mostra o nível. Fica âmbar acima de 85%, sinal de que a trava não está agindo.

## Depuração USB (já ativa)
- Opções do desenvolvedor > Depuração USB: ligada. O PC já está autorizado (`adb devices` mostra `RX8M301G98B device`).
- Opções do desenvolvedor > **Permanecer ativo** (tela não apaga carregando): ligar.

## Conexão
- **Cabo:** rode `scripts\start.ps1` no PC. Ele faz `adb reverse tcp:8080 tcp:8080`; no celular, abra `http://localhost:8080`.
- **Wi-Fi:** troque o `token` em `config.toml` e abra `http://<ip-do-pc>:8080/?t=<token>`. Libere a porta 8080 no Firewall do Windows só para a rede privada.

## Tela cheia
- No Chrome: menu > **Adicionar à tela inicial** e abra pelo ícone. Para esconder as barras de vez, use o **Fully Kiosk Browser** (opção sem root) apontando para a mesma URL.
- Brilho manual baixo (< 10%), brilho automático desligado e tema escuro do sistema.
- Configurações > Tela > Tempo limite da tela: o máximo. O painel também pede Wake Lock.

## Sem cabo (adb por Wi-Fi), configurado em 2026-11-17
- O celular (192.168.3.6) fica em `adb tcpip 5555` e o PC conecta com `adb connect 192.168.3.6:5555`. O `config.toml` (`[celular] adb_serial`) e o `scripts/start.ps1` já fazem isso.
- O servidor refaz o `adb reverse tcp:8080 tcp:8080` a cada 15 s, então o celular abre **http://localhost:8080** mesmo sem cabo. Esse endereço conta como "seguro" para o Chrome, o que libera tela cheia, Wake Lock e instalação como app.
- **Depois de reiniciar o celular**, o modo tcpip some: ligue o cabo uma vez e rode `C:\platform-tools\adb.exe tcpip 5555`. Depois pode tirar o cabo.
- Reserve o IP 192.168.3.6 para o celular no roteador (DHCP fixo). Se o IP mudar, troque `adb_serial` no `config.toml`.
- Plano B sem adb: `http://192.168.3.37:8080/?t=<token do config.toml>`. O token fica gravado num cookie, e depois basta abrir `http://192.168.3.37:8080/`. Por esse caminho o Chrome não segura a tela acesa.
- Configurado via adb (sem root): `screen_off_timeout` no máximo (a tela não apaga sozinha), `stay_on_while_plugged_in=7` e rotação travada em paisagem (`user_rotation 1`).

## Conexão automática (sobrevive a reinícios)
Sem root, o Android desliga o adb por Wi-Fi a cada reinício. Por isso o painel não depende do adb: o celular fala direto com o PC pelo Wi-Fi.

- **PC:** `scripts\autostart.ps1` (PowerShell **como administrador**) registra a Tarefa Agendada "Painel S10+ Servidor". Ela roda no logon com prioridade alta, sem o atraso da pasta Inicializar, e o servidor roda com prioridade acima do normal. O script também libera a porta 8080 na rede privada. Para tirar: `scripts\autostart.ps1 -Remover`.
- **Celular:** o Chrome fica aberto em `http://192.168.3.37:8080`. Sem o PC, aparece o portão em X com o botão ON e o celular tenta reconectar a cada 3 s. Quando o PC responde, a porta abre sozinha.
- **Botão ON:** força uma tentativa na hora. Se o PC não responder em 4 s, o botão treme em vermelho.
- **Botão ⏻ no topo:** fecha a porta. O painel continua conectado, e o botão ON fica aceso esperando o toque.

Configuração única no celular:
1. Chrome → `chrome://flags` → "Insecure origins treated as secure" → `http://192.168.3.37:8080` → Enabled → Relaunch. Isso libera o service worker, que mostra o portão mesmo com o PC desligado.
2. Abrir uma vez `http://192.168.3.37:8080/?t=<token do config.toml>`. O token fica gravado num cookie.
3. Reservar no roteador o IP 192.168.3.37 para o PC. Se o IP mudar, o celular não acha mais o PC.

## App no celular: Fully Kiosk Browser
O Chrome não abre em tela cheia direto um app instalado de endereço `http://`: ele sempre abre numa aba. Por isso o painel roda no Fully Kiosk Browser, instalado pela Play Store só no celular.

- Ícone **Painel S10+ OLED** na tela inicial: abre direto em tela cheia.
- Configuração do Fully:
  - Start URL `http://192.168.3.37:8080/?t=<token>`;
  - Fullscreen ligado;
  - Keep Screen On ligado;
  - Launch on Boot ligado;
  - Auto Reload after Page Error = 5 s.
- Para abrir as configurações: segurar na borda esquerda e deslizar para a direita.
- Celular ligado com o PC desligado: tela preta com "Loading…", e o Fully tenta de novo a cada 5 s. Quando o PC sobe, o painel abre sozinho.
- Se a conexão cair com o painel aberto, entra o portão em X da página.
- Se o token mudar no `config.toml`, troque também a Start URL do Fully.

## Vendel no Fully: microfone, câmera e som (tela 8)
O Fully (WebView) não tem reconhecimento de voz nem voz falada própria. Por isso o celular só **grava** e
**toca**: quem ouve é o gemma4 no PC (1 s) e quem fala é a voz "Microsoft Daniel" do Windows.
Para isso funcionar, no Fully (Settings → **Web Content Settings**) ligue:
- **Enable Microphone Access** (falar com o Vendel);
- **Enable Webcam Access** (o Vendel saber se você está na mesa e o botão de mostrar uma foto);
- **Autoplay Videos/Audio** (ele falar sozinho os avisos, como "terminei no s10+").
Na primeira vez o Android pergunta a permissão de câmera e microfone para o Fully: aceite.

Privacidade:
- **mudo** (canto de baixo, à esquerda): o microfone nem abre. Mesmo sem mudo, o microfone só abre quando
  você toca no botão e fecha sozinho quando você para de falar.
- **cego**: a câmera nem abre, e o Vendel aparece de olhos vendados. Sem cego, a câmera abre 1 s a cada
  10 s só para ver se tem movimento (dois quadrinhos de 32×24 em cinza, comparados no próprio celular;
  nada sai do celular). A foto do botão da câmera vai para o PC, é olhada e jogada fora.
- **forma** (canto de cima): base e 2 pensam no PC; 3 (agy) e suprema (Claude) pensam na nuvem, e o
  pedaço de memória da conversa sai do PC. Depois de 10 min sem conversa ele volta para a base.

## Espelhar o S10+ no PC (scrcpy, Wi-Fi)
Depois de cada reinício do celular, ligue o cabo uma vez e rode `adb tcpip 5555`. Depois:
`scrcpy -s 192.168.3.6:5555 --window-title "S10+ Painel" --max-size 1280 --no-audio --max-fps 30`
- O `-s` prende o scrcpy a este aparelho e não atrapalha outra instância, como a do projetor.
- O `--no-audio` evita misturar o som do celular com o do projetor.

## Desbloquear o PC com a digital (Remote Fingerprint Unlock)
- PC: módulo do Windows instalado (`FingerprintCredentialProvider`). Na tela de bloqueio ele escuta na porta 4009 (TCP/UDP).
- Celular: app `ro.andreimircius.remotefingerauth`, com o PC **ONEDERSON** pareado e a conta Microsoft cadastrada.
- No painel: com o PC bloqueado, o portão fecha com o botão **DESBLOQUEAR** (ícone de digital). O servidor detecta o bloqueio pelo `LogonUI.exe` (`server/collectors/bloqueio.py`); antes do logon, quem avisa é o vigia.
- O toque abre o app de digital por um link `intent:`. No Fully grátis isso exige ligar **Settings → Open Other URL Schemes**, e não depende de adb. O JavaScript Interface é PLUS e fica desligado.
- **Só abre no toque:** o app de digital nunca abre sozinho. Com o PC bloqueado, desligado, suspenso ou reiniciando, o painel fica no portão (**LIGAR** ou **DESBLOQUEAR**) até você tocar no botão do centro.
- Se o adb estiver no ar, o PC traz o Fully de volta para a frente depois do desbloqueio (ação `voltar_painel`). Sem adb, toque em voltar.
- Depois do toque em DESBLOQUEAR: abre o leitor, e a barra fica em 60% com **Encoste o dedo**. Quando o PC desbloqueia, ela corre até 100% e a porta abre no painel. Se você voltar sem desbloquear, a barra some em 6 s, o botão treme e mostra "Não desbloqueou"; o mesmo acontece se o leitor ficar 60 s aberto sem dedo.
- **Vídeo desligado:** com o PC desbloqueado e o monitor apagado por inatividade, o painel mostra a tela "Vídeo desligado". O toque acende o monitor com um movimento de mouse invisível (ação `acender_video`). Se o PC estiver bloqueado, a tela da digital aparece no lugar. O servidor recebe o estado do vídeo pelo aviso `GUID_CONSOLE_DISPLAY_STATE` do Windows (`server/collectors/bloqueio.py`).
- Se o desbloqueio falhar por firewall, crie a regra no PowerShell como administrador:
  `New-NetFirewallRule -DisplayName 'Remote Fingerprint Unlock' -Direction Inbound -Protocol TCP -LocalPort 4009 -Profile Private -Action Allow`

## Energia (tela 7 do painel)
- Botão gigante: tocar **suspende** (S3; a hibernação está desligada neste PC). Arrastar ↕ troca para Desligar, Reiniciar e Bloquear. Desligar e Reiniciar pedem um segundo toque em até 4 s.
- **Tela de cada estado:** antes de sumir, o PC avisa o celular. O aviso vale para qualquer caminho: painel, menu Iniciar, botão físico ou inatividade (`server/collectors/bloqueio.py`: `PBT_APMSUSPEND` e `WM_QUERYENDSESSION`; reiniciar ou desligar sai do evento 1074 do log System). O portão fecha na hora com **PC suspenso**, **PC desligado** ou **Reiniciando…**, e o ON fica esperando o toque. Se o PC some sem avisar (queda de energia, Wi-Fi), aparece "PC desligado ou dormindo". Depois de 2 min sem toque, a tela esmaece para poupar o OLED, e o primeiro toque acende de novo.
- **Barra de 0 a 100%:** ao tocar no ON, ao reiniciar ou quando o PC liga sozinho, o portão mostra uma barra. 0–25% ligando/acordando, 35–55% Windows iniciando, **60% Windows na tela de bloqueio**, 70–96% entrando no Windows e abrindo o painel, **100% = painel conectado**, e aí a porta abre. Se a barra chegou aos 60% sem um toque seu (reinício, PC ligado pelo botão físico), ela some e fica o DESBLOQUEAR. Se você já tinha tocado no LIGAR, ela espera em 60% e o botão abre o leitor. As fases vêm do vigia (porta **8081**, só leitura), que roda desde o boot, antes do logon.
- **Ligar:** com o PC dormindo ou desligado, o botão ON do portão abre o app de digital. O app manda o Wake-on-LAN (3 pacotes) **quando você encosta o dedo**, não ao abrir; conferido em 2026-11-18. O portão espera até 90 s, porque ligar do zero demora.
- **Configuração do WoL no app** (versão PRO), no PC ONEDERSON: *Send WoL-Packet* ligado, MAC `2C:F0:5D:E9:46:7D`, endereço **`192.168.3.255`** (broadcast, não o IP do PC: dormindo, o PC não responde no IP dele) e porta **9**.
- A placa de rede já está pronta para acordar o PC. Conferido em 2026-11-18: *Wake on Magic Packet* e *Shutdown Wake-On-Lan* ligados, armada no `powercfg`, e a inicialização rápida inativa porque a hibernação está desligada. Se um dia sair: `powercfg /deviceenablewake "Realtek PCIe GbE Family Controller #2"` (como administrador).
- Ligar depois de **desligar de verdade** depende da BIOS (MSI B450M PRO-M2 MAX, tecla Del no boot):
  - *Settings → Advanced → Power Management Setup → ErP Ready = **Disabled***;
  - *Settings → Advanced → Wake Up Event Setup → Resume By PCI-E Device = **Enabled***.

## Digital sozinha quando o PC liga ou acorda (vigia)
- `server/vigia.py` roda como Tarefa Agendada a partir do boot, antes de qualquer logon. Sempre que o PC vai para a tela de bloqueio, ele acende o celular e abre o app de digital pelo adb. Isso vale ao ligar, ao acordar da suspensão, com Win+L, pelo painel ou por inatividade. Depois do desbloqueio, traz o Fully de volta.
- Painel congelado com o ponto verde e sem dados novos: desde 2026-11-18 ele se reconecta sozinho depois de 6 s sem receber nada do PC.
- Instalar uma vez, no PowerShell **como administrador**: `powershell -File scripts\vigia.ps1`. Para tirar: `scripts\vigia.ps1 -Remover`.
- Log: `cache\vigia.log`.
- O vigia também responde o estado do boot em `http://<pc>:8081/` (só leitura, sem token): é dali que vem a barra de carregamento. O instalador libera a porta 8081 na rede privada.
- Depende do adb por Wi-Fi no ar (ver acima). Sem adb, sobra a reserva do próprio painel: tocar no botão de digital.
