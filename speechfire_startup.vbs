' Speechfire - Auto-start silencioso
' Coloque este arquivo em:
'   %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
'
' Ajuste os caminhos abaixo conforme sua instalacao:

Set WshShell = CreateObject("WScript.Shell")

pythonw = "D:\Scripts\Speechfire\.venv\Scripts\pythonw.exe"
script  = "D:\Scripts\Speechfire\speechfire.py"
workdir = "D:\Scripts\Speechfire"

WshShell.CurrentDirectory = workdir
WshShell.Run """" & pythonw & """ """ & script & """", 0, False
