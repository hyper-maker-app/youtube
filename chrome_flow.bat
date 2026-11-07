@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ----------------------------------------------------------------------------
:: Grok Imagine Cinematic Studio - Google Flow CDP Multi-Account Launcher
:: ----------------------------------------------------------------------------

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
set "FLOW_AUTOMATION=0"
set "TARGET_ACCOUNT="
set "IS_INTERACTIVE=0"

:: Check if launched without arguments
if "%~1"=="" set "IS_INTERACTIVE=1"

:parse_args
if "%~1"=="" goto after_parse
if /I "%~1"=="--automation" (
    set "FLOW_AUTOMATION=1"
    shift
    goto parse_args
)
if /I "%~1"=="--account" (
    set "TARGET_ACCOUNT=%~2"
    shift
    shift
    goto parse_args
)
if "%~1"=="1" (
    set "TARGET_ACCOUNT=1"
    shift
    goto parse_args
)
if "%~1"=="2" (
    set "TARGET_ACCOUNT=2"
    shift
    goto parse_args
)
if "%~1"=="3" (
    set "TARGET_ACCOUNT=3"
    shift
    goto parse_args
)
if "%~1"=="4" (
    set "TARGET_ACCOUNT=4"
    shift
    goto parse_args
)
if /I "%~1"=="active" (
    set "TARGET_ACCOUNT=active"
    shift
    goto parse_args
)
if /I "%~1"=="status" (
    goto show_status
)
if /I "%~1"=="reset" (
    goto do_reset
)
if /I "%~1"=="check-credits" (
    goto do_check_credits
)
if /I "%~1"=="scan-credits" (
    goto do_check_credits
)
if /I "%~1"=="credits" (
    goto do_check_credits
)
shift
goto parse_args
:after_parse

:: If interactive mode, present the full menu
if "%IS_INTERACTIVE%"=="1" goto menu

:: If non-interactive and no account specified, default to active
if "%TARGET_ACCOUNT%"=="" set "TARGET_ACCOUNT=active"
goto launch_selected_account

:menu
cls
set "ACC_1_NAME=Account 1"
set "ACC_2_NAME=Account 2"
set "ACC_3_NAME=Account 3"
set "ACC_4_NAME=Account 4"
set "ACC_1_CREDITS=Giris Yapilmali"
set "ACC_2_CREDITS=Giris Yapilmali"
set "ACC_3_CREDITS=Giris Yapilmali"
set "ACC_4_CREDITS=Giris Yapilmali"
set "ACC_1_RESET=Aylik/Gunluk"
set "ACC_2_RESET=Aylik/Gunluk"
set "ACC_3_RESET=Aylik/Gunluk"
set "ACC_4_RESET=Aylik/Gunluk"

for /L %%i in (5,1,8) do (
    set "ACC_%%i_NAME="
    set "ACC_%%i_CREDITS="
    set "ACC_%%i_RESET="
)

set "TEMP_FLOW_ENV=%TEMP%\flow_acc_env_%RANDOM%.bat"
python "%SCRIPT_DIR%tools\cinematic_studio_cli.py" flow accounts env > "!TEMP_FLOW_ENV!" 2>nul
if exist "!TEMP_FLOW_ENV!" (
    call "!TEMP_FLOW_ENV!"
    del /f /q "!TEMP_FLOW_ENV!" >nul 2>&1
)

echo ============================================================================
echo   GROK CINEMATIC STUDIO - GOOGLE FLOW COKLU HESAP MERKEZI
echo ============================================================================
echo   [1] Hesap 1 (FlowCDPProfile)  - !ACC_1_NAME! [!ACC_1_CREDITS!] [!ACC_1_RESET!]
echo   [2] Hesap 2 (FlowCDPProfile2) - !ACC_2_NAME! [!ACC_2_CREDITS!] [!ACC_2_RESET!]
echo   [3] Hesap 3 (FlowCDPProfile3) - !ACC_3_NAME! [!ACC_3_CREDITS!] [!ACC_3_RESET!]
echo   [4] Hesap 4 (FlowCDPProfile4) - !ACC_4_NAME! [!ACC_4_CREDITS!] [!ACC_4_RESET!]
if defined ACC_5_NAME echo   [5] Hesap 5 (FlowCDPProfile5) - !ACC_5_NAME! [!ACC_5_CREDITS!] [!ACC_5_RESET!]
if defined ACC_6_NAME echo   [6] Hesap 6 (FlowCDPProfile6) - !ACC_6_NAME! [!ACC_6_CREDITS!] [!ACC_6_RESET!]
if defined ACC_7_NAME echo   [7] Hesap 7 (FlowCDPProfile7) - !ACC_7_NAME! [!ACC_7_CREDITS!] [!ACC_7_RESET!]
if defined ACC_8_NAME echo   [8] Hesap 8 (FlowCDPProfile8) - !ACC_8_NAME! [!ACC_8_CREDITS!] [!ACC_8_RESET!]
echo   * Google Flow: 1000 Aylik Kredi + Her 24 Saatte Bir +50 Gunluk Kredi
echo   --------------------------------------------------------------------------
echo   [A] Aktif Hesabi Calistir (Uretim Icin Varsayilan Daemon - Arka Plan)
echo   [C] Canli Kredileri Tara ve Guncelle (Scan Live Credits)
echo   [S] Hesap Durumlarini ve Kota Istatistiklerini Goruntule
echo   [R] Kota / Bekleme Surelerini Sifirla (Reset All Cooldowns)
echo   [+] Yeni Hesap Ekle (5., 6. vb. Hesap Havuzuna Ekle)
echo   [Q] Cikis
echo ============================================================================
set "USER_CHOICE="
set /p USER_CHOICE="Lutfen bir secim yapin [1, 2, 3, 4, +, A, C, S, R, Q]: "
if not defined USER_CHOICE goto menu
set "USER_CHOICE=!USER_CHOICE: =!"

