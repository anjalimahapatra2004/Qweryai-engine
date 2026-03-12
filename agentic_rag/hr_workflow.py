# from typing import Annotated
# from typing_extensions import TypedDict

# from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.runnables import Runnable, RunnableConfig
# from langgraph.graph import StateGraph, START, END
# from langgraph.prebuilt import ToolNode, tools_condition
# from langgraph.graph.message import add_messages

# from agentic_rag.tools.hr_tools import (
#     doc_search_tool,
# )
# from agentic_rag.tools.ticket_tools import (
#     search_user_tool,
#     create_user_tool,
#     raise_ticket_tool,
# )
# from utils.llm import build_llm
# from utils.logger import get_logger

# logger = get_logger(__name__)

# # STATE

# class State(TypedDict):
#     messages:        Annotated[list[AnyMessage], add_messages]
#     customer_id:     str
#     firstname:       str
#     lastname:        str
#     sources:         list[dict]
#     ticket_response: dict


# # ASSISTANT

# class Assistant:
#     def __init__(self, runnable: Runnable):
#         self.runnable = runnable

#     def __call__(self, state: State, config: RunnableConfig):
#         while True:
#             configuration = config.get("configurable", {})
#             customer_id   = configuration.get("customer_id", "")
#             firstname     = configuration.get("firstname",   "")
#             lastname      = configuration.get("lastname",    "")

#             logger.info(f"[Assistant] customer_id={customer_id}")

#             state = {**state, "customer_id": customer_id, "firstname": firstname, "lastname": lastname}

#             result = self.runnable.invoke(state)

#             # Re-prompt if LLM returns empty response
#             if not result.tool_calls and (
#                 not result.content
#                 or isinstance(result.content, list)
#                 and not result.content[0].get("text")
#             ):
#                 messages = state["messages"] + [("user", "Respond with a real output.")]
#                 state = {**state, "messages": messages}
#             else:
#                 break

#         # Extract sources from tool messages 
#         sources = []
#         for msg in state["messages"]:
#             if isinstance(msg, ToolMessage) and msg.name == "doc_search_tool":
#                 # Parse [Source: filename] tags from tool output
#                 import re
#                 matches = re.findall(r'\[Source: (.+?)\]', msg.content)
#                 for match in matches:
#                     source_entry = {"title": match, "source": ""}
#                     if source_entry not in sources:
#                         sources.append(source_entry)

#         return {"messages": result, "sources": sources}


# # LLM  (provider set in .env — groq | openai | ollama)

# llm = build_llm()

# # PROMPT

# primary_assistant_prompt = ChatPromptTemplate.from_messages([
#     (
#         "system",
#         """You are a helpful assistant. Your name is Qwery.AI, developed by Prodevans Innovation Hub.

# You work for Prodevans Technologies.

# STRICT RULES — follow always:
# 1. ALWAYS call doc_search_tool FIRST before answering any HR policy question. Never answer from memory.
# 2. Only answer based on what doc_search_tool returns. If nothing is found, say "I could not find this information in our documents."
# 3. Never repeat the same information twice in one response.
# 4. If the user reports a problem or requests a support ticket:
#    - First ask: "I understand you are having an issue with [problem]. Would you like me to raise a support ticket?"
#    - Wait for explicit confirmation before calling any ticket tools.
#    - After confirmation: call search_user_tool → create_user_tool (if needed) → raise_ticket_tool.
#    - The customer_id is injected automatically. NEVER ask the user for their email.

# RESPONSE FORMATTING RULES — follow strictly:
# - Do NOT use ## or ### headings — the frontend does not render them.
# - Use **bold** for policy names and key labels only.
# - Use numbered lists (1. 2. 3.) for multiple policies.
# - Use bullet points (- ) for details under each policy.
# - Keep responses clean, structured, and concise.
# - Never dump raw unformatted text.

# Example format:
# 1. **Privilege Leave (PL)**
#    - **No. of Days**: 15 days per calendar year
#    - **Eligibility**: After probation period completion
#    - **Carry Forward**: Up to 30 days maximum

# 2. **Sick Leave (SL)**
#    - **No. of Days**: 10 days per calendar year
#    - **Eligibility**: Available from date of joining

# After every response add:
# ---
# For assistance, contact HR at Prodevans Technologies: ask@prodevans.com | +91 8095933365.

# Current user: {customer_id}"""
#     ),
#     ("placeholder", "{messages}"),
# ])

# # TOOL REGISTRATION

# tools = [
#     doc_search_tool,
#     search_user_tool,
#     create_user_tool,
#     raise_ticket_tool,
# ]

