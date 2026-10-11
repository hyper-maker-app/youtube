# MASTER PROMPT: @zamanyolcusudefne Standardında Otonom AI Belgesel Pipeline Optimizasyonu

Aşağıdaki talimatları, sana ekte verilen `project_for_llm.zip` arşivindeki kod tabanını, mimari belgeleri ve son üretim çıktılarını inceleyerek harfiyen uygula.

---

## 1. PROJE VE HEDEF TANIMI
Bu proje, YouTube için tam otonom yapay zekâ belgesel videoları üreten bir Python pipeline'ıdır.
Hedefimiz: **https://www.youtube.com/@zamanyolcusudefne** kanalının kalitesinde (özellikle 18 Mart 1915 Çanakkale Boğaz Savaşı: https://www.youtube.com/watch?v=PXixPeATIQc ve 1470 İstanbul belgeselleri gibi) 16:9 yatay (1920x1080 / 1280x720) sinematik tarih belgeselleri üretmektir.

- **Format**: 16:9 Geniş Ekran (Widescreen Landscape).
- **Karakter / Anlatıcı**: 28 yaşında zamanyolcusu kadın araştırmacı "Nova" (`services/character.py`). Kilitli fiziksel özellikler (ela-kehribar gözler, çiller, dalgalı kestane saç), sol bileğinde pirinç gyroskopik zamansal kronometre ve döneme uygun kamuflaj kıyafetleri.
- **Seslendirme (TTS)**: Deepgram Aura-2 Hera (`aura-2-hera-en`, 1.0x doğal belgesel temposu).
- **Müzik ve Ses**: FFmpeg tabanlı çok katmanlı ortam sesleri (`ambient_soundscape.wav`), 40 Hz derin bas merak teması (`audio_bed_epic_curiosity.wav`) ve taktil Foley ses efektleri.

---

## 2. DONANIM VE SAĞLAYICI KISITLARI (ÇOK KRİTİK)
- **Vertex AI / Ücretli API YOKTUR**: Kullanıcının Vertex AI veya ücretli Google Cloud API kredisi YOKTUR.
- **Tek Video ve Görsel Kaynağı**: Kullanıcının **Google Flow (Veo / Beluga)** kredisi vardır.
  - Bu sistem, arka planda çalışan Chrome CDP port `9223` (`chrome_flow.bat`) ve `flow-windows.exe` üzerinden çalışır (`services/playwright_flow_client.py`).
  - Video Provider: `playwright_flow`
  - Image Provider: `playwright_flow`
- **İşletim Sistemi**: Windows, Python 3.12, imageio-ffmpeg üzerinden FFmpeg 7.1.
- **Kullanıcı Kuralı**: Kullanıcı kod yazmayacak, terminalde elle hata çözmeyecek ("ben hiçbir şeyi ellemek istemiyorum, zaman ve api sınırı yok"). Tüm analiz, kod düzeltme ve video üretimini sen otonom yöneteceksin.

---

## 3. YAŞANAN TEMEL SORUN VE KÖK NEDENİ
Kullanıcı en son şu komutu çalıştırdı:
`python main.py --format longform --topic "The Secrets of Gobekli Tepe" --video playwright_flow --image playwright_flow`

Üretilen video (`out/the-secrets-of-gobekli-tepe_20261011_144431/final.mp4`) incelendiğinde kullanıcının tespiti:
> **"Yine sabit görsel üstüne ses eklenmiş!"**

### Kök Neden Analizi:
1. **`LONGFORM_HYBRID_MODE=True` Hatası**: Pipeline'da (`pipeline.py:1594-1610`) B-roll sahneleri (videonun %85'i), video üretim modeline hiç sokulmadan doğrudan `editor.render_ken_burns_block` fonksiyonuna (sabit fotoğrafa dijital zoom/pan) yönlendiriliyordu.
2. **Sessiz Fallback**: Geriye kalan 3 sunucu sahnesinde Flow motoru hata verdiğinde `except Exception` bloğu sessizce Ken Burns sabit fotoğrafına düşüyordu.
3. **Sonuç**: 108 saniyelik videonun 15 bloğunun 15'i de tamamen sabit fotoğraflardan oluşan bir slayt gösterisinden ibaret kaldı.
4. **Aldatıcı Testler**: Eski test scriptleri FFmpeg dijital zoom hareketini "video hareketi" sanıp yeşil ışık yakıyordu.

