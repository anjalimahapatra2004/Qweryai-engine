import os
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
from utils.logger import get_logger
from utils.config import settings

logger = get_logger("mcp_server")

ZOHO_BASE = settings.zoho_base_url

def auth_header(token: str) -> dict:
    return {"Authorization": f"Zoho-oauthtoken {token}"}


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 1 — Get Employee Record
# Endpoint: GET /api/forms/employee/getRecords
# Params  : searchColumn=EmailID, searchValue=<email>
# ══════════════════════════════════════════════════════════════════════════════

async def get_employee_record(
    access_token:   str,
    employee_email: str,
) -> dict:
    """
    Fetch Zoho People profile of an employee by work email.
    Returns employee_zoho_id (numeric), full_name, designation, department,
    reporting_manager, date_of_joining, work_location, employment_status.
    Call this FIRST before any leave operation to get employee_zoho_id.

    Args:
        access_token   (str): Zoho OAuth access token.
        employee_email (str): Work email e.g. anjali.mahapatra@prodevans.com
    """
    logger.info(f"[Tool] get_employee_record | email={employee_email}")

    if not employee_email or "@prodevans.com" not in employee_email:
        return {"error": "Valid @prodevans.com email is required."}
    if not access_token:
        return {"error": "Zoho access token is missing."}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{ZOHO_BASE}/api/forms/P_EmployeeView/records",
                headers=auth_header(access_token),
                params={
                    "searchColumn": "EMPLOYEEMAILALIAS",
                    "searchValue":  employee_email,
                    "limit":        "1",
                },
            )
        logger.info(f"[Tool] Employee status={resp.status_code} body={resp.text[:400]}")
        data = resp.json()

        # Handle error dict response
        if isinstance(data, dict):
            errors = data.get("response", {}).get("errors", {})
            if isinstance(errors, dict) and errors.get("code") in [7218, 401]:
                return {"error": "Invalid OAuth scope or expired token."}
            return {"error": f"Zoho error: {data.get('response', {}).get('message', 'Unknown error')}"}

        # P_EmployeeView returns plain list
        if not isinstance(data, list) or not data:
            return {"error": f"No employee found with email {employee_email}."}

        rec = data[0]
        employee_zoho_id = str(rec.get("recordId", ""))

        logger.info(f"[Tool] get_employee_record success | zoho_id={employee_zoho_id} | name={rec.get('Full Name', '')}")

        return {
            "employee_zoho_id": employee_zoho_id,
            "employee_record": rec,
        }

    except Exception as e:
        logger.error(f"[Tool] get_employee_record error: {e}")
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 2 — Get Leave Balance
# Endpoint: GET /people/api/v2/leavetracker/reports/user
# Params  : employee=<erecno (Long)>
# Scope   : ZOHOPEOPLE.leave.READ
# ══════════════════════════════════════════════════════════════════════════════

async def get_leave_balance(
    access_token:     str,
    employee_zoho_id: Any,
) -> dict:
    """
    Fetch leave balance for all leave types of an employee.
    Returns list of leave types with leavetypeID, leavetypeName, available, taken.
    MUST call this before apply_leave to get the correct numeric leavetypeID.

    Args:
        access_token     (str): Zoho OAuth access token.
        employee_zoho_id (str): Numeric Zoho ID from get_employee_record e.g. 46224000012838001
    """
    logger.info(f"[Tool] get_leave_balance | employee_zoho_id={employee_zoho_id}")

    if not employee_zoho_id:
        return {"error": "employee_zoho_id is required. Call get_employee_record first."}
    if not access_token:
        return {"error": "Zoho access token is missing."}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{ZOHO_BASE}/people/api/v2/leavetracker/reports/user",
                headers=auth_header(access_token),
                params={"employee": str(employee_zoho_id)},
            )
        logger.info(f"[Tool] Leave balance status={resp.status_code} body={resp.text[:500]}")
        data = resp.json()

        if "error" in data:
            return {"error": f"Zoho error: {data['error'].get('message', str(data['error']))}"}

        # Response format per docs:
        # {"employeeName": "...", "leavetypes": [{"leavetypeID": ..., "leavetypeName": ..., "available": ..., "taken": ...}]}
        leave_types = data.get("leavetypes", [])
        if not leave_types:
            return {"error": "No leave types found. Check employee_zoho_id or token scope."}

        balance_list = []
        for lt in leave_types:
            balance_list.append({
                "leave_type_id"   : str(lt.get("leavetypeID",   "")),
                "leave_type_name" : lt.get("leavetypeName", ""),
                "days_available"  : float(lt.get("available", 0)),
                "days_taken"      : float(lt.get("taken",     0)),
                "leave_unit"      : lt.get("unit", "Day"),
                "leave_type_type" : lt.get("type", ""),
            })

        logger.info(f"[Tool] get_leave_balance success | {len(balance_list)} types")
        return {
            "employee_name"    : data.get("employeeName", ""),
            "leave_balance_list": balance_list,
        }

    except Exception as e:
        logger.error(f"[Tool] get_leave_balance error: {e}")
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 3 — Get Leave Records
# Endpoint: GET /people/api/v2/leavetracker/leaves/records
# Params  : from*, to*  (date strings)
# Scope   : ZOHOPEOPLE.leave.READ
# ══════════════════════════════════════════════════════════════════════════════

