"""Local research MCP: Wikipedia context plus Crossref/PubMed evidence discovery."""
from __future__ import annotations
from mcp.server.mcpserver import MCPServer
import research

mcp = MCPServer("youtube-research")

@mcp.tool()
def research_topic(topic: str) -> dict:
    """Return public source candidates and whether the topic is medically sensitive."""
    return {"topic": topic, "sensitive": research.is_sensitive(topic), "sources": research.collect_sources(topic)}

@mcp.tool()
def evaluate_claim(topic: str, claim: str) -> dict:
    """Evaluate one proposed factual claim against collected public evidence."""
    return research.build_manifest(topic, "factual", research.collect_sources(topic), [claim])

if __name__ == "__main__":
    mcp.run()