# assistant_runnable = primary_assistant_prompt | llm.bind_tools(tools)

# # GRAPH BUILDER

# def build_graph(customer_id: str, firstname: str, lastname: str):
#     builder = StateGraph(State)

#     builder.add_node("assistant", Assistant(assistant_runnable))
#     builder.add_node("tools",     ToolNode(tools))

#     builder.add_edge(START, "assistant")
#     builder.add_conditional_edges("assistant", tools_condition)
#     builder.add_edge("tools", "assistant")

#     logger.info("[Graph] Compiled successfully")
#     return builder.compile()



from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph.message import add_messages

from agentic_rag.tools.hr_tools import (
    doc_search_tool,
)
from agentic_rag.tools.ticket_tools import (
    search_user_tool,
    create_user_tool,
    raise_ticket_tool,
)
from utils.llm import build_llm
from utils.logger import get_logger

logger = get_logger(__name__)


# STATE

class State(TypedDict):
    messages:        Annotated[list[AnyMessage], add_messages]
    customer_id:     str
    firstname:       str
    lastname:        str
    sources:         list[dict]
    ticket_response: dict


# ASSISTANT

class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        while True:
            configuration = config.get("configurable", {})
            customer_id   = configuration.get("customer_id", "")
            firstname     = configuration.get("firstname",   "")
            lastname      = configuration.get("lastname",    "")

            logger.info(f"[Assistant] customer_id={customer_id}")

            state = {**state, "customer_id": customer_id, "firstname": firstname, "lastname": lastname}

            result = self.runnable.invoke(state)

            # Re-prompt if LLM returns empty response
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break

        # Extract sources from tool messages 
        sources = []
        for msg in state["messages"]:
            if isinstance(msg, ToolMessage) and msg.name == "doc_search_tool":
                # Parse [Source: filename] tags from tool output
                import re
                matches = re.findall(r'\[Source: (.+?)\]', msg.content)
                for match in matches:
                    source_entry = {"title": match, "source": ""}
                    if source_entry not in sources:
                        sources.append(source_entry)

        return {"messages": result, "sources": sources}


# LLM  (provider set in .env — groq | openai | ollama)

llm = build_llm()


# PROMPT

primary_assistant_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a helpful assistant. Your name is Qwery.AI, developed by Prodevans Innovation Hub.

You work for Prodevans Technologies.

STRICT RULES — follow always:
1. For greetings like "hi", "hello", "hey" — just greet back warmly. Do NOT call any tool.
2. ONLY call doc_search_tool when the user asks a specific HR policy question.
3. Only answer based on what doc_search_tool returns. If nothing is found, say "I could not find this information in our documents."
4. Never repeat the same information twice in one response.
5. If the user reports a problem or requests a support ticket:
   - First ask: "I understand you are having an issue with [problem]. Would you like me to raise a support ticket?"
   - Wait for explicit confirmation before calling any ticket tools.
   - After confirmation: call search_user_tool → create_user_tool (if needed) → raise_ticket_tool.
   - The customer_id is injected automatically. NEVER ask the user for their email.

RESPONSE FORMATTING RULES — follow strictly:
- Do NOT use ## or ### headings — the frontend does not render them.
- Use **bold** for policy names and key labels only.
- Use numbered lists (1. 2. 3.) for multiple policies.
- Use bullet points (- ) for details under each policy.
- Keep responses clean, structured, and concise.
- Never dump raw unformatted text.

Example format:
1. **Privilege Leave (PL)**
   - **No. of Days**: 15 days per calendar year
   - **Eligibility**: After probation period completion
   - **Carry Forward**: Up to 30 days maximum

2. **Sick Leave (SL)**
   - **No. of Days**: 10 days per calendar year
   - **Eligibility**: Available from date of joining

After every response add:
---
For assistance, contact HR at Prodevans Technologies: ask@prodevans.com | +91 8095933365.

Current user: {customer_id}"""
    ),
    ("placeholder", "{messages}"),
])


# TOOL REGISTRATION

tools = [
    doc_search_tool,
    search_user_tool,
    create_user_tool,
    raise_ticket_tool,
]

assistant_runnable = primary_assistant_prompt | llm.bind_tools(tools)


# GRAPH BUILDER

def build_graph(customer_id: str, firstname: str, lastname: str):
    builder = StateGraph(State)

    builder.add_node("assistant", Assistant(assistant_runnable))
    builder.add_node("tools",     ToolNode(tools))

    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")

    logger.info("[Graph] Compiled successfully")
    return builder.compile()