if /I "!USER_CHOICE!"=="1" (
    set "TARGET_ACCOUNT=1"
    set "FLOW_AUTOMATION=0"
    goto launch_selected_account
)
if /I "!USER_CHOICE!"=="2" (
    set "TARGET_ACCOUNT=2"
    set "FLOW_AUTOMATION=0"
    goto launch_selected_account
)
if /I "!USER_CHOICE!"=="3" (
    set "TARGET_ACCOUNT=3"
    set "FLOW_AUTOMATION=0"
    goto launch_selected_account
)
if /I "!USER_CHOICE!"=="4" (
    set "TARGET_ACCOUNT=4"
    set "FLOW_AUTOMATION=0"
    goto launch_selected_account
)
if /I "!USER_CHOICE!"=="A" (
    set "TARGET_ACCOUNT=active"
    set "FLOW_AUTOMATION=1"
    goto launch_selected_account
)
if /I "!USER_CHOICE!"=="C" goto do_check_credits
if /I "!USER_CHOICE!"=="S" goto show_status
if /I "!USER_CHOICE!"=="R" goto do_reset
if "!USER_CHOICE!"=="+" goto do_add
if /I "!USER_CHOICE!"=="ADD" goto do_add
if /I "!USER_CHOICE!"=="Q" goto exit_script

:: Allow selecting any numeric account ID (5, 6, etc.)
for /f "tokens=1 delims=0123456789" %%i in ("%USER_CHOICE%") do goto invalid_choice
if not "%USER_CHOICE%"=="" (
    set "TARGET_ACCOUNT=%USER_CHOICE%"
    set "FLOW_AUTOMATION=0"
    goto launch_selected_account
)
:invalid_choice

echo [HATA] Gecersiz secim! Lutfen listeden bir secenek secin.
ping -n 2 127.0.0.1 >nul
goto menu

:show_status
echo.
echo [BILGI] Google Flow hesap durumlari listeleniyor...
python "%SCRIPT_DIR%tools\cinematic_studio_cli.py" flow accounts status
if errorlevel 1 (
    if exist "%SCRIPT_DIR%config\flow_accounts.json" (
        type "%SCRIPT_DIR%config\flow_accounts.json"
    ) else (
        echo [UYARI] Hesap yapilandirma dosyasi henuz olusturulmadi.
    )
)
echo.
if "%IS_INTERACTIVE%"=="1" (
    pause
    goto menu
)
exit /b 0

:do_check_credits
echo.
echo [BILGI] Google Flow hesaplarindaki canli krediler taraniyor...
python "%SCRIPT_DIR%tools\cinematic_studio_cli.py" flow accounts check-credits --all
set "TEMP_FLOW_ENV=%TEMP%\flow_acc_env_%RANDOM%.bat"
python "%SCRIPT_DIR%tools\cinematic_studio_cli.py" flow accounts env > "!TEMP_FLOW_ENV!" 2>nul
if exist "!TEMP_FLOW_ENV!" (
    call "!TEMP_FLOW_ENV!"
    del /f /q "!TEMP_FLOW_ENV!" >nul 2>&1
)
echo.
if "%IS_INTERACTIVE%"=="1" (
    pause
    goto menu
)
exit /b 0

:do_reset
echo.
echo [BILGI] Tum hesaplarin bekleme sureleri ve gunluk kotalari sifirlaniyor...
python "%SCRIPT_DIR%tools\cinematic_studio_cli.py" flow accounts reset
if errorlevel 1 (
    echo [UYARI] CLI uzerinden sifirlanamadi.
)
echo.
if "%IS_INTERACTIVE%"=="1" (
    pause
    goto menu
)
exit /b 0

