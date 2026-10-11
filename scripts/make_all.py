# Auto-generator for project enhancements
from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parents[1]

def build_decisions_md():
    content = """# YouTube Shorts Automation — Architecture Decision Records (ADR) & Experiment Log

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
"""
    (ROOT / "DECISIONS.md").write_text(content.strip() + "\n", encoding="utf-8")
    print("DECISIONS.md written")

def build_decision_py():
    content = '''"""Decision record manager and CLI for YouTube Shorts pipeline."""
from __future__ import annotations

import argparse
import datetime
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS_FILE = ROOT / "DECISIONS.md"

@dataclass
class Decision:
    id: str
    title: str
    date: str
    status: str
    raw_text: str

def parse_decisions(file_path: Path = DECISIONS_FILE) -> list[Decision]:
    if not file_path.is_file():
        return []
    content = file_path.read_text(encoding="utf-8")
    sections = re.split(r"\\n###\\s+\\[(ADR-\\d+)\\]\\s+", content)
    decisions: list[Decision] = []
    for i in range(1, len(sections), 2):
        adr_id = sections[i]
        body = sections[i + 1] if i + 1 < len(sections) else ""
        title_line = body.splitlines()[0].strip() if body else ""
        date_match = re.search(r"\\*\\*Tarih\\*\\*:\\s*(\\S+)", body)
        status_match = re.search(r"\\*\\*Durum\\*\\*:\\s*`?([A-Z_]+)`?", body)
        decisions.append(
            Decision(
                id=adr_id,
                title=title_line,
                date=date_match.group(1) if date_match else "unknown",
                status=status_match.group(1) if status_match else "UNKNOWN",
                raw_text=f"### [{adr_id}] {body}".strip(),
            )
        )
    return decisions

def search_decisions(query: str, file_path: Path = DECISIONS_FILE) -> list[dict]:
    query_lower = query.lower()
    results: list[dict] = []
    for d in parse_decisions(file_path):
        if query_lower in d.raw_text.lower():
            results.append({
                "id": d.id,
                "title": d.title,
                "date": d.date,
                "status": d.status,
                "content": d.raw_text,
            })
    return results

def next_adr_id(file_path: Path = DECISIONS_FILE) -> str:
    decisions = parse_decisions(file_path)
    if not decisions:
        return "ADR-001"
    ids = [int(re.search(r"\\d+", d.id).group()) for d in decisions if re.search(r"\\d+", d.id)]
    return f"ADR-{max(ids) + 1:03d}"

def record_decision(
    title: str,
    status: str,
    request: str,
    outcome: str,
    reason: str,
    lesson: str,
    file_path: Path = DECISIONS_FILE,
) -> dict:
    status = status.upper().strip()
    valid_statuses = {"ACCEPTED", "REJECTED", "ABANDONED", "SUPERSEDED"}
    if status not in valid_statuses:
        raise ValueError(f"Status must be one of {valid_statuses}")
    
    adr_id = next_adr_id(file_path)
    today = datetime.date.today().isoformat()
    entry = f"""
### [{adr_id}] {title}
- **Tarih**: {today}
- **Durum**: `{status}`
- **Talep / Fikir**: {request}
- **Yapılan İş / Sonuç**: {outcome}
- **İptal / Kabul Gerekçesi**: {reason}
- **Kalıcı Kural / Ders**: {lesson}
"""
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(entry + "\\n---\\n")
    return {"id": adr_id, "title": title, "status": status, "recorded": True}

def main():
    parser = argparse.ArgumentParser(description="Manage Architecture Decision Records")
    subparsers = parser.add_subparsers(dest="command")

    list_p = subparsers.add_parser("list", help="List all decisions")
    search_p = subparsers.add_parser("search", help="Search decisions")
    search_p.add_argument("query", help="Keyword or phrase to search")

    rec_p = subparsers.add_parser("record", help="Record a new decision or experiment")
    rec_p.add_argument("--title", required=True, help="Decision title")
    rec_p.add_argument("--status", choices=["ACCEPTED", "REJECTED", "ABANDONED", "SUPERSEDED"], required=True)
    rec_p.add_argument("--request", required=True, help="What was asked or attempted")
    rec_p.add_argument("--outcome", required=True, help="What happened")
    rec_p.add_argument("--reason", required=True, help="Why it was accepted, rejected or abandoned")
    rec_p.add_argument("--lesson", required=True, help="Lesson or rule learned")

    args = parser.parse_args()
    if args.command == "list":
        for d in parse_decisions():
            print(f"[{d.id}] ({d.status}) {d.title} ({d.date})")
    elif args.command == "search":
        matches = search_decisions(args.query)
        if not matches:
            print(f"No decisions matching '{args.query}' found.")
        for m in matches:
            print(f"\\n[{m['id']}] ({m['status']}) {m['title']}\\n{m['content']}")
    elif args.command == "record":
        res = record_decision(args.title, args.status, args.request, args.outcome, args.reason, args.lesson)
        print(f"Recorded successfully: {res}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
'''
    (ROOT / "scripts" / "decision.py").write_text(content.strip() + "\n", encoding="utf-8")
    print("scripts/decision.py written")

