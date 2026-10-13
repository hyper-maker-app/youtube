# YouTube Shorts Automation — Architecture Decision Records (ADR) & Experiment Log

Bu belge, projede talep edilen, denenen, kabul edilen veya **kötü sonuçlanıp iptal edilen** tüm teknik ve sanatsal kararların kalıcı hafızasıdır.

> [!IMPORTANT]
> **TÜM LLM'LER İÇİN ZORUNLU KURAL**:
> Kullanıcıdan yeni bir özellik, stil veya mimari değişiklik istendiğinde, bu dosyayı kontrol etmeden işe başlanamaz. Daha önce denenip iptal edilen bir yaklaşım tekrar önerilemez veya uygulanamaz. Eğer kullanıcının istediği bir şey denenip başarısız olursa veya kullanıcı "bu olmadı, iptal edelim / geri alalım" derse, bu durum anında gerekçesiyle bu dosyaya `ABANDONED` veya `REJECTED` olarak kaydedilmelidir.

---

## Karar Durumları (Statuses)
- `ACCEPTED`: Denendi, doğrulandı ve aktif üretim standardı olarak kabul edildi.
- `REJECTED`: Önerildi veya değerlendirildi ancak risk/maliyet/kalite nedeniyle reddedildi.
- `ABANDONED`: Denendi/kodlandı fakat pratikte kötü sonuç verdiği için iptal edildi/geri alındı.
- `SUPERSEDED`: Daha önce geçerliydi ancak yerini daha iyi bir karar aldı.

---

## Karar Kayıtları

### [ADR-001] 3 Bloklu Sabit Senaryodan Dinamik Sağlayıcı Tabanlı Plana Geçiş
- **Tarih**: 2026-08-01
- **Durum**: `SUPERSEDED`
- **Talep / Fikir**: Başlangıçta tüm videolar 3 blok x 10 saniye sabit yapıda üretiliyordu.
- **Sonuç / Problem**: Veo ve Fal modellerinin doğal video üretim süreleri (4s, 5s, 8s) ile uyuşmadı. LLM 10 saniyelik sahneleri doldurmak için hareketi erken bitirip donma (freeze) talimatları veriyordu; bu da izleyici terkine yol açtı.
- **Verilen Karar**: Sabit süre terk edildi. Sağlayıcı yerel (provider-native) 6–13 x 4.0s (veya 5–8s Veo/H3) blok planına geçildi.
- **Kalıcı Ders**: Asla modelin doğal üretim süresinin üzerinde yapay uzatma veya sahne dondurma yapılmamalı.

---

### [ADR-002] Karakter Konuşması, Dudak Hareketi ve Lip-Sync Kesin Yasağı
- **Tarih**: 2026-08-10
- **Durum**: `ABANDONED`
- **Talep / Fikir**: Zack D. Films animasyonlarındaki 3D insan modelleri ağızlarını açıp konuşsun veya dublaj ile dudak senkronu (Wav2Lip/SadTalker vb.) yapılsın.
- **Yapılan İş**: 3D karakter yüzlerine açık ağız ve konuşma mimikleri denendi.
- **Sonuç**: KÖTÜ / FAIL.
- **İptal Edilme Sebebi**:
  1. Zack D. Films'in orijinal tarzında karakterler asla konuşmaz; anlatıcı (voiceover) dışarıdan olayı klinik ve sakin bir dille anlatır, karakterler yalnızca durumun fiziksel etkisini yaşar.
  2. Yapay zeka ile üretilen dudak hareketleri uncanny valley (tekinsiz vadi) hissi yarattı, medikal/anatomik ciddiyeti bozdu ve deformasyonlara neden oldu.
- **Kalıcı Kural**: Karakterlerin ağızları daima kapalı veya nötr olmalıdır. Promptlarda açıkça `closed mouth`, `neutral mouth`, `no speaking`, `no dialogue` bulunmalıdır. Altyazılar sadece FFmpeg/ASS ile eklenir.

---

### [ADR-003] Her Sahneye Otomatik Neon Ok ve Trajectory Efekti Eklenmesi
- **Tarih**: 2026-08-18
- **Durum**: `ABANDONED`
- **Talep / Fikir**: İzleyicinin dikkatini çekmek için her sahneye parlak neon yeşil oklar, kırmızı yörüngeler veya vurgular otomatik eklensin.
- **Yapılan İş**: Generator prompt derleyicisine varsayılan olarak yeşil ok ve yörünge direktifleri eklendi.
- **Sonuç**: KÖTÜ / FAIL.
- **İptal Edilme Sebebi**: Her sahnede rastgele yönleri gösteren anlamsız oklar belirdi; videoyu profesyonel 3D belgeselden ucuz mobil oyun reklamı havasına soktu.
- **Kalıcı Kural**: Bir işaretçi (neon ok / kırmızı yörünge) YALNIZCA senaryodaki `proof_on_screen` açıkça bir fiziksel kanıtı (örneğin çatlağın başladığı mikro nokta) işaret etmeyi şart koştuğunda eklenir. Süs amaçlı dekoratif ok eklemek yasaktır. Eklenen işaretçi asla alt-orta altyazı alanında olamaz.

---

### [ADR-004] Hızlı Kesimler (Fast-Cuts) ve Agresif Crash Zoom/Shake
- **Tarih**: 2026-08-25
- **Durum**: `REJECTED`
- **Talep / Fikir**: TikTok/Shorts dinamizmini artırmak için 1-2 saniyelik çok hızlı kesimler ve FFmpeg ile ani sarsıntı/crash zoom efektleri verilsin.
- **Yapılan İş**: Filtre grafiğine 1.5x crash zoom ve titreme efektleri uygulandı.
- **Sonuç**: KÖTÜ / REDDEDİLDİ.
- **İptal Edilme Sebebi**: Zack D. Films estetiğinin temeli sakin, ağırbaşlı, net ve didaktik 3D anlatımdır. Ani titremeler izleyicinin mikroskobik veya anatomik detayı incelemesini engelledi ve kalite puanını düşürdü.
- **Kalıcı Kural**: Sahneler arası geçişler hard-cut'tır. Yalnızca kritik fiziksel darbe anlarında maksimum %1.2 hafif yerel yeniden çerçeveleme (reframe) yapılabilir. Ekstra titreme/crash zoom yasaktır.

---

### [ADR-005] FFmpeg `gte*lt` Yarım Açık Pencereler ve `clip()` Koordinat Koruması
- **Tarih**: 2026-08-28
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Zaman aralıklarını `<= ve >=` ile yazmak veya kırpma koordinatlarını basitleştirmek.
- **Sonuç / Problem**: Tam sınır karelerinde çift kare sahipliği (glitch/flicker) oluştu ve sınır dışına taşan zoom koordinatlarında siyah şeritler (black edge exposure) meydana geldi.
- **Verilen Karar**: `editor.py` içerisindeki `gte(time,t0)*lt(time,t1)` yarım-açık pencere kapısı ve `clip(dim*target - dim/zoom/2, 0, dim - dim/zoom)` formülü KESİNLİKLE değiştirilemez.
- **Kalıcı Ders**: Bu formüllere hiçbir LLM dokunamaz; audit betiği bunu her çalıştırmada doğrular.

---

### [ADR-006] Ses Ölçümlü Dinamik Zaman Çizelgesi (Audio-Locked Native Plan)
- **Tarih**: 2026-09-02
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Video süresini önce rastgele belirleyip sonra sesi uydurmaya çalışmak.
- **Sonuç / Problem**: Ses videodan kısa kaldığında video anlamsızca donuyor, uzun kaldığında ise son cümle kesiliyordu.
- **Verilen Karar**: Senaryo metni önce üretilir, gerçek TTS ile mikrosaniyesine kadar ölçülür, ardından `TimelinePlan` kilitlenir (6–13 x 4.0s). En sona 1.5 saniyelik klonlanmış kuyruk (`tpad=stop_mode=clone`) eklenir. `script.json` içine kaydedilen plan değiştirilemez.
- **Kalıcı Ders**: Zamanlamanın tek patronu ölçülen sestir.

---

### [ADR-007] Flow CLI Aracı Başarısızlığında Otomatik Sağlayıcı Değiştirmeme (Handoff Kuralı)
- **Tarih**: 2026-09-05
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Google Flow CLI veya oturumu çöktüğünde sistem sessizce Fal.ai veya Vertex AI'a geçsin.
- **Sonuç / Problem**: Kullanıcının haberi olmadan yüksek maliyetli veya farklı görsel dile sahip API çağrıları tetiklendi.
- **Verilen Karar**: Flow başarısız olursa sistem `HandoffPending` fırlatır ve `handoff.md` yazar. Kullanıcı ya adımları manuel tamamlar ya da bilinçli olarak `--video vertex_veo` bayrağı ile yeni bir akış başlatır. Asla sessizce fallback yapılamaz.

### [ADR-008] Veo Video Generation Concurrency Limit
- **Tarih**: 2026-09-08
- **Durum**: `REJECTED`
- **Talep / Fikir**: Run Vertex Veo 3.1 video block generation with concurrency >= 2 to cut video rendering time in half
- **Yapılan İş / Sonuç**: Google Vertex AI Veo dropped video payloads silently (operation completed without generated video) on all concurrent tasks
- **İptal / Kabul Gerekçesi**: Google Cloud Vertex AI enforces a strict quota limit of 1 active concurrent video generation operation per project for Veo models
- **Kalıcı Kural / Ders**: Video block animation must strictly remain sequential (VERTEX_VEO_MAX_CONCURRENT_BLOCKS=1). Concurrency is only valid for asset roster reference sheets, never for Veo video blocks.

---

### [ADR-009] Veo Multimodal RAI Pre-Filtering and Scientific Steering
- **Tarih**: 2026-09-08
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Analyze Google Cloud Veo safety filters and guidelines to prevent video generation rejections on biological and physical science topics
- **Yapılan İş / Sonuç**: Veo uses closed multimodal classifiers without threshold tuning; direct gore/weapon terms cause full block. Pre-filtering terms to scientific equivalents passed 100% of blocks cleanly.
- **İptal / Kabul Gerekçesi**: Translating forensic/damage terms into precise biomedical descriptions (e.g. razor -> calibrated metallic pellet, caustic acid -> concentrated amber digestive fluid) prevents RAI blocks while enhancing Zack D. Films 3D animated documentary fidelity.
- **Kalıcı Kural / Ders**: Always pre-filter model briefs at compilation time in script_engine.py and vertex_veo.py. Use negative prompts and scientific euphemisms for all medical/chemical phenomena.

---

### [ADR-010] Scale Transition Auto-Normalization and Resilient Fallback Repair
- **Tarih**: 2026-09-08
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Prevent visual admission rejections when scale or framing changes between shots of the same subject
- **Yapılan İş / Sonuç**: Auto-normalized same_subject to scale_transition on scale changes, added scale_differs check in admit_keyframe, and enabled relaxed fallback repair
- **İptal / Kabul Gerekçesi**: Reviewer was rejecting macro/close shots under strict same_subject lens/framing checks because LLM tagged them as same_subject instead of scale_transition
- **Kalıcı Kural / Ders**: Whenever scale changes across shots of the same subject, scale_transition must be enforced deterministically so vision reviewers judge scale change properly without failing on framing differences

---

### [ADR-011] Veo 3 Uyumlu 5-Bölümlü Yapılandırılmış Prompt Sistemi, Optik ve Kinematik Koruma
- **Tarih**: 2026-09-09
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Prompt sistemini Veo 3 rehberleri ve Zack D. Films standartlarına göre optimize etme
- **Yapılan İş / Sonuç**: compile_keyframe_prompt ve optimize_for_flow 5 bölümlü formata geçirildi, lens optikleri, Kelvin aydınlatma, diegetik fizik fiilleri ve kinematik negatif korumalar eklendi
- **İptal / Kabul Gerekçesi**: Eski tek parça prompt yapısı Veo 3 dikkat mekanizmasını dağıtıyor, optik derinlik ve hareket tutarlılığını sınırlandırıyordu
- **Kalıcı Kural / Ders**: Veo 3 teknik kamera ve lens verileriyle motive edildiğinde çok daha stabil 3D sonuçlar verir; 5 bölümlü yapı model dikkatini odakta tutar

