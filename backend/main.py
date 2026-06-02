import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from app.routers import inventory

load_dotenv()
logging.basicConfig(
    level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", force=True
)
logging.getLogger("app.services.rekognition").setLevel(
    getattr(logging, os.getenv("REKOGNITION_LOG_LEVEL", "INFO").upper(), logging.INFO)
)

app = FastAPI(title="Project Theia API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inventory.router, prefix="/api/v1")
app.mount("/static", StaticFiles(directory="static"), name="static")