---

## 4. YAPILAN CANLI DOĞRULAMA VE İLK DÜZELTMELER
Zip arşivini incelemeden önce bilmen gereken son canlı test sonuçları:
1. `services/playwright_flow_client.py` motoru doğrudan test edildi:
   - `flow-windows.exe generate -prompt "..." -aspect landscape -reference <kf.png>` komutuyla Google Flow'un **1280x720 16:9 yerel yatay video ürettiği kanıtlandı** (`scratch/test_flow_ref_landscape.mp4`).
   - Kamera vinç gibi yukarı süzülüyor, 3D derinlik ve paralaks mükemmel çalışıyor.
2. `config.py`, `.env` ve `pipeline.py` içinde `LONGFORM_HYBRID_MODE=False` yapıldı ve sessiz Ken Burns fallback'i kaldırıldı.
3. `main.py` içerisine `--hybrid` opsiyonel bayrağı eklendi (varsayılanı `False`, yani %100 AI video).

---

## 5. BU SİSTEMİ DAHA SAĞLAM ZEMİNE OTURTMAK İÇİN MİMARİ KARŞILAŞTIRMA VE EKSİKLER
Aşağıdaki 4 öncü GitHub deposunun mimarileri incelendi. Bizim pipeline'ımızın bunlara göre eksikleri ve senin uygulaman gereken reformlar:

### Referans Depolar:
1. **https://github.com/KKenny0/script-weaver**
2. **https://github.com/ai-playbooks/historical-documentary-video-workflow**
3. **https://github.com/ai-playbooks/videoexpress-historical-documentary-agent**
4. **https://github.com/HiAPIAI/awesome-ai-video-workflows**

### 1) Senaryo ve Dramatik Kurgu Eksikleri (Script-Weaver Deseni):
- **Eksik**: Bizim `services/screenplay.py` dosyamız temel bir yapıya sahip olsa da, LLM çağrısı başarısız olduğunda veya şablona düştüğünde tekrarlayan kalıplar kullanıyor.
- **Uygulanacak**: Script-Weaver'ın 5-fazlı dramatik yayını (`core/narrative_longform.py` ve `services/screenplay.py`) tam otonom hale getir:
  1. *Hook / Cold Open (0-10s)*: Sarsıcı bir anomali, paradoks veya dramatik soru.
  2. *Context & Sensory Immersion (10-30s)*: Dönemin sokakları, sesleri, toz, duman, pazar yeri, zanaatkarlar.
  3. *Rising Investigation (30-60s)*: İpuçları, kazı detayları, tarihi tanıklar veya gizli mekanizmalar.
  4. *Turning Point / Core Discovery (60-90s)*: Gizemin kırılma noktası veya tarihi dönüm anı.
  5. *Legacy & Philosophical Reflection (90-120s)*: Tarihsel miras ve günümüze yansıması.
- Her sahne için karakter durumu, ışık saati (golden hour, chiaroscuro torchlight) ve dramatik tempo belirlenmelidir.

### 2) Tarihsel Doğruluk ve Anakronizm Kalkanı (ai-playbooks & HiAPIAI Deseni):
- **Eksik**: Prompt derleyicimiz (`services/prompt_compiler.py`) zaman zaman Flow'a genel ve soyut ifadeler gönderiyor, bu da modelin tarihi sahnelerde modern hatalar yapmasına yol açabiliyor.
- **Uygulanacak**:
  - **Clothing Lock (Kıyafet Kilidi)**: "Ancient clothing" gibi belirsiz tabirleri kesinlikle yasakla; kumaş cinsi (kaba dokuma keten, yün tunik), kesim, dikiş ve maden aksamını kilitli tut.
  - **Movement Lock (Canlı Eylem Zorunluluğu)**: Durağan pozları ("standing", "looking", "watching") kesinlikle yasakla. Bunun yerine amaca yönelik fiziksel iş eylemleri ("çakmaktaşıyla kireçtaşı yontma", "halat asılma", "fırtınada küreklere yüklenme") ve `"Natural continuous body movement, shifting weight, moving fabric, coordinated purposeful labor, and atmospheric wind physics"` ekle.
  - **Ancient Equipment Rule**: Modern mekanik terimleri ("crane", "metal bolt") yasakla; insan gücü, meşe kütükleri ve kenevir halatları zorunlu kıl.

