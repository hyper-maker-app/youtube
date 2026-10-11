"""Decision record manager and CLI for YouTube Shorts pipeline."""
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
    sections = re.split(r"\n###\s+\[(ADR-\d+)\]\s+", content)
    decisions: list[Decision] = []
    for i in range(1, len(sections), 2):
        adr_id = sections[i]
        body = sections[i + 1] if i + 1 < len(sections) else ""
        title_line = body.splitlines()[0].strip() if body else ""
        date_match = re.search(r"\*\*Tarih\*\*:\s*(\S+)", body)
        status_match = re.search(r"\*\*Durum\*\*:\s*`?([A-Z_]+)`?", body)
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
    ids = [int(re.search(r"\d+", d.id).group()) for d in decisions if re.search(r"\d+", d.id)]
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
        f.write(entry + "\n---\n")
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
            print(f"\n[{m['id']}] ({m['status']}) {m['title']}\n{m['content']}")
    elif args.command == "record":
        res = record_decision(args.title, args.status, args.request, args.outcome, args.reason, args.lesson)
        print(f"Recorded successfully: {res}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
