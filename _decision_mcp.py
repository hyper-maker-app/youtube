"""MCP server for searching and recording Architecture Decision Records (ADR)."""
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
