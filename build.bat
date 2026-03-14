@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Speechfire - Build do executavel (.exe)
echo ============================================
echo.

set "PYEXE=.venv\Scripts\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

echo [*] Usando Python: %PYEXE%

if not exist "speechfire.py" (
  echo [ERRO] speechfire.py nao encontrado.
  pause
  exit /b 1
)

if not exist "speechfire.spec" (
  echo [ERRO] speechfire.spec nao encontrado.
  pause
  exit /b 1
)

echo [*] Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [*] Gerando via speechfire.spec...
"%PYEXE%" -m PyInstaller --noconfirm --clean speechfire.spec
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
echo  Saida: dist\speechfire\speechfire.exe
echo ============================================
pause
