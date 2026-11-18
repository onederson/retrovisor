# Sobe o painel do S10+. Uso: powershell -File scripts\start.ps1
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$py = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    python -m venv .venv
    & $py -m pip install -q -r requirements.txt
}

$adb = "C:\platform-tools\adb.exe"
$m = Select-String -Path config.toml -Pattern '^adb_serial\s*=\s*"([^"]+)"'
if ((Test-Path $adb) -and $m) {
    # So o aparelho do painel (-s): nunca mexe em outros dispositivos no adb (TV, projetor...)
    $serial = $m.Matches[0].Groups[1].Value
    if ($serial -match ":") { & $adb connect $serial | Out-Null }
    & $adb -s $serial reverse tcp:8080 tcp:8080 2>$null | Out-Null
}
Write-Host "Painel: http://<ip-do-pc>:8080 (o celular conecta sozinho pelo Wi-Fi)"

& $py -m uvicorn server.main:app --host 0.0.0.0 --port 8080
