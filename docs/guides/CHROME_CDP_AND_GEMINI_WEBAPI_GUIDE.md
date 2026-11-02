# Chrome CDP (Port 9223) & Gemini WebAPI (Port 8085) Operational Guide

Bu kılavuz; Grok Imagine Cinematic Studio projesinde **Google Flow CDP** ve **Google Gemini WebAPI** çift hakemli üretim motorlarının sıfır hata ile nasıl çalıştırılacağını, karşılaşılan Windows süreç kapanma tuzaklarını ve kalıcı çözüm mimarisini belgeler. Gelecekteki tüm LLM'ler ve otomasyon ajanları bu protokolü izlemelidir.

---

## 1. Mimari Bileşenler ve Port Haritası

| Bileşen | Port | Profil Dizini / İkili | Görev |
| :--- | :---: | :--- | :--- |
| **İzole Google Chrome** | `9223` | `%LOCALAPPDATA%\Google\Chrome\FlowCDPProfile` | Google Flow (Veo render) & Gemini Web oturumu için CDP sunucusu |
| **Gemini Web2API Daemon** | `8085` | `engine/vendor/gemini_webapi/bin/gemini-web2api.exe` | Chrome'dan çekilen çerezlerle yerel OpenAI-uyumlu Gemini API sunucusu |
| **CDP Koruma Daemon'ı** | - | `scripts/keep_chrome_alive.py` | Chrome sürecini Windows Job Object sonlandırmasından koruyan kalıcı bekçi |

---

## 2. Neden Önceden Kapanıyordu? (Kritik Windows Tuzakları)

1. **Windows Job Object Sonlandırması:**
   Ajan veya terminal araçları arka planda bir komut çalıştırıp işlem bittiğinde, o komutun başlattığı tüm alt süreçleri (child processes) otomatik olarak `TerminateProcess` ile temizler. Chrome `start ""` veya `subprocess.Popen` ile tek başına çağrıldığında, çağıran Python betiği çıkış yaptığı an Chrome da kapanıyordu.
2. **`chrome_flow.bat` İçindeki `timeout` Hatası:**
   `timeout /t 1 /nobreak >nul` komutu stdin yeniden yönlendirildiğinde (non-interactive / agent pipe) `ERROR: Input redirection is not supported` verip süreci anında kırıyordu. Yerine `ping -n 2 127.0.0.1 >nul` konuldu.
3. **Ana Chrome ile Delegasyon Çakışması:**
   Kullanıcının kişisel Chrome tarayıcısı açıkken, `--user-data-dir` belirtilmezse yeni Chrome bağımsız açılmaz; sekmeyi mevcut açık Chrome'a devreder ve 9223 portunu açmadan hemen sonlanır. İzole `--user-data-dir="%LOCALAPPDATA%\Google\Chrome\FlowCDPProfile"` zorunludur.

---

## 3. Kalıcı ve Garantili Çalıştırma Yöntemi

### Adım 1: Chrome CDP Daemon'ını Başlatma (Port 9223)
Antigravity veya harici bir LLM/ajan ortamından çalıştırırken `scripts/keep_chrome_alive.py` kullanılmalıdır. Bu betik `proc.wait()` ile süreci canlı tutar.

**Antigravity Ajanı İçin:**
```json
run_command(
  CommandLine="python scripts/keep_chrome_alive.py",
  IsDaemon=true,
  WaitMsBeforeAsync=500,
  toolSummary="Run Chrome CDP daemon on port 9223"
)
```

**Kullanıcı / Terminal İçin:**
```powershell
python scripts/keep_chrome_alive.py
# Veya çift tıklama ile:
chrome_flow.bat
```

### Adım 2: Çerez Senkronizasyonu ve Gemini Web2API Daemon'ı (Port 8085)
Chrome port 9223 üzerinde açıkken, `engine.providers.gemini_webapi` doğrudan çerezleri çeker ve 8085 daemon'ını başlatır:

```python
from engine.providers import gemini_webapi

# 1. 9223'ten Google çerezlerini (google.com, gemini.google.com) çek ve cookies.txt'e kaydet
gemini_webapi.sync_cookies_sync(cdp_port=9223)

# 2. Port 8085 üzerinde gemini-web2api.exe daemon'ını başlat
gemini_webapi.ensure_server_running(force_refresh=True)

# 3. Bağlantıyı doğrula
assert gemini_webapi.is_server_alive() is True
```

### Adım 3: Gerçek Gemini Yanıtını Test Etme
```python
from engine.providers.gemini_webapi import call_gemini_chat

response = call_gemini_chat("Say HELLO GROK STUDIO in one sentence.", timeout=30.0)
print(response)  # "HELLO GROK STUDIO"
```

---

## 4. Üretim Komutunu Çalıştırma

Chrome 9223 ve WebAPI 8085 açıkken doğrudan standart CLI çalıştırılır (hiçbir `--allow-deepmind-fallback` parametresi gerekmez; sistem gerçek Gemini ve Grok ile canlı çift hakemli çalışır):

```powershell
python tools/cinematic_studio_cli.py produce-film "What If Oceans Boiled Away?" --genre catastrophe --duration 300 --plan-only
```
