# YouTube Shorts Automation — Güncel Uygulama Durumu (Current Status)

Bu belge, boru hattının aktif durumunu, desteklenen sağlayıcı yollarını ve ana mimari kuralları özetler.

---

## 📌 Hızlı Referans & Dokümantasyon
- **Kalıcı Yükseltme & Prodüksiyon Günlüğü:** [`WALKTHROUGH.md`](file:///c:/Users/bekir/OneDrive/Masaüstü/Yeni%20klasör%20(2)/YOUTUBE/WALKTHROUGH.md)
- **Mimari Karar Kayıtları (ADR-001..ADR-042):** [`DECISIONS.md`](file:///c:/Users/bekir/OneDrive/Masaüstü/Yeni%20klasör%20(2)/YOUTUBE/DECISIONS.md)
- **Sistem İnvaryantları & Sözleşmeleri:** [`PROJECT_CONTEXT.md`](file:///c:/Users/bekir/OneDrive/Masaüstü/Yeni%20klasör%20(2)/YOUTUBE/PROJECT_CONTEXT.md)
- **En Son Başarılı 16:9 Arka Plan Üretimi (ADR-042):** [`output/test_video_1.mp4`](file:///c:/Users/bekir/OneDrive/Masaüstü/Yeni%20klasör%20(2)/YOUTUBE/output/test_video_1.mp4) (2.0 MB) ve [`output/test_video_2.mp4`](file:///c:/Users/bekir/OneDrive/Masaüstü/Yeni%20klasör%20(2)/YOUTUBE/output/test_video_2.mp4) (2.4 MB, 16:9 720p 24fps Veo video, sıfır odak ihlali, CS2 arkasında arka planda üretildi).

---

## 🎬 Aktif Prodüksiyon Standartları ve İki Format

1. **Format Seçenekleri (İki Format):**
   - **Format A: 16:9 Yatay Uzun Format (Nova Belgeseli - ADR-040):** `--format longform`, `LONGFORM_MODE=true` (1920x1080 / 1280x720). 28 yaşındaki kâşif "Nova" önderliğinde arkeolojik gizemler belgeseli. A-Roll (Nova konuşur, lip-sync: %10-15), B-Roll (%85-90), 40 Hz derin bas `epic_curiosity` müzik yatağı.
   - **Format B: 9:16 Dikey Shorts (Zack D. Films - ADR-001..ADR-039):** `--format short` (1080x1920), karakterler konuşmaz, alt-orta altyazı alanı boş.

2. **Zaman Çizelgesi (Timeline Contract - ADR-006):**
   - Video süresinin tek belirleyicisi gerçek TTS seslendirmesidir.
   - Ölçülen ses süresine göre kilitlenen **sağlayıcı yerel 6–13 x 4.0 saniye** (veya 5–8s Veo/H3) blok planı + **1.5 saniyelik klonlanmış kuyruk** (`tpad=stop_mode=clone`).
   - `script.json` içine kaydedilen zaman çizelgesi asla yeniden planlanmaz veya değiştirilemez.

3. **Üretim Rotaları ve Arka Plan Fabrikası (Zero-Focus Background Factory - ADR-042):**
   - **[Önerilen / Varsayılan] Playwright CDP (`playwright_flow`):** Port `9223` üzerindeki bağımsız küçültülmüş Chrome (`FlowCDPProfile`) üzerinden gerçek reCAPTCHA Enterprise token'ları (2500+ karakter) üretir, canlı çerezleri `flow-windows.exe`'ye besler. Kullanıcı CS2 oynarken veya çalışırken faresini hareket ettirmez, pencere odağını çalmaz.
   - **[2] Vertex AI:** Nano Banana Pro ve Veo 3.1 (`vertex_veo`).
   - **[3] Flow Agent:** `flow_agent` (Port 8001 servis köprüsü).


3. **Seslendirme Motoru (Deepgram Hermes):**
   - Model: `aura-2-hermes-en` (Zack D. Films belgesel tonuna uygun otoriter erkek sesi).
   - Hız & Tempo: `DEEPGRAM_TTS_SPEED=1.12`, `DEEPGRAM_ENGLISH_WPS=2.75` (Zack D. Films 160–175 WPM staccato ritmi - ADR-022).
   - Beat 1 Kancası (Hook): İlk 2-3 saniyede izleyiciyi kilitlemek için zorunlu doğrudan ikinci tekil şahıs ("You" / "What happens if you...") hitabı (ADR-030).
   - FFmpeg ASS altyazıları milisaniyelik `words.json` ile tam senkronizedir.

4. **Karakter ve Görsel Stil (Zack D. Films Estetiği):**
   - Karakterler asla konuşmaz veya dudak oynatmaz (`closed mouth`, `no dialogue`, `no lip-sync` - ADR-002).
   - Düz cansız CPR mankeni yerine canlı cilt altı saçılımlı (SSS), PBR materyalli, gri spor tişörtlü ve saydam anatomik kesitli stilize 3D animasyon karakteri kullanılır.
   - Tüm üretimler daima **9:16 dikey** (1080x1920) formatındadır.

5. **Sinematik Bitiş Geçişi (Terminal Pull-Out Decay):**
   - İç mekanizmadan/organdan dış insan bedenine dönüş anında (`boundaries[-1]`), kameranın 0.5 saniyede geriye doğru süzülerek (`zoom 1.08 -> 1.0`) tüm bedeni kadraja alması sağlanır; ani sıçramalar (jump-cut) engellenir.

6. **Veo Eşzamanlılık Kısıtlaması (ADR-008):**
   - Google Cloud Vertex AI Veo kota politikası gereği video blok üretimi sıralı kalmalıdır (`VERTEX_VEO_MAX_CONCURRENT_BLOCKS=1`). Çoklu eşzamanlı video çağrıları sessizce video verisini düşürür.

7. **Veo Çok Modlu Güvenlik ve Bilimsel Yönlendirme (ADR-009):**
   - Kesici alet, yakıcı asit, yara, kan ve yanık kelimeleri istem derleyicide (`script_engine.py`) önden filtrelenerek hassas biyomedikal laboratuvar karşılıklarına (`calibrated metallic pellet`, `concentrated amber digestive fluid`, `epithelial cellular matrix`, `thermal reaction`) dönüştürülür.
   - Nano Banana Pro'nun jilet çizmesi ve Veo'nun çok modlu güvenlik engelleri (Support code 42237218 vb.) kalıcı olarak önlenmiştir.

8. **Taktil ASMR Foley & Otonom Kalite Kontrolü (ADR-029, ADR-030):**
   - 18 fiziksel temas kategorisi ile somut ASMR ses üretimi (hidrolik tıslama, kıkırdak gerilmesi, cam çatlaması, mikro-statik vb.).
   - -10 dBFS gain staging ve +2 dB @ 4 kHz ASMR varlığı ile seslendirmeyi ezmeyen net transientler.
   - `youtube-media-inspector` MCP üzerinden anlık `analyze_audio_spectrum` ve `analyze_video_stability` kalite denetimi.

9. **Canlı Takip Arayüzü, Sıfır-Ret Motoru & Mekânsal Karakter Tutarlılık Kalkanı (ADR-031):**
   - **5 Aşamalı Canlı Takip Konsolu:** `[1/5]` Senaryo, `[2/5]` Hermes TTS ve süre kilidi, `[3/5]` Kilit kare zinciri (anlık kabul skoru: `[KABUL - Skor: 8/10]`), `[4/5]` Veo video blokları (geçen süre, % ilerleme ve kalan tahmini süre - ETA), `[5/5]` Final miksaj. Uzun API bekleme sürelerinde 15 saniyelik konsol kalp atışı (`... işleniyor (bekleme: 45s)`).
   - **Sıfır-Ret Motoru:** `compile_keyframe_prompt()` içinde `[Deterministic Proof Evidence]` zorunlu fiziksel kanıt enjeksiyonu ve `missing_object` cerrahi onarım önceliği ile kilit kare ret döngüleri 1-2 denemeye indirildi.
   - **Mekânsal & Rol Ayrıştırma Kalkanı:** Çok karakterli sahnelerde kıyafet ve rütbe ayrıştırması (`_INCIDENT_ROLE_COSTUMES`), kokpit acil durumlarında 180 derece kamera ekseni kilidi (`port-side / sol taraf`) ve monoton nedensellik denetimi (`validate_script()`).

10. **Görsel Bütünlük Mimarisi & AI Erime/Bulanma Engelleme (ADR-035):**
   - **Veo Sahneler Arası Erime Engeli (`pipeline.py`):** `build_frame_plan()` içinde `end_frame_id` ataması strictly kapılandı. Sadece aynı konu ve ölçek geçişinde (`same_subject`, `scale_transition`) ve kesme (hard cut) olmayan tekil sahne içi kamera uçuşlarında son kare bağlanır; tüm mekân ve konu değişimlerinde (`location_change`, `subject_change`) `end_frame_id = None` yapılarak bloklar birinci kareden fiziksel hareket üretir ve sahne geçişi FFmpeg temiz hard-cut ile yapılır. Kokpitin uçağa veya gözün moleküllere erimesi (AI smear) tamamen engellendi.
   - **Varlık Sınıflandırma ve İnsan/Araç Önceliği (`asset_roster.py`):** Gövde (`body`) kelimesi yüzünden uçak/araçların karaktere dönüşmesi engellendi; insan rolleri (`pilot`, `copilot`, `captain`, `attendant` vb.) sandalye/kemer (`seat`, `strap`) kelimeleri geçse dahi daima `character` olarak üretilir (kaybolan yardımcı pilot sorunu çözüldü). Tüm araç ve mekanik sahne nesnelerine kesin anti-antropomorfizm kuralı (`no face, no eyes, not a character`) eklendi (Pixar uçak gözü engellendi).
   - **Olay Modu Render Ayrıştırması (`script_engine.py`):** Olay/kaza modundaki mekanik/araç sahnelerine özel `Glossy Stylized 3D Incident Reconstruction Render` render dalı eklendi; uçaklar yanlışlıkla "medikal kesit" veya "karakter" olarak tanımlanmaktan kurtarıldı.
   - **Vizyon Kabul Kapısı Kalkanı (`nano_banana_pro.py`):** Kilit kare kabul istemine Zack D. Films 3D kil estetiği dışına sapma (2D çizgi film, Pixar karikatürü, fotogerçekçi canlı fotoğraf), araçlarda yüz/göz çizimi ve 2D çıkartma okları ret şartı olarak entegre edildi.

11. **Zack D. Films Benchmark Replikasyonu & POV Sürekliliği (ADR-037, ADR-038):**
   - **1-FPS Kare Bazlı Denetim:** Referans Zack D. Films videosundan (`fps=1`) çıkarılan karelerle 1:1 kıyaslama yapıldı. Sürücü 1. tekil şahıs POV kokpit açısı, sıcak taba/bej deri direksiyon/torpido, çıplak kaslı erkek ön kolları (saatsiz, kolsuz, beyaz tişört, mavi kot pantolon) ve sızdırmaz kabin fiziği (su ön camın dışında yükselirken kabin içi kuru kalır) kilitlendi.
   - **Hacimsel 3D Kuvvet Okları:** Basınç okları asla 2D düz çıkartma olamaz; konik başlıklı katı 3D silindirik akkor oklar (`solid 3D glowing volumetric arrows`) olarak tanımlanır.
   - **Flow Agent Port 8001 İzolasyonu:** `http://127.0.0.1:8001` FastAPI sunucusu üzerinden üretim yapılır; `flow-windows.exe bridge` arka planda daemon olarak bırakılmaz (port 9222 serbest tutulur).

12. **20-Saniyelik Flow Agent Üretimi, Beluga Model ve Sualtı Tahliye İnvariantları (ADR-039):**
   - **Beluga Model & HTTP Captcha:** Görsel üretiminde batchexecute boş kare retlerini önlemek için `FLOW_IMAGE_MODEL=beluga` ve broker hatalarını önlemek için `FLOW_RECAPTCHA=http` yapılandırıldı.
   - **Sualtı Yüzme Tahliyesi POV & Mekanik Kesit:** Açık camdan parlak güneşli su yüzeyine doğru yukarı yüzen 1. şahıs POV ve kapı içinde göl suyuyla kısa devre yapan sarı dişli motor / yeşil PCB devre kartı makro dairesel mekanik kesiti `services/script_engine.py` içine kalıcı olarak işlendi.
   - **Final 20.0s Önizleme:** 5 video bloğu, -14.9 LUFS yayın standardı ses miksajı, 8 taktil ASMR Foley efekti ve milisaniyelik Pop altyazı ile `production_20s/preview_20s.mp4` üretilerek doğrulandı.

---

## 💻 Temel Komutlar

# 16:9 Longform Nova Belgeseli (Arka planda, sıfır odak çalma ile):
python main.py --format longform --topic "The Lost Labyrinth of Hawara" --video playwright_flow --image playwright_flow

# Tek tıkla arka plan Flow oturumu açma / yenileme:
.\chrome_flow.bat

# İki blokluk hızlı arka plan duman testi (smoke test):
python main.py --format longform --test-blocks 2 --video playwright_flow --image playwright_flow

# Tam otomatik yeni üretim (rota sorar, konuyu otomatik araştırıp seçer):
python main.py

# Belirli bir konuda Vertex AI ile doğrudan üretim:
python main.py --topic "Why Your Stomach Doesn't Dissolve Itself" --video vertex_veo

# Belirli bir konuda Flow Agent ile üretim:
python main.py --topic "Why Your Stomach Doesn't Dissolve Itself" --video flow_agent

# Sıfır maliyetli yerel derleme (FFmpeg grafiği, altyazı ve zamanlama testi):
python main.py --topic "Why Your Stomach Doesn't Dissolve Itself" --dry-run

# Yarıda kalan bir üretimi kaldığı yerden devam ettirme:
python main.py --resume "run_directory_name"

# Tüm sistem mimarisini ve sözleşmeleri denetleme:
python scripts/audit_and_sync.py
```
