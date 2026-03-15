@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  SOLetrando - Build completo
echo ============================================

set "PYEXE=.venv\Scripts\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

echo.
echo [1/2] Gerando executavel via PyInstaller...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
"%PYEXE%" -m PyInstaller --noconfirm --clean soletrando.spec
if errorlevel 1 (
  echo [ERRO] Build do PyInstaller falhou!
  pause
  exit /b 1
)

echo.
echo [2/2] Gerando instalador via Inno Setup...
where iscc >nul 2>&1
if errorlevel 1 (
  echo [AVISO] Inno Setup (iscc) nao encontrado no PATH.
  echo Instale em: https://jrsoftware.org/isdl.php
  echo Ou compile manualmente: abra installer.iss no Inno Setup.
  echo.
  echo O executavel standalone esta em: dist\soletrando\soletrando.exe
  pause
  exit /b 0
)

if not exist "installer_output" mkdir installer_output
iscc installer.iss
if errorlevel 1 (
  echo [ERRO] Inno Setup falhou!
  pause
  exit /b 1
)

echo.
echo ============================================
echo  [OK] Build completo!
echo  Executavel: dist\soletrando\soletrando.exe
echo  Instalador: installer_output\SOLetrandoSetup.exe
echo ============================================
pause
