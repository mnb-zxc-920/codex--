$ErrorActionPreference = 'Stop'

$widgetRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$entryPoint = Join-Path $widgetRoot 'codex_whale_v0.py'
if (-not (Test-Path -LiteralPath $entryPoint -PathType Leaf)) {
    throw "Missing widget entry point: $entryPoint"
}

$selected = $null
$pythonw = Get-Command pythonw.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if ($pythonw) {
    $consolePeer = Join-Path (Split-Path -Parent $pythonw.Source) 'python.exe'
    if (Test-Path -LiteralPath $consolePeer -PathType Leaf) {
        & $consolePeer -c "import tkinter" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $selected = $pythonw.Source
        }
    }
}

if (-not $selected) {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($python) {
        & $python.Source -c "import tkinter" 2>$null
    }
    if ($LASTEXITCODE -eq 0) {
        $selected = $python.Source
    }
}
if (-not $selected) {
    throw 'No Python runtime with tkinter support was found.'
}

Start-Process -FilePath $selected -ArgumentList @($entryPoint) -WorkingDirectory $widgetRoot -WindowStyle Hidden
