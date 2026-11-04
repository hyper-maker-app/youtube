# MASTER UYGULAMA PLANI
## Holistic Screenplay Reviewer ve Full-Video Multimodal QA

**Kaynak:** Antigravity chat `356a1e91-ae76-4e35-964e-8482592f7ba2`, teknik spesifikasyon v4.2.0 ve Grok Imagine Cinematic Studio.
**Kapsam:** Yalnızca uygulama planı. Kod uygulaması bu dosyanın kapsamında değildir.

## 1. Değerlendirme ve Kritik İyileştirmeler

Kaynak plan; CLI sözleşmeleri, holistic screenplay gate, Phase 2.5 video QA, seçici block yeniden üretimi, FFmpeg splice, artifact raporları ve test başlıkları bakımından güçlü bir teknik omurga sunuyor. Production-ready kabul edilmesi için şu boşluklar kapatılmalıdır: secret rotation/redaction, canonical state machine, strict QA JSON sözleşmesi, evidence/provenance, threshold kalibrasyonu, splice doğrulaması, insan onayı, idempotency, crash recovery ve gerçek medya testleri.

## 2. Değişmez İlkeler

- Eksik, çelişkili veya düşük güvenli analiz `PASS` olamaz; sonuç `INCOMPLETE` veya `NEEDS_REVIEW` olur.
- Model önerir, deterministic policy ve insan onayı yayın kararını verir.
- Her bulgu zaman kodu, frame/clip/audio kanıtı, source hash ve confidence ile izlenir.
- Yama en küçük etkili değişiklik olmalı; orijinal render salt-okunur tutulmalı ve her patch geri alınabilir olmalıdır.
- Fiziksel render, fallback ve `--force-render` bütçe ve yetki kapısından geçmelidir.
- Secret, cookie, Authorization header, signed URL veya kişisel veri log/artifact içine yazılmaz.

## 3. Faz 0: Güvenlik ve Baseline

Önce kaynak chat/log kayıtlarında görünür olmuş tüm API anahtarları, tokenlar ve cookie/session değerleri iptal edilmeli veya rotate edilmelidir. `.env`, transcript, log ve artifact yazıcılarına redaction eklenmeli; redaction unit test ile doğrulanmalıdır.

Aynı fazda mevcut test baseline alınır, etkilenecek dosyalar ve çağrı zinciri envanterlenir, model/CDP/Flow/FFmpeg/audio/subtitle capability matrix doğrulanır ve açık kararlar kayda alınır.

Zorunlu kararlar: `--force-render` yetkisi, raw video mu hibrit örnekleme mi kullanılacağı, codec uyumsuzluğunda politika, insan onaysız patch kapsamı ve evidence retention süresi.

## 4. Canonical Yaşam Döngüsü

Tek state machine kullanılmalıdır:

`PREFLIGHT -> BIBLE_LOCKED -> SCREENPLAY_AUTHORED -> PREGEN_LINTED -> SCREENPLAY_REVIEWED -> SCREENPLAY_CERTIFIED -> PLAN_ONLY_EXIT veya AUDIO_SYNTHESIZED -> VIDEO_RENDERED -> BOUNDARY_QA_COMPLETE -> VIDEO_QA_COMPLETE -> PATCHING -> REGRESSION_VERIFIED -> MASTER_ASSEMBLED -> DELIVERY_SEALED`

Her state için input/output artifact, legal next state, retryable error sınıfı, timeout, bütçe, idempotency key ve audit event tanımlanır. `--plan-only` ve `--dry-run` fiziksel üretime girmeyen terminal dallardır; zero-spend testleri zorunludur.

## 5. Faz 1: Holistic Screenplay Reviewer

CLI sözleşmesi korunur: `--screenplay-mode holistic|strict-checklist`, `--video-qa/--no-video-qa`, `--video-qa-model`, `--max-patch-passes`. `ProductionPipelineConfig` immutable olmalı; CLI parsing engine yürütmesinden ayrılmalıdır.

Holistic rubric dört 25 puanlık sütunu korur: narrative escalation & pacing, micro-survival verisimilitude, cinematic visual prompt ergonomics ve hard invariants. Ağırlık toplamı testle 100 olarak garanti edilir.

Dual-judge sonucunda yalnızca `min(Grok, Gemini)` tutulmamalı; model skorları, confidence/uncertainty, çelişki durumu, rubric/prompt sürümü, kritik defect listesi ve ham yanıt hash’i de saklanmalıdır. Çelişkili veya düşük güvenli sonuç `NEEDS_REVIEW` üretir.