def build_decision_mcp():
    content = '''"""MCP server for searching and recording Architecture Decision Records (ADR)."""
from __future__ import annotations
from pathlib import Path
from mcp.server.mcpserver import MCPServer
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import decision

mcp = MCPServer("youtube-decision-memory")

@mcp.tool()
def search_decisions(query: str) -> list[dict]:
    """Search project history and ADRs to see if an idea, feature, or style was tried, accepted, or abandoned."""
    return decision.search_decisions(query)

@mcp.tool()
def list_decisions() -> list[dict]:
    """List all recorded architecture and styling decisions."""
    return [{"id": d.id, "title": d.title, "status": d.status, "date": d.date} for d in decision.parse_decisions()]

@mcp.tool()
def record_decision(title: str, status: str, request: str, outcome: str, reason: str, lesson: str) -> dict:
    """Record an experiment, rejected idea, or accepted architectural change into permanent project memory."""
    return decision.record_decision(title, status, request, outcome, reason, lesson)

if __name__ == "__main__":
    mcp.run()
'''
    (ROOT / "_decision_mcp.py").write_text(content.strip() + "\n", encoding="utf-8")
    print("_decision_mcp.py written")

def build_media_mcp():
    content = '''"""MCP server for inspecting video, audio, loudness (LUFS), freeze frames, and captions."""
from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path
from mcp.server.mcpserver import MCPServer
import config

mcp = MCPServer("youtube-media-inspector")

@mcp.tool()
def inspect_media(media_path: str) -> dict:
    """Probe a media file for resolution, aspect ratio (verifies 9:16 vertical), duration, fps, and codecs."""
    path = Path(media_path).resolve()
    if not path.is_file():
        return {"error": f"File not found: {media_path}"}

    ffmpeg = config.resolve_ffmpeg()
    # Run ffprobe if available or ffmpeg -i probe
    probe_cmd = [
        ffmpeg, "-hide_banner", "-i", str(path), "-f", "null", "-"
    ]
    proc = subprocess.run(probe_cmd, capture_output=True, text=True, check=False)
    stderr = proc.stderr

    duration_m = re.search(r"Duration:\\s*(\\d+):(\\d+):([\\d.]+)", stderr)
    video_m = re.search(r"Stream #\\d+:\\d+.*Video:.*,\\s*(\\d+)x(\\d+)", stderr)
    fps_m = re.search(r"([\\d.]+)\\s*fps", stderr)
    audio_m = re.search(r"Stream #\\d+:\\d+.*Audio:\\s*(\\w+)", stderr)

    duration_sec = 0.0
    if duration_m:
        h, m, s = duration_m.groups()
        duration_sec = int(h) * 3600 + int(m) * 60 + float(s)

    width, height = (int(video_m.group(1)), int(video_m.group(2))) if video_m else (0, 0)
    is_vertical_9_16 = (width > 0 and height > 0) and abs((height / width) - (16.0 / 9.0)) < 0.05

    return {
        "file": str(path),
        "exists": True,
        "duration_sec": duration_sec,
        "width": width,
        "height": height,
        "aspect_ratio_9_16": is_vertical_9_16,
        "fps": float(fps_m.group(1)) if fps_m else None,
        "has_audio": bool(audio_m),
        "audio_codec": audio_m.group(1) if audio_m else None,
    }

@mcp.tool()
def measure_audio_loudness(media_path: str) -> dict:
    """Measure integrated loudness (LUFS), true peak (dBTP), and loudness range (LRA) using EBU R128."""
    path = Path(media_path).resolve()
    if not path.is_file():
        return {"error": f"File not found: {media_path}"}

    ffmpeg = config.resolve_ffmpeg()
    cmd = [ffmpeg, "-hide_banner", "-i", str(path), "-af", "ebur128=framelog=verbose", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    stderr = proc.stderr

    i_m = re.search(r"\\s*I:\\s*([-\\d.]+)\\s*LUFS", stderr)
    tp_m = re.search(r"\\s*Peak:\\s*([-\\d.]+)\\s*dBFS", stderr)
    lra_m = re.search(r"\\s*LRA:\\s*([-\\d.]+)\\s*LU", stderr)

    integrated = float(i_m.group(1)) if i_m else None
    return {
        "file": str(path),
        "integrated_lufs": integrated,
        "true_peak_db": float(tp_m.group(1)) if tp_m else None,
        "lra_lu": float(lra_m.group(1)) if lra_m else None,
        "optimal_for_shorts": bool(integrated and -16.0 <= integrated <= -13.0),
    }

@mcp.tool()
def detect_black_or_freeze(video_path: str) -> dict:
    """Detect accidental black frames or freeze frames in a rendered short."""
    path = Path(video_path).resolve()
    if not path.is_file():
        return {"error": f"File not found: {video_path}"}

    ffmpeg = config.resolve_ffmpeg()
    cmd = [
        ffmpeg, "-hide_banner", "-i", str(path),
        "-vf", "freezedetect=n=0.003:d=1.6,blackdetect=d=0.5:pix_th=0.10",
        "-f", "null", "-"
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    stderr = proc.stderr

    freezes = re.findall(r"freeze_start:\\s*([\\d.]+).*?freeze_duration:\\s*([\\d.]+)", stderr)
    blacks = re.findall(r"black_start:\\s*([\\d.]+).*?black_duration:\\s*([\\d.]+)", stderr)

    return {
        "file": str(path),
        "freeze_events": [{"start": float(s), "duration": float(d)} for s, d in freezes],
        "black_events": [{"start": float(s), "duration": float(d)} for s, d in blacks],
        "has_defect": bool(freezes or blacks),
    }

if __name__ == "__main__":
    mcp.run()
'''
    (ROOT / "_media_mcp.py").write_text(content.strip() + "\n", encoding="utf-8")
    print("_media_mcp.py written")