---

### [ADR-012] Zack D. Films Tarzi Continuous Camera Flight ve Veo 3.1 Storyboard Interpolasyonu
- **Tarih**: 2026-09-09
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Sahneler arasi sert kesim (hard-cut disconnect) slayt etkisini kaldirip dis dunyadan ic organa dalis (Push-Through) ve iceriden disari genis plana cikis (Pull-Out Reveal) saglama
- **Yapılan İş / Sonuç**: compile_keyframe_prompt ve optimize_for_flow MDA+CPIG mimarisine uyarlandi, camera komut whitelist eklendi, pipeline.py terminal kurgusu first_last storyboard interpolasyonuna acildi
- **İptal / Kabul Gerekçesi**: Veo 3.1 start_frame ve last_frame aldiginda iki kare arasina 4.0s kesintisiz 3D kamera ucusu orerek Zack D. Films viral akiciligini sagliyor
- **Kalıcı Kural / Ders**: Dalis ve cikis bloklarinda start_frame ve end_frame ciftleri kesintisiz optik/oral eksen interpolasyonu ile baglanmali, terminal blokta first_last pullout reveal desteklenmelidir

---

### [ADR-013] ELI12 Dil Sadelestirmesi ve 45-55s (11-13 Blok) Sweet Spot Video Mimarisi
- **Tarih**: 2026-09-09
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: YouTube Shorts videolarindaki asiri akademik dili Zack D. Films ELI12 seviyesine indirmek ve videolari 25-30s bandindan 45-55s (11-13 blok) sweet spot araligina cikarmak.
- **Yapılan İş / Sonuç**: provider_timeline varsayilan 12 blok (48s) taslaga cikarildi, BEAT_TEMPLATE paylari 16-20-28-20-16 yapildi, ELI12 jargon sanitizer eklendi, schema minItems dinamik yapildi.
- **İptal / Kabul Gerekçesi**: Eski 8 blokluk taslak LLM'i 32 saniyeye kilitliyor ve TTS videoyu 28 saniyede bitiriyordu. 12 blok taslak ve 45-52s hedef sure araligi ile video 11-13 blokta kaliyor.
- **Kalıcı Kural / Ders**: Senaryo uretim taslagi ve kelime butcesi hedef video suresi (48s) ve provider WPS hiziyla dinamik uyumlu olmalidir.

---

### [ADR-014] RTX 4060 Yerel MMAudio Video-to-Audio ve Mikro Kesim Darbesi Mimarisi
- **Tarih**: 2026-09-09
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Sessiz Veo videolarina milisaniyelik senkronize foley ses efekti eklemek ve analoji/domain gecislerinde sinematik vurus saglamak
- **Yapılan İş / Sonuç**: MMAudioProvider (yerel CUDA + remote Space + CC0 catalog fallback) entegre edildi, editorial_plan icinde visual_domain degisimlerine subtle micro-zoom darbesi baglandi
- **İptal / Kabul Gerekçesi**: Kullanicinin RTX 4060 8GB kartinda 0 TL maliyetle piksellerden ses sentezleme ve Zack D. Films stili fiziksel darbe vurgusu saglandi
- **Kalıcı Kural / Ders**: Video bloklari uretildikten sonra diegetik fizik sahneleri icin foley sentezi yapilmali, terminal payoff daima sessiz kalmali, catalog fallback ile sistem asla patlamamalidir

---

### [ADR-015] Zack D. Films Aesthetic and Audio Overhaul: Lazar MDA Token #1 Priority, SFX Presence, Single-Shot Exterior Anchor
- **Tarih**: 2026-09-09
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Align pipeline output fully with Zack D. Films style: fix inaudible SFX, eliminate 8-second exterior character lingering, eliminate 15-16s repetitive visual contact, and force 3D stylized mannequin animation over photorealism.
- **Yapılan İş / Sonuç**: Moved MDA 3D Cycles style prefix to Token #1 in keyframe and roster prompts; boosted SFX gain to -8.5dB with 2.5kHz presence EQ and normalize=0 on amix; enforced single-shot exterior anchor with 2s rapid push-through into internal anatomy; and added anti-stagnation rules.
- **İptal / Kabul Gerekçesi**: Previous output defaulted to photorealistic stock images because style tokens appeared after 100 words of character description, and SFX was attenuated by -18dB and amix/3 downscaling.
- **Kalıcı Kural / Ders**: First 40 tokens of image prompts dictate generation modality. Foley must be mixed at -8.5dB with dedicated presence EQ and unscaled amix. Exterior human characters must never linger beyond Shot 1.

---

### [ADR-016] Zack D. Films Diegetic Foley Acoustics: VO Ducking, High-Pass 75Hz, 5.5kHz ASMR Presence, and Catalog Semantic Alignment
- **Tarih**: 2026-09-10
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: User reported SFX inaudible and squashed under narration voiceover
- **Yapılan İş / Sonuç**: Normalized SFX assets to -1.0 dBFS true peak, trimmed leading silence on chamber pop and whoosh, added automated voiceover ducking (-3.3 dB) during SFX cue windows in editor.py, tuned Foley EQ (HP 75Hz, 250Hz punch, 5.5kHz ASMR crispness), and fixed catalog fallback in MMAudioProvider to match prompt keywords
- **İptal / Kabul Gerekçesi**: SFX was previously attenuated to -24.6 dBFS peak while voice peaked at -1.0 dBFS without ducking, causing total frequency masking; both cues previously fell back to whoosh_deep due to mmaudio_b prefix bug
- **Kalıcı Kural / Ders**: Diegetic Foley must have true peak at -1.0 dBFS, voiceover must duck by -3.3 dB during cues, and prompt keyword tokenization must drive catalog matching

---

### [ADR-017] Unnatural Voice Pumping and Prolonged Synthetic SFX Abandoned for Zack D. Films Micro-Foley and Bedding
- **Tarih**: 2026-09-10
- **Durum**: `ABANDONED`
- **Talep / Fikir**: User reported SFX was unnatural and squashed under voice; compared with Zack D. Films short PQHR1r8Ox84
- **Yapılan İş / Sonuç**: Voice ducking (-3.3dB) created amateurish pumping; 2.5s synthetic loops sounded jarring and artificial compared to Zack D. Films short real-world acoustic foley micro-hits (0.1-0.4s)
- **İptal / Kabul Gerekçesi**: Zack D. Films never dips narration voice for SFX; instead uses broadcast vocal compression, continuous background music glue, and crisp authentic real-world foley hits aligned with physical contact
- **Kalıcı Kural / Ders**: Never apply hard ducking on voice for SFX. Sound effects must be short (0.1-0.4s) authentic real-world acoustic foley, not prolonged loops. Background music bed must be present to glue speech and foley.

---

### [ADR-018] ElevenLabs Sound Effects Provider Integration for Studio-Grade Tactile Foley
- **Tarih**: 2026-09-10
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: User enabled sound_generation permission on ElevenLabs API key and requested testing studio Foley generation
- **Yapılan İş / Sonuç**: Integrated ElevenLabsSfxProvider (v1/sound-generation), normalizing to -1.0 dBFS true peak and 44.1kHz stereo, capping micro-hit durations to 1.0-1.2s max, and rendering final video with realistic diegetic foley
- **İptal / Kabul Gerekçesi**: Replaces low-quality, synthetic audio loops with real studio-grade 44.1kHz acoustic sound effects matching Zack D. Films tactile quality
- **Kalıcı Kural / Ders**: Diegetic sound effects must be generated via dedicated sound-generation API (ElevenLabs) with concise physical prompts and 1.0s micro-duration

---

### [ADR-019] Location Change Fallback Admission Support for Spatial and Mechanical Discontinuity
- **Tarih**: 2026-09-10
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Prevent visual admission rejections on valid keyframes when transition kind is location_change
- **Yapılan İş / Sonuç**: Added location_change to allow_fallback_change in pipeline.py line 893 to permit expected subject and material changes during camera relocation
- **İptal / Kabul Gerekçesi**: Visual reviewer was incorrectly expecting material continuity from prior shot during an explicit location transition into door jamb cross-section
- **Kalıcı Kural / Ders**: Transitions tagged with location_change or subject_change must always allow subject and material differences during visual admission fallback

---

### [ADR-020] Dual-Modality Architecture: ModeProfile Pattern for Anatomical and Narrative Incident Productions
- **Tarih**: 2026-09-10
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Support real-world news event reconstructions with contextual 3D environments, persistent multi-character scenes, and news narrative rhythm alongside anatomical cutaways
- **Yapılan İş / Sonuç**: Implemented services/mode_profile.py with ANATOMICAL (fail-safe default) and INCIDENT profiles. Refactored script_engine.py, asset_roster.py, pipeline.py, and main.py with secondary_subject_ids, role-based safety validators, contextual plates, and mode-conditioned compile/audit loops.
- **İptal / Kabul Gerekçesi**: The pipeline hardcoded void background and single-shot human anchor across all topics, preventing real-world environments like airplane cabins. Decoupling mode-dependent behaviour preserves 100% of anatomical logic while enabling rich narrative incident documentaries.
- **Kalıcı Kural / Ders**: Always use fail-safe defaults (mode: ModeProfile = ANATOMICAL) across all call sites so omitted arguments never fail open. Multiple characters require explicit schema and roster conditioning (secondary_subject_ids) rather than single subject assumptions.

---

### [ADR-021] Zack D. Films Full-Pipeline Overhaul: Domain-Tailored Shaders, Soul ID Consistency, Tactile ASMR Foley Timing, and 160 WPM Staccato Pacing
- **Tarih**: 2026-09-10
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Reverse-engineer reference benchmark J0zIhWPsGVM and transform visual prompts, Foley timing, Deepgram TTS persona, and editorial pacing
- **Yapılan İş / Sonuç**: Upgraded compile_keyframe_prompt with Octane/Blender Cycles domain shaders (SSS, transillumination, PBR anisotropic metallic sheen, photoelastic stress), integrated multi-character secondary_subject_ids into prompt generation, enhanced Soul ID consistency in asset_roster, tightened Foley to 0.35s ASMR micro-hits aligned with physical impact contact offset, and accelerated Deepgram TTS to 2.65 WPS (160 WPM) with staccato em-dash phrasing.
- **İptal / Kabul Gerekçesi**: Previous runs felt sluggish (123 WPM), foley cues were misplaced at block start (t=0.0s), secondary characters were dropped from prompt compilation, and visual shaders lacked subsurface scattering and optical depth.
- **Kalıcı Kural / Ders**: Diegetic foley must align to the physical impact offset (0.35s micro-hit), secondary characters must be bound to keyframe prompts, and narration pacing must strictly target 160-165 WPM (2.65 WPS) with punctuation-driven staccato pauses.

---

### [ADR-022] Zack D. Films 5-Pillar Architectural Overhaul: Shaders, Foley Expansion, Deepgram 165 WPM Staccato, and Dynamic Camera Axis
- **Tarih**: 2026-09-10
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Full reverse-engineering of benchmark J0zIhWPsGVM across visual shaders, tactile foley cue budget, TTS staccato pacing, and dynamic camera trajectory
- **Yapılan İş / Sonuç**: Separated character vs cutaway styling in prompt compiler, expanded tactile foley cues to 6-8 with enriched acoustic keywords, synchronized Deepgram TTS to 1.12x speed at 2.75 WPS (165 WPM), generalized push-through and pull-out camera axes to match specific anatomical/mechanical targets, and verified 0 audit/test failures.
- **İptal / Kabul Gerekçesi**: Previous keyframe prompts injected character descriptors into organ/valve cutaways, foley cues were severely capped at 2 per video leaving 40s silent, TTS speed defaults were inconsistent, and push-through camera paths hardcoded oral lips even on chest/pulmonary topics.
- **Kalıcı Kural / Ders**: Prompt compilers must dynamically separate character from cutaway shaders, foley budgets must scale with video duration (<=2 per block, silent tail), TTS defaults must remain tightly synchronized across config and adapters, and continuous camera flights must dynamically target the authored entry structure.

