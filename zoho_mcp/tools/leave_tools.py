import os
from datetime import datetime, timedelta
from typing import Any

import httpx
from db.oauth_store import get_user, update_tokens
from utils.logger import get_logger
from utils.config import settings

logger = get_logger("mcp_server")

ZOHO_BASE  = settings.zoho_base_url
OAUTH_BASE = "https://accounts.zoho.in"
LOGIN_URL  = os.getenv("FASTAPI_URL", "http://localhost:8002") + "/auth/zoho/login"

LOGIN_REQUIRED_RESPONSE = {
    "error": "login_required",
    "message": (
        "\U0001f512 You are not logged in or your session has expired.\n\n"
        f"Login here: {LOGIN_URL}"
    ),
}


def auth_header(token: str) -> dict:
    return {"Authorization": f"Zoho-oauthtoken {token}"}


#  Token fetcher with auto refresh 

async def get_token(employee_email: str) -> str | dict:
    """
    Fetch a valid access token for the given employee email.

    Flow:
    1. Check user exists in DB
    2. Validate current access token against Zoho
    3. If expired → auto refresh using refresh token → save new token to DB
    4. If refresh fails → return LOGIN_REQUIRED_RESPONSE
    """
    if not employee_email:
        return LOGIN_REQUIRED_RESPONSE

    # Step 1: fetch user from DB
    try:
        user = await get_user(employee_email)
        if not user:
            logger.warning(f"[Auth] User not found in DB: {employee_email}")
            return LOGIN_REQUIRED_RESPONSE
    except Exception as error:
        logger.error(f"[Auth] DB error: {error}")
        return LOGIN_REQUIRED_RESPONSE

    access_token = user.get("access_token")
    if not access_token:
        return LOGIN_REQUIRED_RESPONSE

    # Step 2: validate current token
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{OAUTH_BASE}/oauth/user/info",
                headers=auth_header(access_token),
            )
        if response.status_code == 200:
            logger.info(f"[Auth] Token valid for {employee_email}")
            return access_token
    except Exception as error:
        logger.error(f"[Auth] Token validation error: {error}")
        return LOGIN_REQUIRED_RESPONSE

    # Step 3: token expired → try refresh
    logger.info(f"[Auth] Token expired for {employee_email} — attempting refresh")
    refresh_token = user.get("refresh_token")
    if not refresh_token:
        logger.warning(f"[Auth] No refresh token for {employee_email}")
        return LOGIN_REQUIRED_RESPONSE

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            refresh_response = await client.post(
                os.getenv("ZOHO_TOKEN_URL", "https://accounts.zoho.in/oauth/v2/token"),
                params={
                    "grant_type":    "refresh_token",
                    "client_id":     os.getenv("ZOHO_CLIENT_ID"),
                    "client_secret": os.getenv("ZOHO_CLIENT_SECRET"),
                    "refresh_token": refresh_token,
                },
            )

        if refresh_response.status_code != 200:
            logger.warning(f"[Auth] Refresh failed for {employee_email}")
            return LOGIN_REQUIRED_RESPONSE

        token_data       = refresh_response.json()
        new_access_token = token_data.get("access_token")
        expires_in       = token_data.get("expires_in", 3600)

        if not new_access_token:
            return LOGIN_REQUIRED_RESPONSE

        # Save new token to DB
        await update_tokens(employee_email, new_access_token, expires_in)
        logger.info(f"[Auth] Token refreshed successfully for {employee_email}")
        return new_access_token

    except Exception as error:
        logger.error(f"[Auth] Refresh error: {error}")
        return LOGIN_REQUIRED_RESPONSE


#  Date helpers 

SUPPORTED_DATE_FORMATS = [
    "%d-%b-%Y",
    "%d %B %Y",
    "%B %d %Y",
    "%B %d, %Y",
    "%Y-%m-%d",
    "%d/%m/%Y",
]


def normalize_date(date_str: str) -> str:
    """Normalize any user-supplied date string to DD-MMM-YYYY for Zoho API."""
    date_str = date_str.strip()
    today    = datetime.today()
    relative = {
        "today":     today,
        "tomorrow":  today + timedelta(days=1),
        "yesterday": today - timedelta(days=1),
    }
    if date_str.lower() in relative:
        return relative[date_str.lower()].strftime("%d-%b-%Y")

    for fmt in SUPPORTED_DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).strftime("%d-%b-%Y")
        except ValueError:
            continue

    raise ValueError(f"Cannot parse date: '{date_str}'. Use format like 24-Mar-2026")


def is_weekend(date_str: str) -> bool:
    """Return True if the given DD-MMM-YYYY date falls on Saturday or Sunday."""
    return datetime.strptime(date_str, "%d-%b-%Y").weekday() >= 5


def get_weekday_name(date_str: str) -> str:
    return datetime.strptime(date_str, "%d-%b-%Y").strftime("%A")

# TOOL-1 GET- EMPLOYEE RECORD