def build_sync_mcp():
    content = '''"""Synchronize MCP server definitions across all AI clients (Antigravity, Codex, Cursor, Claude)."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PY_EXE = sys.executable

MCP_SERVERS = {
    "youtube-pipeline-db": {
        "command": PY_EXE,
        "args": [str((ROOT / "_pipeline_mcp.py").as_posix())],
        "description": "Database history, recent topics, duplicate check, run statistics",
    },
    "youtube-research": {
        "command": PY_EXE,
        "args": [str((ROOT / "_research_mcp.py").as_posix())],
        "description": "Wikipedia, Crossref/PubMed evidence discovery and claim evaluation",
    },
    "youtube-decision-memory": {
        "command": PY_EXE,
        "args": [str((ROOT / "_decision_mcp.py").as_posix())],
        "description": "ADR search, past abandoned experiments, decision logger",
    },
    "youtube-media-inspector": {
        "command": PY_EXE,
        "args": [str((ROOT / "_media_mcp.py").as_posix())],
        "description": "FFmpeg video resolution, 9:16 aspect ratio, LUFS audio, freeze/black frame inspector",
    },
}

def sync_antigravity():
    antigravity_cfg = Path.home() / ".gemini" / "antigravity" / "mcp_config.json"
    antigravity_cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg = {"mcpServers": {}}
    for name, srv in MCP_SERVERS.items():
        cfg["mcpServers"][name] = {
            "command": srv["command"],
            "args": srv["args"]
        }
    antigravity_cfg.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"[OK] Antigravity MCP synchronized: {antigravity_cfg}")

def sync_codex():
    codex_toml = ROOT / ".codex" / "config.toml"
    codex_toml.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        '[mcp_servers.duckduckgo]',
        'command = "uvx"',
        'args = ["duckduckgo-mcp-server"]',
        ''
    ]
    for name, srv in MCP_SERVERS.items():
        short_name = name.replace("youtube-", "")
        lines.append(f"[mcp_servers.{short_name}]")
        lines.append(f'command = "python"')
        rel_script = Path(srv["args"][0]).name
        lines.append(f'args = ["{rel_script}"]')
        lines.append("")
    codex_toml.write_text("\\n".join(lines).strip() + "\\n", encoding="utf-8")
    print(f"[OK] Codex MCP synchronized: {codex_toml}")

def sync_cursor():
    cursor_dir = ROOT / ".cursor"
    cursor_dir.mkdir(parents=True, exist_ok=True)
    cursor_mcp = cursor_dir / "mcp.json"
    cfg = {"mcpServers": {}}
    for name, srv in MCP_SERVERS.items():
        cfg["mcpServers"][name] = {
            "command": srv["command"],
            "args": srv["args"]
        }
    cursor_mcp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"[OK] Cursor MCP synchronized: {cursor_mcp}")

def sync_claude():
    claude_dir = ROOT / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    claude_mcp = claude_dir / "mcp.json"
    cfg = {"mcpServers": {}}
    for name, srv in MCP_SERVERS.items():
        cfg["mcpServers"][name] = {
            "command": srv["command"],
            "args": srv["args"]
        }
    claude_mcp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"[OK] Claude MCP synchronized: {claude_mcp}")

def sync_all():
    sync_antigravity()
    sync_codex()
    sync_cursor()
    sync_claude()

if __name__ == "__main__":
    sync_all()
'''
    (ROOT / "scripts" / "sync_mcp_configs.py").write_text(content.strip() + "\n", encoding="utf-8")
    print("scripts/sync_mcp_configs.py written")

