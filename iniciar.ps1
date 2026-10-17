$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$frontendRoot = Join-Path $projectRoot 'frontend'
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$powerShellExe = Join-Path $PSHOME 'powershell.exe'

if (-not (Test-Path (Join-Path $frontendRoot 'package.json'))) {
    throw "Não encontrei o frontend em '$frontendRoot'."
}

$backendCommand = @"
Set-Location -LiteralPath '$projectRoot'
if (Test-Path '$venvPython') {
    & '$venvPython' -m uvicorn src.fraud_detector.main:app --app-dir backend --reload
} else {
    python -m uvicorn src.fraud_detector.main:app --app-dir backend --reload
}
"@

$frontendCommand = @"
Set-Location -LiteralPath '$frontendRoot'
npm.cmd run start:proxy
"@

$backendEncoded = [Convert]::ToBase64String(
    [Text.Encoding]::Unicode.GetBytes($backendCommand)
)
$frontendEncoded = [Convert]::ToBase64String(
    [Text.Encoding]::Unicode.GetBytes($frontendCommand)
)

Start-Process -FilePath $powerShellExe `
    -WorkingDirectory $projectRoot `
    -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $backendEncoded)

Start-Process -FilePath $powerShellExe `
    -WorkingDirectory $frontendRoot `
    -ArgumentList @('-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $frontendEncoded)

Write-Host 'Backend:  http://127.0.0.1:8000'
Write-Host 'Frontend: http://localhost:4200'
