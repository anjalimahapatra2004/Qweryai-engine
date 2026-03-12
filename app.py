from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.chat_controller import router as chat_router

app = FastAPI(title="Qwery.AI API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers 
app.include_router(chat_router)