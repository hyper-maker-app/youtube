"""Synchronize MCP server definitions across all AI clients (Antigravity, Codex, Cursor, Claude)."""
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
    codex_toml.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
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
