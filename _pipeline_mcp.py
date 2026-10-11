from pathlib import Path
from contextlib import closing
from mcp.server.mcpserver import MCPServer
import run_history

mcp = MCPServer("youtube-pipeline-db")
DB_PATH = Path(__file__).parent / "pipeline_stats.db"

@mcp.tool()
def recent_topics(limit: int = 10) -> list[dict]:
    """Return the newest 1-50 pipeline topics and release state."""
    limit = max(1, min(int(limit), 50))
    with closing(run_history.connect(DB_PATH)) as conn:
        rows = conn.execute("SELECT topic, content_type, timestamp, status FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(zip(("topic", "content_type", "timestamp", "status"), row)) for row in rows]

@mcp.tool()
def topic_exists(normalized_topic: str) -> dict:
    """Check exact normalized-topic history without exposing SQL."""
    key = run_history.topic_key(normalized_topic)
    with closing(run_history.connect(DB_PATH)) as conn:
        count = conn.execute("SELECT COUNT(*) FROM runs WHERE topic_key = ?", (key,)).fetchone()[0]
    return {"topic_key": key, "exists": bool(count), "count": count}

@mcp.tool()
def run_summary() -> dict:
    """Return aggregate run count, cost, duration, and release-state totals."""
    with closing(run_history.connect(DB_PATH)) as conn:
        count, cost, duration = conn.execute("SELECT COUNT(*), COALESCE(SUM(cost_usd), 0), COALESCE(AVG(duration_sec), 0) FROM runs").fetchone()
        states = dict(conn.execute("SELECT status, COUNT(*) FROM runs GROUP BY status").fetchall())
    return {"total_runs": count, "total_cost_usd": cost, "average_duration_sec": duration, "statuses": states}

@mcp.tool()
def record_run(topic: str, content_type: str, status: str, duration_sec: float = 0, cost_usd: float = 0, notes: str = "") -> dict:
    """Record a completed pipeline result. This is the only state-changing MCP tool."""
    if content_type not in {"factual", "folklore", "fiction"}:
        raise ValueError("content_type must be factual, folklore, or fiction")
    if status not in {"pass", "review", "fail", "completed"}:
        raise ValueError("status must be pass, review, fail, or completed")
    run_history.record(DB_PATH, topic, content_type, status, max(0, duration_sec), max(0, cost_usd), notes)
    return {"recorded": True, "topic_key": run_history.topic_key(topic)}

if __name__ == "__main__":
    mcp.run()

