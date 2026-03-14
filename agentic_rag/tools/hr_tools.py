from langchain_core.tools import tool
from utils.rag import build_retriever
from utils.logger import get_logger

logger    = get_logger(__name__)
retriever = build_retriever()


@tool(
    description="""
    Search Prodevans company HR policies and documents.

    This tool:
    1. Takes a query string as input
    2. Searches the vector store for relevant HR documents
    3. Returns matching policy content including:
       - Leave policies (Privilege, Sick, Casual, Maternity, Paternity)
       - Attendance rules and work schedule
       - Holiday calendar
       - Compensatory off policy

    Args:
        query (str): The question or topic to search for in HR documents

    Returns:
        str: Relevant policy content retrieved from the vector store
    """
)
def doc_search_tool(query: str) -> str:
    """Search Prodevans HR policy documents."""
    logger.info(f"[doc_search_tool] query={query}")

    docs = retriever.invoke(query)

    if not docs:
        return "No relevant HR documents found for your query."

    results = []
    for doc in docs:
        source = doc.metadata.get("source", "")
        logger.info(f"[doc_search_tool] metadata={doc.metadata}")  # debug
        if source:
            results.append(f"{doc.page_content}\n[Source: {source}]")
        else:
            results.append(doc.page_content)

    return "\n\n".join(results)