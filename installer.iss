; installer.iss
; Inno Setup Script para HRDigiTool (Modo Instalador con Acceso Directo)

[Setup]
AppName=HRDigiTool
AppVersion=1.1.1
AppPublisher=HR DigiTool
DefaultDirName={autopf}\HRDigiTool
DefaultGroupName=HRDigiTool
; Dónde se guardará el instalador final comprimido
OutputDir=.\dist_installer
OutputBaseFilename=HRDigiTool_Setup
Compression=lzma2/ultra64
SolidCompression=yes
SetupIconFile=LOGO.ico

[Tasks]
; Opcion para crear el acceso directo en el escritorio (marcada por defecto)
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Copia TODA la carpeta generada por PyInstaller en dist\HRDigiTool
Source: "dist\HRDigiTool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Crea el acceso directo en el Menú de Inicio
Name: "{group}\HRDigiTool"; Filename: "{app}\HRDigiTool.exe"; IconFilename: "{app}\LOGO.ico"
; Crea el acceso directo en el Escritorio apuntando directamente al ejecutable
Name: "{autodesktop}\HRDigiTool"; Filename: "{app}\HRDigiTool.exe"; Tasks: desktopicon; IconFilename: "{app}\LOGO.ico"

[Run]
; Casilla final para ejecutar la aplicación inmediatamente tras instalar
Filename: "{app}\HRDigiTool.exe"; Description: "{cm:LaunchProgram,HRDigiTool}"; Flags: nowait postinstall skipifsilent