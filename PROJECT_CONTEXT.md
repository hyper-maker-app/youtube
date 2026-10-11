# YouTube Shorts Automation — Universal Project Context (Single Source of Truth)

Bu belge, projede çalışan tüm yapay zeka modelleri (Gemini / Antigravity, Claude, OpenAI / Codex, Cursor vb.) için ortak ve tekil anayasal referans noktasıdır.
Kalıcı prodüksiyon ve mimari yükseltmeler için [`WALKTHROUGH.md`](file:///c:/Users/bekir/OneDrive/Masaüstü/Yeni%20klasör%20(2)/YOUTUBE/WALKTHROUGH.md), güncel durum için [`DURUM.md`](file:///c:/Users/bekir/OneDrive/Masaüstü/Yeni%20klasör%20(2)/YOUTUBE/DURUM.md), mimari kararlar için [`DECISIONS.md`](file:///c:/Users/bekir/OneDrive/Masaüstü/Yeni%20klasör%20(2)/YOUTUBE/DECISIONS.md) eşlik eden temel belgelerdir.

---

## 1. Temel Üretim Sözleşmesi (Production Contract)
1. **Dinamik Sağlayıcı Tabanlı Zaman Çizelgesi**: Sabit süre terk edilmiştir. Üretilen TTS ses mikrosaniyesine kadar ölçülür, ardından 6–13 x 4.0 saniye (veya 5–8s Veo/H3) blok planı (`TimelinePlan`) kilitlenir ve `script.json`'a yazılır. 1.5s klonlanmış kuyruk (`tpad=stop_mode=clone`) içerir. Resumedan gelen plan asla değiştirilemez.
2. **Karakterler Konuşmaz (Lip-Sync Yasağı)**: Zack D. Films formatında karakterler ağızlarını açmaz. Promptlar `closed mouth, neutral mouth, no dialogue` içermelidir. Altyazılar sadece FFmpeg/ASS ile eklenir.
3. **9:16 Dikey Geometri & Altyazı Güvenli Alanı**: Tüm render ve görseller 1080x1920 (veya 720x1280) dikey olmalıdır. Alt-orta alan altyazı için boştur, buraya görsel kanıt veya ok konulamaz.
4. **FFmpeg Matematiksel Güvenliği**: `editor.py` içerisindeki `gte(time,t0)*lt(time,t1)` yarım-açık pencere kapısı ve `clip()` koordinat sınırları ASLA değiştirilemez.
5. **API Anahtarları & Gizlilik**: Kod içine hiçbir anahtar, token veya endpoint yazılamaz. Her şey `.env` üzerinden okunur; `.env.example` senkron tutulur.

---

## 2. Karar ve Deney Hafızası Kuralı (ADR Mandate)
- Bir özellik, prompt veya mimari değişiklik yapılmadan önce mutlaka `DECISIONS.md` taranmalıdır (`youtube-decision-memory` MCP veya `python scripts/decision.py search "<konu>"`).
- Önceden denenip iptal edilen (`ABANDONED` / `REJECTED`) fikirler (örneğin lip-sync, her kareye neon ok, hızlı kesimler vb.) kullanıcıya gerekçesi hatırlatılarak engellenmelidir.
- Kullanıcı bir şey denettirip "bu olmadı / iptal edelim" dediğinde veya bir test başarısız olduğunda, AI ajan durumu hemen `DECISIONS.md` dosyasına kaydetmelidir.

---

## 3. Otomatik Bakım, Doğrulama ve Git Push Kuralı (Zero-Manual-Effort)
- **Kullanıcı manuel audit veya git komutu çalıştırmayacaktır.**
- Bir AI ajan veya geliştirici (hangi LLM olursa olsun) kodda, promptta, dokümantasyonda, konfigürasyonda, sağlayıcılarda veya zamanlamada bir değişiklik yaptığında:
  1. Yanıt vermeden önce **otomatik olarak** `python scripts/audit_and_sync.py` çalıştırmak ve 0 hata ile geçtiğini doğrulamak zorundadır.
  2. Doğrulamanın hemen ardından yapılan tüm değişiklikleri **otomatik olarak** Git'e commit edip GitHub uzak deposuna pushlamak (`git add .`, `git commit -m "..."`, `git push origin main`) zorundadır. Yerel çalışma dizininde commit'lenmemiş veya push'lanmamış değişiklik bırakılamaz.

---

## 4. Mevcut MCP Sunucuları
1. **`youtube-pipeline-db` (`_pipeline_mcp.py`)**: SQLite geçmişi, son konular, dublike kontrolü, çalışma özetleri.
2. **`youtube-research` (`_research_mcp.py`)**: Wikipedia, Crossref/PubMed iddia analizi ve kanıt toplama.
3. **`youtube-decision-memory` (`_decision_mcp.py`)**: Geçmişte denenmiş/iptal edilmiş kararları arama ve yeni karar kaydetme.
4. **`youtube-media-inspector` (`_media_mcp.py`)**: FFmpeg video çözünürlük, 9:16 en-boy, LUFS ses seviyesi, freeze/black kare, FFT ses dinamik spektrum analizi (`analyze_audio_spectrum`) ve video hareket kararlılığı (`analyze_video_stability`).

---

## 5. Mevcut Beceriler (Skills)
- `decision-tracker`: Karar geçmişini denetleme ve yeni iptalleri kaydetme.
- `zack-d-director`: Zack D. Films 3D tarzı, 6 ölçekli ışıklandırma ve görsel kanıt direktifleri.
- `ffmpeg-diagnostics`: FFmpeg yarım-açık pencere, filtre grafiği ve altyazı sorun giderme.
- `topic-scout`: Causal fiziksel geçişlere uygun bilimsel konu keşfi.
- `fact-check`: Araştırma manifesti üzerinden olgusal doğrulama.
- `shorts-script-editor`: 5-beat senaryo ve süre bütçesi düzenleme.
- `video-qa`: Render edilmiş artefakt kalite kontrolü.
- `audio-mastering-qa`: Broadcast -14 LUFS, -1.5 dBTP, -10 dBFS Foley gain staging, Haas stereo ve frekans maskeleme denetimi (ADR-029, ADR-030).
- `cinematic-color-grading`: 3D Cycles stüdyo void ışıklandırma, PBR gölgelendiriciler, vinyet ve filmik kum analizi.

---

## 6. Tri-Modalite ve Akustik Standart (ADR-025, ADR-026, ADR-029, ADR-030)
- **Mod Algılama Önceliği:** `incident > mechanical > anatomical` (varsayılan).
- **Akustik Boşluk Yasağı:** Seslendirme arkasında sessizlik olamaz. `--music` yoksa lavfi motoru otomatik mood-matched bed üretir.
- **Sidechain & Anti-Pumping:** `MUSIC_VOLUME = 0.19` (-14.4 dBFS). Vokal ducking pumping'i yasaktır (ADR-017).
- **ASMR Foley:** 0.55–0.75s doğal sönümlü (exponential decay) mikro vuruşlar, -10 dBFS gain staging, peak-transient senkronu (ADR-029).
- **Taktil Foley Sözlüğü:** 18 fiziksel temas kategorisi (hidrolik tıslama, mikro-statik elektrik, kıkırdak gerilmesi, cam çatlaması, kauçuk sürtünmesi, mikrodil/kavitasyon vb.) ve soyut bilimsel terim kalkanı (ADR-030).
- **Broadcast Hedefi:** Entegre -14 LUFS / -1.5 dBTP YouTube Shorts standardı.

---

## 7. Canlı Terminal Takip Arayüzü & Sıfır-Ret Mimarisi (ADR-031)
- **5 Aşamalı Konsol Raporlaması:** Tüm pipeline adımları terminalde canlı takip edilebilir: `[1/5]` Senaryo, `[2/5]` Hermes TTS ve süre kilidi, `[3/5]` Kilit kare zinciri (`[KABUL - Skor: X/10]`), `[4/5]` Veo 3.1 video blokları (% ilerleme, geçen süre ve kalan tahmini süre - ETA), `[5/5]` Taktil Foley & Final FFmpeg miksajı.
- **Konsol Kalp Atışı (15s Heartbeat):** Uzun API beklemelerinde (özellikle Veo render) terminal sessiz kalmaz; her 15 saniyede bir `... işleniyor (bekleme: 45s)` nabzı basılır.
- **Sıfır-Ret Motoru:** `compile_keyframe_prompt()` her kare istemine `proof_on_screen` ve hedef durumu `[Deterministic Proof Evidence]` başlığıyla zorunlu olarak enjekte eder; denetmen reddi durumunda `missing_object` kategorisi cerrahi onarımın en başına alınarak eksik fiziksel bileşen doğrudan isteme eklenir.
- **Mekânsal & Rol Ayrıştırma Kalkanı:** Çok karakterli olaylarda karakterlerin rol değiştirmesi (pilot/yardımcı pilot/kabin memuru) `_INCIDENT_ROLE_COSTUMES` ve üniforma detaylarıyla kilitlenir; kokpit acil durumlarında 180 derece eksen kilidi ile sol/port taraf bütünlüğü korunur; dış gövdeye sıkışmış karakterlerin kokpit içinde kontrol kullandığı mantıksal hatalar `validate_script()` ile engellenir.

---

## 8. Zack D. Films Benchmark Replikasyonu, POV Sürekliliği ve Flow Agent İzolasyonu (ADR-037, ADR-038, ADR-039)
- **Zack D. Films Referans Sadakati (ADR-037):** Bir referans video kopyalanırken saniye saniye (`fps=1`) kare analizi yapılır; kamera açısı (1. şahıs POV vs 3. şahıs), kabin döşeme rengi (`warm tan/beige leather`), kol/kıyafet sürekliliği (`bare male forearms with warm natural skin tone, white crew-neck t-shirt, blue denim jeans, no sleeves, no watch`) ve renk kodlu etkileşim hedefleri (neon kırmızı-turuncu sıkışmış kapı kolu, neon yeşil `#39FF14` emniyet kemeri, siyah elektrikli cam düğmesi) birebir korunur.
- **Kapalı Kabin Su Fiziği & Sualtı Aydınlatma Kilidi (ADR-038):** Suya düşen araç sahnelerinde su kabinin *içine* direksiyon üstüne sıçramaz; su *ön camın dışından* yükselir, dış görünüm koyu mavi göl suyuna ve farların aydınlattığı yeşil dip otlarına dönüşür. Sualtı karelerinde (`kf02`–`kf04`, `block02`–`block03`) kabin içi aydınlatma loş soğuk-mavi sualtı ışığı olarak kilitlenir ve yan cam/ayna dışında her zaman koyu mavi sualtı görünümü belirtilir (kuru asfalt/otopark halüsinasyonu ve camda yüz yansıması yasaktır).
- **Hacimsel (Solid 3D) Kuvvet Okları:** Dış su basıncı veya kuvvet vektörleri asla içi boş 2B neon çizgi (`->`) olarak çizilmez; `solid 3D glowing red volumetric arrows (solid 3D conical arrowheads with glowing cylindrical shafts, NOT flat hollow outline arrows)` olarak belirtilir.
- **NanoBanana (`NARWHAL`) Inline Güvenlik Kalkanı:** Statik kilit kare (`kf01`) istemlerinde `"drives off ... straight into a lake"` gibi ifadeler kendine zarar verme filtresine takılıp boş yanıt (`empty`) döndürebilir; statik karede `"drives toward a calm blue lake on a sunny day"` kullanılır, suya dalış hareketi `abra_i2v_4s` video isteminde (`block01`) verilir.
- **Flow Agent Port 8001 İzolasyonu:** Görsel ve video üretiminde yalnızca `http://127.0.0.1:8001` (`--video flow_agent --image flow_agent`) kullanılır; `flow-windows.exe bridge` arka planda daemon olarak açık bırakılmaz (`9222` portunu kilitlememesi için) ve `flow.db` içinde `account_index='0'` SQLite tetikleyicisiyle kilitli tutulur.
- **Flow Agent Beluga Model & HTTP Captcha Bypass (ADR-039):** Görsel üretiminde `FLOW_IMAGE_MODEL=beluga` modeli varsayılandır (`narwhal` batchexecute retlerini önler). `flow.captcha` broker değerlendirme hatalarını önlemek için `.env` içinde `FLOW_RECAPTCHA=http` yapılandırılır.
- **Sualtı Yüzme Tahliyesi ve Dairesel Mekanik Kesit İnvariantları (ADR-039):** Açık camdan yukarı yüzme sahnelerinde yukarı bakan 1. tekil şahıs POV, parlak güneşli su yüzeyine doğru kurbağalama yapan çıplak kollar ve yükselen hava kabarcıkları kilitlenir. Elektrik arızası açıklamasında kapı döşemesi içinde dairesel makro mekanik kesit (sarı cam dişli motoru ve göl suyuyla kısa devre yapan yeşil PCB devre kartı) kullanılır.

---

## 9. 16:9 Yatay Uzun Format "Model A Hibrit Zaman Yolcusu" Belgeseli (ADR-040, ADR-043)
- **Format:** 16:9 Yatay Widescreen (1920x1080 / 1280x720, `LONGFORM_MODE=True`, `--format longform`, 7–12 dk Defne standardı).
- **Konsept & Karakter Tutarlılığı (`services/character.py`):** 28 yaşında kadın kronolojik zaman yolcusu ve araştırmacı kâşif "Nova".
  - **Değişmez Yüz & Kimlik Kilidi:** Kehribar hareleri olan ela gözler, belirgin elmacık kemikleri, burun sırtında zarif çiller, kestane rengi dalgalı saçlar, simetrik yüz anatomisi.
  - **Zaman Yolcusu Simgesi:** Sol bileğinde dönen gyroskopik kadranlı pirinç/bronz temporal kronometre cihazı ve minyatür kum saati kolyesi tüm videolarda ve çağlarda sabit kalır.
  - **Çağ Kamuflaj Gardırobu (`detect_era()`):** Ziyaret edilen döneme göre otantik kamuflaj kıyafetleri (Neolitik, Antik Mısır, Greko-Romen, Osmanlı, Mezopotamya, Orta Çağ, Viktorya dönemi veya modern keşif safari ceketi).
- **Model A Hibrit Montaj Mimarisi (`LONGFORM_HYBRID_MODE=True`):**
  - **A-Roll (Kilit Anlar — %10-15):** Açılış kancası (Blok 1), dönüm noktası/şok keşif tepkisi ve kapanış değerlendirmesi; Google Flow AI video üretimi (`playwright_flow`, port 9223).
  - **B-Roll (%85-90):** Antik yapılar, yeraltı labirentleri, tapınak kabartmaları, tarihi haritalar; yüksek çözünürlüklü 2.5D Ken Burns Pan/Zoom montajı (`editor.render_ken_burns_block`).
- **Seslendirme & Müzik:** Deepgram Aura-2 ile doğal belgesel temposu (1.0x, `DEEPGRAM_TTS_SPEED=1.0`), 40 Hz derin baslı `epic_curiosity` müzik yatağı (`services/audio_bed.py`).

---

## 10. Arka Plan Sıfır-Odak Üretim Fabrikası (Zero-Focus Background Factory - ADR-042)
- **Sağlayıcı:** `IMAGE_PROVIDER=playwright_flow`, `VIDEO_PROVIDER=playwright_flow`.
- **Çalışma Prensibi:**
  - `chrome_flow.bat` ile port `9223` üzerinde izole bir Chrome oturumu (`FlowCDPProfile`) açılır.
  - Kullanıcı bu pencerede bir kez Google Flow'a giriş yapar ve pencereyi simge durumuna küçültür (minimize eder).
  - Playwright CDP (`services/playwright_flow_client.py`), arka planda `flow.google.com` origin'inde gerçek `grecaptcha.enterprise.execute` (2500+ karakter) token'ları üretir ve oturum çerezlerini `flow-windows.exe` motoruna `ws://127.0.0.1:9222` köprüsüyle besler.
- **Kullanıcı Deneyimi:** İşletim sistemi faresini oynatmaz, pencere odağını çalmaz, kullanıcı CS2 oynarken veya başka işle uğraşırken 100% arka planda çalışır.
- **Geri Dönüş (Fallback) Zinciri:**
  1. `playwright_flow` (Port 9223 CDP — sıfır odak ihlali, varsayılan)
  2. `flow_agent` / extension bridge (Port 9222 WebSocket)
  3. `virtual_desktop_runner` (`pyvda` Windows Sanal Masaüstü 2 izolasyonu)
- **Üretim Komutu:**
  `python main.py --format longform --topic "The Lost Labyrinth of Hawara" --video playwright_flow --image playwright_flow`


