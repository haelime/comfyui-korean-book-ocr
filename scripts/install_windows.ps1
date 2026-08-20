$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$repoRoot = Split-Path -Parent $PSScriptRoot
$customNodes = Split-Path -Parent $repoRoot
$comfyRoot = Split-Path -Parent $customNodes

Write-Host ""
Write-Host "ComfyUI 한국어 책 OCR 설치를 시작합니다." -ForegroundColor Cyan

if ((Split-Path -Leaf $customNodes) -ne "custom_nodes") {
    Write-Host ""
    Write-Host "설치 폴더를 찾지 못했습니다." -ForegroundColor Red
    Write-Host "이 폴더를 ComfyUI\custom_nodes 안에 넣은 뒤 install_windows.bat을 다시 실행하세요."
    Write-Host "현재 폴더: $repoRoot"
    exit 1
}

$pythonCandidates = @(
    (Join-Path $comfyRoot ".venv\Scripts\python.exe"),
    (Join-Path $comfyRoot "venv\Scripts\python.exe"),
    (Join-Path (Split-Path -Parent $comfyRoot) "python_embeded\python.exe")
)
$comfyPython = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $comfyPython) {
    Write-Host ""
    Write-Host "ComfyUI 전용 Python을 찾지 못했습니다." -ForegroundColor Red
    Write-Host "ComfyUI Desktop 또는 Windows portable의 실제 custom_nodes 폴더인지 확인하세요."
    exit 1
}

Write-Host "[1/3] 필요한 OCR 패키지를 설치합니다. 처음에는 몇 분 걸릴 수 있습니다."
& $comfyPython -m pip install -r (Join-Path $repoRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Python 패키지 설치에 실패했습니다." }

Write-Host "[2/3] 기본 워크플로우를 복사합니다."
$workflowDir = Join-Path $comfyRoot "user\default\workflows"
New-Item -ItemType Directory -Path $workflowDir -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot "korean_ocr_to_image.workflow.json") `
    -Destination (Join-Path $workflowDir "korean_ocr_to_image.json") -Force
$batchInputDir = Join-Path $comfyRoot "input\대량_OCR_사진"
New-Item -ItemType Directory -Path $batchInputDir -Force | Out-Null

Write-Host "[3/3] 로컬 교정 AI를 확인합니다."
$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
$ollamaExe = if ($ollamaCommand) {
    $ollamaCommand.Source
} else {
    Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
}

if (Test-Path -LiteralPath $ollamaExe) {
    $modelList = & $ollamaExe list 2>$null
    if (($modelList -join "`n") -notmatch "qwen3:8b") {
        Write-Host "Qwen 교정 모델(qwen3:8b, 약 5.2GB)이 없습니다."
        $answer = Read-Host "지금 다운로드할까요? [Y/n]"
        if ([string]::IsNullOrWhiteSpace($answer) -or $answer -match "^[Yy]$") {
            & $ollamaExe pull qwen3:8b
            if ($LASTEXITCODE -ne 0) { throw "Qwen 모델 다운로드에 실패했습니다." }
        } else {
            Write-Host "나중에 명령 프롬프트에서 'ollama pull qwen3:8b'를 실행할 수 있습니다."
        }
    } else {
        Write-Host "qwen3:8b 모델이 이미 설치되어 있습니다."
    }
} else {
    Write-Host ""
    Write-Host "선택 기능인 Ollama가 아직 설치되지 않았습니다." -ForegroundColor Yellow
    Write-Host "https://ollama.com/download/windows 에서 설치한 뒤 이 파일을 다시 실행하면"
    Write-Host "Qwen 교정 모델을 받을 수 있습니다. OCR과 수동 수정은 Ollama 없이도 사용할 수 있습니다."
}

Write-Host ""
Write-Host "설치가 끝났습니다. ComfyUI를 완전히 종료했다가 다시 실행하세요." -ForegroundColor Green
Write-Host "워크플로우 메뉴에서 korean_ocr_to_image를 열면 됩니다."
