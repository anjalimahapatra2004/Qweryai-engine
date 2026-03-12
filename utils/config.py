import os
from dotenv import load_dotenv

load_dotenv()

# LLM Provider 
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")       

# Models
LLM_MODEL    = os.getenv("LLM_MODEL",   "llama-3.3-70b-versatile")
EMBED_MODEL  = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

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