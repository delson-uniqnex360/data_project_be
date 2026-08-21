# main.py

from contextlib import asynccontextmanager
from seleniumbase import Driver

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.core.browser as browser
from app.api.v1 import router as v1_router

# WEBSHARE_PROXY = "mrumywcp:mo6ncrvy5f61@p.webshare.io:80"

WEBSHARE_PROXY = "mrumywcp:mo6ncrvy5f61@64.137.96.74:6641"


@asynccontextmanager
async def lifespan(app: FastAPI):
    browser.driver = Driver(
        uc=True,
        headless=False,  # NOT headless2 — run headed, let Xvfb provide the display
        proxy=WEBSHARE_PROXY,
        chromium_arg="--no-sandbox,--disable-dev-shm-usage,--disable-gpu",
    )

    try:
        yield
    finally:
        if browser.driver:
            browser.driver.quit()
            browser.driver = None


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://data-project-fe.onrender.com/",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")