async def get_leave_records(
    access_token:      str,
    employee_zoho_id:  Any,
    number_of_records: int = 10,
) -> dict:
    """
    Fetch recent leave history of an employee for the current year.
    Returns leave records with leave_record_id needed for cancellation.

    Args:
        access_token      (str): Zoho OAuth access token.
        employee_zoho_id  (str): Numeric Zoho ID from get_employee_record.
        number_of_records (int): Number of records. Default 10, max 20.
    """
    number_of_records = min(int(number_of_records), 20)
    logger.info(f"[Tool] get_leave_records | employee_zoho_id={employee_zoho_id}")

    if not access_token:
        return {"error": "Zoho access token is missing."}

    today         = datetime.today()
    from_date     = f"01-Jan-{today.year}"
    to_date       = f"31-Dec-{today.year}"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{ZOHO_BASE}/people/api/v2/leavetracker/leaves/records",
                headers=auth_header(access_token),
                params={
                    "from":  from_date,
                    "to":    to_date,
                    "limit": number_of_records,
                },
            )
        logger.info(f"[Tool] Leave records status={resp.status_code} body={resp.text[:500]}")
        data = resp.json()

        raw     = data.get("records", {})
        records = []
        for rid, rdata in raw.items():
            days_dict  = rdata.get("Days", {})
            total_days = sum(float(d.get("LeaveCount", 0)) for d in days_dict.values())
            records.append({
                "leave_record_id" : str(rid),
                "leave_type_name" : rdata.get("Leavetype",      ""),
                "leave_from_date" : rdata.get("From",           ""),
                "leave_to_date"   : rdata.get("To",             ""),
                "number_of_days"  : total_days,
                "approval_status" : rdata.get("ApprovalStatus", ""),
                "leave_reason"    : rdata.get("Reasonforleave", ""),
            })

        logger.info(f"[Tool] get_leave_records success | count={len(records)}")
        return {"leave_records": records}

    except Exception as e:
        logger.error(f"[Tool] get_leave_records error: {e}")
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 4 — Apply Leave
# Endpoint: POST /people/api/forms/json/leave/insertRecord
# Params  : inputData={'Employee_ID':...,'Leavetype':...,'From':...,'To':...,'days':{...}}
# Scope   : ZOHOPEOPLE.leave.CREATE
# ══════════════════════════════════════════════════════════════════════════════