def build_skills():
    # 1. decision-tracker
    dt_dir = ROOT / "skills" / "decision-tracker"
    dt_dir.mkdir(parents=True, exist_ok=True)
    (dt_dir / "SKILL.md").write_text('''---
name: decision-tracker
description: Consult past architecture decisions and record abandoned or accepted experiments before changing code or prompts.
---

# Decision tracker

Use this skill whenever:
1. The user asks for a new style, feature, timing, animation, or workflow change.
2. An experiment or test is completed, fails, or is cancelled by the user.

- Query `DECISIONS.md` (or call `youtube-decision-memory` MCP / `python scripts/decision.py search "<keyword>"`) BEFORE implementing any architectural or artistic change.
- If an idea was previously marked `ABANDONED` or `REJECTED`, warn the user with the date and reasoning from the ADR record, explaining why it was bad.
- If a new change is rejected, produces bad visual results, or the user says "iptal ettik / geri alalım", immediately record the decision with status `ABANDONED`, documenting what was requested, what was done, why it failed, and the lesson learned.
'''.strip() + "\n", encoding="utf-8")
    print("skills/decision-tracker written")

    # 2. zack-d-director
    zd_dir = ROOT / "skills" / "zack-d-director"
    zd_dir.mkdir(parents=True, exist_ok=True)
    (zd_dir / "SKILL.md").write_text('''---
name: zack-d-director
description: Direct and enforce Zack D. Films 3D vertical documentary visual style, lighting matrix, and calm editorial language.
---

# Zack D. Films 3D Director

Use this skill when drafting keyframe prompts, motion prompts, and camera directions for this repository.

- Characters never speak, mouth words, or lip-sync. Mouths must remain closed or neutral.
- Every clip must show one irreversible causal physical state change: Entry (latent state) -> Dominant physical event -> Exit (peak state).
- Use the 6-scale lighting matrix:
  * Wide: Golden daylight, long readable shadows.
  * Human: Soft key, shallow contrast, natural bounce.
  * Object: Controlled studio key with edge highlight.
  * Macro: Diffuse rim illumination across translucent microstructures.
  * Micro: Cool clinical key light with warm internal practical.
  * Nano: Bioluminescent X-Ray Blue through translucent nanoscale structures.
- Markers (neon-green arrow, red trajectory) are evidence, not decorations. Add a marker ONLY when `proof_on_screen` requires it. Never place markers in the lower-middle caption-safe zone.
- Transitions are calm hard-cuts. No crash zooms, screen shake, or fast MTV-style editing.
'''.strip() + "\n", encoding="utf-8")
    print("skills/zack-d-director written")

    # 3. ffmpeg-diagnostics
    ff_dir = ROOT / "skills" / "ffmpeg-diagnostics"
    ff_dir.mkdir(parents=True, exist_ok=True)
    (ff_dir / "SKILL.md").write_text('''---
name: ffmpeg-diagnostics
description: Diagnose and inspect FFmpeg filtergraphs, half-open window math, ASS subtitles, and audio loudness.
---

# FFmpeg diagnostics

Use this skill when diagnosing render glitches, audio ducking, freeze frames, or caption errors.

- Never modify the half-open window gate: `gte(time,t0)*lt(time,t1)` in `editor.py`.
- Never modify the live crop clamp: `clip(dim*target - dim/zoom/2, 0, dim - dim/zoom)`.
- Use the `youtube-media-inspector` MCP or `scripts/audit_and_sync.py` to inspect LUFS loudness (-16 to -13 LUFS is optimal) and detect freeze/black frames.
- Subtitle ASS files must fit the vertical 1080x1920 layout and must never collide with visual proof markers.
'''.strip() + "\n", encoding="utf-8")
    print("skills/ffmpeg-diagnostics written")

    # 4. topic-scout
    ts_dir = ROOT / "skills" / "topic-scout"
    ts_dir.mkdir(parents=True, exist_ok=True)
    (ts_dir / "SKILL.md").write_text('''---
name: topic-scout
description: Research high-curiosity scientific, medical, and everyday mystery topics tailored for 3D causal animation.
---

# Topic scout

Use this skill when picking or evaluating new topics for `--auto-topic`.

- Verify duplicate prevention using `youtube-pipeline-db.topic_exists` before approving a topic.
- A topic must depict a physical, irreversible mechanism (e.g. why bones mend, how venom coagulates, why lighthouses use fresnel lenses). Purely abstract philosophical or conversational topics are forbidden.
- For medical/biological claims, require peer-reviewed or institutional evidence via `youtube-research` MCP; Wikipedia is only background context.
'''.strip() + "\n", encoding="utf-8")
    print("skills/topic-scout written")