Screenplay healer en fazla dört tur çalışır. Her tur scene ID, before/after diff, yeni kusur ve maliyetle kaydedilir. Deterministic linter hard invariant’ların son otoritesidir. Sert invariant ihlali doğrudan bloklanır; score `< 90` ise açık ve denetimli override olmadan render başlamaz.

## 6. Faz 2: Shot Sözleşmesi ve Handoff

Her scene/block için beklenen durum sözleşmesi üretilir: narration, visual/motion prompt, micro-math, duration, camera, lighting, continuity dependencies, audio cues, kabul ölçütleri ve kritik defect sınıfları.

`handoff.json` içinde schema version, run/correlation ID, project ID, input/source hash, scene/block hash, model/tool sürümleri, prompt/rubric/threshold sürümleri, spend estimate, approval state, artifact links, patch budget ve provenance zorunludur. Handoff atomic yazılır; eksik veya yarım dosya geçerli sayılmaz.

## 7. Faz 3: Render ve Boundary QA

TTS/SFX ve video render idempotent işler olmalıdır. Her block için hash, duration, codec, resolution, FPS, time base, audio stream, PTS/DTS ve üretim parametreleri kaydedilir.

Boundary QA yalnızca ilk/son kareyi değil, geçiş çevresindeki frame window’u ve audio PTS sürekliliğini inceler. Bozuk stream, siyah/donmuş kare, invalid timestamp, eksik ses veya beklenmeyen duration farkı `INCOMPLETE` ya da `BLOCKED` üretir.

## 8. Faz 4: Full-Video Multimodal QA

Hibrit inceleme uygulanır: deterministic teknik tarama; başlangıç, boundary, climax ve şüpheli segmentlerden görsel örnekleme; motion/temporal bağlam gerektiğinde kısa ham klip. Her evidence block ID, timecode, frame index ve source hash ile eşleşir.

Model çıktısı strict JSON schema ile parse edilir: `schema_version`, `block_id`, `verdict`, `overall_score`, `confidence`, `defects`, `evidence`, `expected_vs_observed`, `recommended_patch`, `review_required`. Geçersiz veya eksik JSON hiçbir koşulda `PASS` olamaz.

Kusur sınıfları en az şunları kapsar: `CRITICAL_MORPH`, `LIMB_OR_FACE_DISTORTION`, `CAMERA_STALL`, `TEMPORAL_STUTTER`, `FRAME_DROP`, `UNREADABLE_ARTIFACT`, `VISUAL_CONTINUITY`, `AUDIO_SYNC`, `AUDIO_CLIPPING`, `SUBTITLE_DRIFT`, `TECHNICAL_MEDIA_FAILURE`.

Block `< 85` veya kritik defect `FLAGGED`; düşük confidence ya da judge çelişkisi `NEEDS_REVIEW`; tüm teknik ve multimodal kontroller temizse `PASSED` olur. Eşikler golden set ile kalibre edilmeden production policy olarak kilitlenmemelidir.

## 9. Faz 5: Cerrahi Patch Engine

Her patch; patch ID, parent render hash, target block/time range, korunacak invariantlar, corrective prompt diff, model/tool sürümü, beklenen yan etkiler, bütçe, reviewer requirement ve rollback pointer taşır.

Yalnızca kusurlu block yeniden üretilir. Başarısız veya eksik block splice edilemez. Patch sonucu orijinalden ayrı immutable artifact olarak saklanır.

Splice öncesi codec, resolution, FPS, time base ve audio layout uyumu; sonrası PTS/DTS, duration, video/audio/subtitle continuity, output hash, media probe, boundary karşılaştırması ve hedef dışı block korunumu doğrulanır. “Lossless” yalnızca ölçülmüş uyumlu koşullarda kullanılmalıdır; aksi halde re-encoded olduğu raporlanır.

`max_patch_passes` 0..2 ile sınırlıdır. Her tur QA snapshot -> patch -> hedef ve komşu block regression şeklinde yürür. İki turda çözülmeyen aynı kusur otomatik loop’u durdurur ve insan incelemesine taşınır.

## 10. Faz 6: Regresyon, İnsan Onayı ve Yayın

