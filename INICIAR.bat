@echo off
chcp 65001 >nul
title VideoViral
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [1/2] Criando ambiente virtual...
  python -m venv .venv
  if errorlevel 1 (
    echo ERRO: Instale Python 3.11+ de https://www.python.org/downloads/
    pause
    exit /b 1
  )
  echo [2/2] Instalando dependencias...
  .venv\Scripts\pip install -q -r requirements.txt
)

set PY=%~dp0.venv\Scripts\python.exe
set PATH=%PATH%;%ProgramFiles%\ffmpeg\bin

:menu
cls
echo.
echo  ========================================
echo    VideoViral - Menu principal
echo  ========================================
echo.
echo   1 - Abrir PAINEL no navegador (recomendado)
echo   2 - Baixar video do YouTube (busca)
echo   3 - Baixar video por URL
echo   4 - Processar video completo (download + corte + render)
echo   5 - Abrir pasta dos VIDEOS PRONTOS
echo   6 - Editar configuracao (.env)
echo   7 - Teste rapido (sem internet extra)
echo   0 - Sair
echo.
set /p op="Escolha: "

if "%op%"=="1" goto painel
if "%op%"=="2" goto busca
if "%op%"=="3" goto url
if "%op%"=="4" goto completo
if "%op%"=="5" goto pasta
if "%op%"=="6" goto env
if "%op%"=="7" goto teste
if "%op%"=="0" exit /b 0
goto menu

:painel
echo.
echo Iniciando servidor... NAO FECHE esta janela.
echo Painel: http://127.0.0.1:8000
start http://127.0.0.1:8000
"%PY%" run_api.py
goto fim

:busca
set /p q="Termo de busca (ex: curiosidades shorts): "
if "%q%"=="" set q=curiosidades shorts viral
"%PY%" -m src.pipeline.run_download --search "%q%" --top 1
pause
goto menu

:url
set /p u="Cole a URL do YouTube Short: "
if "%u%"=="" (
  echo URL vazia.
  pause
  goto menu
)
"%PY%" -m src.pipeline.run_download --url "%u%"
pause
goto menu

:completo
set /p q2="Busca para baixar (Enter = curiosidades shorts): "
if "%q2%"=="" set q2=curiosidades shorts
echo Processando... pode demorar alguns minutos.
"%PY%" -m src.pipeline.run_real_test --search "%q2%" --auto-approve --mock-transcribe
explorer "%~dp0storage\output"
pause
goto menu

:pasta
explorer "%~dp0storage\output"
if not exist "%~dp0storage\output" explorer "%~dp0storage"
goto menu

:env
if exist ".env" (notepad ".env") else (notepad ".env.example")
goto menu

:teste
"%PY%" -m src.pipeline.run_local_test
explorer "%~dp0storage\output"
pause
goto menu

:fim
pause
