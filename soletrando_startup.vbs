' Soletrando - Auto-start silencioso
' Coloque este arquivo em:
'   %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
'
' Ajuste os caminhos abaixo conforme sua instalacao:

Set WshShell = CreateObject("WScript.Shell")

pythonw = "D:\Scripts\Soletrando\.venv\Scripts\pythonw.exe"
script  = "D:\Scripts\Soletrando\soletrando.py"
workdir = "D:\Scripts\Soletrando"

WshShell.CurrentDirectory = workdir
WshShell.Run """" & pythonw & """ """ & script & """", 0, False