def build_project_context():
    content = '''# YouTube Shorts Automation — Universal Project Context (Single Source of Truth)

Bu belge, projede çalışan tüm yapay zeka modelleri (Gemini / Antigravity, Claude, OpenAI / Codex, Cursor vb.) için ortak ve tekil anayasal referans noktasıdır.

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

## 3. Otomatik Bakım ve Doğrulama Kuralı (Zero-Manual-Effort)
- **Kullanıcı manuel audit komutu çalıştırmayacaktır.**
- Bir AI ajan (hangi LLM olursa olsun) kodda, promptta, sağlayıcılarda veya zamanlamada bir değişiklik yaptığında, yanıt vermeden önce **otomatik olarak** `python scripts/audit_and_sync.py` çalıştırmak ve 0 hata ile geçtiğini doğrulamak zorundadır.

---

## 4. Mevcut MCP Sunucuları
1. **`youtube-pipeline-db` (`_pipeline_mcp.py`)**: SQLite geçmişi, son konular, dublike kontrolü, çalışma özetleri.
2. **`youtube-research` (`_research_mcp.py`)**: Wikipedia, Crossref/PubMed iddia analizi ve kanıt toplama.
3. **`youtube-decision-memory` (`_decision_mcp.py`)**: Geçmişte denenmiş/iptal edilmiş kararları arama ve yeni karar kaydetme.
4. **`youtube-media-inspector` (`_media_mcp.py`)**: FFmpeg video çözünürlük, 9:16 en-boy, LUFS ses seviyesi ve donma/siyah kare analizi.

---

## 5. Mevcut Beceriler (Skills)
- `decision-tracker`: Karar geçmişini denetleme ve yeni iptalleri kaydetme.
- `zack-d-director`: Zack D. Films 3D tarzı, 6 ölçekli ışıklandırma ve görsel kanıt direktifleri.
- `ffmpeg-diagnostics`: FFmpeg yarım-açık pencere, filtre grafiği ve altyazı sorun giderme.
- `topic-scout`: Causal fiziksel geçişlere uygun bilimsel konu keşfi.
- `fact-check`: Araştırma manifesti üzerinden olgusal doğrulama.
- `shorts-script-editor`: 5-beat senaryo ve süre bütçesi düzenleme.
- `video-qa`: Render edilmiş artefakt kalite kontrolü.
'''
    (ROOT / "PROJECT_CONTEXT.md").write_text(content.strip() + "\n", encoding="utf-8")
    print("PROJECT_CONTEXT.md written")

