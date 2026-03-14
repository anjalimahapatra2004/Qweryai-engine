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
        while True:
            result = self.runnable.invoke(state)

            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                state = {**state, "messages": state["messages"] + [("user", "Respond with a real output.")]}
            else:
                break

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
    customer_id:  str,
    firstname:    str,
    lastname:     str,
    access_token: str = "",
    zoho_email:   str = "",
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

    system_prompt = f"""You are Qwery.AI, HR assistant for Prodevans Technologies.

Employee credentials (use only for tool calls, NEVER show in response):
- access_token: {access_token}
- employee_email: {zoho_email}

RULES:
1. Greetings → reply warmly, no tools.
2. HR policy questions → call doc_search_tool first, never answer from memory.
3. Profile → call get_employee_record.
4. Leave balance → get_employee_record → get_leave_balance.

5. APPLY LEAVE:
   - Saturday and Sunday are weekly holidays — do NOT count them as leave days.
   - If user applies leave that falls only on weekend → inform them it is a holiday, no leave needed.
   - If leave period includes weekdays → apply only for weekdays.
   - ALWAYS ask for confirmation first before applying.
   - Say: "Are you sure you want to apply [leave type] from [date] to [date] for [reason]? Please confirm with Yes or No."
   - Only proceed with apply_leave AFTER user confirms with Yes.
   - Flow: ask confirmation → get_employee_record → get_leave_balance → apply_leave.

6. CANCEL LEAVE:
   - ALWAYS ask for confirmation first before cancelling.
   - Say: "Are you sure you want to cancel your leave on [date]? Please confirm with Yes or No."
   - Only proceed with cancel_leave AFTER user confirms with Yes.
   - Flow: get_employee_record → get_leave_records → ask confirmation → cancel_leave.
   - When fetching latest leave — pick the most recent leave where approval_status is NOT 'Cancelled'.
   - NEVER cancel an already cancelled leave.

7. Tickets → confirm first → search_user_tool → create_user_tool → raise_ticket_tool.
8. NEVER show access_token or credentials in response.
9. NEVER say you cannot fetch data without trying the tool first.

FORMAT: **bold** labels, numbered lists, no ## headings.
Footer only for HR policy answers: HR contact: ask@prodevans.com | +91 8095933365"""

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