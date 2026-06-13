; ══════════════════════════════════════════════════════════════════════
; BLUE AI — Inno Setup Installer Script
; 
; Bu dosya BLUE AI uygulamasının profesyonel bir Windows installer'ını
; oluşturur. Setup.exe içinde:
;   ✓ Uygulama dosyaları (PyInstaller çıktısı)
;   ✓ Masaüstü + Başlat Menüsü kısayolları
;   ✓ Otomatik Ollama kurulumu
;   ✓ Program Ekle/Kaldır entegrasyonu
;   ✓ Uninstaller
;
; Derleme: Inno Setup Compiler ile bu dosyayı açıp Compile (Ctrl+F9)
; ══════════════════════════════════════════════════════════════════════

#define MyAppName "BLUE AI"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Dayan Software"
#define MyAppURL "https://github.com/dayan-software/blue-ai"
#define MyAppExeName "BLUE_AI.exe"

; ── PyInstaller dist çıktı klasörü (bu dosyaya göre göreceli) ──
; Installer klasörü: C:\...\BLUE_AI\installer\
; Dist klasörü:      C:\...\BLUE_AI\dist\BLUE_AI\
#define DistDir "..\dist\BLUE_AI"

[Setup]
; Uygulama tanımlayıcı (GUID) — benzersiz olmalı, değiştirmeyin
AppId={{B1A2C3D4-E5F6-7890-ABCD-1234567890EF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Kurulum dizini
DefaultDirName={autopf}\BLUE_AI
DefaultGroupName={#MyAppName}

; Lisans ve bilgi dosyaları
LicenseFile=license_tr.txt

; Çıktı ayarları
OutputDir=..\output
OutputBaseFilename=BLUE_AI_Setup_v{#MyAppVersion}
SetupIconFile=blue_ai.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; Sıkıştırma (lzma2 — en iyi oran)
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Windows versiyon gereksinimleri
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; UI ayarları
WizardStyle=modern
WizardSizePercent=110,110
DisableProgramGroupPage=yes
DisableWelcomePage=no

; Yönetici gerektirmesin (kullanıcı dizinine de kurulabilir)
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Uninstall ayarları
UninstallDisplayName={#MyAppName}
Uninstallable=yes
CreateUninstallRegKey=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[CustomMessages]
turkish.WelcomeLabel2=Bu sihirbaz [name] v{#MyAppVersion} uygulamasını bilgisayarınıza kuracaktır.%n%nBLUE AI, yapay zeka destekli bilgisayar yönetim asistanınızdır. Ses komutlarıyla bilgisayarınızı kontrol edin, sistem performansını izleyin ve daha fazlasını yapın.%n%nDevam etmek için İleri'ye tıklayın.

[Tasks]
Name: "desktopicon"; Description: "Masaustune kisayol olustur"; GroupDescription: "Ek gorevler:"
Name: "autostart"; Description: "Windows baslangicinda otomatik calistir"; GroupDescription: "Ek gorevler:"; Flags: unchecked
Name: "installollama"; Description: "Ollama otomatik kur (LLM motoru - gerekli)"; GroupDescription: "Bagimliliklar:"

[Files]
; Ana uygulama EXE
Source: "{#DistDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; _internal klasörü (tüm bağımlılıklar)
Source: "{#DistDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

; Installer yardımcı dosyaları
Source: "post_install.bat"; DestDir: "{app}\installer"; Flags: ignoreversion
Source: "blue_ai.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Baslat Menusu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\blue_ai.ico"; Comment: "BLUE AI - Yapay Zeka Asistani"
Name: "{group}\{#MyAppName} Kaldir"; Filename: "{uninstallexe}"; IconFilename: "{app}\blue_ai.ico"

; Masaustu kisayolu (opsiyonel)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\blue_ai.ico"; Comment: "BLUE AI - Yapay Zeka Asistani"; Tasks: desktopicon

[Registry]
; Windows başlangıcında çalıştır (opsiyonel)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "BLUE_AI"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

; Uygulama bilgileri
Root: HKCU; Subkey: "Software\Dayan Software\BLUE_AI"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Dayan Software\BLUE_AI"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey

[Run]
; Kurulum sonrasi - Ollama kurulumu ve yapilandirma
Filename: "cmd.exe"; Parameters: "/C ""{app}\installer\post_install.bat"""; Description: "Ollama ve LLM modelini kur (onerilir)"; Flags: postinstall skipifsilent runasoriginaluser; Tasks: installollama; WorkingDir: "{app}\installer"

; Uygulamayi baslat (opsiyonel)
Filename: "{app}\{#MyAppExeName}"; Description: "BLUE AI simdi baslat"; Flags: nowait postinstall skipifsilent unchecked shellexec

[UninstallDelete]
; Uninstall sırasında temizlenecek ek dosyalar
Type: filesandordirs; Name: "{app}\installer"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\logs"

[UninstallRun]
; Uninstall öncesi — çalışan BLUE AI'yi kapat
Filename: "taskkill"; Parameters: "/F /IM BLUE_AI.exe"; Flags: runhidden; RunOnceId: "KillBlueAI"

[Code]
// ── Pascal Script — Gelişmiş Ollama Tespit Sistemi ──────────────

var
  OllamaFound: Boolean;
  OllamaPath: String;

// Bir dosyanın var olup olmadığını kontrol et
function FileExistsCheck(Path: String): Boolean;
begin
  Result := FileExists(Path);
end;

// Ollama'yı tüm olası konumlarda ara
function DetectOllama(): Boolean;
var
  LocalAppData, ProgramFiles, ProgramFilesX86: String;
  SystemPath: String;
  ResultCode: Integer;
begin
  Result := False;
  OllamaPath := '';
  
  // 1. PATH'de kontrol (en güvenilir yöntem)
  if Exec('cmd.exe', '/C where ollama >nul 2>&1', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      OllamaPath := 'PATH';
      Result := True;
      Exit;
    end;
  end;
  
  // 2. Standart kurulum dizinleri
  LocalAppData := ExpandConstant('{localappdata}');
  ProgramFiles := ExpandConstant('{autopf}');
  
  // Ollama varsayılan konumları
  if FileExistsCheck(LocalAppData + '\Programs\Ollama\ollama.exe') then
  begin
    OllamaPath := LocalAppData + '\Programs\Ollama\ollama.exe';
    Result := True;
    Exit;
  end;
  
  if FileExistsCheck(ProgramFiles + '\Ollama\ollama.exe') then
  begin
    OllamaPath := ProgramFiles + '\Ollama\ollama.exe';
    Result := True;
    Exit;
  end;
  
  // 3. Registry kontrolü
  if RegKeyExists(HKEY_CURRENT_USER, 'Software\Ollama') then
  begin
    OllamaPath := 'Registry (HKCU)';
    Result := True;
    Exit;
  end;
  
  if RegKeyExists(HKEY_LOCAL_MACHINE, 'Software\Ollama') then
  begin
    OllamaPath := 'Registry (HKLM)';
    Result := True;
    Exit;
  end;
  
  // 4. Program Ekle/Kaldır listesinde ara
  if RegKeyExists(HKEY_LOCAL_MACHINE, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\Ollama') then
  begin
    OllamaPath := 'Uninstall Registry';
    Result := True;
    Exit;
  end;

  if RegKeyExists(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\Ollama') then
  begin
    OllamaPath := 'Uninstall Registry (HKCU)';
    Result := True;
    Exit;
  end;
end;

// Kurulum başlangıcında Ollama'yı tespit et
procedure InitializeWizard();
begin
  OllamaFound := DetectOllama();
end;

// Task sayfası gösterilirken Ollama durumunu güncelle
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpSelectTasks then
  begin
    OllamaFound := DetectOllama();
    if OllamaFound then
    begin
      // Ollama zaten varsa, "Ollama kur" task'ını gizleyemeyiz
      // ama post_install.bat zaten kontrol edecek
      WizardForm.TasksList.Checked[2] := False;  // "installollama" checkbox'ını kaldır
    end;
  end;
end;

// Kurulum tamamlandıktan sonra özet bilgi
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not OllamaFound then
    begin
      // Ollama yoksa ve kullanıcı kurulum seçtiyse, post_install.bat halledecek
      // Seçmediyse bilgilendir
      if not WizardIsTaskSelected('installollama') then
      begin
        MsgBox(
          'BLUE AI tam işlevsellik için Ollama gerektirir.' + #13#10 + #13#10 +
          'Ollama''yı daha sonra https://ollama.com adresinden indirebilirsiniz.' + #13#10 + #13#10 +
          'Ollama olmadan BLUE AI temel sistem yönetimi işlevlerini kullanabilirsiniz, ' +
          'ancak yapay zeka sohbet özelliği çalışmaz.',
          mbInformation, MB_OK
        );
      end;
    end;
  end;
end;
