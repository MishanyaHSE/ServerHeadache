import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import logging
from app.database import Base, engine
from app.routes.auth import router as auth_router
from app.routes.main_menu import router as main_menu_router
from app.routes.notes import router as notes_router

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_MINUTES = 30 * 6000
SMTP_CONFIG = {
    "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
    "port": int(os.getenv("SMTP_PORT", 587)),
    "user": os.getenv("SMTP_USER", "your-email@gmail.com"),
    "password": os.getenv("SMTP_PASSWORD", "your-app-password")
}



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.include_router(auth_router)
app.include_router(main_menu_router)
app.include_router(notes_router)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=origins,
    allow_headers=origins,
)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

