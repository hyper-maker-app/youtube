# Dual-Modality Refactoring: Bağımsız Denetim Doğrulama Raporu (Claude İncelemesi İçin)

Bu belge, Claude (Anthropic) tarafından yapılan ikinci tur incelemedeki tüm soruları, şüpheleri ve satır numarası kaymalarını doğrudan kaynak kodla açıklamaktadır. Bu dosyayla birlikte tüm güncellenmiş kaynak kodlar, yeni unit testler ve gerçek test logları zip içerisinde paylaşılmaktadır.

---

## 1. 📏 Satır Numarası Kayması Açıklaması (Neden 802 Satırdan 881 Satıra Çıktı?)

Orijinal `services/script_engine.py` dosyası tam **803 satırdı**. Yapılan refactoring ile dosyaya yeni fonksiyonlar, şablonlar ve doğrulama blokları eklendi ve dosya net **881 satıra** ulaştı (+78 satır).

İşte eklenen yeni bileşenler ve güncel 881 satırlık dosyadaki **kesin satır konumları**:

| Bileşen | Yeni Dosyadaki Konumu | Açıklama |
|---|---|---|
| **ModeProfile Import** | `script_engine.py:13` | `from services.mode_profile import ANATOMICAL, ModeProfile` eklendi. |
| **Domain Fizik Fiilleri & Sesler** | `script_engine.py:59, 69, 87-91` | `incident` domain'i ve alias'ları (`news`, `event`, `accident`) eklendi. |
| **Ortam Sansürü Kaldırılması** | `script_engine.py:91-114` | `_MODEL_BRIEF_REWRITES` içerisindeki hardcoded `hospital|street|bedroom|wall|sky` regex'leri kaldırıldı. |
| **Fail-Safe `_canonicalize_model_brief`** | `script_engine.py:180-190` | `mode: ModeProfile = ANATOMICAL` eklendi. Yalnızca `if mode.environment_censor:` durumunda sansür uygulanıyor. |
| **`Shot.secondary_subject_ids`** | `script_engine.py:263` | `Shot` dataclass'ına eklendi. |
| **`Shot.from_dict` Parsing** | `script_engine.py:334` | `secondary_subject_ids=[str(x) for x in value.get("secondary_subject_ids") or []]` eklendi. |
| **`Script.mode` Serialization** | `script_engine.py:355, 372, 385` | `Script` sınıfına `mode: str = "anatomical"` eklendi, `to_dict` ve `from_dict`'e bağlandı. |
| **`_environment_clause` (YENİ)** | `script_engine.py:408-414` | Yeni yardımcı fonksiyon. İncident modunda `shot.location_id`'yi glossy 3D mekan olarak prompta basar. |
| **`compile_keyframe_prompt`** | `script_engine.py:416-432` | `mode: ModeProfile = ANATOMICAL` parametresi aldı. Hardcoded void yerine `_environment_clause` çağırır. |
| **`_environment_motion_clause` (YENİ)** | `script_engine.py:435-442` | Hareket promptları için dinamik mekan cümlesi üretir. |
| **`optimize_for_flow`** | `script_engine.py:444-490` | `mode: ModeProfile = ANATOMICAL` aldı, 3 hareket dalında da mekan cümlesini kullanır. |
| **İnsan Yasağı Mod Koşulu** | `script_engine.py:579-581` | `if mode.single_shot_human_anchor:` içine alındı. İncident modunda shot 2+ insan karakter serbest. |
| **Mekan Sansürü Validator Koşulu** | `script_engine.py:582-584` | `if mode.environment_censor:` içine alındı. İncident modunda mekan kelimeleri serbest. |
| **Gerçek Kişi Güvenlik Validatorü (YENİ)**| `script_engine.py:597-611` | `if not mode.single_shot_human_anchor:` altında küçük harf rol ID (`unruly_passenger`) ve narration özel isim kontrolü. |
| **BeatEngine Schema Genişletmesi** | `script_engine.py:654` | LLM JSON şemasına `secondary_subject_ids` dizisi eklendi. |
| **`_incident_system_prompt` (YENİ)** | `script_engine.py:733-755` | Haber/olay için Zack D. Films 3D belgesel senaryo talimatı (kronolojik akış, gizlilik, çoklu karakter). |
| **`_assemble` Human Domain Düzeltmesi** | `script_engine.py:821-825` | `if self.mode.single_shot_human_anchor and index > 1 and _is_human_subject(merged):` yapılarak incident modunda domain'in zorla `anatomical` yapılması engellendi. |

