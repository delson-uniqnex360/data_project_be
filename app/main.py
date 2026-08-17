# main.py

from contextlib import asynccontextmanager
from seleniumbase import Driver

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.core.browser as browser
from app.api.v1 import router as v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    browser.driver = Driver(uc=True)

    try:
        yield
    finally:
        if browser.driver:
            browser.driver.quit()
            browser.driver = None


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")
