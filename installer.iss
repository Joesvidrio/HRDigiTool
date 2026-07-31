; installer.iss

[Setup]
; Información básica de tu aplicación
AppName=HRDigiTool
AppVersion=1.0
AppPublisher=Tu Nombre o Empresa
DefaultDirName={autopf}\HRDigiTool
DefaultGroupName=HRDigiTool
; Dónde se guardará el instalador final
OutputDir=.\dist
; Nombre del instalador generado
OutputBaseFilename=HRDigiTool_Setup
Compression=lzma
SolidCompression=yes
; Opcional: Si tienes un ícono para el instalador
; SetupIconFile=assets\icon.ico 

[Tasks]
; Esta sección crea la casilla de verificación en el instalador para el acceso directo
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Toma el ejecutable generado por PyInstaller (asumiendo modo onefile)
Source: "dist\HRDigiTool.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Crea el acceso directo en el menú de inicio
Name: "{group}\HRDigiTool"; Filename: "{app}\HRDigiTool.exe"
; Crea el acceso directo en el escritorio (vinculado a la tarea [Tasks])
Name: "{autodesktop}\HRDigiTool"; Filename: "{app}\HRDigiTool.exe"; Tasks: desktopicon

[Run]
; Permite al usuario abrir la aplicación al terminar de instalar
Filename: "{app}\HRDigiTool.exe"; Description: "{cm:LaunchProgram,HRDigiTool}"; Flags: nowait postinstall skipifsilent