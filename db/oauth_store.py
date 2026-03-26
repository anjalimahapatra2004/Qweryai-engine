import time
import json
import re
import asyncio
import asyncpg
from urllib.parse import unquote

from utils.config import PGVECTOR_CONNECTION
from utils.logger import get_logger

logger = get_logger(__name__)

pool: asyncpg.Pool | None = None


# Parse DB URL 

def _parse_pg_url(url: str) -> dict:
    url   = url.replace("postgresql+psycopg://", "")
    match = re.match(r"(.+):(.+)@(.+):(\d+)/(.+)", url)
    if not match:
        raise ValueError(f"Cannot parse PG URL: {url}")
    user, password, host, port, database = match.groups()
    return {
        "user":     user,
        "password": unquote(password),
        "host":     host,
        "port":     int(port),
        "database": database,
    }


# Init DB pool 

async def init_db():
    global pool
    if pool:
        return

    pg_params = _parse_pg_url(PGVECTOR_CONNECTION)
    pool = await asyncpg.create_pool(
        **pg_params,
        min_size=10,
        max_size=50,
        command_timeout=60,
        max_inactive_connection_lifetime=300,
    )
    logger.info("[DB] Connection pool created")

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS oauth_users (
                email         TEXT PRIMARY KEY,
                access_token  TEXT,
                refresh_token TEXT,
                expires_at    BIGINT,
                user_info     JSONB,
                session_token TEXT
            )
        """)
    logger.info("[DB] oauth_users table ready")


#  Close DB pool 
async def close_db():
    global pool
    if pool:
        await pool.close()
        pool = None
        logger.info("[DB] Pool closed")


# Retry wrapper 

async def _retry_db_call(func, retries=3, delay=0.2):
    for attempt in range(retries):
        try:
            return await func()
        except Exception as error:
            logger.error(f"[DB] Retry {attempt + 1}/{retries} failed: {error}")
            if attempt == retries - 1:
                raise
            await asyncio.sleep(delay)


#  Save / upsert user 

async def save_user(email, access_token, refresh_token, expires_in, user_info):
    if not pool:
        raise RuntimeError("[DB] Pool not initialized — call init_db() first")

    expire_at = int(time.time()) + expires_in

    async def _query():
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO oauth_users
                    (email, access_token, refresh_token, expires_at, user_info)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (email) DO UPDATE SET
                    access_token  = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    expires_at    = EXCLUDED.expires_at,
                    user_info     = EXCLUDED.user_info
            """, email, access_token, refresh_token, expire_at, json.dumps(user_info))

    await _retry_db_call(_query)
    logger.info(f"[DB] User saved: {email}")


#  Get user 

async def get_user(email: str) -> dict | None:
    if not pool:
        logger.error("[DB] Pool not initialized — call init_db() first")
        raise RuntimeError("[DB] Pool not initialized — call init_db() first")

    async def _query():
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM oauth_users WHERE email=$1", email
            )
            return dict(row) if row else None

    return await _retry_db_call(_query)


#  Update access token 

async def update_tokens(email, access_token, expires_in):
    if not pool:
        raise RuntimeError("[DB] Pool not initialized — call init_db() first")

    expire_at = int(time.time()) + expires_in

    async def _query():
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE oauth_users
                SET access_token=$1, expires_at=$2
                WHERE email=$3
            """, access_token, expire_at, email)

    await _retry_db_call(_query)
    logger.info(f"[DB] Tokens updated for: {email}")