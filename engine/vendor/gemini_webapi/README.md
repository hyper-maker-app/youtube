# gemini-web2api sidecar

This directory holds the `gemini-web2api` Go binary and transient session cookies extracted from the user's authenticated Google Pro session on Chrome CDP port 9223.

- Binary executable: `bin/gemini-web2api.exe` (Ignored in git)
- Transient session cookies: `cookies.txt` (Ignored in git)
- Upstream project: https://github.com/zexadev/gemini-web2api-go
- Daemon port: 8085
- Provider integration: `providers/gemini_webapi.py`
- MCP tool integration: `_media_mcp.py` -> `audit_visual_fidelity`
