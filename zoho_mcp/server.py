import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from tools.leave_tools import registerable_tools as leave_tools

from utils.logger import get_logger

logger = get_logger("mcp_server")

mcp = FastMCP("prodevans-hr-mcp", port=8001)


def _register(tools_fn):
    for tool in tools_fn():
        mcp.tool()(tool)
        logger.info(f"[MCP] Registered: {tool.__name__}")


_register(leave_tools)


if __name__ == "__main__":
    logger.info("[MCP] Starting server on port 8001")
    mcp.run(transport="sse")