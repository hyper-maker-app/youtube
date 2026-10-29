# GROK CINEMATIC STUDIO v4.0 — VIRAL NARRATIVE & PHYSICAL FACTORY REARCHITECTING PLAN (APPROVED)

## Goal Description
Pilot bölümde (`Project Rigor Mortis Episode 01`) tespit edilen 6 kritik hatayı ve YouTube'da 2.7M+ izlenen "Beanie Survives" viral zombi hayatta kalma anlatı matematiğini temel alarak, `GROK_CINEMATIC_STUDIO` platformunu kökten revize etmek. Bu düzenlemeler tek bir projeye özel geçici yamalar değil; bundan sonra üretilecek tüm sinematik yapımların fabrika standardı haline gelecektir.

> [!IMPORTANT]
> **%100 İngilizce Üretim Değişmezi (Zero-Turkish Invariant):**  
> Tüm senaryo metinleri, manuscript beatleri, TTS seslendirmeleri, STT forced alignment ve altyazı motoru istisnasız **%100 İngilizce** (`en` / `en-US`) olarak çalışacaktır. Türkçe üretim kesinlikle yapılmayacaktır.

---

## Technical Highlights & Verified Invariants

1. **Spoken Text Sanitizer Gateway:**
   Metinlerdeki "Act 1:", "Scene 01:", `[Sound of sirens]` gibi direktiflerin TTS ve altyazıya girmesini engelleyen Regex ve AST filtresi.
