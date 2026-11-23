@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual...
  python -m venv .venv
  .venv\Scripts\pip install -q -r requirements.txt
)
set PY=.venv\Scripts\python.exe
echo.
echo === VideoViral - Menu de testes ===
echo.
echo 1 - Teste local (sem APIs, gera video final)
echo 2 - Testar Gemini
echo 3 - Subir dashboard (http://127.0.0.1:8000)
echo 4 - Teste local + abrir pasta do video
echo.
set /p opcao="Escolha 1-4: "

if "%opcao%"=="1" (
  %PY% -m src.pipeline.run_local_test
  pause
  exit /b
)
if "%opcao%"=="2" (
  %PY% -m src.pipeline.test_gemini
  pause
  exit /b
)
if "%opcao%"=="3" (
  echo Abrindo http://127.0.0.1:8000 ...
  start http://127.0.0.1:8000
  %PY% run_api.py
  exit /b
)
if "%opcao%"=="4" (
  %PY% -m src.pipeline.run_local_test
  explorer "%~dp0storage\output"
  pause
  exit /b
)
echo Opcao invalida.
pause
