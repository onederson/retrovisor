# Vigia do painel S10+: abre app de digital ao bloquear/iniciar o PC.
# Deve ser executado como Administrador.
#   powershell -File scripts\vigia.ps1          -> instala e inicia como Tarefa Agendada
#   powershell -File scripts\vigia.ps1 -Remover -> remove a tarefa agendada
param([switch]$Remover)

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Warning "Este script precisa ser executado como Administrador."
    exit 1
}

$taskName = "Painel S10+ Vigia"

if ($Remover) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tarefa '$taskName' removida com sucesso."
    return
}

$raiz = Split-Path -Parent $PSScriptRoot
$pyw = Join-Path $raiz ".venv\Scripts\pythonw.exe"
$py = Join-Path $raiz ".venv\Scripts\python.exe"
$pythonExe = if (Test-Path $pyw) { $pyw } else { $py }

$action = New-ScheduledTaskAction -Execute $pythonExe -Argument "-m server.vigia" -WorkingDirectory $raiz
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -Priority 1 -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
# Porta 8081: o celular acompanha o boot (barra de carregamento) antes de o painel subir
if (-not (Get-NetFirewallRule -DisplayName "Painel S10+ Vigia (8081)" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "Painel S10+ Vigia (8081)" -Direction Inbound -Protocol TCP -LocalPort 8081 -Profile Private -Action Allow | Out-Null
}
Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue  # reinicia com o codigo novo
Start-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
Write-Host "Tarefa '$taskName' registrada e iniciada com sucesso."
