@echo off
chcp 65001 >nul 2>&1
echo.
echo ===================================================
echo   Soletrando - Instalador
echo ===================================================
echo.
echo Criando atalhos no Desktop e Startup do Windows...
echo.

python install.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERRO] Python nao encontrado ou install.py falhou.
    echo Certifique-se de que o Python 3.10+ esta instalado e no PATH.
    echo.
)

pause