async def get_employee_record(employee_email: str) -> dict:
    logger.info(f"[Tool] get_employee_record | {employee_email}")

    access_token = await get_token(employee_email)
    if isinstance(access_token, dict):
        return access_token

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{ZOHO_BASE}/api/forms/P_EmployeeView/records",
                headers=auth_header(access_token),
                params={
                    "searchColumn": "EMPLOYEEMAILALIAS",
                    "searchValue": employee_email,
                    "limit": "1",
                },
            )

        logger.info(f"[Tool] Status={response.status_code}")
        logger.info(f"[Tool] Raw response={response.text}")

        if response.status_code != 200:
            return {"error": f"Zoho API error {response.status_code}"}

        try:
            data = response.json()
        except Exception:
            return {"error": "Invalid JSON from Zoho API"}

        if not isinstance(data, list) or not data:
            return {"error": f"No employee found for {employee_email}"}

        record = data[0]

        return {
            "employee_zoho_id": str(record.get("recordId", "")),
            "employee_record": record,
        }

    except Exception as e:
        logger.error(f"[Tool] get_employee_record error: {e}")
        return {"error": str(e)}

# TOOL 2 — Get Leave Balance

async def get_leave_balance(employee_zoho_id: Any, employee_email: str) -> dict:
    """
    Fetch leave balance for all leave types of an employee.
    Returns list of leave types with leavetypeID, leavetypeName, available, taken.
    MUST call this before apply_leave to get the correct numeric leavetypeID.

    Args:
        employee_zoho_id (str): Numeric Zoho ID from get_employee_record.
        employee_email   (str): Work email for token lookup.
    """
    logger.info(f"[Tool] get_leave_balance | employee_zoho_id={employee_zoho_id}")

    access_token = await get_token(employee_email)
    if isinstance(access_token, dict):
        return access_token

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{ZOHO_BASE}/people/api/v2/leavetracker/reports/user",
                headers=auth_header(access_token),
                params={"employee": str(employee_zoho_id)},
            )
        logger.info(f"[Tool] Leave balance status={response.status_code}")
        data = response.json()

        leave_types = data.get("leavetypes", [])
        if not leave_types:
            return {"error": "No leave types found."}

        balance_list = []
        for leave_type in leave_types:
            balance_list.append({
                "leave_type_id":   str(leave_type.get("leavetypeID",   "")),
                "leave_type_name": leave_type.get("leavetypeName", ""),
                "days_available":  float(leave_type.get("available", 0)),
                "days_taken":      float(leave_type.get("taken",     0)),
                "leave_unit":      leave_type.get("unit", "Day"),
            })

        logger.info(f"[Tool] get_leave_balance success | {len(balance_list)} types")
        return {
            "employee_name":      data.get("employeeName", ""),
            "leave_balance_list": balance_list,
        }

    except Exception as error:
        logger.error(f"[Tool] get_leave_balance error: {error}")
        return {"error": str(error)}


# TOOL 3 — Get Leave Records

async def get_leave_records(employee_zoho_id: Any, employee_email: str) -> dict:
    """
    Fetch recent leave history of an employee for the current year.
    Returns leave records with leave_record_id needed for cancellation.

    Args:
        employee_zoho_id (str): Numeric Zoho ID from get_employee_record.
        employee_email   (str): Work email for token lookup.
    """
    logger.info(f"[Tool] get_leave_records | employee_zoho_id={employee_zoho_id}")

    access_token = await get_token(employee_email)
    if isinstance(access_token, dict):
        return access_token

    today     = datetime.today()
    from_date = f"01-Jan-{today.year}"
    to_date   = f"31-Dec-{today.year}"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{ZOHO_BASE}/people/api/v2/leavetracker/leaves/records",
                headers=auth_header(access_token),
                params={"from": from_date, "to": to_date},
            )
        logger.info(f"[Tool] Leave records status={response.status_code}")
        data = response.json()

        records = []
        for record_id, record_data in data.get("records", {}).items():
            days_dict  = record_data.get("Days", {})
            total_days = sum(float(day.get("LeaveCount", 0)) for day in days_dict.values())
            records.append({
                "leave_record_id": str(record_id),
                "leave_type_name": record_data.get("Leavetype",      ""),
                "leave_from_date": record_data.get("From",           ""),
                "leave_to_date":   record_data.get("To",             ""),
                "number_of_days":  total_days,
                "approval_status": record_data.get("ApprovalStatus", ""),
                "leave_reason":    record_data.get("Reasonforleave", ""),
            })

        logger.info(f"[Tool] get_leave_records success | count={len(records)}")
        return {"leave_records": records}

    except Exception as error:
        logger.error(f"[Tool] get_leave_records error: {error}")
        return {"error": str(error)}


# TOOL 4 — Apply Leave

