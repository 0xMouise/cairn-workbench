param([string]$Distribution = 'kali-linux')
$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $repository 'web')
try { npm.cmd ci --no-fund --no-audit; if ($LASTEXITCODE) { throw 'Frontend dependency installation failed.' }; npm.cmd run build; if ($LASTEXITCODE) { throw 'Frontend build failed.' } } finally { Pop-Location }
$wslSource = (wsl -d $Distribution -- wslpath -a $repository).Trim()
if ($LASTEXITCODE) { throw 'WSL distribution is unavailable. Install WSL and Kali first.' }
$linuxHome = (wsl -d $Distribution -- printenv HOME).Trim()
$linuxTarget = "$linuxHome/apps/cairn-workbench"
wsl -d $Distribution -- mkdir -p $linuxTarget
wsl -d $Distribution -- cp -a "$wslSource/cairn" "$linuxTarget/"
wsl -d $Distribution -- cp -a "$wslSource/scripts" "$linuxTarget/"
wsl -d $Distribution -- cp "$wslSource/dispatch.local.example.yaml" "$linuxTarget/"
if ($LASTEXITCODE) { throw 'Copying runtime files failed.' }
wsl -d $Distribution -- bash -lc 'python3 ~/apps/cairn-workbench/scripts/install_wsl.py'
if ($LASTEXITCODE) { throw 'Backend installation failed.' }
Write-Host 'Cairn Workbench installed. Run scripts/Start-Workbench.ps1.'
