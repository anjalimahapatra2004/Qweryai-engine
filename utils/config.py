import os
from dotenv import load_dotenv

load_dotenv()

# LLM Provider
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")

# Models
LLM_MODEL   = os.getenv("LLM_MODEL",   "llama-3.3-70b-versatile")
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# API Keys
GROQ_API_KEY   = os.getenv("GROQ_API_KEY",   "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Ticket API
TICKET_API_BASE_URL = os.getenv("TICKET_API_BASE_URL", "")

# Vector Store
VECTOR_DB_TYPE      = os.getenv("VECTOR_DB_TYPE",      "pgvector")
PGVECTOR_CONNECTION = os.getenv("PGVECTOR_CONNECTION", "")
PGVECTOR_COLLECTION = os.getenv("PGVECTOR_COLLECTION", "documents")
MONGODB_URI         = os.getenv("MONGODB_URI",         "mongodb://localhost:27017")
MONGODB_DB          = os.getenv("MONGODB_DB",          "qweryai")
MONGODB_COLLECTION  = os.getenv("MONGODB_COLLECTION",  "document")

# Zoho (India region)
ZOHO_CLIENT_ID     = os.getenv("ZOHO_CLIENT_ID",     "")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET", "")
ZOHO_REFRESH_TOKEN = os.getenv("ZOHO_REFRESH_TOKEN", "")
ZOHO_ACCESS_TOKEN  = os.getenv("ZOHO_ACCESS_TOKEN",  "")
ZOHO_REDIRECT_URI  = os.getenv("ZOHO_REDIRECT_URI",  "http://localhost:8002/auth/zoho/callback")
ZOHO_TOKEN_URL     = os.getenv("ZOHO_TOKEN_URL",     "https://accounts.zoho.in/oauth/v2/token")
ZOHO_BASE_URL      = os.getenv("ZOHO_BASE_URL",      "https://people.zoho.in")
ALLOWED_DOMAIN     = os.getenv("ALLOWED_DOMAIN",     "prodevans.com")

# MCP Server
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/sse")

# FastAPI
APP_HOST    = os.getenv("APP_HOST",    "0.0.0.0")
APP_PORT    = int(os.getenv("APP_PORT", "8002"))
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8002")


# Settings object
class _Settings:
    zoho_base_url      = ZOHO_BASE_URL
    zoho_client_id     = ZOHO_CLIENT_ID
    zoho_client_secret = ZOHO_CLIENT_SECRET
    zoho_redirect_uri  = ZOHO_REDIRECT_URI
    zoho_token_url     = ZOHO_TOKEN_URL


settings = _Settings()