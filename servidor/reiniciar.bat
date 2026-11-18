@echo off
rem Fecha e abre de novo o servidor do painel.
call "%~dp0fechar.bat"
ping -n 1 127.0.0.1 >nul
call "%~dp0abrir.bat"