Regresyon; hedef defect’in kapanmasını, hedef dışı içeriğin korunmasını, komşu boundary’leri, audio alignment, LUFS/clipping, subtitle timing, continuity, prompt faithfulness ve teknik teslim standardını doğrular.

P0/P1, düşük confidence, çelişkili judge, policy/copyright/brand etkisi, `--force-render`, patch budget exhaustion ve anlatısal değişiklik insan onayı gerektirir. Review kaydı reviewer role, decision, rationale, timestamp, evidence, artifact hash ve override scope içerir.

Geçerli yayın durumları yalnızca `APPROVED`, `APPROVED_WITH_KNOWN_ISSUES`, `NEEDS_REVIEW` ve `BLOCKED` olmalıdır. Eksik artifact, incomplete QA veya unresolved critical defect yayınlanamaz.

## 11. Artifact ve Telemetry

Üretilmesi gereken artifact’ler: screenplay audit, video QA report, evidence index, patch forensic log, regression report, immutable handoff ve final delivery manifest. Her artifact schema version, run ID, source hash, generated-at, model/tool sürümü, rubric/threshold sürümü, status, redaction status ve parent pointer taşır.

Her dış çağrı provider/model, latency, retry, timeout, token/media size, estimated cost, result status ve error class ile izlenir. Secret değerleri telemetry’ye girmez. Retry sınırlı, idempotent ve crash-resumable olmalıdır.

## 12. Test Stratejisi

Deterministic testler: CLI routing, config immutability, rubric toplamı, threshold policy, strict JSON parser, state transition legality, handoff schema, atomic write, redaction, idempotency ve retry budget.

Media testleri: synthetic MP4, single ve multi-block splice, codec/time-base/FPS mismatch, audio preservation, PTS drift, subtitle sync, black/freeze/frame-drop, corrupt media, missing audio, boundary window ve hedef dışı içerik korunumu.

QA testleri: clean pass zero patch, yalnız kusurlu block dispatch, max budget, low confidence -> review, contradictory judges -> review, malformed response != pass, prompt injection/adversarial media fixture ve golden-set precision/recall calibration.

Uçtan uca testler: clean production, healer success, screenplay blocked, plan-only zero spend, dry-run, one-block patch success, persistent defect, CDP unavailable, provider timeout, partial artifact recovery, crash restart ve force-render audit.

## 13. Uygulama Sırası

**Sprint 0:** secret rotation/redaction, baseline, capability discovery, schema/version.

**Sprint 1:** CLI/config, deterministic linter, holistic judge adapter, scorecard, healer, screenplay artifact ve plan-only gate.

**Sprint 2:** canonical state machine, atomic handoff, provenance, idempotency, retry/timeout/error modeli.

**Sprint 3:** technical QA, evidence index, multimodal schema parser, hybrid sampling ve block audit matrix.

**Sprint 4:** selective re-render, patch contract, compatibility checks, splice, rollback ve regression.

**Sprint 5:** human review, override audit, publication gates ve final delivery manifest.

**Sprint 6:** golden set, threshold tuning, cost/latency ölçümü, controlled pilot ve failure drills.

Bağımlılık: güvenlik ve schema olmadan model entegrasyonu; handoff/state machine olmadan patch loop; media compatibility testleri olmadan splice; golden-set calibration olmadan production threshold kilitlenmez.

## 14. Risk Kaydı ve Nihai Kapı

İzlenecek riskler: model hallucination, düşük etiket kalitesi, false positive/negative, patch sonrası regresyon, ID/hash kopması, PTS drift, vendor değişikliği, CDP instability, maliyet artışı, review kuyruğu, secret sızıntısı ve prompt injection. Her risk owner, likelihood, impact, trigger, mitigation, contingency ve residual risk alanlarıyla tutulur.

Production’a geçişten önce secret rotation, baseline, canonical schema/state machine, capability matrix, golden-set calibration, splice/rollback testleri, human review, force-render audit ve plan-only zero-spend kanıtı tamamlanmalıdır. Bunlardan biri eksikse otomatik yayın ve production render açılmaz.

## Sonuç

Kaynak chat’teki v4.2.0 teknik spesifikasyon uygulanabilir ve güçlüdür; bu master plan onu koruyarak operasyonel boşlukları kapatır. Özellikle secret yönetimi, evidence/provenance, strict schema, calibration, splice doğrulaması, insan onayı, idempotency ve gerçek medya testleri tamamlanmadan plan production-ready kabul edilmemelidir.
