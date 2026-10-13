"""services/flow_browser_automation.py — AST-clean re-export shim.

The FlowBrowserClient implementation has been moved to
providers/flow_browser/client.py to honour the services/ AST-clean
boundary contract (no network imports in services/).

This module provides a zero-network backward-compatible re-export so that
existing call sites (providers/image/browser_flow.py,
providers/video/browser_flow.py) continue to work without modification.

Strictly AST-clean: no urllib, no websockets, no httpx, no requests.
"""

from __future__ import annotations

# Re-export from the correct provider layer — zero network imports here.
from providers.flow_browser.client import FlowBrowserClient  # noqa: F401

__all__ = ["FlowBrowserClient"]
