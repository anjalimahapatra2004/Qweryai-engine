from zoho_mcp.mcp_client import get_mcp_tools
from utils.logger import get_logger

logger = get_logger(__name__)


async def load_zoho_tools():
    """Load Zoho tools from MCP server as-is."""
    tools = await get_mcp_tools()
    logger.info(f"[ZohoTools] Loaded: {[t.name for t in tools]}")
    return tools