2. **Beanie Survives 2. Tekil Şahıs ("You/Sen") Kurgu Reformu:**
   3. şahıs pasif anlatım yasak. İlk 3 saniyede kriz kancası (in media res), somut mikro hayatta kalma matematiği (su, kalori, 70dB desibel sınırı, koli bandı barikatı) ve yüz halüsinasyonunu sıfırlayan atmosferik/durumsal planlar (kapı gözetleme deliği / peephole POV, kilit sürgüsü, batarya LED'i, silüet). Dinamik 4-10s kurgu ritmi.
3. **Çift Kademeli SFX & Foley Motoru:**
   - **Ana Sistem (Primary):** `gradio_client` ile Hugging Face Space bağlantısı (`fffiloni/audiogen` & `declare-lab/TangoFlux`).
   - **Yedek Güvence (Fallback):** Çevrimdışı, sıfır maliyetli, Windows uyumlu (`config.resolve_ffmpeg()`) FFmpeg `lavfi` sentetik foley motoru (whoosh, sub-bass thud, tension heartbeat, wind drone).
4. **Gemini Flash "Transition Boundary Triplet" (Filmstrip Grid) QA Kapısı:**
   Komple video yüklemenin 1 FPS körlüğünü ve gecikmesini aşmak için bellek içinde OpenCV ile birleşik JPEG:
   `[Hero DNA Plate] + [Block N Exit Frame (t=T-0.04s)] + [Block N+1 Entry Frame (t=0.04s)]`.
   6 süreklilik kuralı (kıyafet, eldeki eşyalar, ışık vektörü, bakış açısı, hasar/fiziksel durum, jump-cut). Skor < 0.85 ise 1x düzeltici re-roll; ikinci denemede tolerans dışı kalsa dahi advisory log ile devam.
5. **Dry-Run Motor Düzeltmesi:**
   `flow_bridge.py:264` satırındaki hardcoded `editor.render(..., dry_run=False)` hatasının `dry_run=dry_run` olarak düzeltilmesi.
6. **Kalıcı Kurallar & AGENTS.md:**
   `references/agents/VIRAL_SECOND_PERSON_RETENTION_FOLEY_PROTOCOL_v4.0.md` protokolünün oluşturulması ve `AGENTS.md` içerisine zorunlu fabrika standardı olarak işlenmesi.
7. **Pluggable Voyslity & ElevenLabs English Voice Provider:**
   %100 İngilizce sinematik seslendirme (Adam, Daniel, Antoni, Rachel) + Deepgram Nova-3 English STT forced alignment + SequenceMatcher ile noktalama kurtarma.

---

## Detailed Components & Implementation Order

### Component 1: Spoken Text Sanitizer & Metadata Stripper Gateway
- **[NEW] `engine/services/text_sanitizer.py`**:
  - `sanitize_spoken_text(text: str) -> str`:
    - Regex temizleme: `(?:Act|Scene|Part|Chapter)\s*\d+\s*[:\-–]?`
    - Direktif temizleme: `\[(?:Sound|SFX|Audio|Visual|Shot|Camera|Whisper|Foley|Pause|Beat)[^\]]*\]`, `\([^\)]*\)`
    - Konuşmacı etiketleri: `^(?:Narrator|Voiceover|VO|You)\s*:\s*`
- **[MODIFY] `tools/cli/produce_commands.py`**:
  - Line 116 `"narration": f"Act {min(3, act_num)}: {action}"` kalıbı kaldırılıp temiz eyleme dönüştürülecek.
  - Handoff kaydetme/yükleme aşamalarına `sanitize_spoken_text()` güvenlik filtresi eklenecek.
- **[MODIFY] `engine/flow_bridge.py`**:
  - `beats` listesi hazırlanırken metin zorunlu sanitizasyondan geçirilecek.
- **[MODIFY] `engine/providers/voice/_utils.py`**:
  - `narration_text` fonksiyonuna regex temizleme filtresi eklenecek.

---

### Component 2: Narrative & Hook Reform ("Beanie Survives" Standardı)
- **[MODIFY] `tools/cli/produce_commands.py`**:
  - `generate_local_3act_scenes` içindeki tüm sahneler 2. tekil şahıs ("You"), mikro hayatta kalma matematiği (su, desibel, barikat) ve atmosferik görsel odaklara (peephole POV, kilit yuvası, telsiz, su damlası) dönüştürülecek.
  - LLM sistem istemi güncellenecek.
  - Blok süreleri sabit 8.0s yerine `[4.0, 6.0, 8.0, 10.0]` saniye dinamik kurgu setinden sahne dramaturjisine göre seçilecek.

---

### Component 3: Hugging Face Gradio Space SFX & FFmpeg Lavfi Foley
- **[NEW] `engine/providers/sfx/gradio_space.py`**:
  - `gradio_client.Client` ile `fffiloni/audiogen` ve `declare-lab/TangoFlux` Space'lerine 20s zaman aşımıyla bağlantı.
- **[NEW] `engine/providers/sfx/ffmpeg_lavfi.py`**:
  - `config.resolve_ffmpeg()` ile Windows uyumlu 4 sentetik foley reçetesi (Whoosh, Sub-Bass Thud, Tension Heartbeat, Wind Drone).
- **[MODIFY] `engine/providers/factory.py`**:
  - `sfx_provider` kaydına `gradio_space` ve `ffmpeg_lavfi` eklenecek.
- **[MODIFY] `engine/flow_bridge.py`**:
  - Senaryo aksiyonlarından SFX ipuçları türetilip önce Space ardından Lavfi fallback ile üretilecek ve `editor.render(..., sfx_cues=sfx_cues)` ile FFmpeg kurgusuna aktarılacak.

---

### Component 4: Gemini Flash "Transition Boundary Triplet" & Cross-Block QA
- **[MODIFY] `engine/.env`**:
  - `ALLOW_UNREVIEWED_KEYFRAMES=false`
  - Google AI Studio ücretsiz katmanı (`GEMINI_API_KEY`) eklenecek.
- **[NEW] `engine/services/boundary_inspector.py`**:
  - OpenCV ile bellek içinde (292 ms'de) `[Hero DNA] + [Block N Exit] + [Block N+1 Entry]` birleşik görseli (16.5 KB, ~258 token) oluşturulacak.
  - Gemini 2.5 Flash yapılandırılmış JSON şeması ile 6 kural denetlenecek.
- **[MODIFY] `engine/flow_bridge.py`**:
  - Blok üretim döngüsüne Transition Boundary denetimi entegre edilecek; skor < 0.85 ise `corrective_prompt_injection` ile 1x re-roll yapılacak.

---

### Component 5: Dry-Run Modu & FFmpeg Kurgu Düzeltmesi
- **[MODIFY] `engine/flow_bridge.py`**:
  - Line 264'teki `editor.render(..., dry_run=False)` ifadesi `editor.render(..., dry_run=dry_run)` olarak düzeltilecek.

---

### Component 6: Kalıcı Kurallar ve AGENTS.md Dokümantasyonu
- **[NEW] `references/agents/VIRAL_SECOND_PERSON_RETENTION_FOLEY_PROTOCOL_v4.0.md`**:
  - Tüm "Beanie Survives" 2. tekil şahıs senaryo kuralları, mikro matematik, peephole kamera kuralları ve SFX protokolü belgelenecek.
- **[MODIFY] `AGENTS.md`**:
  - "MANDATORY PRODUCTION ENGINE" bölümüne v4.0 kuralları zorunlu fabrika standardı olarak işlenecek.

---

### Component 7: Pluggable Voyslity / ElevenLabs English Voice Provider & Nova-3 STT
- **[NEW] `engine/providers/voice/voyslity_english.py`**:
  - Voyslity REST API (tarayıcı User-Agent ve asenkron polling destekli).
  - İngilizce modeller: `eleven_multilingual_v2`, `eleven_flash_v2_5`.
  - Daniel, Adam, Rachel, Antoni sesleri.
  - `.env` içindeki `ELEVENLABS_API_KEY` ile resmi API fallback desteği.
  - İndirilen MP3'ün FFmpeg ile 48kHz mono PCM WAV'a çevrilmesi.
  - Deepgram Nova-3 English STT forced alignment + SequenceMatcher ile noktalama kurtarma.
- **[MODIFY] `engine/providers/factory.py`**:
  - `voyslity` ve `elevenlabs` ses sağlayıcıları kaydedilecek.
- **[MODIFY] `engine/flow_bridge.py` & `tools/cli/produce_commands.py`**:
  - `--voice-provider` (`deepgram` | `voyslity` | `elevenlabs`) bayrağı eklenecek, varsayılan dil `en` kilitlenecek.
