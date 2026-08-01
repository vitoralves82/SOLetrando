; SOLetrando Installer - Inno Setup Script
; Requer Inno Setup 6.3+ (https://jrsoftware.org/isinfo.php)

; Versao lida de version.txt para nao divergir do resto do projeto.
#define VersionFile FileOpen("version.txt")
#define AppVersion Trim(FileRead(VersionFile))
#expr FileClose(VersionFile)

[Setup]
; AppId fixo: sem ele, cada build era tratado como um app diferente e o
; Windows acumulava varias entradas em "Aplicativos instalados".
AppId={{9B0F1C2E-6A45-4E1B-9D3A-1F7C8B2E5A41}
AppName=SOLetrando
AppVersion={#AppVersion}
AppPublisher=Vitor Alves Domingues
AppPublisherURL=https://github.com/vitoralves82/soletrando
DefaultDirName={autopf}\SOLetrando
DefaultGroupName=SOLetrando
OutputDir=installer_output
OutputBaseFilename=SOLetrandoSetup
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=lowest
; Antes apontava para assets\icon.ico, que nao existe no repositorio
; (assets/ esta no .gitignore) e fazia o iscc falhar no build.
SetupIconFile=soletrando.ico
UninstallDisplayIcon={app}\soletrando.exe
WizardStyle=modern
DisableProgramGroupPage=yes
; Impede instalar por cima do app rodando (arquivos em uso).
CloseApplications=yes
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

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
; "filesandirs" nao e um valor valido de Type (o correto e filesandordirs);
; o Inno Setup rejeitava a linha e a pasta de dados/modelos ficava para tras.
Type: filesandordirs; Name: "{localappdata}\Soletrando"
