import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from zoho_mcp.tools.leave_tools import registerable_tools as leave_tools
from db.oauth_store import init_db
from utils.logger import get_logger

logger = get_logger("mcp_server")

mcp = FastMCP("prodevans-hr-mcp", port=8001)


def _register(tools_fn):
    for tool in tools_fn():
        mcp.tool()(tool)
        logger.info(f"[MCP] Registered: {tool.__name__}")


_register(leave_tools)


async def run_server():
    """Initialize DB and run MCP server in the SAME event loop."""
    await init_db()
    logger.info("[MCP] Database initialized")
    await mcp.run_sse_async()  # fixed


if __name__ == "__main__":
    logger.info("[MCP] Starting server on port 8001")
    asyncio.run(run_server())