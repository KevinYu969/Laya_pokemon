param(
    [string]$Rom,
    [string]$State,
    [string]$PlayerName = 'KEVIN',
    [string]$Objective = 'Complete the opening introduction and choose a default name to reach the player bedroom.',
    [ValidateRange(1, 300)][int]$Steps = 300
)

$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $taskPython)) { throw '尚未建立專案 .venv，請先執行 scripts/bootstrap.ps1。' }

if (!$Rom) {
    $taskRoms = @(Get-ChildItem -LiteralPath (Join-Path $taskRoot 'roms') -Filter '*.gb' -File -ErrorAction SilentlyContinue)
    if ($taskRoms.Count -ne 1) { throw '請將有權使用的英文紅／藍版 .gb 放入 roms，或使用 -Rom 指定完整路徑；目前無法自動選定 ROM。' }
    $Rom = $taskRoms[0].FullName
}
$Rom = (Resolve-Path -LiteralPath $Rom).Path
if ($State) { $State = (Resolve-Path -LiteralPath $State).Path }

Push-Location $taskRoot
try {
    & $taskPython -m laya_pokemon.cli check-rom --rom $Rom
    if ($LASTEXITCODE -ne 0) { throw 'ROM 完整性檢查未通過，未啟動遊戲。' }
    $taskRun = 'outputs/runs/pyboy-live-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
    $taskArguments = @('-m', 'laya_pokemon.cli', 'play', '--rom', $Rom,
        '--objective', $Objective, '--policy', 'laya', '--steps', "$Steps",
        '--player-name', $PlayerName,
        '--window', '--scale', '4', '--offline', '--video', '--output', $taskRun)
    if ($State) { $taskArguments += @('--state', $State) }
    Write-Host '即將開啟 PyBoy 桌面視窗。每輪最多 60 秒；PAUSED 表示正在載入／等待模型，可關閉視窗停止。'
    Write-Host '這是尚待真實 ROM 校準的控制展示，沒有宣稱可以完成開場或破關。'
    & $taskPython @taskArguments
    if ($LASTEXITCODE -ne 0) { throw "遊戲執行失敗，請查看 $taskRun 的 metadata.json／summary.json。" }
} finally {
    Pop-Location
}
