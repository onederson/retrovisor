@echo off
rem Abre o servidor do painel escondido (igual ao que sobe com o Windows).
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-CimInstance Win32_Process -Filter \"Name like 'python%%'\" | Where-Object CommandLine -like '*uvicorn server.main*') { Write-Host 'O servidor ja esta aberto.' } else { Start-Process wscript.exe -ArgumentList ('\"' + '%~dp0..\scripts\iniciar_oculto.vbs' + '\"'); Write-Host 'Servidor aberto.' }"
ping -n 2 127.0.0.1 >nul