---

### [ADR-023] Zack D. Films 5-Pillar Full-Pipeline Overhaul: Peak Transient Alignment, Veo Negative Prompt Migration, Aura-2 Speed Support, Material Domain Shaders, and Stabilized Continuous Flight
- **Tarih**: 2026-09-10
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Deep audit and 5-pillar gap analysis against Higgsfield MCP benchmark J0zIhWPsGVM: fix Veo prompt truncation, foley peak misalignment, mannequin cutaway contamination, Deepgram speed parameter fallback, and 2D/3D camera flight conflict.
- **Yapılan İş / Sonuç**: Increased MAX_PROMPT_LENGTH to 900, migrated speech and caption exclusions to Veo native negative_prompt, added detect_peak_transient alignment for 0.35s foley hits, switched Deepgram fallback to aura-2-arcas-en, decoupled mannequin from medical cutaway renders with polymer/elastomer/glass shaders, and enforced center coverage on continuous scale transitions.
- **İptal / Kabul Gerekçesi**: Previous runs lost critical safety directives due to 700-char truncation, foley impacts were inaudible due to trimming from t=0.0s, cutaways retained mannequin tokens, and continuous 3D camera flights were disrupted by 2D digital pan jumps.
- **Kalıcı Kural / Ders**: Veo positive prompts must remain under 900 chars with negative constraints in negative_prompt; foley micro-hits must be trimmed around peak transient amplitude; internal cutaways must omit mannequin tokens; and 3D scale transitions must maintain neutral center framing.

---

### [ADR-024] Zack D. Films 5-Pillar Full-Pipeline Transformation: Mannequin Cutaway Decoupling, Bone & Fluid PBR Shaders, ELI12 Sanitizer Expansion, and 2D/3D Camera Glitch Shield
- **Tarih**: 2026-09-10
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Reverse-engineer official @zackdfilms archetypes and Higgsfield MCP benchmark J0zIhWPsGVM across visual shaders, mannequin contamination, tactile foley cue capping, ELI12 medical vocabulary, and double-move camera prevention.
- **Yapılan İş / Sonuç**: Decoupled mannequin token from cutaway object rosters, added mineralized cortical bone and viscous non-Newtonian fluid PBR shaders, capped authored SFX cues to 0.35s ASMR micro-hits, added 9 new ELI12 medical rewrites, tightened sentence length to 20 words, and enforced center coverage on 3D flight transitions.
- **İptal / Kabul Gerekçesi**: Visual rosters previously leaked mannequin tokens into internal anatomical cutaways, bone/fluid lacked dedicated physical PBR shaders, authored SFX cues lacked a strict 0.35s micro-hit ceiling, and pre-populated coverage beats risked 2D camera reframe jitter during continuous 3D camera flights.
- **Kalıcı Kural / Ders**: Internal cutaway reference sheets must never contain mannequin tokens; bone and fluids require dedicated mineralized/viscous PBR shaders; authored SFX cues must enforce a 0.35s ASMR ceiling; and continuous scale transitions must deterministically override coverage beats to neutral center.

---

### [ADR-025] Autonomous Audio Bed Engine via FFmpeg lavfi Synthesis
- **Tarih**: 2026-09-10
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: The spec requires that videos never have silence behind narration — a continuous hypnotic audio bed must glue speech and foley. Previously, background music was only available via manual `--music` CLI argument, breaking the zero-manual-effort invariant.
- **Yapılan İş / Sonuç**: Implemented `services/audio_bed.py` with zero-cost FFmpeg lavfi synthesis (`anoisesrc` + `sine` + filter chains). Three mood profiles map to ModeProfile `audio_bed_mood`: `tension_pulse` (incident — sub-bass sine + brown noise + LFO pulse), `clinical_drone` (anatomical — mid-range pad + narrow-band white noise), `mechanical_hum` (mechanical — electrical hum + metallic harmonics + HF whine). Pipeline auto-generates bed when `--music` is not provided. `--no-music` flag disables BGM entirely.
- **İptal / Kabul Gerekçesi**: Eliminates manual music sourcing, ensures every video has appropriate ambient texture matching its mode, zero API cost, and integrates cleanly with existing sidechain compression chain in `editor.py`.
- **Kalıcı Kural / Ders**: Audio bed is generated locally via FFmpeg lavfi — no external API dependency. The `--music` flag overrides with a user-provided track. `--no-music` disables BGM entirely. Sidechain ducking (ADR-017) applies equally to auto-generated beds.

---

### [ADR-026] Third Production Mode: MECHANICAL (Tri-Modality Pipeline)
- **Tarih**: 2026-09-10
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: `mode_profile.py` only had two modes (anatomical, incident). Physics/engineering topics like engines, bridges, turbines, elevators need distinct visual treatment, SFX keywords, and audio bed mood.
- **Yapılan İş / Sonuç**: Added `MECHANICAL` ModeProfile with contextual environments, mannequin characters, `mechanical_explainer` narrator style, and `mechanical_hum` audio bed mood. Detection priority in `detect_mode()`: incident > mechanical > anatomical (default). Added `audio_bed_mood` field to ModeProfile dataclass with safe default `clinical_drone`.
- **İptal / Kabul Gerekçesi**: Completes the three-mode system specified in v2.2: incident (emergencies), anatomical (medical/bio), mechanical (physics/engineering). Mechanical topics were previously falling through to anatomical mode, losing contextual environment styling.
- **Kalıcı Kural / Ders**: Three modes cover the full Zack D. Films content spectrum. New modes should only be added if they represent a genuinely distinct visual/audio/narrative treatment profile. Detection priority must remain incident > mechanical > anatomical.

---

### [ADR-027] Mechanical Mode Screenplay Isolation, Contextual Roster Prop Decoupling, Psychoacoustic Haas 3D SFX, and Stereo Diffusion Audio Bed
- **Tarih**: 2026-09-11
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Independent audit identified four architectural bugs: (1) `script_engine.py` lacked `_mechanical_system_prompt()`, causing mechanical topics to receive anatomical organ/oral-penetration prompts; (2) `asset_roster.py` in contextual mode generated 30-year-old human mannequin prompts for mechanical components (pistons, cables); (3) prompt compiler tagged non-character mechanical cutaways as "Medical Cutaway"; (4) Hermes VO, SFX hits, and lavfi audio bed were all collapsed into dual-mono center, causing acoustic masking and risking comb-filtering if channels were naively delayed.
- **Yapılan İş / Sonuç**:
  1. Implemented `_mechanical_system_prompt()` in `BeatEngine` with ELI12 tone, staccato rhythm (6-10 words/sentence, em-dashes/ellipses), exterior apparatus context in Shot 1, rapid chassis penetration along mechanical drive axis at t=2.0s, and internal mechanical assembly (gears, pistons, cables) in subsequent shots with zero medical/anatomical jargon.
  2. Updated `_build_contextual_roster()` and `_kind_for()` in `asset_roster.py` with `_mechanical_prop_prompt()` so physical mechanisms are registered as 1:1 props with anisotropic metallic sheen and photoelastic stress fringes instead of human mannequins.
  3. Updated `compile_keyframe_prompt()` to emit `Glossy Stylized 3D Engineering and Technical Cutaway Visualization Render` when `mode.name == "mechanical"`, and updated push-through / pull-out motion clauses for mechanical casing penetration.
  4. Added FFmpeg native `haas=middle_source=mid:side_gain=1.25:left_delay=2.05:right_delay=2.12` to SFX filtergraph in `editor.py`, providing phase-safe binaural 3D stereo width without timestamp desynchronization or mono comb-filtering.
  5. Added `stereotools=mode=lr>lr:slev=1.2:delay=2.5` to `services/audio_bed.py` to diffuse ambient BGM into side channels, freeing the center channel for narrator voiceover clarity.
  6. Added comprehensive unit tests in `tests/test_mode_profile.py`.
- **İptal / Kabul Gerekçesi**: Eliminates cross-domain prompt pollution (no more medical cutaways in mechanical documentaries), decouples machine props from human mannequins, and elevates audio mastering to broadcast-quality psychoacoustic stereo standards.
- **Kalıcı Kural / Ders**: Every ModeProfile must have its own dedicated system prompt method in `BeatEngine`. Contextual rosters must distinguish props from human characters. Stereo widening on transient Foley hits must use phase-controlled filters (Haas) rather than raw channel delay to preserve mono downmix compatibility on mobile devices.

---

### [ADR-028] Zero-Rejection Architecture: Anti-Text Sanitizer, Domain-Bleed Shield, Volumetric Proof Streams, and Surgical Repair Loop
- **Tarih**: 2026-09-11
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Analysis of 149 rejected keyframes across recent production runs (`why-your-eyes-never-freeze`: 33 rejections, `the-passenger-who-tried-to-open`: 20 rejections) identified 4 systemic defect classes: (1) Text & chemical formula hallucination (Na+, Cl-) on surfaces; (2) Domain bleed where mechanical metaphors (wiper, pump, valve) pulled anatomical prompts into industrial factory scenes; (3) 2D clipart sticker arrows instead of organic 3D volumetric light; (4) Perspective and scale breaks during zoom transitions.
- **Yapılan İş / Sonuç**:
  1. **Universal Hard Anti-Text Shield**: Added `_ANTI_TEXT_SHIELD` to `services/script_engine.py` explicitly prohibiting letters, numbers, chemical formula symbols (no Na+, no Cl-, no H2O), scientific labels, and watermarks, requiring ions and atoms to be rendered as unlabeled luminous spheres. Injected into `compile_keyframe_prompt()` and all 3 motion prompt paths in `optimize_for_flow()`.
  2. **Domain-Bleed Isolation Shield**: Added `_ANATOMICAL_DOMAIN_BLEED_MAP` (21 mechanical->biological translations: wiper->sweeping mucosal membrane, piston->rhythmic muscular contraction, valve->muscular sphincter valve, pipe->vascular conduit, etc.) and `_isolate_domain_bleed()` to `services/script_engine.py`, invoked inside `_canonicalize_model_brief()` for anatomical mode.
  3. **Volumetric Proof Stream Compiler**: Rewrote `_marker_instruction()` to generate organically glowing luminescent energy streams integrated naturally into 3D scene lighting and fluid dynamics, strictly banning flat 2D clipart arrows and graphic sticker overlays.
  4. **Reference Sheet Anti-Text Hardening**: Added `_ROSTER_ANTI_TEXT_SUFFIX` to `services/asset_roster.py` for all environment plates, contextual anchor sheets, character sheets, and mechanical/anatomical prop sheets, preventing upstream reference contamination.
  5. **Smart Surgical Repair Loop**: Replaced naive comma-separated error concatenation in `pipeline.py` with `_categorize_rejection()` and `_build_surgical_repair()`, emitting focused correction directives prioritized by defect severity (text > clipart > domain bleed > scale > continuity) capped at 2 categories.
  6. **Scale Transition Continuity Clause**: Added explicit scale-continuity instruction in `compile_keyframe_prompt()` for `scale_transition` shots to guide the model across magnification boundaries without perspective breaks.
