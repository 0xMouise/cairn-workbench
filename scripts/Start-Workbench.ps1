param([switch]$Browser)
$ErrorActionPreference = 'Stop'
Start-Process -FilePath 'wsl.exe' -ArgumentList '-d kali-linux -- flock -n /tmp/cairn-workbench-host.lock bash -c "exec -a cairn-workbench-host /bin/sleep infinity"' -WindowStyle Hidden
wsl -d kali-linux -- systemctl --user start cairn-workbench.service
if ($LASTEXITCODE) { throw 'Run Install-Workbench.ps1 first, then check the WSL service.' }
for ($attempt=0; $attempt -lt 30; $attempt++) {
    try {
        $null = Invoke-RestMethod -Uri 'http://127.0.0.1:18100/api/v2/health' -TimeoutSec 2
        $linuxHome = (wsl -d kali-linux -- printenv HOME).Trim()
        $accessToken = (wsl -d kali-linux -- cat "$linuxHome/.local/share/cairn-workbench/access-token").Trim()
        $repository = Split-Path -Parent $PSScriptRoot
        $executable = Join-Path $repository 'web\src-tauri\target\release\cairn-workbench.exe'
        if (!$Browser -and (Test-Path -LiteralPath $executable)) { Start-Process -FilePath $executable; exit 0 }
        Start-Process ('http://127.0.0.1:18100/#token=' + $accessToken)
        exit 0
    } catch { Start-Sleep -Milliseconds 500 }
}
throw 'Service did not become ready. Check: wsl -d kali-linux -- journalctl --user -u cairn-workbench -n 30'
