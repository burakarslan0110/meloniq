[Setup]
AppName=Meloniq
AppVersion=1.1.0
AppPublisher=Burak Arslan
DefaultDirName={autopf}\Meloniq
DefaultGroupName=Meloniq
OutputBaseFilename=Meloniq_Setup
Compression=lzma
SolidCompression=yes
SetupIconFile=src\meloniq\resources\icon.ico

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Meloniq\Meloniq.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Meloniq\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Meloniq"; Filename: "{app}\Meloniq.exe"
Name: "{autodesktop}\Meloniq"; Filename: "{app}\Meloniq.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Meloniq.exe"; Description: "{cm:LaunchProgram,Meloniq}"; Flags: nowait postinstall skipifsilent
