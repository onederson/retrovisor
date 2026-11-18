' Sobe o painel do S10+ junto com o Windows, sem janela.
' Chamado pela Tarefa Agendada "Painel S10+ Servidor" (scripts\autostart.ps1) e por servidor\abrir.bat.
' Vai direto ao python, sem passar pelo PowerShell nem esperar o adb: o servidor refaz o
' adb reverse sozinho a cada 15 s.
Set fso = CreateObject("Scripting.FileSystemObject")
raiz = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
py = raiz & "\.venv\Scripts\python.exe"
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = raiz
If fso.FileExists(py) Then
  sh.Run """" & py & """ -m uvicorn server.main:app --host 0.0.0.0 --port 8080", 0, False
Else
  sh.Run "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & raiz & "\scripts\start.ps1""", 0, False
End If