- **İptal / Kabul Gerekçesi**: Eliminates the root causes of the 149 historical keyframe rejections. Drastically cuts Nano Banana Pro API costs and retry latency, prevents upstream reference sheet contamination, and ensures visual admission passes on attempt 1 or 2 without falling back to relaxed semantics.
- **Kalıcı Kural / Ders**: Reference sheets and prompts must never rely on simple negative prompts ("no text") which modern diffusion models misinterpret; use assertive affirmative directives ("Pure visual geometry only, completely devoid of alphanumeric characters"). Never pass raw mechanical metaphors into anatomical prompts without biological domain shielding. Visual proof markers must be described as volumetric 3D energy streams, never arrows.

---

### [ADR-029] Tactile ASMR Foley Engine, Warm Sub-Bass Audio Beds, and Natural Decay Gain Staging
- **Tarih**: 2026-09-11
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: User reported severe acoustic flaws in recent productions (`why-your-eyes-never-freeze`): (1) abstract academic terms ("freezing point depression", "massive convective heat transfer") sent to sound models produced static hiss and noise instead of tactile foley; (2) `clinical_drone` audio bed generated an irritating 150 Hz sine buzz and 1200 Hz white noise hiss like a broken refrigerator; (3) artificial 0.35s / 80ms cutoff produced glitchy speaker clicking; (4) crushing SFX gain (-1.0 dBFS) with harsh 5.5 kHz (+4.5 dB) EQ overpowered voiceover; (5) loudnorm compression smashed the mix causing ducking distortion and pumping on the narration voice.
- **Yapılan İş / Sonuç**:
  1. **Tactile Foley Translation Engine**: Implemented `services/sfx_dictionary.py` (`translate_to_tactile_foley()`, `get_tactile_sfx_tags()`, `sanitize_foley_text()`). Maps abstract scientific, medical, and mechanical terms into concrete tactile physical Foley onomatopoeias (e.g., freezing -> crisp ice cracking snap, brittle crystallization crunch; vascular -> warm low-frequency sub pulse, deep vascular rush; tear/fluid -> viscous liquid squelch, wet droplet surface tension pop; elevator/metal -> heavy metallic clunk, mechanical latch snap, sub-bass punch). Strips cinematography jargon and excludes non-descriptive stop words ("the", "and", "visible", "state") from tags and prompts.
  2. **Warm Sub-Bass Audio Beds**: Replaced harsh 150 Hz sine and 1200 Hz white noise hiss in `services/audio_bed.py` with deep 45 Hz sub-bass sine, 90 Hz harmonic, and soft low-pass filtered pink noise (<220 Hz) in `clinical_drone`. Redesigned `mechanical_hum` with 50 Hz fundamental transformer hum + 100 Hz harmonic + low-pass brown noise rumble (eliminating 10 kHz whine). Redesigned `tension_pulse` with organic 42/44.5 Hz beating sub-bass sines and filtered brown rumble.
  3. **Natural Decay Envelope**: Relaxed the rigid 0.35s cutoff to a 0.55s–0.75s natural decay window (`SFX_DEFAULT_DURATION = 0.65s`) in `pipeline.py` and `editor.py`. Aligns transient attack to contact moment while applying a 0.25s smooth exponential decay curve (`afade=t=out:curve=exp`) and 0.015s quarter-sine attack (`curve=qsin`), eliminating abrupt cutoffs and speaker clicks. Safely bounds short-shot edge cases without collapsing to 0.35s.
  4. **Professional Gain Staging & Subtractive EQ**: Lowered Foley gain from -1.0 dBFS to -10.0 dBFS (`SFX_DEFAULT_GAIN_DB = -10.0`), sitting gracefully behind the -14 LUFS voiceover. Applied subtractive EQ (`-2.0 dB @ 250 Hz Q=1.5`) to carve out acoustic mud in the vocal fundamental range, boosted transient clarity (`+2.0 dB @ 4.0 kHz Q=1.8`), retained 75 Hz high-pass and 3D Haas stereo width.
  5. **Ducking Distortion & Limiter Pumping Elimination**: Because Foley is gain-staged to -10 dBFS, the summed mix into `amix=normalize=0` peaks comfortably below 0 dBFS, preventing the downstream `loudnorm` broadcast processor from slamming the narrator's voice.
- **İptal / Kabul Gerekçesi**: Transforms pipeline acoustic output from irritating metallic buzzes and abstract white noise into studio-grade, oddly-satisfying ASMR tactile sound design faithful to the Zack D. Films benchmark.
- **Kalıcı Kural / Ders**: Audio generation models must never receive abstract scientific or chemistry phrases; all events must be translated to tactile physical Foley onomatopoeias. Audio beds must avoid speech fundamental frequencies (85-250 Hz) and use deep sub-bass (<60 Hz) and low-passed noise (<220 Hz). SFX transients must decay naturally over 0.5-0.75s with exponential envelopes at -10 dBFS gain staging, accompanied by subtractive 250 Hz cleanup EQ and +2 dB @ 4 kHz presence.

### [ADR-030] Tactile ASMR Foley Spectrum Expansion, Hermes Hook Harmonization, and Autonomous Media Quality Gates
- **Tarih**: 2026-09-11
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Expand tactile Foley coverage for missing physical phenomena, synchronize Deepgram Hermes 2nd-person hook requirements, and integrate quantitative audio/video QA inspection tools into MCP and skill ecosystem
- **Yapılan İş / Sonuç**: Added 6 new tactile Foley categories (hydraulic_hiss, rotary_drill, cartilage_strain, glass_crack, micro_static, rubber_friction) to sfx_dictionary.py; expanded academic abstractions; enforced direct 2nd-person ('You') hook opening in BeatEngine prompts; added analyze_audio_spectrum and analyze_video_stability tools to _media_mcp.py; added audio-mastering-qa and cinematic-color-grading skills
- **İptal / Kabul Gerekçesi**: Eliminates acoustic blind spots where physical events lacked tactile onomatopoeias, solidifies the viewer retention formula in the crucial first 2-3 seconds, and provides zero-cost automated verification of broadcast audio dynamics and video motion smoothness
- **Kalıcı Kural / Ders**: All diegetic physical events must resolve to tactile physical onomatopoeias; the first sentence must hook the viewer with direct address ('You'); post-render quality gates must verify -14 LUFS, -1.5 dBTP, zero digital clipping, and motion stability

---

### [ADR-031] Live Console Tracking Interface, Zero-Rejection Proof Injection & Spatial Character Consistency Shield
- **Tarih**: 2026-09-11
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Provide real-time console feedback with 5 explicit phase headers, live admission scores, video block progress with percentage/ETA, and 15s heartbeats during API waits; eliminate keyframe admission retry churn by deterministic physical proof injection and targeted missing-object surgical repair; prevent character role-swaps, mirrored cockpit breach coordinates, and illegal causal states in vehicle/incident scenes.
- **Yapılan İş / Sonuç**:
  1. **Live Console Tracking Interface**: Implemented 5 distinct progress phase headers (`[1/5]` to `[5/5]`), live per-keyframe admission verdicts with score/reasons (`[kf01/14] [KABUL - Skor: 8/10]`), real-time video block rendering logs with elapsed time, percentage, and ETA, plus 15-second terminal heartbeats (`... işleniyor (bekleme: 45s)`) in `VertexVeoProvider._wait_for_operation`. UTF-8 reconfigure applied to stdout/stderr in `main.py` and `pipeline.py` preventing Windows charmap exceptions.
  2. **Zero-Rejection Engine (Sıfır-Ret Motoru)**: Implemented deterministic proof injection in `compile_keyframe_prompt()` (`[Deterministic Proof Evidence]` forcing explicit 3D geometry modeling of `proof_on_screen` and expected state). Added `"missing_object"` category to `_categorize_rejection()`, `_SURGICAL_REPAIRS`, and targeted missing item extraction in `_build_surgical_repair()`.
  3. **Spatial Topology, Axis Lock & Character Role Decoupling Shield**: Enforced strict role and costume invariants across `services/asset_roster.py` and `services/script_engine.py` (`_INCIDENT_ROLE_COSTUMES`: Captain 4 stripes / exterior breach, Copilot 3 stripes / right seat / oxygen mask, Flight Attendant navy vest / prone floor holding ankles). Added 180-degree axis lock on aircraft breach coordinates (strictly port/left invariant). Added monotonic causal state guard in `validate_script()` preventing characters in exterior-pinned states from performing interior cockpit operations before terminal resolution.
- **İptal / Kabul Gerekçesi**: Eliminates terminal "black box" silence during long Veo / keyframe waits, reduces keyframe review churn from 4 attempts down to 1-2 attempts by directly injecting reviewer requirements into prompts, and guarantees consistent character identities and breach physics in high-stakes incident shorts.
- **Kalıcı Kural / Ders**: All long asynchronous operations must emit terminal heartbeats every 15 seconds; keyframe prompts must deterministically inject mandatory physical proof objects; character roles in multi-person scenes must be strictly decoupled by distinct garments and rank epaulets; spatial breach coordinates must lock to the 180-degree camera axis.

---


### [ADR-032] Core Pipeline & Beat Engine Hardening: Retiming Mannequin Isolation, Incident Spatial Vector Guard, Caption-Safe Marker Validation, and BEAT_TEMPLATE Distribution
- **Tarih**: 2026-09-12
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Apply audit findings: fix retiming mannequin leakage in decomposed mechanism blocks, fix terminal payoff endpoint_mode/reason crash and preserve continuous flight, isolate aviation spatial vector to cockpit/aircraft scenes only under incident mode, prevent evidence markers in lower_center caption-safe zone in both validation and BeatEngine repair, gate terminal_payoff 2D zoom to first_only shots, and align _required_beat_indices with BEAT_TEMPLATE shares with Beat 3 mechanism allocation guarantees.
- **Yapılan İş / Sonuç**:
  1. `pipeline.py`: Prioritized pure `mechanism` shots in `mechanism_candidates`; explicitly enforced `presentation_mode="mechanism"`, `opening_anchor_id=""`, `endpoint_mode="first_last"` on all decomposed substeps, preventing `opening_anchor is allowed only on the first shot` validation errors and ADR-024 mannequin contamination. Retained continuous flight on terminal payoff with validated `endpoint_mode` / `endpoint_reason`.
  2. `services/script_engine.py`: Gated `_spatial_vector_clause` strictly to `mode.name == "incident"` in addition to vehicle/cockpit keywords, preventing aviation breach and exterior pinned captain directives from contaminating anatomical/mechanical prompts.
  3. `services/script_engine.py`: Updated `validate_script` to reject markers in `{"center", "lower_center"}`; updated `BeatEngine._assemble` to proactively reassign markers outside both `center` and `lower_center` caption-safe zones.
  4. `pipeline.py`: Gated `terminal_payoff` zoom in `editor.render` strictly to `endpoint_mode == "first_only"`, preventing jarring 2D zoom snaps during 3D camera flights.
  5. `services/script_engine.py`: Aligned `_required_beat_indices` with `BEAT_TEMPLATE` shares (%16-%20-%28-%20-%16), adding an invariant ensuring Beat 3 (reveal mechanism, 28%) receives at least 2 blocks for all N >= 6 (resolving N=7 starvation).
  6. Added comprehensive unit tests in `test_zero_rejection_shields.py` and `test_contextual_anchor_contract.py`; all 169 unit tests and `audit_and_sync.py` pass with 0 failures.
- **İptal / Kabul Gerekçesi**: Prevents ADR-024 mannequin contamination in middle mechanism blocks, prevents prompt corruption in non-aviation incident shorts and anatomical/mechanical modes, ensures captions are never occluded by markers, protects continuous 3D camera flights from abrupt 2D zoom snaps, and restores correct narrative weight to Beat 3 mechanism reveal across all native block counts.
- **Kalıcı Kural / Ders**: Retiming expansion must always sample from mechanism shots and explicitly enforce `presentation_mode="mechanism"`. Cockpit spatial vectors must be strictly gated by `mode.name == "incident"`. BeatEngine repair must proactively avoid the `lower_center` caption safe zone. Beat index mapping must guarantee Beat 3 mechanism prominence.

