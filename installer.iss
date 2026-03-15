; SOLetrando Installer - Inno Setup Script
; Requer Inno Setup 6+ (https://jrsoftware.org/isinfo.php)

[Setup]
AppName=SOLetrando
AppVersion=1.0.0
AppPublisher=Vitor Alves Domingues
AppPublisherURL=https://github.com/vitoralves82/soletrando
DefaultDirName={autopf}\SOLetrando
DefaultGroupName=SOLetrando
OutputDir=installer_output
OutputBaseFilename=SOLetrandoSetup
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=lowest
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\soletrando.exe
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Area de Trabalho"; GroupDescription: "Atalhos:"
Name: "startupicon"; Description: "Iniciar com o Windows automaticamente"; GroupDescription: "Atalhos:"; Flags: checkedonce

[Files]
; Todo o conteudo da pasta dist\soletrando\
Source: "dist\soletrando\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\SOLetrando"; Filename: "{app}\soletrando.exe"
Name: "{autodesktop}\SOLetrando"; Filename: "{app}\soletrando.exe"; Tasks: desktopicon
Name: "{userstartup}\SOLetrando"; Filename: "{app}\soletrando.exe"; Tasks: startupicon

[Run]
Filename: "{app}\soletrando.exe"; Description: "Iniciar SOLetrando agora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandirs; Name: "{localappdata}\Soletrando"
