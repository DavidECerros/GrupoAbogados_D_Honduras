$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Se requiere Python de 64 bits.' }
}
if (Test-Path -LiteralPath 'wheelhouse') {
    & '.\.venv\Scripts\python.exe' -m pip install --no-index --find-links wheelhouse -r requirements-lock.txt
} else {
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
}
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) {
    Push-Location -LiteralPath 'frontend'
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias frontend.' }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo compilar la interfaz.' }
    } finally { Pop-Location }
}
$desktopPath = [Environment]::GetFolderPath('Desktop')
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktopPath 'Grupo Abogados D Honduras.lnk'))
$shortcut.TargetPath = Join-Path $PSScriptRoot 'Iniciar.cmd'
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Save()
Write-Host 'Instalación terminada. Use el acceso directo o Iniciar.cmd.'
