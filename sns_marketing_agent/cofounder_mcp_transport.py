"""Real network MCPToolCaller: talks to co-mcp over streamable HTTP.

PRD §6.2: `https://cofounder-api.jengablock.com/mcp`, Python `mcp` SDK.

⚠️ Auth is unresolved (PRD §9 Q1 — "co-mcp 인증 방식... 강주원 확인 필요").
This sends `Authorization: Bearer <COFOUNDER_MCP_TOKEN>` as the most likely
scheme (matching how the rest of this codebase reads secrets from the
environment), but that has NOT been confirmed against the real server from
outside a Claude-session MCP binding — the chat session this prototype was
built in has its own separate "operator" MCP access that a standalone script
can't reuse. Until Q1 is confirmed, treat a 401/403 here as "expected", not
"broken": swap in whatever header 강주원 confirms.

This module is the only place that imports `mcp` or does network I/O for
co-mcp — everything else goes through ReadOnlyCofounderClient, which only
knows about the MCPToolCaller.call() surface (cofounder_client.py).
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

DEFAULT_ENDPOINT = "https://cofounder-api.jengablock.com/mcp"


class CofounderMcpAuthError(Exception):
    """Raised when co-mcp rejects the request. See this module's docstring — Q1."""


class CofounderMCPTransport:
    """Real streamable-HTTP transport. One instance holds one session per call
    (co-mcp calls from this prototype are infrequent — once per snapshot
    refresh — so paying connection setup per call is simpler than pooling
    a long-lived session across FastAPI requests)."""

    def __init__(self, endpoint: str | None = None, token: str | None = None):
        self._endpoint = endpoint or os.environ.get("COFOUNDER_MCP_ENDPOINT", DEFAULT_ENDPOINT)
        self._token = token or os.environ.get("COFOUNDER_MCP_TOKEN")

    def call(self, tool: str, **kwargs: Any) -> dict:
        return asyncio.run(self._call_async(tool, kwargs))

    async def _call_async(self, tool: str, kwargs: dict) -> dict:
        import httpx2
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        http_client = httpx2.AsyncClient(headers=headers)

        try:
            async with streamable_http_client(self._endpoint, http_client=http_client) as (
                read_stream,
                write_stream,
                _get_session_id,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool, arguments=kwargs)
        except Exception as exc:  # narrow once Q1 confirms the real failure shape
            raise CofounderMcpAuthError(
                f"co-mcp call to {tool!r} failed — auth scheme unconfirmed (PRD §9 Q1): {exc}"
            ) from exc
        finally:
            await http_client.aclose()

        if result.isError:
            raise CofounderMcpAuthError(f"co-mcp returned an error for {tool!r}: {result.content}")

        for block in result.content:
            if getattr(block, "type", None) == "text":
                import json

                return json.loads(block.text)
        raise CofounderMcpAuthError(f"co-mcp response for {tool!r} had no text content block")
