from langchain_huggingface import HuggingFaceEmbeddings
from utils.config import (
    EMBED_MODEL,
    VECTOR_DB_TYPE,
    PGVECTOR_CONNECTION, PGVECTOR_COLLECTION,
    MONGODB_URI, MONGODB_DB, MONGODB_COLLECTION,
)
from utils.logger import get_logger

logger = get_logger(__name__)


def _get_embeddings():
    logger.info(f"[RAG] Loading embedding model: {EMBED_MODEL}")
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)

# PGVECTOR

def _build_pgvector_retriever():
    from langchain_postgres import PGVector

    logger.info("[RAG] Connecting to PGVector...")
    vectorstore = PGVector(
        embeddings=_get_embeddings(),
        collection_name=PGVECTOR_COLLECTION,
        connection=PGVECTOR_CONNECTION,
    )
    logger.info("[RAG] PGVector retriever ready")
    return vectorstore.as_retriever(search_kwargs={"k": 5})


# MONGODB

def _build_mongodb_retriever():
    from langchain_mongodb import MongoDBAtlasVectorSearch
    from pymongo import MongoClient

    logger.info("[RAG] Connecting to MongoDB")
    client      = MongoClient(MONGODB_URI)
    collection  = client[MONGODB_DB][MONGODB_COLLECTION]
    vectorstore = MongoDBAtlasVectorSearch(
        collection=collection,
        embedding=_get_embeddings(),
        index_name="vector_index",
        text_key="text",
        embedding_key="embedding",
    )
    logger.info("[RAG] MongoDB retriever ready")
    return vectorstore.as_retriever(search_kwargs={"k": 5})


# PUBLIC ENTRY POINT

def build_retriever():
    """
    Returns a retriever based on VECTOR_DB_TYPE in .env.
    Use anywhere in the project:

        from utils.rag import build_retriever
        retriever = build_retriever()
    """
    logger.info(f"[RAG] VECTOR_DB_TYPE = {VECTOR_DB_TYPE}")

    if VECTOR_DB_TYPE == "pgvector":
        return _build_pgvector_retriever()
    elif VECTOR_DB_TYPE == "mongodb":
        return _build_mongodb_retriever()
    else:
        raise ValueError(f"Unknown VECTOR_DB_TYPE: '{VECTOR_DB_TYPE}'. Use pgvector or mongodb")