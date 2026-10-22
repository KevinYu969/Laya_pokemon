param([string]$Python = 'py', [switch]$Locked)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    if ($Python -eq 'py') { & py -3.11 -m venv .venv } else { & $Python -m venv .venv }
    if ($LASTEXITCODE -ne 0) { throw '無法建立 Python 3.11 虛擬環境，請用 -Python 指定解譯器' }
}
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
& $taskPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip 更新失敗' }
if ($Locked) {
    & $taskPython -m pip install -r requirements-lock.txt --extra-index-url https://download.pytorch.org/whl/cpu
} else {
    & $taskPython -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    if ($LASTEXITCODE -ne 0) { throw 'CPU PyTorch 安裝失敗' }
    & $taskPython -m pip install -e '.[dev]'
}
if ($LASTEXITCODE -ne 0) { throw '專案相依套件安裝失敗' }
& $taskPython -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw '專案套件安裝失敗' }
& $taskPython -m pip check
if ($LASTEXITCODE -ne 0) { throw '相依套件檢查失敗' }
& $taskPython -m laya_pokemon.cli doctor --output outputs/environment/doctor.json
if ($LASTEXITCODE -ne 0) { throw '環境檢查失敗' }

