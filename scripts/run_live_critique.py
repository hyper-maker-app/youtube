import os
import sys
from pathlib import Path
from openai import OpenAI

# Add engine directory to sys.path
sys.path.insert(0, str(Path("engine").resolve()))
from providers.gemini_webapi import call_gemini_chat

def main():
    fikir_path = Path(r"C:\Users\bekir\OneDrive\Masaüstü\fikir.txt")
    plan_path = Path(r"c:\Users\bekir\.gemini\antigravity\brain\2dba5d28-a136-4150-9a1d-0b1045894b7f\skill_dosyalari_arastirma_ve_iyilestirme_plani_v3.1.md")

    fikir_text = fikir_path.read_text(encoding="utf-8")
    plan_text = plan_path.read_text(encoding="utf-8")

    prompt = f"""Aşağıda YouTube'da 5 dakikalık (300 saniye) 'Procedural Catastrophe & Micro-Survival' (Örn: 1000 Yanardağ Aynı Anda Patlarsa) belgeseli üreten film fabrikamızın mimari planı ve fikir manifestosu yer almaktadır.
Üretim motoru: Google Flow CDP (Veo 3.1) + Deepgram/ElevenLabs VO + 3 Katmanlı Sentetik Foley/FFmpeg.
LLM: grok-4.20-0309-non-reasoning (0 reasoning token).
Planlanan mimari: Karakter/yüz/kostüm/diyalog ve NSFW tamamen eleniyor. 5 aşamalı zamana dayalı bilimsel tırmanış motoru yazılıyor. 2D veri haritası B-roll ekleniyor. 18 skill arşivleniyor, 24 çekirdek skill korunuyor, 4 yeni felaket yönetmeni ekleniyor.

---
### DOKÜMAN 1: fikir.txt (Vizyon ve Manifest)
{fikir_text}

---
### DOKÜMAN 2: skill_dosyalari_arastirma_ve_iyilestirme_plani_v3.1.md (Mimari Plan)
{plan_text}

---
Lütfen bu planı ve mimariyi acımasızca, en üst düzey yönetmen ve teknik mimar gözüyle değerlendir:
1. Bu plan üretim ve YouTube retention başarısı açısından ne kadar iyi? (1-10 puan ver)
2. Planda gözden kaçan, teknik olarak kırılacak veya eksik kalan en kritik 3-5 açık/risk nedir?
3. Skill sadeleştirme stratejisi (özellikle 18 skill'in elenmesi ve 24 skill'in korunması) doğru mu? Ekstra elenmesi veya kesinlikle tutulması gereken başka bir şey var mı?
4. Google Veo 3.1 video kalitesi (Noun Rule, sıfır yüz deformasyonu) ve YouTube algoritması açısından bu planın v4.0 sürümüne hangi somut maddeler eklenmelidir?
"""

    out_dir = Path("out")
    out_dir.mkdir(exist_ok=True)

    print("--- 1. Calling xAI Grok API (grok-4.20-0309-non-reasoning) ---")
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        env_file = Path(".env")
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("XAI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()

    if not api_key:
        raise ValueError("XAI_API_KEY could not be found in environment or .env file.")

    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    grok_response = client.chat.completions.create(
        model="grok-4.20-0309-non-reasoning",
        messages=[
            {"role": "system", "content": "Sen dünyanın en üst düzey sinema yönetmeni, YouTube viral retention ve algoritma stratejisti, ve otonom medya üretim sistemleri baş mimarısın. Soruları acımasız, doğrudan ve somut teknik detaylarla yanıtla."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=4000
    )
    grok_critique = grok_response.choices[0].message.content
    grok_out_file = out_dir / "live_grok_critique.txt"
    grok_out_file.write_text(grok_critique, encoding="utf-8")
    print(f"Grok critique saved to {grok_out_file} (length: {len(grok_critique)} chars)")

    print("\n--- 2. Calling Gemini WebAPI (gemini-3.1-pro) ---")
    gemini_critique = call_gemini_chat(prompt, model="gemini-3.1-pro", timeout=180.0)
    gemini_out_file = out_dir / "live_gemini_critique.txt"
    gemini_out_file.write_text(gemini_critique, encoding="utf-8")
    print(f"Gemini critique saved to {gemini_out_file} (length: {len(gemini_critique)} chars)")

    print("\nBoth critiques obtained successfully!")

if __name__ == "__main__":
    main()