:do_add
echo.
echo [BILGI] Havuza yeni Flow hesabi ekleniyor...
python "%SCRIPT_DIR%tools\cinematic_studio_cli.py" flow accounts add
echo.
if "%IS_INTERACTIVE%"=="1" (
    pause
    goto menu
)
exit /b 0

:launch_selected_account
:: Resolve "active" account ID if requested
if /I "%TARGET_ACCOUNT%"=="active" (
    if defined ACTIVE_ACCOUNT_ID (
        set "TARGET_ACCOUNT=!ACTIVE_ACCOUNT_ID!"
    ) else (
        set "TARGET_ACCOUNT=1"
    )
)

if "%TARGET_ACCOUNT%"=="" set "TARGET_ACCOUNT=1"

:: Resolve Profile Directory Path
if "%TARGET_ACCOUNT%"=="1" (
    set "PROFILE_DIR=%LOCALAPPDATA%\Google\Chrome\FlowCDPProfile"
    if exist "%LOCALAPPDATA%\Google\Chrome\FlowCDPProfile_1" set "PROFILE_DIR=%LOCALAPPDATA%\Google\Chrome\FlowCDPProfile_1"
) else if "%TARGET_ACCOUNT%"=="2" (
    set "PROFILE_DIR=%LOCALAPPDATA%\Google\Chrome\FlowCDPProfile2"
    if exist "%LOCALAPPDATA%\Google\Chrome\FlowCDPProfile_2" set "PROFILE_DIR=%LOCALAPPDATA%\Google\Chrome\FlowCDPProfile_2"
) else (
    set "PROFILE_DIR=%LOCALAPPDATA%\Google\Chrome\FlowCDPProfile%TARGET_ACCOUNT%"
    if exist "%LOCALAPPDATA%\Google\Chrome\FlowCDPProfile_%TARGET_ACCOUNT%" set "PROFILE_DIR=%LOCALAPPDATA%\Google\Chrome\FlowCDPProfile_%TARGET_ACCOUNT%"
)

:: Locate Chrome Executable
set "CHROME_BIN=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_BIN%" set "CHROME_BIN=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_BIN%" set "CHROME_BIN=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

if not exist "%CHROME_BIN%" (
    echo [HATA] Google Chrome bulunamadi! Lutfen Chrome'un kurulu oldugundan emin olun.
    if "%IS_INTERACTIVE%"=="1" (
        pause
        goto menu
    )
    exit /b 1
)

:: Window mode flag
set "FLOW_WINDOW_MODE="
if "%FLOW_AUTOMATION%"=="1" set "FLOW_WINDOW_MODE=--start-minimized"

:: 1. Terminate only Flow Chrome processes (Safely preserves personal Chrome)
echo.
echo [1/2] Arka planda acik kalan izole FlowCDPProfile surecleri temizleniyor (Ana Chrome pencerelerinize DOKUNULMAZ)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | Where-Object { $_.CommandLine -match 'FlowCDPProfile' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
ping -n 2 127.0.0.1 >nul

:: Update active account in manager state
python "%SCRIPT_DIR%tools\cinematic_studio_cli.py" flow accounts switch %TARGET_ACCOUNT% >nul 2>&1

:: 2. Launch Chrome with isolated profile on port 9223
echo [2/2] Google Flow izole Chrome oturumu (Hesap %TARGET_ACCOUNT% ^| Port 9223) baslatiliyor...
echo       Profil Dizini: %PROFILE_DIR%
start "" "%CHROME_BIN%" --remote-debugging-port=9223 --user-data-dir="%PROFILE_DIR%" --disable-blink-features=AutomationControlled %FLOW_WINDOW_MODE% --no-first-run --no-default-browser-check "https://flow.google.com"

echo.
echo ============================================================================
if "%FLOW_AUTOMATION%"=="1" (
    echo  DAEMON BASLATILDI! Hesap %TARGET_ACCOUNT% arka planda simge durumunda acildi.
    echo  CDP Portu: 9223 ^| Profil: %PROFILE_DIR%
    echo  Artik CS2 veya baska oyun oynarken uretim arka planda calisabilir!
) else (
    echo  TAMAMLANDI! Acilan Chrome penceresinde Google Flow hesabiniza giris yapin.
    echo  Hesap: %TARGET_ACCOUNT% ^| Profil: %PROFILE_DIR%
    echo.
    echo  Giris yaptiktan sonra o pencereyi KAPATMAYIN, sadece simge durumuna
    echo  kucultun [simge durumuna kucultun]. Boylece arka planda uretim kesintisiz surer.
)
echo ============================================================================

if "%IS_INTERACTIVE%"=="1" (
    echo.
    pause
    goto menu
)

if "%FLOW_AUTOMATION%"=="0" (
    pause
)
exit /b 0

:exit_script
echo.
echo Grok Cinematic Studio'dan cikiliyor. Iyi gunler!
exit /b 0
