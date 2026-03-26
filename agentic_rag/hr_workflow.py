import re
from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import AnyMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph.message import add_messages

from agentic_rag.tools.hr_tools import doc_search_tool
from agentic_rag.tools.ticket_tools import (
    search_user_tool,
    create_user_tool,
    raise_ticket_tool,
)
from agentic_rag.tools.zoho_tools import load_zoho_tools
from utils.llm import build_llm
from utils.system_prompt import build_system_prompt
from utils.logger import get_logger

logger = get_logger(__name__)


# STATE

class State(TypedDict):
    messages:        Annotated[list[AnyMessage], add_messages]
    customer_id:     str
    firstname:       str
    lastname:        str
    access_token:    str
    zoho_email:      str
    sources:         list[dict]
    ticket_response: dict

# ASSISTANT

class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        result = self.runnable.invoke(state)

        # Extract sources 
        sources = []
        for msg in state["messages"]:
            if isinstance(msg, ToolMessage) and msg.name == "doc_search_tool":
                matches = re.findall(r'\[Source: (.+?)\]', msg.content)
                for match in matches:
                    entry = {"title": match, "source": ""}
                    if entry not in sources:
                        sources.append(entry)

        return {"messages": result, "sources": sources}


llm = build_llm()

# GRAPH BUILDER

async def build_graph(
    customer_id: str,
    firstname:   str,
    lastname:    str,
    zoho_email:  str = "",
):
    try:
        zoho_tools = await load_zoho_tools()
        logger.info(f"[Graph] Loaded {len(zoho_tools)} Zoho tools")
    except Exception as e:
        logger.warning(f"[Graph] MCP not available: {e}")
        zoho_tools = []

    tools = [
        doc_search_tool,
        search_user_tool,
        create_user_tool,
        raise_ticket_tool,
        *zoho_tools,
    ]

    system_prompt = build_system_prompt(
        zoho_email=zoho_email,
        firstname=firstname,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ])

    assistant_runnable = prompt | llm.bind_tools(tools)

    builder = StateGraph(State)
    builder.add_node("assistant", Assistant(assistant_runnable))
    builder.add_node("tools",     ToolNode(tools))

    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")

    logger.info("[Graph] Compiled successfully")
    return builder.compile()