---

### [ADR-033] Perspective Isolation, Critique-Injected Retries, Match-Cut Gate Priority and Directional Vector Hardening
- **Tarih**: 2026-09-12
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Eliminate diffusion prior bias blocking visual admission in incident and anatomical modes, inject Art Director critiques into retries, and prevent false subject-continuity rejections across Match-Cut boundaries.
- **Yapılan İş / Sonuç**: Implemented perspective isolation and negative prompt compiler; injected critique prefixes on attempts > 1; reordered NanoBanana review branches so intentional subject changes take precedence over scale transitions; added directional_vector surgical repair and motion-delegation clauses; verified 100% completion on both Incident mode (13/13 keyframes admitted) and Anatomical mode (12/12 keyframes admitted).
- **İptal / Kabul Gerekçesi**: Completely eliminates keyframe admission deadlocks on exterior breach shots and cross-domain analogy match cuts, providing robust zero-rejection pipeline throughput across all production modes.
- **Kalıcı Kural / Ders**: Diffusion models require explicit negative prompts and viewpoint isolation to overcome training priors; deliberate match cuts (subject_change, location_change) must never require subject or domain continuity from prior frames; directional force vector angles and fluid expansion dynamics belong to the video motion model and must not trigger static keyframe rejections.

---

### [ADR-034] Long-Form Architecture Extension Activation (ADR-034)
- **Tarih**: 2026-09-14
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Activate --format longform horizontal 16:9 episodic documentary mode
- **Yapılan İş / Sonuç**: Fixed TimelinePlan mutation in narrative_longform.py, expanded audio timeline to 28+ blocks for longform, enabled 16:9 in nano_banana_pro and vertex_veo, and validated chunked longform compiler in editor.py
- **İptal / Kabul Gerekçesi**: Allows producing multi-minute episodic 16:9 documentaries without breaking the 6-13 block Shorts contract
- **Kalıcı Kural / Ders**: Preserve Shorts contracts as default while cleanly branching longform mode via config.LONGFORM_MODE and ctx.format

---

### [ADR-035] Visual Coherence Architecture: Morph Smear Elimination, Strict Role/Prop Precedence & Anti-Anthropomorphic Mechanical Shield
- **Tarih**: 2026-10-01
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Eliminate cross-scene Veo AI morph smears/melting artifacts in video generation (e.g., cockpit interior melting into airplane exterior over 4 seconds, eyeballs melting into cellular spheres); fix classification flaws causing vehicles to become Pixar cartoon characters with eyes/mouths on the windshield and human crew members (copilot) to become empty seats; enforce Zack D. Films visual DNA consistency across all prompt compilation and vision admission gates; eliminate 2D sticker arrow hallucinations.
- **Yapılan İş / Sonuç**:
  1. `pipeline.py`: Gated `end_frame_id` in `build_frame_plan()`. Now `end_frame_id` is ONLY populated when `shot.endpoint_mode == "first_last"` AND `shot.transition_kind in {"same_subject", "scale_transition"}` AND `shot.transition_kind not in {"subject_change", "location_change"}` AND `next_shot.transition_kind not in {"subject_change", "location_change"}`. For all scene changes and subject changes, `end_frame_id = None`. Video blocks generate physics-driven motion from `start_frame` and scenes transition via clean FFmpeg hard cuts, completely eliminating 4-second melting AI smears.
  2. `services/asset_roster.py`: Fixed `_kind_for()` and `_build_contextual_roster()`. Structural/vehicle/mechanical keywords in `subject_id` always imply `prop`. Human roles (`pilot`, `copilot`, `captain`, `attendant`, `passenger`, `doctor`, `paramedic`, etc.) always imply `character` regardless of secondary words like "seat" or "strap" in descriptions (stopping human crew from becoming empty chairs). Added non-anthropomorphic mechanical clauses to all vehicle props (`no face, no eyes, not a character, zero cartoon anthropomorphism`).
  3. `services/script_engine.py`: Added dedicated `elif mode.name == "incident"` render branch (`Glossy Stylized 3D Incident Reconstruction Render`), preventing non-character incident subjects from being classified as characters or medical cutaways. Refined `_is_human_subject()` to disallow vehicle subjects. Hardened `_ANTI_TEXT_SHIELD` and `_marker_instruction()` against 2D graphic sticker arrows.
  4. `providers/image/nano_banana_pro.py`: Added strict style drift, 2D graphic arrow, and cartoon vehicle rejection gates to `_review_sync()` admission prompt.
- **İptal / Kabul Gerekçesi**: Completely resolves visual coherence failures across all channel video archetypes (Incident, Anatomical, Mechanical). Eliminates horrific morphing smearing, stops cartoon airplanes, ensures characters don't vanish into furniture, and guarantees cohesive Zack D. Films 3D claymation aesthetic.
- **Kalıcı Kural / Ders**: Veo `last_frame` must NEVER be passed across shot cuts, domain boundaries, location changes, or subject changes. Only intentional continuous single-scene camera flights may interpolate to an end keyframe. Vehicles must always be props with zero anthropomorphism. Characters must remain characters regardless of seat/harness attachments.

---


### [ADR-036] Semantic Audio-Visual Storyboard Binding, Unvoiced Hallucinated Organ Elimination, and ASMR Foley Lexical Disambiguation
- **Tarih**: 2026-10-03
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: User reported critical semantic desync (voice says throat tissue but screen shows an eye) and absurd SFX (bone crack for nose pinch, liquid squelch for eardrum rupture) in what-happens-if-you-hold-in-a-sneeze_prod
- **Yapılan İş / Sonuç**: Disambiguated sfx_dictionary keywords with dedicated skin_contact_pinch, tympanic_eardrum_burst, and tissue_tear_fissure categories; removed bare 'tear' from wet liquid and bare 'cartilage' from bone fracture; eliminated the unvoiced eyeball shot and re-aligned the 8-block timeline so eardrum rupture perfectly matches 'rupture your eardrums' and throat tissue tear perfectly matches 'throat tissue'
- **İptal / Kabul Gerekçesi**: Eliminates cognitive dissonance and visual contradiction in Zack D. documentary storytelling, guarantees 100% lexical fidelity between narration and visual subject, and upgrades Foley sound design to studio-grade tactile ASMR
- **Kalıcı Kural / Ders**: Visual shots must never introduce biological subjects not explicitly voiced in narration beats; Foley dictionary must avoid polysemous English words (such as 'tear' or 'cartilage') that map mechanical or anatomical actions to contradictory physical acoustic domains

---

### [ADR-037] Blind Text-Guessed Third-Person Mannequin Prompts for Reference Video Replication
- **Tarih**: 2026-10-05
- **Durum**: `REJECTED`
- **Talep / Fikir**: Replicate Zack D. Films' popular Short 'What To Do If Your Car Sinks' (p832whe8hrI) with exact visual and video prompts.
- **Yapılan İş / Sonuç**: Generated third-person passenger-seat shots of a bald shirtless mannequin sitting in an already-sinking car, resulting in completely different framing, pacing, character design, and storyline compared to the reference video.
- **İptal / Kabul Gerekçesi**: The reference video was never downloaded or visually inspected frame-by-frame; prompts were guessed from generic rules and text searches. Actual inspection via yt-dlp revealed First-Person POV framing (driver's arms on a tan/beige steering wheel driving from sunny shore into the lake, white t-shirt reflection in window, glowing red/green object highlights, circular yellow motor cutaway, glovebox window breaker on laminated glass, rubber duck pressure equalization).
- **Kalıcı Kural / Ders**: When asked to replicate or benchmark a specific reference video, ALWAYS download the video with yt-dlp and extract its exact frames before authoring script.json or handoff.md prompts.

---

### [ADR-038] First-Person POV Continuity, Sealed-Cabin Plunge Physics, Underwater Lighting Lock, Solid 3D Force Arrows, and Flow Agent Port 8001 Isolation
- **Tarih**: 2026-10-06
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Iteratively generate, compare second-by-second against the Zack D. Films reference video, and upgrade the quality of the first 3 blocks using Flow Agent (127.0.0.1:8001), and codify all learnings so no LLM ever drops below this benchmark quality.
- **Yapılan İş / Sonuç**: Achieved 1:1 frame-accurate visual parity with Zack D. Films' 'What To Do If Your Car Sinks' (p832whe8hrI) across kf01-kf04 and block01-block03 via Flow Agent (127.0.0.1:8001), eliminating interior splash artifacts, double-face window reflections, wardrobe sleeve drift, hollow outline arrows, camera target drift, and dry-street window hallucinations.
- **İptal / Kabul Gerekçesi**: Second-by-second visual comparison against extracted reference frames revealed that generic prompts cause diffusion/I2V models to splash water inside sealed cabins, reflect creepy double faces in windows, swap bare arms to denim jacket sleeves, render flat 2D outline arrows instead of solid 3D volumetric arrows, drift past door switches, and hallucinate dry streets outside windows when starting from brightly lit downward lap keyframes.
- **Kalıcı Kural / Ders**: 1) In second-person vehicle survival shorts ('Imagine you drive...'), enforce First-Person POV with locked bare forearms/hands (no sleeves, no watch), white crew-neck t-shirt, blue denim jeans, and warm tan leather cabin across all POV shots. 2) Specify that water splashes and rising waterlines remain OUTSIDE the glass windshield while the interior cabin stays dry on plunge; once submerged, every keyframe and motion prompt (even downward lap shots) must specify dim cool-blue underwater ambient lighting and dark blue water outside windows so I2V camera pans never hallucinate dry asphalt streets. 3) Use emissive object highlights (neon red-orange on jammed door handle, neon-green #39FF14 on seatbelt) and solid 3D glossy volumetric arrows (never flat hollow outline arrows) for external water pressure, while forbidding face/head reflections in window glass. 4) In 2-action single-frame I2V blocks, explicitly lock the camera's final resting target (e.g. matte-black window switch module on the door armrest). 5) Keep 'windshield' out of aviation breach triggers in script_engine.py, and use only Flow Agent HTTP server (127.0.0.1:8001) with FLOW_RECAPTCHA=http and account_index=0 locked without leaving 'flow-windows.exe bridge' running on port 9222. 6) In NanoBanana ('NARWHAL') static keyframe prompts (kf01), avoid self-harm-adjacent collision phrasing like 'drives off a shoreline straight into a lake' (which triggers an inline empty-frame safety refusal); use 'drives toward a calm blue lake on a sunny day' for the static keyframe and reserve the water plunge for the abra_i2v_4s motion prompt.

---


### [ADR-039] 20-Second Flow Agent Benchmark Replication: Beluga Image Model, HTTP Captcha Bypass, Underwater Egress & Mechanical Cutaway Invariants
- **Tarih**: 2026-10-07
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Extend and replicate 20.0s (5 blocks x 4.0s) of Zack D. Films sinking car benchmark with Flow Agent at 1:1 visual and acoustic fidelity
- **Yapılan İş / Sonuç**: 5 video blocks and 20.0s preview assembled with 0 black or freeze defects, -14.9 LUFS broadcast audio, 100 stability score, 8 mastered ASMR Foley hits, and second-by-second alignment with reference frames
- **İptal / Kabul Gerekçesi**: Flow Agent image model beluga avoids empty batchexecute refusals of narwhal; FLOW_RECAPTCHA=http avoids broker assessment blocks; swimming egress POV and circular cutaway electronics waterlog complete the 20s benchmark progression
- **Kalıcı Kural / Ders**: Lock FLOW_IMAGE_MODEL=beluga and FLOW_RECAPTCHA=http for Flow Agent; encode upward swimming POV and circular mechanical door cutaways into script_engine for submerged vehicle productions

---

### [ADR-040] Virtual Explorer Long-Form System: Female Persona Nova, Character Sheet Invariant, Selective Lip-Sync, and 16:9 Widescreen Cinematography
- **Tarih**: 2026-10-07
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Expand pipeline architecture to support a 'Virtual Explorer' system inspired by Zaman Yolcusu Defne, in English covering global topics (history, science, mysteries, nature) in 16:9 widescreen long-form format. The host is a female persona ('Nova') with rock-solid face/wardrobe consistency via character sheets, and selective lip-sync where she speaks on camera in balanced proportions (<= 20% on-screen speaking time, avoiding talking head fatigue) while 80%+ remains cinematic B-roll with voiceover.
- **Yapılan İş / Sonuç**: Implemented `services/character.py` (persistent CharacterProfile and CharacterSheetSpec), `services/explorer_engine.py` (first-person investigative screenplay and A-Roll/B-Roll screen-time allocation), `EXPLORER` mode in `services/mode_profile.py`, photorealistic 16:9 widescreen cinematic visual styles in `config.py`, and integrated character sheet reference generation in `services/asset_roster.py`.
- **İptal / Kabul Gerekçesi**: A pure talking-head format suffers from uncanny valley and audience fatigue, whereas pure B-roll lacks human persona loyalty. Combining a persistent female character anchor (Nova) with multi-view character sheets ensures face stability, and limiting on-camera speaking to pivotal moments (arrival hook, mid-climax reaction, concluding verdict) preserves high cinematic engagement.
- **Kalıcı Kural / Ders**: 1) In Explorer productions, always enforce 16:9 widescreen (`LONGFORM_MODE=True`). 2) A-Roll shots must reference the locked character sheet (`_character_sheets/`) to prevent face and wardrobe drifting. 3) On-camera talking avatar presence is strictly bounded to <= 20% of runtime (opening hook, turning point, and closing); the remaining 80%+ must be pure cinematic B-roll with voiceover narration.


