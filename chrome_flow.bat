@echo off
chcp 65001 >nul
echo [1/2] Arka planda acik kalan izole FlowCDPProfile surecleri temizleniyor (Ana Chrome pencerelerinize DOKUNULMAZ)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | Where-Object { $_.CommandLine -match 'FlowCDPProfile' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
timeout /t 1 /nobreak >nul

echo [2/2] Google Flow izole Chrome oturumu (Port 9223) baslatiliyor...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
    --remote-debugging-port=9223 ^
    --user-data-dir="%LOCALAPPDATA%\Google\Chrome\FlowCDPProfile" ^
    --disable-blink-features=AutomationControlled ^
    --no-first-run ^
    --no-default-browser-check ^
    "https://flow.google.com"

echo.
echo ============================================================================
echo  TAMAMLANDI! Acilan Chrome penceresinde Google Flow hesabiniza giris yapin.
echo  Giris yaptiktan sonra o pencereyi KAPATMAYIN, sadece simge durumuna
echo  kucultun (minimize edin). Artik CS2 oynarken arka planda uretim yapabilir!
echo ============================================================================
pause

