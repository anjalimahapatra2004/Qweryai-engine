from langchain_mcp_adapters.client import MultiServerMCPClient
from utils.config import MCP_SERVER_URL
from utils.logger import get_logger
 
logger = get_logger("mcp_client")
 
 
async def get_mcp_tools():
    """
    Connect to MCP server and return all tools
    as LangChain-compatible tools for LangGraph.
    """
    logger.info(f"[MCPClient] Connecting to MCP server: {MCP_SERVER_URL}")
 
    client = MultiServerMCPClient(
        {
            "prodevans-hr-mcp": {
                "url":       MCP_SERVER_URL,
                "transport": "sse",
            }
        }
    )
    logger.info(f"{client.connections}")
    tools = await client.get_tools()
    logger.info(f"[MCPClient] Loaded {len(tools)} tools from MCP server")
    return tools