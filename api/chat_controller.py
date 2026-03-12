import json
from typing import Generator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from langchain_core.messages import HumanMessage, AIMessageChunk

from agentic_rag import build_graph
from data_model.chat_model import MessagesRequest, ChatMessage
from utils.helpers import build_message_history
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# STREAMING GENERATOR — single pass, captures sources from updates stream

def stream_graph(payload: MessagesRequest) -> Generator[str, None, None]:
    graph = build_graph(
        customer_id=payload.customer_id,
        firstname=payload.firstname,
        lastname=payload.lastname,
    )

    message_history = build_message_history(payload.chat_history)
    message_history.append(HumanMessage(content=payload.message))

    initial_state = {
        "messages":        message_history,
        "customer_id":     payload.customer_id,
        "firstname":       payload.firstname,
        "lastname":        payload.lastname,
        "sources":         [],
        "ticket_response": {},
    }

    config = {
        "configurable": {
            "customer_id": payload.customer_id,
            "firstname":   payload.firstname,
            "lastname":    payload.lastname,
        }
    }

    full_response   = ""
    final_sources   = []
    ticket_response = {}

    try:
        # Single pass: stream tokens + capture sources
        for chunk, metadata in graph.stream(
            initial_state,
            config=config,
            stream_mode="messages",
        ):
            if isinstance(chunk, AIMessageChunk) and chunk.content:
                token = chunk.content
                full_response += token
                yield json.dumps({"type": "response", "content": token}) + "\n\n"

            # capture sources from state updates in metadata
            if isinstance(metadata, dict):
                langgraph_node = metadata.get("langgraph_node", "")
                if langgraph_node == "assistant":
                    state = metadata.get("__state__", {})
                    if state.get("sources"):
                        final_sources = state["sources"]
                        logger.info(f"[stream_graph] sources from metadata={final_sources}")

        logger.info(f"[stream_graph] final_sources={final_sources}")

        # Yield sources 
        if final_sources:
            yield json.dumps({"type": "metadata", "content": final_sources}) + "\n\n"

        #  Yield ticket response 
        if ticket_response:
            yield json.dumps({"type": "ticket", "content": ticket_response}) + "\n\n"

        # History update 
        updated_history = payload.chat_history + [
            ChatMessage(role="user",      content=payload.message),
            ChatMessage(role="assistant", content=full_response),
        ]
        yield json.dumps({"type": "history_update", "content": [m.model_dump() for m in updated_history]}) + "\n\n"

        yield json.dumps({"type": "done", "content": ""}) + "\n\n"

    except Exception as e:
        logger.error(f"[stream_graph] Error: {e}")
        yield json.dumps({"type": "error", "content": str(e)}) + "\n\n"


# ROUTES

@router.get("/messages")
async def get_messages():
    """Endpoint to retrieve all messages."""
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