async def apply_leave(
    access_token:     str,
    employee_zoho_id: Any,
    leave_type_id:    Any,
    leave_from_date:  str,
    leave_to_date:    str,
    leave_reason:     str,
) -> dict:
    """
    Submit a leave application to Zoho People.
    IMPORTANT: Call get_employee_record then get_leave_balance first.
    leave_type_id MUST be numeric ID from get_leave_balance e.g. 46224000000210011.

    Args:
        access_token     (str): Zoho OAuth access token.
        employee_zoho_id (str): Numeric Zoho ID from get_employee_record.
        leave_type_id    (str): Numeric leave type ID from get_leave_balance.
        leave_from_date  (str): Start date DD-MMM-YYYY e.g. 15-Mar-2026.
        leave_to_date    (str): End date DD-MMM-YYYY e.g. 16-Mar-2026.
        leave_reason     (str): Reason for leave e.g. fever.
    """
    logger.info(f"[Tool] apply_leave | {employee_zoho_id} | {leave_from_date} → {leave_to_date} | type={leave_type_id}")

    if not employee_zoho_id: return {"error": "employee_zoho_id required."}
    if not leave_type_id:    return {"error": "leave_type_id required. Call get_leave_balance first."}
    if not leave_from_date:  return {"error": "leave_from_date required in DD-MMM-YYYY format."}
    if not leave_to_date:    return {"error": "leave_to_date required in DD-MMM-YYYY format."}
    if not leave_reason:     return {"error": "leave_reason required."}
    if not access_token:     return {"error": "Zoho access token missing."}

    # Cast to string and validate numeric
    leave_type_id = str(leave_type_id).strip()
    if not leave_type_id.isdigit():
        return {"error": f"leave_type_id must be numeric e.g. 46224000000210011, not '{leave_type_id}'. Call get_leave_balance first."}

    try:
        # Build days dict as per Zoho docs
        fmt      = "%d-%b-%Y"
        from_dt  = datetime.strptime(leave_from_date, fmt)
        to_dt    = datetime.strptime(leave_to_date,   fmt)
        days_dict = {}
        cur = from_dt
        while cur <= to_dt:
            days_dict[cur.strftime(fmt)] = {"LeaveCount": 1.0}
            cur += timedelta(days=1)

        # Build inputData string — Zoho expects Python dict format NOT JSON
        # e.g. {'Employee_ID':'123','Leavetype':'456','From':01-Jan-2026,...}
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

        logger.info(f"[Tool] apply_leave inputData={input_data}")

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{ZOHO_BASE}/people/api/forms/json/leave/insertRecord",
                headers=auth_header(access_token),
                params={"inputData": input_data},
            )
        logger.info(f"[Tool] Apply leave status={resp.status_code} body={resp.text[:1000]}")
        data = resp.json()

        result  = data.get("response", {}).get("result",  {})
        message = data.get("response", {}).get("message", "")
        leave_id = result.get("pkId", "")

        if "successfully" in message.lower() or leave_id:
            return {"status": "success", "applied_leave_id": leave_id, "message": "Leave applied successfully."}
        return {"error": message or f"Leave application failed: {data}"}

    except Exception as e:
        logger.error(f"[Tool] apply_leave error: {e}")
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# TOOL 5 — Cancel Leave
# Endpoint: PATCH /people/api/v2/leavetracker/leaves/records/cancel/{leave_record_id}
# Scope   : ZOHOPEOPLE.leave.UPDATE
# ══════════════════════════════════════════════════════════════════════════════

async def cancel_leave(
    access_token:        str,
    employee_email:      str,
    leave_record_id:     Any,
    cancellation_reason: str = "Cancelled by employee",
) -> dict:
    """
    Cancel an existing leave application in Zoho People.
    Call get_leave_records first to get leave_record_id if not known.

    Args:
        access_token        (str): Zoho OAuth access token.
        employee_email      (str): employee email
        leave_record_id     (str): Leave record ID from get_leave_records.
        cancellation_reason (str): Reason for cancellation.
    """
    logger.info(f"[Tool] cancel_leave | leave_record_id={leave_record_id}")
    logger.info(f"[Tool] leave record id {leave_record_id}")
    if not leave_record_id:
        employee_records = await get_employee_record(access_token, employee_email)
        employee_id = employee_records['employee_zoho_id']
        logger.info(f"[Tool] employee_id:{employee_id}")
        leave_records = await get_leave_records(access_token, employee_id)
        return {"error": "leave_record_id required. Call get_leave_records first."}

    leave_record_id = str(leave_record_id).strip().strip('"')
    logger.info(f"[Tool] leave record id {leave_record_id}")
    if not access_token: return {"error": "Zoho access token missing."}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.patch(
                f"{ZOHO_BASE}/people/api/v2/leavetracker/leaves/records/cancel/{leave_record_id}",
                headers={
                    "Authorization": f"Zoho-oauthtoken {access_token}",
                },
            )
            logger.info(f"[Tool] response : {resp.request.headers}")
            logger.info(f"[Tool]response  :{resp.request.content}")
        logger.info(f"[Tool] Cancel leave status={resp.status_code} body={resp.text[:400]} response: {resp.json()}")
        data = resp.json()

        message = data.get("response", {}).get("message", "")
        if resp.status_code == 200 or "success" in message.lower():
            return {"status": "success", "message": "Leave cancelled successfully."}
        return {"error": message or f"Cancel failed: {data}"}

    except Exception as e:
        logger.error(f"[Tool] cancel_leave error: {e}")
        return {"error": str(e)}

def registerable_tools():
    return [
        get_employee_record,
        get_leave_balance,
        get_leave_records, 
        
        apply_leave,
        cancel_leave
    ]

