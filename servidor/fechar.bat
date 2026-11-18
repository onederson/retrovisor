@echo off
rem Fecha o servidor do painel.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Get-CimInstance Win32_Process -Filter \"Name like 'python%%'\" | Where-Object CommandLine -like '*uvicorn server.main*'; if ($p) { $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Write-Host 'Servidor fechado.' } else { Write-Host 'O servidor ja estava fechado.' }"
ping -n 2 127.0.0.1 >nul