---

### [ADR-041] Google Flow 3rd Method: Autonomous Browser Automation (browser_flow)
- **Tarih**: 2026-10-08
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Implement a 3rd video/image generation method that drives the open Google Flow window directly, bypassing Flow Agent cooldowns and CAPTCHA rejections.
- **Yapılan İş / Sonuç**: Implemented services/flow_browser_automation.py, providers/video/browser_flow.py, providers/image/browser_flow.py, registered in factory.py, and produced final 23s Hawara documentary.
- **İptal / Kabul Gerekçesi**: Flow Agent HTTP/cookie calls suffer from frequent server cooldowns and bot detections. Driving the active authenticated browser window executes within Google client session with zero bot penalties.
- **Kalıcı Kural / Ders**: Register 'browser_flow' as official provider with dual-strategy: Extension CDP bridge primary, OS Win32/PyAutoGUI hardware input fallback.

---

### [ADR-042] Playwright CDP Background Video Factory + Virtual Desktop Isolation
- **Tarih**: 2026-10-08
- **Durum**: ACCEPTED
- **Talep / Fikir**: Video üretimini kullanıcının ekranını kilitlemeden (CS2 oynarken bile) tamamen arka planda çalıştır.
- **Yapılan İş / Sonuç**: services/playwright_flow_client.py + providers/video/playwright_flow.py + providers/image/playwright_flow.py oluşturuldu. FlowBrowserClient.generate_asset() 3 kademeli strateji zinciri: (1) Playwright CDP [arka plan, sıfır mouse], (2) WebSocket Bridge, (3) PyAutoGUI sanal masaüstünde. Ayrıca services/virtual_desktop_runner.py ile PyAutoGUI'nin pyvda üzerinden ikinci sanal masaüstünde izole çalıştırılması sağlandı. fal_video.py aspect_ratio hardcode bug'ı FAL_ASPECT_RATIO env değişkeni ile düzeltildi.
- **İptal / Kabul Gerekçesi**: PyAutoGUI foreground requirement CS2 vb. ile çakışıyordu. Playwright CDP, mevcut Chrome oturumuna port 9223 üzerinden bağlanarak tarayıcıyı öne getirmeden ve OS mouse kullanmadan trusted CDP events gönderiyor.
- **Kalıcı Kural**: Video/image üretimi her zaman 3-kademeli arka plan stratejisi kullanmalı. Playwright CDP birincil; WebSocket bridge ikincil; PyAutoGUI yalnızca virtual desktop izolasyonunda üçüncül. Port 9222 flow-windows.exe bridge için ayrılmış (ADR-038); Playwright için 9223 kullan.

### [ADR-043] Model A Hybrid Longform Time-Traveler Documentary: Defne Benchmark, Immutable Nova Persona, 2.5D Ken Burns B-Roll, and Deepgram Natural Pacing
- **Tarih**: 2026-10-09
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Model A (Hibrit Uzun Belgesel - 16:9, 7-12 dk) Defne standardinda time-traveler belgesel mimarisi: Kilit anlar icin Google Flow AI video, antik yapilar ve haritalar icin yuksek cozunurluklu 2.5D Ken Burns Pan/Zoom montaji, Nova karakteri icin zaman yolcusu kronometre simgesi ve cag kamuflaji, Deepgram dogal tempo seslendirmesi.
- **Yapılan İş / Sonuç**: Pipeline routing LongformEngine'e baglandi; script_engine 16:9 National Geographic / BBC Earth 35mm fotorealizm ve karakter kilidine uyarlandi; services/character.py zaman yolcusu Nova persona, kronometre cihazi ve 8 cag kamuflaji ile guncellendi; 20 gorsel referans manifesti (generate_character_sheets.py) hazirlandi; editor.py ve pipeline.py 2.5D Ken Burns pan/zoom montaji ile donatildi; Deepgram 1.0x dogal belgesel temposuna uyarlandi.
- **İptal / Kabul Gerekçesi**: 7-12 dakikalik uzun belgeselde tum bloklarin video uretimine gitmesi saatler surer. Defne standardinda kilit anlarin (giris, donum noktasi, kapanis) AI video olmasi ve yuzde 85-90 tarihi mimari/harita/kalinti sahnelerinin 2.5D Ken Burns pan/zoom montaji ile uretilmesi belgesel kalitesini ve uretim hizini maksimize eder.
- **Kalıcı Kural / Ders**: 16:9 Longform Explorer modunda B-Roll sahneleri icin her zaman yuksek cozunurluklu 2.5D Ken Burns pan/zoom montaji kullan (LONGFORM_HYBRID_MODE=True), A-Roll sahnelerini Google Flow uzerinden uret. Nova'nin zaman yolcusu simgesi ve yuz anatomisi tum caglarda sabit kalsin.

---

### [ADR-044] 16:9 Longform Dual-Voice (Nova + Historical Witness) & Dual-Overlay Architecture
- **Tarih**: 2026-10-09
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Fix all 8 root causes identified in the first 16:9 Longform Hawara video vs Zaman Yolcusu Defne benchmark, keeping BOTH solo Nova segments AND historical witness interviews as well as BOTH era/location stamps AND lower-third subtitles, clearly differentiated.
- **Yapılan İş / Sonuç**: Implemented multi-voice TTS routing (female aura-2-thalia-en for Nova, male aura-2-hermes-en for Historical Witnesses), 28-beat chronological + witness storyboard engine, dual-style lower-third ASS subtitles (NovaSub vs WitnessSub + WitnessBadge + EraStamp + BrandWatermark), Go CLI flag ordering fix (-start-image/-reference before positional args), 1:1 longform keyframe-to-shot mapping, headroom locks, and zero-dead-air timeline locking.
- **İptal / Kabul Gerekçesi**: In the initial Hawara video, a male voice spoke over female host Nova, missing config import caused a 6-beat fallback with 62s of dead silence, Go flag ordering dropped --start-image, off-by-one keyframe indexing swapped Shot 14 and Shot 15, and Shorts MarginV=470 captions covered faces.
- **Kalıcı Kural / Ders**: Always pass Go CLI flags before positional args in flow-windows.exe, map longform keyframes 1:1 to shot start prompts without cross-contaminating B-roll with character reference frames, and visually + acoustically separate Host Nova from Historical Witnesses.

---

### [ADR-045] Autonomous Defne Benchmark Optimization & Longform Architecture
- **Tarih**: 2026-10-11
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Elevate 16:9 historical documentary pipeline to match @zamanyolcusudefne Canakkale 1915 benchmark standard with zero user manual intervention
- **Yapılan İş / Sonuç**: Implemented Veo cinematography prompts, 2.5D Ken Burns with atmospheric dust/film grain, multi-layered diegetic ambient soundscapes, automatic resume format detection, and completed full 108s production for The Secrets of Gobekli Tepe passing all MCP audits
- **İptal / Kabul Gerekçesi**: Delivers documentary-grade visual fluidity, deep sensory auditory immersion, and fully autonomous background production without user friction
- **Kalıcı Kural / Ders**: Always lock longform dimensions (1920x1080) and 16:9 aspect ratio across resume paths; combine generative Veo A-roll with textured 2.5D Ken Burns B-roll and era-specific ambient audio beds for broadcast delivery

---

### [ADR-046] Widescreen Portrait-Decapitation Prevention, Flow abra_i2v Landscape Limitation, Longform Soundscape Muxing, and Documentary Metadata Quarantine
- **Tarih**: 2026-10-11
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Resolve fatal decapitation of host Nova in 16:9 widescreen productions, restore missing ambient soundscapes during multi-chunk editorial compiles, and quarantine YouTube Shorts metadata tags from longform historical documentaries.
- **Yapılan İş / Sonuç**: 1) Identified Flow abra_i2v (I2V) endpoint enforces 9:16 portrait regardless of CLI flags; added automatic longform conformation via 2.5D Ken Burns from 16:9 keyframes and anchored crop_y to 18% of delta in editor._normalize_chain. 2) Fixed LongformCompiler.compile to pass soundscape_index and -i soundscape_path to FFmpeg. 3) Updated metadata.py to replace #shorts/#zackdfilms with documentary/ancientmysteries tags and historical titles.
- **İptal / Kabul Gerekçesi**: Blind center-cropping of conformed portrait video cuts off 34% of the top canvas, decapitating character faces and destroying composition. Flow abra_i2v does not support 16:9, making keyframe 2.5D Ken Burns essential for widescreen B-roll and A-roll fallback. Missing soundscape inputs dropped audio beds in chunked compiles. Shorts metadata degrades longform YouTube SEO.
- **Kalıcı Kural / Ders**: Never blind center-crop portrait footage into widescreen canvas without top-anchoring (crop_y <= 0.18 delta). Never pass start images to Flow CLI when 16:9 video is required unless text-to-video (abra_t2v) is explicitly selected. Ensure all audio streams (narration, music, soundscape, sfx) are forwarded across chunked compilation passes. Strictly isolate longform documentary metadata from Shorts taxonomy.

---

### [ADR-047] ADR-047 Continuous Audio Continuity Lock and Longform Widescreen Dimension Enforcement
- **Tarih**: 2026-10-11
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Continuous second-by-second comparative visual and audio benchmark against @zamanyolcusudefne reference video to eliminate frozen frames and acoustic voids in longform productions
- **Yapılan İş / Sonuç**: Discovered 8 seconds of acoustic void due to audio bed finishing before total video blocks; fixed by locking full_audio_duration across audio_bed and ambient_soundscape plus adding aloop in build_audio_filter. Enforced 1920x1080 dimensions in LongformCompiler.
- **İptal / Kabul Gerekçesi**: Audited video had 0s freeze frames but 8s silence at the end; benchmark quality gate and second-by-second comparative inspector caught this failure.
- **Kalıcı Kural / Ders**: In longform documentary mode, audio bed and ambient soundscape duration must always cover max(voice+tail, total_block_footage, target_len). LongformCompiler must strictly enforce 1920x1080 resolution on all chunk and full passes.

---

