@echo off
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo.
echo ===================================================
echo   SOLetrando - Instalador
echo ===================================================
echo.

:: 1. Detectar soletrando.exe na mesma pasta
set "EXE_PATH=%~dp0soletrando.exe"
if not exist "%EXE_PATH%" (
    echo [ERRO] soletrando.exe nao encontrado em: %~dp0
    echo        Certifique-se de que o install.bat esta na mesma pasta do soletrando.exe
    echo.
    pause
    exit /b 1
)

set "INSTALL_DIR=%~dp0"
:: Remover barra final para evitar problemas no PowerShell
if "%INSTALL_DIR:~-1%"=="\" set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"

echo   Encontrado: %EXE_PATH%
echo.

:: 2. Obter caminho real do Desktop via PowerShell
for /f "delims=" %%i in ('powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"') do set "DESKTOP=%%i"

:: 3. Criar atalho no Desktop
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP%\SOLetrando.lnk'); $s.TargetPath = '%EXE_PATH%'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Description = 'SOLetrando - Ditado por voz local'; $s.IconLocation = '%INSTALL_DIR%\soletrando.ico'; $s.Save()"
if %ERRORLEVEL% equ 0 (
    echo   [OK] Atalho criado no Desktop
) else (
    echo   [ERRO] Falha ao criar atalho no Desktop
)

:: 4. Criar atalho no Startup
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%STARTUP%\SOLetrando.lnk'); $s.TargetPath = '%EXE_PATH%'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Description = 'SOLetrando - Ditado por voz local'; $s.IconLocation = '%INSTALL_DIR%\soletrando.ico'; $s.Save()"
if %ERRORLEVEL% equ 0 (
    echo   [OK] Atalho criado no Startup (inicializacao automatica)
) else (
    echo   [ERRO] Falha ao criar atalho no Startup
)

echo.
echo   [OK] Instalacao concluida!
echo.

:: 5. Perguntar se quer iniciar agora
set /p INICIAR="  Deseja iniciar o SOLetrando agora? (s/n): "
if /i "%INICIAR%"=="s" (
    echo   Iniciando SOLetrando...
    start "" "%EXE_PATH%"
) else (
    echo   OK. Execute o SOLetrando pelo atalho no Desktop quando quiser.
)

echo.
pause
endlocal
