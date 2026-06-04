import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from app.routers import inventory

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure after uvicorn has finished its own logging setup.
    # Attaching directly to the "app" logger (parent of all our loggers)
    # with propagate=False means uvicorn's root-logger config can't interfere.
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    log_level = getattr(
        logging, os.getenv("REKOGNITION_LOG_LEVEL", "INFO").upper(), logging.INFO
    )
    app_log = logging.getLogger("app")
    app_log.addHandler(handler)
    app_log.setLevel(log_level)
    app_log.propagate = False
    yield


app = FastAPI(title="Project Theia API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inventory.router, prefix="/api/v1")
app.mount("/static", StaticFiles(directory="static"), name="static")
