; LeagueLoop Nexus Installer — Inno Setup Script

#define AppName "LeagueLoop Nexus"
#define AppVersion "0.1.0"
#define AppPublisher "Intrusive Thots"
#define AppURL "https://github.com/Intrusive-Thots/LL-NEXUS"
#define AppExeName "league-loop-nexus.exe"

[Setup]
AppId={{D37F21F6-46F2-498C-B8D2-E4048A541D8B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\LeagueLoop Nexus
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=LeagueLoop_Nexus_Installer
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\assets\app.ico
Compression=lzma2/ultra64
SolidCompression=yes
LZMADictionarySize=65536
LZMAUseSeparateProcess=yes
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\league-loop-nexus\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\league-loop-nexus\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\app.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "assets\app.png"; DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\app.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; IconFilename: "{app}\assets\app.ico"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