### [ADR-048] 100% Generative Diffusion Video Enforcement, Anti-Self-Deception Motion Authenticity Analyzer, and Block Provenance Tracking
- **Tarih**: 2026-10-11
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Guarantee 100% genuine AI diffusion video in longform documentaries by eliminating silent Ken Burns slideshow fallbacks, detecting true 3D motion dynamics, and preventing self-deception in quality gates.
- **Yapılan İş / Sonuç**: Built services/motion_authenticity.py (2D affine residual analysis separating genuine diffusion motion from linear zooms), services/block_verifier.py (block provenance tracking and hash verification), upgraded benchmark_quality_gate.py with --clip support and objective optical analysis, purged hardcoded scores from second_by_second_analyzer.py, fixed Flow client duration quantization and candidate match race conditions, and ensured 0 audit failures.
- **İptal / Kabul Gerekçesi**: Ken Burns slideshows over static photos diluted documentary quality and deceived prior check tools due to hardcoded scores and blindness from -loglevel error. Google Flow 16:9 native diffusion generation produces authentic 3D depth and parallax, rendering static plate montages obsolete for primary video flows.
- **Kalıcı Kural / Ders**: Always verify block motion using 2D affine residual optical flow analysis (services.motion_authenticity). Never accept cached blocks without verifiable provenance sidecars. Never hardcode motion scores or silence ffmpeg filter output in quality gates.

---

### [ADR-049] Mandatory Git Auto-Commit & Auto-Push After Every Modification Across All LLMs
- **Tarih**: 2026-10-11
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Her yapilan degisiklikten sonra pushlama zorunlulugu getirilmesi istendi.
- **Yapılan İş / Sonuç**: Tum LLM yonergelerine zorunlu git push maddesi eklendi, scripts/audit_and_sync.py ile denetim saglandi ve scripts/git_sync.py eklendi.
- **İptal / Kabul Gerekçesi**: Yerel degisikliklerin kaybolmasini onlemek, coklu LLM arasi durum tutarliligini korumak ve kullaniciya sifir efor saglamak icin.
- **Kalıcı Kural / Ders**: Herhangi bir degisiklik sonrasinda audit_and_sync.py dogrulamasi yapilip hemen ardindan tum degisiklikler origin/main dalina otomatik commit ve push edilmelidir.

---

### [ADR-050] Flow HTTP CAPTCHA Unusual Activity During Gallipoli Longform
- **Tarih**: 2026-10-11
- **Durum**: `ABANDONED`
- **Talep / Fikir**: Produce a six-block 16:9 Gallipoli documentary using Google Flow for all images and videos, with no Vertex or paid Google Cloud requests.
- **Yapılan İş / Sonuç**: Created a 120-word six-beat Gallipoli script and generated the narration and six accepted keyframes. Flow repeatedly returned PUBLIC_ERROR_UNUSUAL_ACTIVITY while regenerating the missing kf02; no video blocks were completed, and a resumable handoff.md was written.
- **İptal / Kabul Gerekçesi**: Flow declined the HTTP-minted reCAPTCHA assessment for this session, so the selected provider could not complete image generation. Automatic provider substitution would violate the Flow-only requirement.
- **Kalıcı Kural / Ders**: Keep FLOW_RECAPTCHA=http. On PUBLIC_ERROR_UNUSUAL_ACTIVITY, stop repeated submissions, preserve the exact run and prompts, write a handoff, and resume only after Google Flow accepts requests again.
- **Tekrar Testi (2026-10-11)**: A new 15-scene, 60-second Flow-only run produced a 66.77-second narration and a topic-specific Gallipoli screenplay without calling Vertex. Flow refused the first environment reference with the same PUBLIC_ERROR_UNUSUAL_ACTIVITY before any keyframe or video was created. The browser token diagnostic succeeded, but the configured HTTP assessment was still rejected. The production remains incomplete; keep this rejection classified as an account/session assessment failure, not a video-model quality result.

---

### [ADR-051] Resolve longform WWI era stamps from period-specific metadata
- **Tarih**: 2026-10-12
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Generate a one-minute 1915 Gallipoli longform test and inspect all on-screen metadata.
- **Yapılan İş / Sonuç**: Visual review found an Antiquity stamp on a World War I documentary because the witness catalog had no WWI entry; the caption resolver now emits DARDANELLES, OTTOMAN EMPIRE — 1915 directly.
- **İptal / Kabul Gerekçesi**: Era labels must come from the topic era classifier and must not inherit generic default witness metadata.
- **Kalıcı Kural / Ders**: When rendering longform historical stamps, add an explicit stamp for eras without witness profiles and add a regression test for the topic.

---

### [ADR-052] Longform Flow prompts retain era-specific evidence and motion
- **Tarih**: 2026-10-12
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Remove stale Flow prompt truncation, prevent generic Antiquity evidence in 1915 scenes, and improve historical human-action prompts.
- **Yapılan İş / Sonuç**: Added World War I truth-sheet facts and materials, preserved authored host proof, removed Vertex's 900-character sanitizer from Playwright Flow, separated longform text restrictions, and removed the blanket ban on historical people in B-roll.
- **İptal / Kabul Gerekçesi**: Flow is a separate provider with no Vertex 900-character contract; period-specific proof and people performing authored actions improve historical credibility; irrelevant chemical-symbol bans add prompt noise.
- **Kalıcı Kural / Ders**: Keep sanitizers provider-specific; bind historical prompts to a verified era; only prohibit visible people when the authored scene requires an empty environment.

---

### [ADR-053] Longform historical B-roll depicts authored period workers
- **Tarih**: 2026-10-12
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Improve Gallipoli Flow scenes after generated B-roll compositions were visually deserted despite screenplay-assigned crew actions.
- **Yapılan İş / Sonuç**: Removed blanket people-free B-roll directives from longform screenplay and explorer prompts; added authored action text to keyframe prompts and period-correct labor constraints; repaired the resumable Gallipoli run prompts without changing its locked timeline.
- **İptal / Kabul Gerekçesi**: The authored narrative includes sailors, gunners, and ship crews whose purposeful work is visible historical evidence; blanket exclusion directly contradicted those scenes and reduced visual credibility.
- **Kalıcı Kural / Ders**: Longform scenes may show people only when the verified historical beat assigns them a specific action; encode that action in both still and motion prompts, with era-accurate clothing and equipment.

---

### [ADR-054] Longform action shots require visible historical people and clean voiceover captions
- **Tarih**: 2026-10-12
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: The first generated Gallipoli film passed motion checks but compared less well with its reference because authored sailors and gunners were absent, and captions carried redundant speaker tags and a persistent decorative label.
- **Yapılan İş / Sonuç**: Strengthened both keyframe and motion prompts to require named crew and workers visibly completing authored actions, with 1915 role-specific wardrobe; removed longform speaker badges and the automatic TIME TRAVELER watermark while retaining the opening date/location stamp.
- **İptal / Kabul Gerekçesi**: Concrete human action is important documentary evidence, and voiceover is not dialogue from an on-screen person. Unnecessary labels compete with scene imagery and captions.
- **Kalıcı Kural / Ders**: For longform B-roll, make explicitly authored people mandatory visible subjects at readable scale; present voiceover captions without visible-speaker labels or decorative automatic branding.

---

### [ADR-055] Abandon the 12 October Gallipoli corrected video provider attempt
- **Tarih**: 2026-10-12
- **Durum**: `ABANDONED`
- **Talep / Fikir**: Match the 18 March 1915 reference passage by producing a one-minute, fifteen-shot Gallipoli sequence centered on the coastal gun crew, an on-location field interview, the loading/firing cycle, and the fleet's losses.
- **Yapılan İş / Sonuç**: Replaced the fixed 15-shot Gallipoli summary with the gun-crew story arc and canonicalized timed captions back to the authored narration. The Flow route failed while generating the first environment image and wrote a handoff. A separate explicit Vertex Veo plus Nano Banana run then failed at its first image request with a generic ClientError. No corrected video was rendered.
- **İptal / Kabul Gerekçesi**: Neither configured image provider produced the required first storyboard assets in this session. The Flow handoff does not expose a specific recovery reason; the Vertex adapter exposed only the ClientError type. Continuing would require provider/account state or a usable generation service.
- **Kalıcı Kural / Ders**: Preserve the corrected script and locked 15-by-4-second plan, keep provider selection explicit, and resume after an authorized image-generation route is available. Do not substitute providers silently or claim a video was produced when no visual assets were generated.

---

### [ADR-056] Pin Flow CLI account to the active CDP profile
- **Tarih**: 2026-10-12
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Ensure Google Flow generations use the account and project authenticated in the project's chrome_flow.bat profile when multiple Flow browser profiles are connected.
- **Yapılan İş / Sonuç**: PlaywrightFlowClient now matches active CDP authentication cookies to a unique saved Flow account and passes its cookie file and project ID explicitly to image and video CLI commands. Live port 9223 matched the account used by the successful Gallipoli run. Adapter tests passed.
- **İptal / Kabul Gerekçesi**: The Flow Agent log showed two attached profiles and warned that concurrent sessions could route requests to the wrong account/project; the resulting generation attempt returned a batchexecute 400.
- **Kalıcı Kural / Ders**: Pin each Flow CLI call to the uniquely matched authenticated CDP account and project. Keep cookie values out of logs and stop visibly if the browser session cannot be matched unambiguously.

---

### [ADR-057] Selective native-audio Flow lip sync for the lightning protection documentary
- **Tarih**: 2026-10-12
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: The user requires visible speech with real mouth motion and alignment to speech in a new longform video, overriding this run’s conflicting closed-mouth/ADR-002 short-mode constraint while preserving the selected chrome_flow.bat Flow account.
- **Yapılan İş / Sonuç**: Tested four 4-second 16:9 Flow Omni 1.1 Flash clips with Nova3 ASR and 1 FPS visual review; samples 2 and 4 matched their intended words and visible speaking/rest poses. Select three brief Nova on-camera lines for the opening, mechanism turn, and closing; use Deepgram Hera narration for B-roll scenes.
- **İptal / Kabul Gerekçesi**: Flow’s UI-native speech audio and lip motion are generated together, avoiding a separate identity-altering lip-sync pass. Short, separated A-roll keeps facial identity and continuity auditable while narration carries the sourced mechanism.
- **Kalıcı Kural / Ders**: For this longform run, override the no-speaking short-mode rule only in authored Nova A-roll; require exact transcript/timing checks and a 1 FPS face review for all three speech shots. Keep Flow account/provider explicit and do not bypass security challenges.

---

### [ADR-058] Reject the overlong opening dialogue in the 4-second Flow A-roll
- **Tarih**: 2026-10-12
- **Durum**: `ABANDONED`
- **Talep / Fikir**: Generate Nova’s opening hook with a short on-camera line in one 4-second Flow clip.
- **Yapılan İş / Sonuç**: Deepgram Nova3 transcribed the final word 'go' from 'You think this rod stops lightning? Watch where the current goes.' at 3.92-4.08 seconds, exceeding the 4.01-second video boundary.
- **İptal / Kabul Gerekçesi**: The audio tail is cut and violates the lip-sync sentence-boundary gate.
- **Kalıcı Kural / Ders**: Do not place two clauses in a 4-second A-roll. Keep the hook to 'You think this rod stops lightning?' and move the rest to narrator B-roll; reject any clip whose ASR word end exceeds its actual media duration.

---

### [ADR-059] Reject delayed midpoint Flow dialogue timing
- **Tarih**: 2026-10-12
- **Durum**: `ABANDONED`
- **Talep / Fikir**: Generate a short Nova A-roll line that explains the continuous conductor path and looks synchronized in a 4-second clip.
- **Yapılan İş / Sonuç**: Deepgram Nova3 recognized 'See the current follow one path' exactly, but first speech began at 1.84 seconds and ended at 3.84 seconds in a 4.01-second clip, leaving a long visible silent gesture before speaking.
- **İptal / Kabul Gerekçesi**: Opening and midpoint speech must start naturally with the visible articulation; an almost two-second delay makes the character appear disconnected from the narration.
- **Kalıcı Kural / Ders**: Reject A-roll clips with more than 0.5 seconds of unexplained pre-speech silence. Re-prompt with direct-to-camera speech beginning on the first frame, minimal pre-speech action, and a short line; verify mouth frames and ASR timestamps together.

