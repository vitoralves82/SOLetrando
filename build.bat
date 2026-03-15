@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Soletrando - Build do executavel (.exe)
echo ============================================
echo.

set "PYEXE=.venv\Scripts\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

echo [*] Usando Python: %PYEXE%

if not exist "soletrando.py" (
  echo [ERRO] soletrando.py nao encontrado.
  pause
  exit /b 1
)

if not exist "soletrando.spec" (
  echo [ERRO] soletrando.spec nao encontrado.
  pause
  exit /b 1
)

echo [*] Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [*] Gerando via soletrando.spec...
"%PYEXE%" -m PyInstaller --noconfirm --clean soletrando.spec
if errorlevel 1 (
  echo.
  echo ============================================
  echo  [ERRO] Build falhou! Verifique os logs acima.
  echo ============================================
  pause
  exit /b 1
)

echo.
echo ============================================
echo  [OK] Build concluido.
echo  Saida: dist\soletrando\soletrando.exe
echo ============================================
pause
