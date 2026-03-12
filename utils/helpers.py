import requests
from langchain_core.messages import HumanMessage, AIMessage
from utils.config import TICKET_API_BASE_URL

# MESSAGE HISTORY HELPER

def build_message_history(chat_history) -> list:
    message_history = []
    for chat_message in chat_history:
        if chat_message.role == "user":
            message_history.append(HumanMessage(content=chat_message.content))
        elif chat_message.role == "assistant":
            message_history.append(AIMessage(content=chat_message.content))
    return message_history


# TICKET API HELPERS

def search_user(email: str) -> dict:
    url     = f"{TICKET_API_BASE_URL}/searchEmail"
    headers = {"accept": "*/*", "x-app-id": "prodevans", "x-app-internal": "true"}
    try:
        response = requests.get(url, headers=headers, json={"email": email}, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}


def create_user(firstname: str, lastname: str, email: str, title: str = "", subject: str = "", description: str = "") -> dict:
    url     = f"{TICKET_API_BASE_URL}/createUser"
    headers = {"accept": "*/*", "x-app-id": "prodevans", "x-app-internal": "true", "Content-Type": "application/json"}
    payload = {
        "firstname":   firstname,
        "lastname":    lastname,
        "email":       email,
        "phone":       "+919876543290",
        "title":       title       or "string",
        "subject":     subject     or "string",
        "description": description or "string",
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}


def raise_ticket(customer_id: str, title: str, body: str, subject: str) -> dict:
    url     = f"{TICKET_API_BASE_URL}/createTicket"
    headers = {"accept": "*/*", "x-app-id": "Prodevans", "x-app-internal": "true", "Content-Type": "application/json"}
    payload = {
        "title":       title,
        "group":       "QweryAI",
        "customer_id": customer_id,
        "web":         "QweryAI",
        "article": {
            "subject":  subject,
            "body":     body,
            "type":     "web",
            "state":    "new",
            "internal": False,
        },
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}