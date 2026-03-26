import json
import re
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from langchain_core.messages import HumanMessage, AIMessageChunk, ToolMessage

from agentic_rag import build_graph
from data_model.chat_model import MessagesRequest, ChatMessage
from utils.helpers import build_message_history
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


async def stream_graph(payload: MessagesRequest) -> AsyncGenerator[str, None]:
    zoho_email = payload.zoho_email or payload.customer_id

    # No token needed — MCP server fetches from DB by email 
    graph = await build_graph(
        customer_id=payload.customer_id,
        firstname=payload.firstname,
        lastname=payload.lastname,
        zoho_email=zoho_email,
    )

    message_history = build_message_history(payload.chat_history)
    message_history.append(HumanMessage(content=payload.message))

    initial_state = {
        "messages":        message_history,
        "customer_id":     payload.customer_id,
        "firstname":       payload.firstname,
        "lastname":        payload.lastname,
        "zoho_email":      zoho_email,
        "sources":         [],
        "ticket_response": {},
    }

    config = {
        "configurable": {
            "customer_id": payload.customer_id,
            "firstname":   payload.firstname,
            "lastname":    payload.lastname,
            "zoho_email":  zoho_email,
        }
    }

    full_response = ""
    final_sources = []
    seen_sources  = set()

    try:
        async for chunk, metadata in graph.astream(
            initial_state, config=config, stream_mode="messages",
        ):
            if isinstance(chunk, AIMessageChunk) and chunk.content:
                token = chunk.content
                full_response += token
                yield json.dumps({"type": "response", "content": token}) + "\n\n"

            if isinstance(chunk, ToolMessage) and chunk.name == "doc_search_tool":
                for match in re.findall(r'\[Source: (.+?)\]', chunk.content or ""):
                    if match not in seen_sources:
                        seen_sources.add(match)
                        final_sources.append({
                            "title":  match.split("/")[-1].replace(".pdf", "").replace("_", " "),
                            "source": match,
                        })

        if final_sources:
            yield json.dumps({"type": "metadata", "content": final_sources}) + "\n\n"

        updated_history = payload.chat_history + [
            ChatMessage(role="user",      content=payload.message),
            ChatMessage(role="assistant", content=full_response),
        ]
        yield json.dumps({"type": "history_update", "content": [m.model_dump() for m in updated_history]}) + "\n\n"
        yield json.dumps({"type": "done", "content": ""}) + "\n\n"

    except Exception as e:
        logger.error(f"[stream_graph] Error: {e}")

        yield json.dumps({
            "type": "error",
            "content": "⚠️ Unable to fetch your profile. Please try again."
        }) + "\n\n"    


@router.get("/messages")
async def get_messages():
    return JSONResponse(content={"messages": []})


@router.post("/messages")
async def send_message(payload: MessagesRequest):
    logger.info(f"[/messages] customer_id={payload.customer_id} | message={payload.message}")
    return StreamingResponse(
        stream_graph(payload),
        media_type="text/event-stream",
        status_code=200,
    )


@router.get("/health")
def health():
    return {"status": "ok"}