---

## 2. 🎯 `_kind_for()` Zafiyetinin Düzeltilmesi (`services/asset_roster.py`)

Claude'un v2 incelemesinde tespit ettiği kritik zafiyet (`flight_attendant_01`, `unruly_passenger` kelimelerinin `human|man|woman` içermediği için yanlışlıkla `kind="prop"` ve 1:1 en-boy oranı alması riski) **Seçenek 2 uygulanarak** kökünden çözüldü:

`services/asset_roster.py:106-146` arasındaki `_build_contextual_roster` fonksiyonunda:

```python
    # 2. All characters (primary + secondary) — in incident mode, every
    #    non-environment entry is a character by definition (no keyword sniffing).
    seen_chars: set[str] = set()
    for shot in shots:
        all_ids = [str(getattr(shot, "subject_id", "subject"))]
        all_ids += list(getattr(shot, "secondary_subject_ids", None) or [])
        for subject_id in all_ids:
            if subject_id in seen_chars:
                continue
            seen_chars.add(subject_id)
            if subject_id == str(getattr(shot, "subject_id", "")):
                description = str(getattr(shot, "subject_description", "") or subject_id)
            else:
                description = subject_id.replace("_", " ")
            # In incident mode, all subjects are characters — no _kind_for() sniffing
            entries.append(RosterEntry(
                subject_id, "character", "2:3",
                _character_prompt(description),
            ))
```

**Sonuç:** İncident modundaki tüm aktörler (primer veya sekonder), ID'leri ne olursa olsun (`suspect_01`, `pilot`, `copilot`, `bystander_a`) istisnasız `kind="character"`, `aspect_ratio="2:3"` ve CPIG 3D karakter modelleme kontratı alır. Ortam plakaları ise ayrı olarak `environment_{location_id}` şeklinde `kind="environment"` olarak üretilir.

---

## 3. 🛡️ Fail-Safe Varsayılan Doğrulaması

Hiçbir fonksiyonda `mode: ModeProfile | None = None` bulunmamaktadır. Tüm fonksiyon imzaları:
`mode: ModeProfile = ANATOMICAL`
şeklinde kilitlenmiştir.

Ayrıca `pipeline.py` içerisinde `_keyframe_jobs`, `validate_script`, `build_roster`, `optimize_for_flow` çağrılarının tamamı `ctx.mode` parametresini açıkça iletir.

---

## 4. 📊 Test ve Denetim Kanıtları (Zip İçindeki Ham Dosyalar)

1. **`pytest_output.txt`**:
   - `python -m pytest tests/ -v` komutunun birebir terminal çıktısıdır.
   - 93 test başarıyla geçmiştir (0 hata, 5 atlanan).
   - Yeni eklenen `tests/test_mode_profile.py` dosyasındaki 5 testin tamamı (sınır durumları, rol-id denetimi, fail-safe sansür, çoklu karakter tespiti) geçmiştir.

2. **`audit_and_sync_output.txt`**:
   - `python scripts/audit_and_sync.py` komutunun birebir terminal çıktısıdır.
   - 8/8 denetim kategorisinin tamamından 0 hata ve 0 uyarı ile geçilmiştir.
   - `DECISIONS.md` içerisine kaydedilen 20 ADR (ADR-020 dahil) doğrulanmıştır.

---

## 5. 🎬 Gerçek Prodüksiyon Kanıtı İçin Sonraki Adım

Claude'un belirttiği gibi: `--dry-run` kodun mantığını doğrular; modelin gerçekte ne çizdiğini görmek için gerçek API gereklidir.

Bir sonraki adım olarak **gerçek Vertex AI API'si (Nano Banana Pro + Veo 3.1)** ile:
```bash
python main.py --test-blocks 3 --mode incident --topic "The Passenger Who Tried to Open an Airplane Door Mid-Flight"
```
çalıştırılarak üretilen 4 kilit kare görseli (`kf01.png`, `kf02.png`, `kf03.png`, `kf04.png`), `asset_roster.json` ve video blokları incelenecektir.
