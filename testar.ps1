# VideoViral — executa testes com o Python correto (.venv)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Criando ambiente virtual..." -ForegroundColor Yellow
    python -m venv .venv
    & $py -m pip install -q -r requirements.txt
}

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [System.Environment]::GetEnvironmentVariable("Path", "User")

Write-Host "`n=== Teste 1: Pipeline local ===" -ForegroundColor Cyan
& $py -m src.pipeline.run_local_test
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== Teste 2: Whisper real (OpenAI) ===" -ForegroundColor Cyan
if ($env:OPENAI_API_KEY) {
    & $py -m src.pipeline.test_whisper --input storage/raw/sample.mp4 2>&1 | Select-Object -Last 12
} else {
    $keyLine = Get-Content .env -ErrorAction SilentlyContinue | Where-Object { $_ -match '^OPENAI_API_KEY=.+' }
    if ($keyLine) {
        & $py -m src.pipeline.test_whisper --input storage/raw/sample.mp4 2>&1 | Select-Object -Last 12
    } else {
        Write-Host "OPENAI_API_KEY nao configurada no .env — pulando Whisper" -ForegroundColor Yellow
    }
}

Write-Host "`n=== Teste 3: Gemini ===" -ForegroundColor Cyan
& $py -m src.pipeline.test_gemini
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n=== Teste 4: API (opcional) ===" -ForegroundColor Cyan
try {
    $h = Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 2
    Write-Host "API online: $($h.status)" -ForegroundColor Green
} catch {
    Write-Host "API offline. Para subir: .\.venv\Scripts\python run_api.py" -ForegroundColor Yellow
}

$latest = Get-ChildItem "storage\output\*_final.mp4" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($latest) {
    Write-Host "`nVideo gerado: $($latest.FullName)" -ForegroundColor Green
}

Write-Host "`n=== Teste 5 (opcional): Pipeline completo ===" -ForegroundColor Cyan
Write-Host "Rodando full_pipeline com auto-approve (cria job no dashboard)..."
& $py -m src.pipeline.full_pipeline --input storage/raw/sample.mp4 --niche curiosidades --auto-approve --mock-transcribe 2>&1 | Select-Object -Last 8

Write-Host "`nTudo OK. Dashboard: http://127.0.0.1:8000" -ForegroundColor Green