### 3) Görsel Devamlılık ve Referans Kilitleme (Reference-to-Video Entegrasyonu):
- **Eksik**: Google Flow'un `-reference` bayrağı daha önce sadece ilk sahnede kullanılıyordu. Sahneler arası karakterin ("Nova") ve tarihi ortamın değişmemesi için tutarlı referans iletimi gereklidir.
- **Uygulanacak**: `_character_sheets/character_sheets_manifest.json` ve `asset_roster.json` içindeki anahtar karakter/ortam referanslarını (`services/playwright_flow_client.py` üzerinden) ilgili her bloğun video üretimine `-reference` olarak besle. Böylece 1. sahnedeki karakter ile 5. sahnedeki karakter tıpatıp aynı kalsın.

### 4) Çok Katmanlı Ses Tasarımı ve Yayın Standardı:
- @zamanyolcusudefne kalitesine ulaşmak için sadece anlatıcı sesi yetmez; 4 katmanlı ses miksajı (`editor.py`):
  1. *Voiceover (TTS)*: Deepgram Aura-2 Hera (-14 LUFS yayın hedefi, kristal netlik).
  2. *Diegetic Foley*: Sahneye senkronize ayak sesleri, deniz dalgaları, meşale çıtırtısı, çekiç darbeleri (`services/sfx.py`).
  3. *Ambient Drone / Room Tone*: 40 Hz derin bas merak tonu veya atmosferik rüzgar (`ambient_soundscape.wav`).
  4. *Cinematic Score*: Anlatıcı sesinin arkasında konuşmayı asla bastırmayan hafif sidechain ducking uygulanmış orkestral müzik bedi.

### 5) Anti-Self-Deception Kalite Kontrol Kapısı (`scripts/benchmark_quality_gate.py`):
- **Eksik**: Eski test scripti dijital zoompan hareketini "video hareketi" sanıp yeşil ışık yakıyordu.
- **Uygulanacak**: `benchmark_quality_gate.py` dosyasını güncelle:
  - Eğer `blocks/*.mp4` dosyalarından herhangi biri `editor.render_ken_burns_block` (statik fotoğraf) ile üretilmişse veya optik akışta (optical flow) sadece 2D afin dönüşüm (salt zoom/pan) varsa, testi doğrudan **BAŞARISIZ (Exit Code 1)** say.
  - Sadece ve sadece gerçek difüzyon videosu (paralaks, deformasyon, ışık dalgalanması) içeren videoları onayla.

---

## 6. SENDEN BEKLENEN SOMUT ADIMLAR
1. **Arşivi İncele**: Ekteki zip dosyasındaki kodları oku.
2. **Eksikleri Tamamla**: Yukarıdaki mimari eksikleri kod tabanında (`services/`, `pipeline.py`, `scripts/benchmark_quality_gate.py`) düzelt.
3. **Audit Kontrolü**: `python scripts/audit_and_sync.py` ve `pytest tests` komutlarının 0 hata ile geçtiğini doğrula.
4. **Gerçek Video Üretimini Başlat ve Doğrula**:
   - `python main.py --format longform --topic "1915 The Battle of Gallipoli" --video playwright_flow --image playwright_flow --blocks 6` komutunu çalıştır.
   - Üretilen her bloğun gerçek Google Flow videosu olduğunu `benchmark_quality_gate.py` ile kanıtla.
   - Kullanıcıya sonuç raporunu ve karşılaştırma analizini sun.
