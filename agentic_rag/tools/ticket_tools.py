from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from data_model.models import TicketInput, UserInput, SearchUserInput
from utils.helpers import search_user, create_user, raise_ticket
from utils.logger import get_logger

logger = get_logger(__name__)

# TOOLS

@tool(
    description="""
    Check whether the current user exists in the ticketing system.

    This tool:
    1. Takes the user's email (auto-injected from session)
    2. Calls the Prodevans ticketing API to search for the user
    3. Returns user information if found, or not-found status

    Args:
        email (str): User email — auto-injected from session, do not ask the user

    Returns:
        dict: API response containing user information or not-found message
    """,
    args_schema=SearchUserInput,
)
def search_user_tool(email: str = "", config: RunnableConfig = None) -> dict:
    """Check if user exists in the ticketing system."""
    customer_id = (config or {}).get("configurable", {}).get("customer_id", email)
    logger.info(f"[search_user_tool] customer_id={customer_id}")
    return search_user(email=customer_id)


@tool(
    description="""
    Create a new user in the Prodevans ticketing system.

    This tool:
    1. Should ONLY be called when search_user_tool confirms user does not exist
    2. Registers the user using session details (name and email auto-injected)
    3. Returns the created user information

    Args:
        title       (str, optional): User's job title
        subject     (str, optional): Subject of the request
        description (str, optional): Additional description

    Returns:
        dict: Created user information from the ticketing system
    """,
    args_schema=UserInput,
)
def create_user_tool(
    firstname:   str = "",
    lastname:    str = "",
    email:       str = "",
    title:       str = "",
    subject:     str = "",
    description: str = "",
    config: RunnableConfig = None,
) -> dict:
    """Create the current user in the ticketing system."""
    cfg         = (config or {}).get("configurable", {})
    customer_id = cfg.get("customer_id", email)
    firstname   = cfg.get("firstname",   firstname)
    lastname    = cfg.get("lastname",    lastname)
    logger.info(f"[create_user_tool] customer_id={customer_id}")
    return create_user(
        firstname=firstname,
        lastname=lastname,
        email=customer_id,
        title=title,
        subject=subject,
        description=description,
    )


@tool(
    description="""
    Raise a support ticket for the current user in the Prodevans ticketing system.

    This tool:
    1. Should ONLY be called after explicit user confirmation
    2. Follows the workflow: search_user_tool → create_user_tool (if needed) → raise_ticket_tool
    3. Submits the ticket and returns confirmation details

    Args:
        title   (str): Short title that summarises the problem
        body    (str): Full description of the problem
        subject (str): Subject line for the ticket article

    Returns:
        dict: Ticket details including ticket ID and status
    """,
    args_schema=TicketInput,
)
def raise_ticket_tool(
    title:       str = "",
    body:        str = "",
    subject:     str = "",
    customer_id: str = "",
    config: RunnableConfig = None,
) -> dict:
    """Raise a support ticket for the current user."""
    customer_id = (config or {}).get("configurable", {}).get("customer_id", customer_id)
    logger.info(f"[raise_ticket_tool] customer_id={customer_id} | title={title}")
    return raise_ticket(
        customer_id=customer_id,
        title=title,
        body=body,
        subject=subject,
    )