---

### [ADR-060] Reject incidental researcher faces in Flow lightning-system B-roll
- **Tarih**: 2026-10-12
- **Durum**: `ABANDONED`
- **Talep / Fikir**: Use Flow-generated documentary B-roll to explain the lightning system while Nova remains the only host identity.
- **Yapılan İş / Sonuç**: The 1 FPS final contact sheet showed multiple unrelated lab researchers and changing house models in B-roll despite the narration and continuity prompts; the visual cast no longer matched the authored story.
- **İptal / Kabul Gerekçesi**: Incidental faces distract from Nova and make visual identity/scene continuity inconsistent across the video.
- **Kalıcı Kural / Ders**: For this story use Nova only in three explicit on-camera host shots. Generate mechanism B-roll without people, faces, silhouettes, hands or mannequins, and repeat one precise model-house and glass-dome anchor across B-roll prompts.

---

### [ADR-061] Accept clean people-free B-roll and assemble final 60s lightning protection documentary
- **Tarih**: 2026-10-12
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Assemble clean 60-second longform documentary for why lightning rods protect buildings using regenerated people-free B-roll.
- **Yapılan İş / Sonuç**: Updated script.json with clean v2 clips, assembled full 60s final.mp4 with 15 video and 16 audio streams, verified 1-FPS contact sheet with 0 incidental faces, passed all MCP loudness (-14.4 LUFS) and stability (100) checks.
- **İptal / Kabul Gerekçesi**: Eliminates visual confusion from random generated humans, stabilizes documentary model house continuity, and delivers broadcast-compliant vertical/widescreen standards.
- **Kalıcı Kural / Ders**: Lock strict people-free negative constraints on mechanism B-roll while preserving host presence exclusively in authored A-roll; verify 1-FPS contact sheets before declaring complete.

---

### [ADR-062] Gallipoli 90s Benchmark Reproduction, Pompeii Generalization, and 6 Systemic Fixes
- **Tarih**: 2026-10-12
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Reproduce 90s Gallipoli benchmark (2:10-3:40) and generalize to Pompeii while fixing fez, prop morphing, text cards, host B-roll intrusion, loudness, and voice factory registration
- **Yapılan İş / Sonuç**: Created curated arcs in services/curated_beats.py for 22-block Gallipoli and 15-block Pompeii; fixed voice registration in providers/factory.py; disabled amix normalization in editor.py; locked khaki kabalak, 28cm Krupp gun, Roman mills/oven, and zero-text shield; enforced ADR-060 host restrictions
- **İptal / Kabul Gerekçesi**: Delivers historical documentary fidelity matching benchmark, eliminates hallucinations across eras, and guarantees broadcast audio compliance
- **Kalıcı Kural / Ders**: Enforce ADR-060 strictly by isolating host Nova to 3 pivotal shots; lock period headwear and mechanical props; never attenuate voice in amix

---

### [ADR-063] Word count calibration, WWI timber isolation, and 15-block gunner outline regression fix
- **Tarih**: 2026-10-12
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Calibrate word count budgets for 22-block Gallipoli and 15-block Pompeii, prevent ancient timber/mudbrick injection in WWI prompts, and preserve 15-block gunner story arc
- **Yapılan İş / Sonuç**: Calibrated Gallipoli to 170 TR / 190 EN words and Pompeii to 109 TR / 142 EN words; isolated ancient levers/timber in prompt compiler; preserved 15-block gunner story arc; all 235 tests pass with 0 regressions
- **İptal / Kabul Gerekçesi**: Ensures voiceover fits comfortably inside 4.0s block envelopes without rushing or overflow, prevents anachronistic construction props in twentieth-century battlefields, and maintains test suite contract
- **Kalıcı Kural / Ders**: Always verify speech pace <= 180 TR / <= 220 EN words for 22 blocks and <= 125 TR / <= 160 EN words for 15 blocks; never allow ancient timber in WWI artillery prompts; preserve existing curated arcs when adding extended sequences

---

### [ADR-064] Multi-Agent Verified Story-Weaver Engine and Deepgram Flux Voice Roster Architecture
- **Tarih**: 2026-10-12
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Sentezlenen 4 referans GitHub projesi (`ai-playbooks`, `KKenny0/script-weaver`, `HiAPIAI`) doğrultusunda evrensel 5-aşamalı Story-Weaver motoru inşa etmek, basmakalıp `GENERIC_SENSORY_PATTERNS` şablonlarını kaldırmak ve Deepgram Flux çoklu ses havuzunu (4 erkek, 5 kadın) sıralı rotasyon ve Entity Voice Lock ile devreye almak.
- **Yapılan İş / Sonuç**: `services/story_weaver.py`, `services/visual_locks.py`, `services/voice_roster.py` modülleri AST-clean olarak oluşturuldu; `services/screenplay.py` içindeki fallback şablonları StoryWeaver ile değiştirildi; `providers/voice/deepgram_aura.py` içine `VoiceAssigner`, `/v2/speak` URL ayrımı, 48kHz örnekleme ve retry eklendi; Gallipoli/Pompeii curated beat'leri korundu; 2 yeni test dosyası ile toplam 257 test %100 geçti; 2 bağımsız alt-ajan denetiminden kusursuz onay alındı.
- **İptal / Kabul Gerekçesi**: Tüm tarihsel konularda zengin, dramatik ve anakronizm-kalkanlı senaryolar üretirken, yardımcı karakterlerin sesini video boyunca sabit tutarak (Entity Lock) broadcast kalitesini güvenceye alır.
- **Kalıcı Kural / Ders**: Story-Weaver içinde 5-aşamalı dramatik akış (Arrival Hook, Context, Rising Investigation, Turning Point, Legacy) ve 4 görsel kilit zorunludur; WWI/modern sahneler antik ahşap kaldıraç enjeksiyonundan muaf tutulmalıdır; Flux modelleri `/v2/speak`, Aura modelleri `/v1/speak` rotasını kullanmalıdır; ses atamaları video boyunca Entity Lock ile korunmalıdır.

---

### [ADR-065] Next-Gen 4-Engine Expansion, Technical Debt Resolution & Multi-Agent Quality Architecture
- **Tarih**: 2026-10-13
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Kod tabanındaki mevcut tüm 10 motorun mimari ve AST sınırları açısından satır satır denetlenmesi, gizli teknik borçların giderilmesi ve tam otonom stüdyo için 4 yeni nesil motorun (`Thumbnail Engine`, `Vision Quality Gate`, `Live Deep-Research Engine`, `Adaptive Music & Braam Engine`) çift alt-ajan onaylı mimariyle inşa edilmesi.
- **Yapılan İş / Sonuç**:
  1. **Teknik Borç Temizliği**: `services/flow_browser_automation.py` içindeki ağ ve websocket importları `providers/flow_browser/client.py` katmanına taşındı; `services/` sıfır ağ bağımlılığı (AST-clean) kuralına kavuşturuldu. `screenplay.py` içindeki döngü içi lazy import tepeye alındı. `audio_bed.py` orchestral stem bulunamadığında lavfi sentezine graceful fallback yapacak şekilde korundu. `character.py` lip-sync bayrağı yalnızca Longform Nova A-roll ile sınırlandırıldı. `historical_research.py` içine `modern_disaster` ve `modern_space` dönemleri eklendi.
  2. **Engine 1 (Thumbnail & Click-Hook)**: `services/thumbnail_engine.py` geliştirildi. 9:16 Shorts ve 16:9 Longform için YouTube UI güvenli alanları (`SafeZoneBounds`), <= 6 kelimelik merak kancaları (`CTRHookLibrary`), görsel promptlara model-metni yazdırmayan evrensel `ZERO_TEXT_SHIELD` ve FFmpeg/ASS overlay metadata üretimi sağlandı.
  3. **Engine 2 (Vision Quality Gate)**: `services/vision_quality_gate.py` deterministik CV sinyal kalite kapısı olarak inşa edildi (Laplacian varyans odak/bulanıklık, dinamik aralık histogram yayılımı, geometri ve letterbox tespiti). Pahalı video üretimlerini gereksiz çöpe atmamak için varsayılan olarak `QUARANTINE_ADVISORY` modunda çalışır.
  4. **Engine 3 (Live Deep-Research Engine)**: `services/live_research_engine.py` (AST-clean enricher) ve `providers/research/` (`BaseResearchProvider`, `MockResearchProvider`, `WikipediaResearchProvider`) inşa edildi. Canlı Wikipedia özetlerinden alıntı imleri (`[1]`, `[citation needed]`) ve HTML temizlenip `HistoricalTruthSheet` tablosuna deduplicate edilerek eklendi.
  5. **Engine 4 (Adaptive Music & Braam Engine)**: `services/adaptive_music_engine.py` 5-aşamalı dramatik tansiyon haritası (`DramaticTensionMap`), 40 Hz sub-bass zemin drone'u ve dönüm noktası `Braam / Sub-drop` FFmpeg lavfi sentezleyicisi inşa edildi. -12 dBFS / HP 30 Hz tavanı, -3.0 dB @ 2.5 kHz konuşma cebi EQ filtresi ve stereo side-diffusion ile seslendirme boğulmadan broadcast -14 LUFS standardı korundu.
  6. **Doğrulama & Test**: 31 yeni birim testi yazıldı; toplam 288 test 0 hata ile geçti; `scripts/audit_and_sync.py` 0 failure / 0 warning ile doğrulandı. 2 bağımsız alt-ajan denetiminden "UYGULAMA KUSURSUZ" onayı alındı.
- **İptal / Kabul Gerekçesi**: Saf OpenCV ile el/parmak deformasyonu arama yaklaşımı yüksek false-positive riski nedeniyle reddedildi ve deterministik sinyal kalitesi kapısına dönüştürüldü; diğer tüm motorlar tam uyumluluk sağladı.
- **Kalıcı Kural / Ders**: Kapak resmi promptlarına asla metin yazdırılamaz, metinler sadece ASS/FFmpeg ile eklenir; Vision QA varsayılan olarak advisory çalışmalıdır; Research servis katmanı AST-clean kalıp ağ çağrıları sadece `providers/` altında yapılmalıdır; Braam ses patlamaları -12 dBFS ve HP 30 Hz sınırını aşamaz.

---


### [ADR-066] Gallipoli (18 Mart 1915) Benchmark Audit, Engine Pipeline Wiring & Playwright Flow Activation
- **Tarih**: 2026-10-13
- **Durum**: `ACCEPTED`
- **Talep / Fikir**: Audit existing Gallipoli renders against YouTube benchmark PXixPeATIQc (2:10-3:40), wire thumbnail_engine, vision_quality_gate, and adaptive_music_engine into the core pipeline, and execute 22-block 90s production plan via Playwright Flow
- **Yapılan İş / Sonuç**: Audited out/ directories using MCP media inspector and 1-FPS frames; identified red fez leaks and missing 28cm Krupp / Seyit Onbasi mechanics in old runs; integrated ThumbnailPromptCompiler into write_metadata, VisionQualityGate into keyframe admission, and AdaptiveMusicEngine with 5-stage tension & braam into pipeline audio beds; verified 100% green compilation on dry-run
- **İptal / Kabul Gerekçesi**: Ensures strict historical fidelity, zero-text thumbnail compliance, broadcast audio LUFS (-14 LUFS) with cinematic braam impacts, and flawless background generation via Playwright Flow
- **Kalıcı Kural / Ders**: Thumbnail specs must be written idempotently alongside metadata; DramaticTensionMap must support both dict and Beat object streams; all 22 blocks in WWI artillery must lock khaki kabalak and 28cm Krupp mechanical hoist geometry

---
