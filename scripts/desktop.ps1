param(
    [ValidateSet('start', 'stop')][string]$Action = 'start',
    [ValidateRange(1024, 65535)][int]$Port = 8000,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$programRoot = Split-Path -Parent $PSScriptRoot
$stateDirectory = Join-Path $env:LOCALAPPDATA 'GrupoAbogados_D_Honduras-launcher'
New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null
$statePath = Join-Path $stateDirectory "$Port.json"
$stopPath = Join-Path $stateDirectory "$Port.stop"
$outputPath = Join-Path $stateDirectory "$Port-output.log"
$errorPath = Join-Path $stateDirectory "$Port-error.log"
$mutex = New-Object System.Threading.Mutex($false, "Local\GrupoAbogados_D_Honduras-$Port")
$locked = $false

function Get-ManagedProcess {
    if (-not (Test-Path -LiteralPath $statePath)) { return $null }
    $saved = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $process = Get-Process -Id $saved.pid -ErrorAction SilentlyContinue
    if ($process -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $saved.started -and $process.Path -eq $saved.executable) {
        return $process
    }
    return $null
}

try {
    $locked = $mutex.WaitOne(30000)
    if (-not $locked) { throw 'Otra ventana esta iniciando o deteniendo el sistema. Intente de nuevo.' }
    $process = Get-ManagedProcess
    if ($Action -eq 'stop') {
        if ($process) {
            [System.IO.File]::WriteAllText($stopPath, 'stop')
            if (-not $process.WaitForExit(30000)) {
                throw "El servidor sigue terminando operaciones. Revise el Administrador de tareas (PID $($process.Id))."
            }
        }
        Remove-Item -LiteralPath $statePath, $stopPath -Force -ErrorAction SilentlyContinue
        return
    }
    $url = "http://127.0.0.1:$Port"
    if (-not $process) {
        # Never start a second server on an occupied port, including an older installation.
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($listener) {
            throw "El puerto $Port ya esta ocupado. Cierre el servidor anterior antes de iniciar esta version."
        }
        $pythonPath = Join-Path $programRoot 'runtime\python.exe'
        if (-not (Test-Path -LiteralPath $pythonPath)) {
            $pythonPath = Join-Path $programRoot '.venv\Scripts\python.exe'
        }
        if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Use el paquete Windows completo o ejecute Instalar.ps1.' }
        Remove-Item -LiteralPath $stopPath -Force -ErrorAction SilentlyContinue
        $runPath = Join-Path $PSScriptRoot 'run.py'
        $arguments = '"{0}" --no-browser --port {1} --stop-file "{2}"' -f $runPath, $Port, $stopPath
        $process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $programRoot -WindowStyle Hidden -RedirectStandardOutput $outputPath -RedirectStandardError $errorPath -PassThru
        @{ pid = $process.Id; started = $process.StartTime.ToUniversalTime().Ticks.ToString(); executable = $process.Path; root = $programRoot } | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
    } else {
        $saved = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        if ($saved.root -ne $programRoot) {
            throw 'Esta ejecutandose otra carpeta del programa. Use Detener.cmd de esa carpeta antes de cambiar de version.'
        }
    }
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        $process.Refresh()
        if ($process.HasExited) { throw "El servidor no pudo iniciar. Revise $errorPath" }
        try {
            $response = Invoke-RestMethod -Uri "$url/api/status" -TimeoutSec 1
            if ($response.version) { $ready = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "El servidor no responde todavia. Revise $errorPath antes de volver a iniciar." }
    if (-not $NoBrowser) { Start-Process $url }
} catch {
    if ($NoBrowser) { throw }
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Grupo Abogados D Honduras') | Out-Null
    exit 1
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
