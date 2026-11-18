# Liga/desliga o painel junto com o Windows. Rode no PowerShell como Administrador.
#   powershell -File scripts\autostart.ps1          -> instala
#   powershell -File scripts\autostart.ps1 -Remover -> remove
# Tarefa Agendada no logon, com prioridade alta e sem o atraso da pasta Inicializar:
# o servidor sobe enquanto o Windows ainda monta a area de trabalho.
param([switch]$Remover)

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "Rode como Administrador (a tarefa usa prioridade alta e o firewall precisa da porta 8080)."
    exit 1
}

$taskName = "Painel S10+ Servidor"
$atalhoAntigo = Join-Path ([Environment]::GetFolderPath("Startup")) "Painel S10+.lnk"
Remove-Item $atalhoAntigo -ErrorAction SilentlyContinue  # metodo antigo (pasta Inicializar, sobe com atraso)

if ($Remover) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removido da inicializacao."
    return
}

$raiz = Split-Path -Parent $PSScriptRoot
$vbs = Join-Path $PSScriptRoot "iniciar_oculto.vbs"
$usuario = "$env:USERDOMAIN\$env:USERNAME"

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbs`"" -WorkingDirectory $raiz
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
# Priority 1 = alta (o padrao das tarefas e 7, abaixo do normal)
$settings = New-ScheduledTaskSettingsSet -Priority 1 -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

# Celular pelo Wi-Fi (so rede privada)
if (-not (Get-NetFirewallRule -DisplayName "Painel S10+ (8080)" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "Painel S10+ (8080)" -Direction Inbound -Protocol TCP -LocalPort 8080 -Profile Private -Action Allow | Out-Null
}
Write-Host "Painel sobe sozinho ao entrar no Windows (tarefa '$taskName', prioridade alta)."
