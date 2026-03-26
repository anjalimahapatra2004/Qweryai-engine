import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse

from api.chat_controller import router as chat_router
from db.oauth_store import init_db, close_db, save_user
from utils.config import (
    ZOHO_CLIENT_ID,
    ZOHO_CLIENT_SECRET,
    ZOHO_REDIRECT_URI,
    ZOHO_TOKEN_URL,
)
from utils.logger import get_logger
import os

logger       = get_logger(__name__)
OAUTH_BASE   = "https://accounts.zoho.in"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app = FastAPI(title="Qwery.AI API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#  Init DB on startup 

@app.on_event("startup")
async def startup():
    await init_db()
    logger.info("[App] Database initialized")


@app.on_event("shutdown")
async def shutdown():
    await close_db()
    logger.info("[App] Database connection pool closed")


# Routers 

app.include_router(chat_router)


#  Auth helpers 

def build_auth_url() -> str:
    scopes = ",".join([
        "ZOHOPEOPLE.leave.ALL",
        "ZOHOPEOPLE.employee.ALL",
        "AaaServer.profile.READ",
        "ZohoPeople.employee.READ",   
        "ZohoPeople.forms.ALL",       
    ])
    return (
        f"{OAUTH_BASE}/oauth/v2/auth"
        f"?response_type=code"
        f"&client_id={ZOHO_CLIENT_ID}"
        f"&scope={scopes}"
        f"&redirect_uri={ZOHO_REDIRECT_URI}"
        f"&access_type=offline"
        f"&prompt=consent"
    )

# Auth endpoints 

@app.get("/auth/zoho/login")
async def zoho_login():
    """
    Initiates the Zoho OAuth 2.0 authorization flow.
    Redirects the user to Zoho's secure login portal for authentication.
    """
    auth_url = build_auth_url()
    logger.info("[Auth] Redirecting user to Zoho login portal")
    return RedirectResponse(url=auth_url)


@app.get("/auth/zoho/callback")
async def zoho_callback(code: str):
    """
    OAuth 2.0 callback handler — invoked by Zoho upon successful user authentication.

    Workflow:
    1. Exchange authorization code for access + refresh tokens
    2. Retrieve authenticated user profile from Zoho
    3. Persist user session and tokens to PostgreSQL
    4. Redirect to frontend with login success flag and tokens
    """
    logger.info("[Auth] OAuth callback received — processing authorization code")

    try:
        # Step 1: Exchange code for tokens
        async with httpx.AsyncClient(timeout=20) as client:
            token_response = await client.post(
                ZOHO_TOKEN_URL,
                params={
                    "grant_type":    "authorization_code",
                    "client_id":     ZOHO_CLIENT_ID,
                    "client_secret": ZOHO_CLIENT_SECRET,
                    "redirect_uri":  ZOHO_REDIRECT_URI,
                    "code":          code,
                },
            )
            token_response.raise_for_status()
            token_data = token_response.json()

        access_token  = token_data.get("access_token",  "")
        refresh_token = token_data.get("refresh_token", "")
        expires_in    = token_data.get("expires_in",    3600)

        # Step 2: Retrieve user profile from Zoho
        async with httpx.AsyncClient(timeout=20) as client:
            user_response = await client.get(
                f"{OAUTH_BASE}/oauth/user/info",
                headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
            )
            user_response.raise_for_status()
            user_info = user_response.json()

        email = user_info.get("Email", "")

        # Step 3: Persist session to PostgreSQL
        await save_user(
            email=email,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user_info=user_info,
        )

        logger.info(f"[Auth] Authentication successful — user={email}")

        # Step 4: Redirect to frontend with login success flag
        return RedirectResponse(
            url=(
                f"{FRONTEND_URL}"
                f"?login=success"
                f"&access_token={access_token}"
                f"&email={email}"
            )
        )

    except Exception as error:
        logger.error(f"[Auth] Callback processing error: {error}")
        return RedirectResponse(
            url=f"{FRONTEND_URL}?login=error&message=Authentication+failed"
        )


@app.get("/auth/zoho/logout")
async def zoho_logout():
    """Terminate session and redirect to authentication portal."""
    return RedirectResponse(url="/auth/zoho/login")


# Health 

@app.get("/")
async def root():
    return {"status": "ok", "message": "Qwery.AI API running"}