def build_llm_rules():
    claude_content = '''# Claude Assistant Guidelines - YouTube Shorts Automation

Follow `PROJECT_CONTEXT.md` and `AGENTS.md` as the authoritative sources of truth.

## Non-negotiable Production Contracts
1. Dynamic provider-native plan: 6–13 x 4.0s (or 5–8s Veo/H3) blocks based on measured voice duration; 1.5s cloned tail; preserve persisted resumes.
2. FFmpeg safety: Never modify `gte(time,t0)*lt(time,t1)` gates or `clip(...,0,dim-(dim/zoom))` clamps in `editor.py`.
3. Characters never speak, lip-sync, or move mouths; captions are FFmpeg/ASS only.
4. Keep all assets and renders 9:16 vertical (1080x1920 or 720x1280) with clear lower-middle caption-safe zones.
5. All credentials and models come from `.env`; keep `.env.example` synchronized.

## Decision Memory & Experiment History (ADR Mandate)
- Before proposing or implementing any new architecture, animation, style, or workflow change, search `DECISIONS.md` (`python scripts/decision.py search "topic"`).
- If an idea was previously marked `ABANDONED` or `REJECTED`, warn the user with the ADR reasoning and do not re-introduce failed patterns.
- If a change is attempted and fails, or if the user requests cancellation/revert ("olmadı / iptal et / geri al"), AUTOMATICALLY record it into `DECISIONS.md` using `scripts/decision.py record`.

## Automatic Maintenance Mandate (Zero Manual Effort for User)
- The user will NEVER manually run `python scripts/audit_and_sync.py`.
- Whenever you make changes to pipeline code, providers, shaders, or timing, you MUST automatically run `python scripts/audit_and_sync.py` and verify 0 failures before finishing.
- If MCP configurations or tools change, automatically run `python scripts/sync_mcp_configs.py`.
'''
    (ROOT / "CLAUDE.md").write_text(claude_content.strip() + "\n", encoding="utf-8")
    print("CLAUDE.md written")

    cursor_content = '''# Cursor Rules - YouTube Shorts Automation

Follow `PROJECT_CONTEXT.md` and `AGENTS.md` as the authoritative sources of truth.

## Core Rules
1. Provider-native plan: 6–13 x 4.0s blocks locked from measured voice duration. Never alter a resumed plan.
2. FFmpeg invariants: Do not change `gte(time,t0)*lt(time,t1)` gates or `clip(...,0,dim-(dim/zoom))` crop clamps in `editor.py`.
3. Visuals & Audio: No spoken characters, no lip-sync, no moving mouths. All renders 9:16. Lower-middle zone is caption-safe.
4. Security: No secrets in code; read all config from `.env` and maintain `.env.example`.

## Decision Memory Mandate
- Check `DECISIONS.md` before changing styles or architecture.
- If an idea failed previously (`ABANDONED`), do not repeat it.
- If a user rejects or cancels an attempted change, automatically document the reason in `DECISIONS.md`.

## Automatic Maintenance (Zero User Effort)
- Never ask the user to run sync or audit commands.
- Automatically execute `python scripts/audit_and_sync.py` after code changes to ensure all contracts pass.
'''
    (ROOT / ".cursorrules").write_text(cursor_content.strip() + "\n", encoding="utf-8")
    print(".cursorrules written")

    gemini_content = '''# Gemini / Antigravity Project Instructions - YouTube Shorts Automation

Follow `PROJECT_CONTEXT.md` and `AGENTS.md` as the authoritative sources of truth.

## Core Invariants
1. Timeline: Provider-native 6–13 x 4.0s (or 5–8s Veo/H3) blocks based on measured voice duration. 1.5s cloned tail. Resumed runs preserve their saved timeline.
2. FFmpeg math: Do not touch `gte(time,t0)*lt(time,t1)` gates or `clip(...,0,dim-(dim/zoom))` clamps in `editor.py`.
3. Zack D. Films style: Characters never speak or lip-sync (closed/neutral mouth). 9:16 vertical framing. Lower-middle caption-safe area.
4. Evidence only: Markers (arrows/trajectories) only when `proof_on_screen` explicitly demands it.
5. Environment: Secrets only in `.env`; keep `.env.example` synchronized.

## Decision Memory (ADR) Mandate
- Always check `DECISIONS.md` (`youtube-decision-memory` MCP or `python scripts/decision.py search "query"`) before changing architecture or visual styles.
- Automatically document cancelled or failed experiments in `DECISIONS.md` with status `ABANDONED` or `REJECTED`.

## Automatic Maintenance (Zero User Effort)
- The user will never manually run audit or synchronization scripts.
- The assistant must automatically execute `python scripts/audit_and_sync.py` after code/prompt modifications to ensure 0 failures.
'''
    (ROOT / "GEMINI.md").write_text(gemini_content.strip() + "\n", encoding="utf-8")
    print("GEMINI.md written")

def run_all():
    build_decisions_md()
    build_decision_py()
    build_decision_mcp()
    build_media_mcp()
    build_sync_mcp()
    build_skills()
    build_project_context()
    build_llm_rules()
    print("ALL ENHANCEMENTS GENERATED SUCCESSFULLY!")


if __name__ == "__main__":
    run_all()