async def apply_leave(
    employee_zoho_id: Any,
    employee_email:   str,
    leave_type_id:    Any,
    leave_from_date:  str,
    leave_to_date:    str,
    leave_reason:     str,
) -> dict:
    """
    Submit a leave application to Zoho People.
    Call get_employee_record then get_leave_balance first.
    leave_type_id MUST be numeric ID from get_leave_balance.

    Args:
        employee_zoho_id (str): Numeric Zoho ID from get_employee_record.
        employee_email   (str): Work email for token lookup.
        leave_type_id    (str): Numeric leave type ID from get_leave_balance.
        leave_from_date  (str): Start date e.g. "tomorrow", "24-Mar-2026".
        leave_to_date    (str): End date.
        leave_reason     (str): Reason for leave e.g. fever.
    """
    logger.info(f"[Tool] apply_leave | {employee_zoho_id} | {leave_from_date} → {leave_to_date}")

    access_token = await get_token(employee_email)
    if isinstance(access_token, dict):
        return access_token

    if not leave_type_id: return {"error": "leave_type_id required. Call get_leave_balance first."}
    if not leave_reason:  return {"error": "leave_reason required."}

    leave_type_id = str(leave_type_id).strip()
    if not leave_type_id.isdigit():
        return {"error": f"leave_type_id must be numeric, not '{leave_type_id}'."}

    try:
        leave_from_date = normalize_date(leave_from_date)
        leave_to_date   = normalize_date(leave_to_date)
    except ValueError as date_error:
        return {"error": str(date_error)}

    if is_weekend(leave_from_date) and is_weekend(leave_to_date):
        from_day = get_weekday_name(leave_from_date)
        to_day   = get_weekday_name(leave_to_date)
        return {
            "error": (
                f"\U0001f604 No leave required! {leave_from_date} is a {from_day}"
                + (f" and {leave_to_date} is a {to_day}" if leave_from_date != leave_to_date else "")
                + ", which is already a weekly holiday. Enjoy your day off! \U0001f389"
            )
        }

    try:
        fmt       = "%d-%b-%Y"
        from_dt   = datetime.strptime(leave_from_date, fmt)
        to_dt     = datetime.strptime(leave_to_date,   fmt)
        days_dict = {}
        current   = from_dt
        while current <= to_dt:
            if current.weekday() < 5:
                days_dict[current.strftime(fmt)] = {"LeaveCount": 1.0}
            current += timedelta(days=1)

        if not days_dict:
            return {
                "error": (
                    "\U0001f604 No leave required! The selected period falls entirely "
                    "on weekly holidays. Enjoy your time off! \U0001f389"
                )
            }

        input_data = (
            "{"
            f"'Employee_ID':'{employee_zoho_id}',"
            f"'Leavetype':'{leave_type_id}',"
            f"'From':{leave_from_date},"
            f"'To':{leave_to_date},"
            f"'Reasonforleave':'{leave_reason}',"
            f"'days':{str(days_dict).replace('True','true').replace('False','false')}"
            "}"
        )

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{ZOHO_BASE}/people/api/forms/json/leave/insertRecord",
                headers=auth_header(access_token),
                params={"inputData": input_data},
            )
        logger.info(f"[Tool] Apply leave status={response.status_code}")
        data     = response.json()
        result   = data.get("response", {}).get("result",  {})
        message  = data.get("response", {}).get("message", "")
        leave_id = result.get("pkId", "")

        if "successfully" in message.lower() or leave_id:
            return {"status": "success", "applied_leave_id": leave_id, "message": "Leave applied successfully."}
        return {"error": message or f"Leave application failed: {data}"}

    except Exception as error:
        logger.error(f"[Tool] apply_leave error: {error}")
        return {"error": str(error)}


# TOOL 5 — Cancel Leave

async def cancel_leave(
    employee_email:  str,
    leave_record_id: Any,
) -> dict:
    """
    Cancel an existing leave application in Zoho People.
    Call get_leave_records first to get leave_record_id if not known.

    Args:
        employee_email   (str): Work email for token lookup.
        leave_record_id  (str): Leave record ID from get_leave_records.
    """
    logger.info(f"[Tool] cancel_leave | leave_record_id={leave_record_id}")

    access_token = await get_token(employee_email)
    if isinstance(access_token, dict):
        return access_token

    if not leave_record_id:
        return {"error": "leave_record_id required. Call get_leave_records first."}

    leave_record_id = str(leave_record_id).strip().strip('"')

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.patch(
                f"{ZOHO_BASE}/people/api/v2/leavetracker/leaves/records/cancel/{leave_record_id}",
                headers=auth_header(access_token),
            )
        logger.info(f"[Tool] Cancel leave status={response.status_code}")
        data    = response.json()
        message = data.get("response", {}).get("message", "")

        if response.status_code == 200 or "success" in message.lower():
            return {"status": "success", "message": "Leave cancelled successfully."}
        return {"error": message or f"Cancel failed: {data}"}

    except Exception as error:
        logger.error(f"[Tool] cancel_leave error: {error}")
        return {"error": str(error)}


#  Register

def registerable_tools():
    return [
        get_employee_record,
        get_leave_balance,
        get_leave_records,
        apply_leave,
        cancel_leave,
    ]